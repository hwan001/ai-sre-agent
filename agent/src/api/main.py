"""
Main API endpoints for SRE Agent.

Provides REST API for the Kubernetes Operator to interact with the agent.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Use absolute imports - pyproject.toml includes src in pythonpath
from configs.config import get_settings
from plugins.prometheus_plugin import (
    prometheus_get_essential_metrics,
    prometheus_get_metric_names,
    prometheus_get_targets,
    prometheus_query_specific_metrics,
)
from workflows.sre_workflow import SREWorkflow

# Web Chat imports
from api.chat_manager import WebChatManager

logger = structlog.get_logger()
settings = get_settings()

# Initialize the SRE workflow
sre_workflow = SREWorkflow()

app = FastAPI(
    title="SRE Agent API",
    description="AutoGen-based SRE Agent for Kubernetes operations with tools",
    version="0.1.0",
    openapi_tags=[
        {
            "name": "core",
            "description": "Core SRE agent functionality",
        },
        {
            "name": "prometheus-plugins",
            "description": "Prometheus agent plugins for testing and monitoring",
        },
        {
            "name": "web-chat",
            "description": "Web-based chat interface with MetricAnalyzeAgent",
        },
    ],
)

# Static files mounting
app.mount("/static", StaticFiles(directory="static"), name="static")


# Request/Response Models
class DecisionRequest(BaseModel):
    """Request for agent decision."""

    event_type: str
    namespace: str
    resource_name: str
    resource_kind: str
    event_data: dict[str, Any]
    context: dict[str, Any] | None = None


class DecisionResponse(BaseModel):
    """Agent decision response."""

    decision: str  # "approve", "reject", "human_review"
    confidence: float  # 0.0 to 1.0
    recommended_actions: list[dict[str, Any]]
    reasoning: str
    correlation_id: str


class ExecutionRequest(BaseModel):
    """Request for action execution."""

    correlation_id: str
    actions: list[dict[str, Any]]
    dry_run: bool = False


class ExecutionResponse(BaseModel):
    """Action execution response."""

    correlation_id: str
    results: list[dict[str, Any]]
    success: bool
    rollback_available: bool


# Prometheus plugins Request/Response Models
class PrometheusQueryRequest(BaseModel):
    """Request for querying specific Prometheus metrics."""

    metric_names: list[str]
    start_time: str | None = None
    end_time: str | None = None
    namespace: str | None = None
    pod_name: str | None = None
    limit_per_metric: int = 50
    step: str = "1m"
    prometheus_url: str | None = None


class PrometheusEssentialMetricsRequest(BaseModel):
    """Request for essential Prometheus metrics."""

    namespace: str | None = None
    pod_name: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    step: str = "1m"
    prometheus_url: str | None = None


class PrometheusMetricNamesRequest(BaseModel):
    """Request for Prometheus metric names."""

    namespace: str | None = None
    pod_name: str | None = None
    metric_name: str | None = None
    limit: int = 1000
    prometheus_url: str | None = None


class PrometheusTargetsRequest(BaseModel):
    """Request for Prometheus targets."""

    prometheus_url: str | None = None


# 글로벌 채팅 매니저
chat_manager = WebChatManager()


@app.get("/health", tags=["core"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


# Web Chat Endpoints
@app.get("/", response_class=HTMLResponse, tags=["web-chat"])
async def get_chat_page():
    """채팅 페이지 HTML"""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Error: HTML file not found</h1><p>Please ensure static/index.html exists.</p>",
            status_code=500,
        )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 엔드포인트"""
    await websocket.accept()
    logger.info("WebSocket connection established")

    try:
        # 연결 성공 메시지 전송
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connection_status",
                    "status": "connected",
                    "message": "에이전트 초기화 중...",
                }
            )
        )

        # 에이전트 초기화
        try:
            await chat_manager.initialize_agent()
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "connection_status",
                        "status": "ready",
                        "message": "Multi-Agent SRE 시스템 준비 완료",
                        "agent_status": chat_manager._get_agent_status({}),
                    }
                )
            )
        except Exception as init_error:
            logger.error(f"Agent initialization failed: {init_error}")
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "error": f"에이전트 초기화 실패: {init_error}",
                    }
                )
            )
            return

        while True:
            # 메시지 수신
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "chat":
                user_message = message_data.get("message", "")
                chat_mode = message_data.get("mode", "team")  # 기본값은 팀채팅
                agent_type = message_data.get(
                    "agent_type", "metric_analyze_agent"
                )  # 개별 모드용 에이전트 타입
                logger.info(
                    f"Received user message: {user_message}, mode: {chat_mode}, agent_type: {agent_type}"
                )

                # 진행 상태 전송
                mode_display = (
                    "🚀 Multi-Agent 팀 시스템"
                    if chat_mode == "team"
                    else "🤖 개별 에이전트"
                )
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "processing",
                            "message": f"{mode_display} 시작...",
                            "mode": chat_mode,
                        }
                    )
                )

                # 선택된 모드에 따라 에이전트와 대화
                await chat_manager.chat_with_agent_streaming(
                    user_message, websocket, chat_mode, agent_type
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
        except:
            pass  # 연결이 이미 끊어진 경우


@app.post("/decide", response_model=DecisionResponse, tags=["core"])
async def decide(request: DecisionRequest) -> DecisionResponse:
    """
    Main decision endpoint called by the Kubernetes Operator.

    The agent analyzes the Kubernetes event and returns a decision
    with recommended actions.
    """
    logger.info(
        "Received decision request",
        event_type=request.event_type,
        namespace=request.namespace,
        resource=request.resource_name,
    )

    try:
        # Use AutoGen workflow for multi-agent decision making
        correlation_id = f"req-{uuid.uuid4().hex}"

        result = await sre_workflow.process_incident(
            event_data=request.event_data,
            namespace=request.namespace,
            resource_name=request.resource_name,
        )

        return DecisionResponse(
            decision=result.get("decision", "human_review"),
            confidence=result.get("confidence", 0.5),
            recommended_actions=result.get("recommended_actions", []),
            reasoning=result.get("reasoning", "Multi-agent analysis completed"),
            correlation_id=correlation_id,
        )

    except Exception as e:
        logger.error("Decision processing failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/execute", response_model=ExecutionResponse, tags=["core"])
async def execute(request: ExecutionRequest) -> ExecutionResponse:
    """
    Execute approved actions.

    Called after the operator receives approval for the recommended actions.
    """
    logger.info(
        "Received execution request",
        correlation_id=request.correlation_id,
        action_count=len(request.actions),
        dry_run=request.dry_run,
    )

    try:
        # TODO: Implement action execution with safety guards
        # 1. Validate actions against allow-list
        # 2. Apply rate limiting and idempotency
        # 3. Execute with rollback capability
        # 4. Monitor execution results

        # Placeholder response
        return ExecutionResponse(
            correlation_id=request.correlation_id,
            results=[],
            success=False,
            rollback_available=False,
        )

    except Exception as e:
        logger.error(
            "Execution failed", correlation_id=request.correlation_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


# Prometheus Plugins Endpoints
@app.post("/plugins/prometheus/query-metrics", tags=["prometheus-plugins"])
async def query_prometheus_metrics(request: PrometheusQueryRequest) -> dict[str, Any]:
    """
    Query specific Prometheus metrics efficiently.

    This endpoint allows testing of the prometheus_query_specific_metrics function
    through Swagger UI with customizable parameters.
    """
    logger.info(
        "Prometheus metrics query request",
        metrics=request.metric_names,
        namespace=request.namespace,
        pod_name=request.pod_name,
    )

    try:
        result = await prometheus_query_specific_metrics(
            metric_names=request.metric_names,
            start_time=request.start_time,
            end_time=request.end_time,
            namespace=request.namespace,
            pod_name=request.pod_name,
            limit_per_metric=request.limit_per_metric,
            step=request.step,
            prometheus_url=request.prometheus_url,
        )
        return result

    except Exception as e:
        logger.error("Prometheus metrics query failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/plugins/prometheus/essential-metrics", tags=["prometheus-plugins"])
async def get_essential_metrics(
    request: PrometheusEssentialMetricsRequest,
) -> dict[str, Any]:
    """
    Get essential system metrics with calculated percentages.

    Returns CPU usage %, memory usage %, disk usage %, system availability,
    and load averages - all pre-calculated and limited in volume.
    """
    logger.info(
        "Prometheus essential metrics request",
        namespace=request.namespace,
        pod_name=request.pod_name,
    )

    try:
        result = await prometheus_get_essential_metrics(
            namespace=request.namespace,
            pod_name=request.pod_name,
            start_time=request.start_time,
            end_time=request.end_time,
            step=request.step,
            prometheus_url=request.prometheus_url,
        )
        return result

    except Exception as e:
        logger.error("Prometheus essential metrics query failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/plugins/prometheus/metric-names", tags=["prometheus-plugins"])
async def get_metric_names(request: PrometheusMetricNamesRequest) -> dict[str, Any]:
    """
    Get list of available metric names from Prometheus.

    Note: This is a placeholder implementation in the current enhanced version.
    """
    logger.info(
        "Prometheus metric names request",
        namespace=request.namespace,
        pod_name=request.pod_name,
        metric_name=request.metric_name,
    )

    try:
        result = await prometheus_get_metric_names(
            namespace=request.namespace,
            pod_name=request.pod_name,
            metric_name=request.metric_name,
            limit=request.limit,
            prometheus_url=request.prometheus_url,
        )
        return result

    except Exception as e:
        logger.error("Prometheus metric names query failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/plugins/prometheus/targets", tags=["prometheus-plugins"])
async def get_targets(request: PrometheusTargetsRequest) -> dict[str, Any]:
    """
    Get information about Prometheus targets (scraped endpoints).

    Returns detailed information about all targets being scraped by Prometheus,
    organized by job with health status and scraping details.
    """
    logger.info("Prometheus targets request")

    try:
        result = await prometheus_get_targets(prometheus_url=request.prometheus_url)
        return result

    except Exception as e:
        logger.error("Prometheus targets query failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    # Direct execution - mainly for production/container deployments
    # For development, use dev.py instead for hot-reload and debug features
    import uvicorn

    # When run as python -m src.api.main, use the app directly
    uvicorn.run(
        app,
        host=settings.api.host,
        port=settings.api.port,
        reload=False,  # No reload in direct execution
        log_level=settings.api.log_level.lower(),
    )


def run_production():
    """Entry point for production deployment."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=False,
        log_level=settings.api.log_level.lower(),
    )


def run_development():
    """Entry point for development with reload."""
    import uvicorn

    settings = get_settings()
    settings.api.reload = True
    settings.development.debug = True

    uvicorn.run(
        "api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=True,
        reload_dirs=["src"],
        log_level=settings.api.log_level.lower(),
    )
