"""
Main API endpoints for SRE Agent.

Provides REST API for the Kubernetes Operator to interact with the agent.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Production에서는 패키지 설치 후 사용하거나 PYTHONPATH 환경변수 설정 권장
# 직접 실행 시에만 임시로 경로 추가
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

# Use absolute imports - pyproject.toml includes src in pythonpath
from configs.config import get_settings
from tools.metrics.prometheus_agent_tools import (
    prometheus_get_essential_metrics,
    prometheus_get_metric_names,
    prometheus_get_targets,
    prometheus_query_specific_metrics,
)
from workflows.sre_workflow import SREWorkflow

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
            "name": "prometheus-tools",
            "description": "Prometheus agent tools for testing and monitoring",
        },
    ],
)


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


# Prometheus Tools Request/Response Models
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


@app.get("/health", tags=["core"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


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


# Prometheus Tools Endpoints
@app.post("/tools/prometheus/query-metrics", tags=["prometheus-tools"])
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


@app.post("/tools/prometheus/essential-metrics", tags=["prometheus-tools"])
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


@app.post("/tools/prometheus/metric-names", tags=["prometheus-tools"])
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


@app.post("/tools/prometheus/targets", tags=["prometheus-tools"])
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


@app.get("/tools/prometheus/examples", tags=["prometheus-tools"])
async def get_examples() -> dict[str, Any]:
    """
    Get usage examples for Prometheus tools.

    Provides example requests and expected responses to help with testing.
    """
    examples = {
        "query_metrics": {
            "description": "Query specific metrics efficiently",
            "example_request": {
                "metric_names": ["up", "node_load1", "node_memory_MemAvailable_bytes"],
                "namespace": "production",
                "pod_name": "web-server",
                "limit_per_metric": 50,
                "step": "1m",
            },
            "common_metrics": [
                "up",
                "node_load1",
                "node_load5",
                "node_load15",
                "node_memory_MemTotal_bytes",
                "node_memory_MemAvailable_bytes",
                "node_cpu_seconds_total",
                "container_cpu_usage_seconds_total",
                "container_memory_usage_bytes",
                "kube_pod_status_phase",
            ],
        },
        "essential_metrics": {
            "description": "Get essential system metrics with calculated percentages",
            "example_request": {
                "namespace": "production",
                "pod_name": "database",
                "step": "5m",
            },
            "returns": [
                "CPU usage percentage",
                "Memory usage percentage",
                "Disk usage percentage",
                "System availability",
                "Load averages",
            ],
        },
    }

    return examples


if __name__ == "__main__":
    # Direct execution - mainly for production/container deployments
    # For development, use dev.py instead for hot-reload and debug features
    import uvicorn

    uvicorn.run(
        "main:app",
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
