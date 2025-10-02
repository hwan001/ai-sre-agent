"""
Metric Analysis Team

Swarm-based team for Prometheus metric analysis using HandOff pattern.
Follows step-by-step workflow for efficient metric investigation.
"""

from __future__ import annotations

from typing import Any

import structlog
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.teams import Swarm
from autogen_core import CancellationToken
from autogen_core.models import ChatCompletionClient

from prompts.loader import load_prompt

logger = structlog.get_logger()


class MetricAnalysisTeam:
    """
    Metric analysis specialized team using Swarm pattern.

    Team structure:
    - PrometheusQueryAgent: Executes Prometheus queries
    - MetricAnalyzerAgent: Interprets metrics with step-by-step workflow
    - AnomalyDetectorAgent: Detects metric anomalies

    Follows best-practice workflow:
    1. Essential metrics
    2. Metric exploration
    3. Detailed queries
    4. Anomaly detection
    """

    def __init__(
        self,
        model_client: ChatCompletionClient,
        prometheus_tools: list,
    ):
        """
        Initialize metric analysis team.

        Args:
            model_client: LLM client for agents
            prometheus_tools: Prometheus query tools
        """
        self.model_client = model_client
        self.prometheus_tools = prometheus_tools

        # Create agents
        self._create_agents()

        # Create Swarm team
        self.team = Swarm(
            participants=[
                self.query_agent,
                self.analyzer_agent,
                self.anomaly_agent,
            ],
            termination_condition=MaxMessageTermination(max_messages=20),
        )

        logger.info("MetricAnalysisTeam initialized")

    def _create_agents(self) -> None:
        """Create team agents."""

        # 1. Prometheus Query Agent - Query execution specialist
        self.query_agent = AssistantAgent(
            name="prometheus_query_agent",
            description=load_prompt("prometheus_query_agent"),
            handoffs=["metric_analyzer_agent"],
            model_client=self.model_client,
            tools=self.prometheus_tools,
        )

        # 2. Metric Analyzer Agent - Analysis and workflow specialist
        self.analyzer_agent = AssistantAgent(
            name="metric_analyzer_agent",
            description=load_prompt("metric_analyzer_agent"),
            handoffs=["prometheus_query_agent", "anomaly_detector_agent"],
            model_client=self.model_client,
            tools=[],
        )

        # 3. Anomaly Detector Agent - Anomaly detection specialist
        self.anomaly_agent = AssistantAgent(
            name="anomaly_detector_agent",
            description=load_prompt("anomaly_detector_agent"),
            handoffs=["metric_analyzer_agent"],
            model_client=self.model_client,
            tools=[],  # Anomaly detection tools would go here
        )

    async def analyze(
        self, task: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Run metric analysis.

        Args:
            task: Analysis task description
            context: Additional context (namespace, pod, etc.)

        Returns:
            Analysis results
        """
        logger.info("Starting metric analysis", task_preview=task[:100])

        try:
            # Add context to task if provided
            full_task = task
            if context:
                full_task += f"\n\nContext: {context}"

            # Run the swarm team
            result = await self.team.run(
                task=full_task,
                cancellation_token=CancellationToken(),
            )

            logger.info("Metric analysis completed")

            return {
                "status": "success",
                "messages": [str(msg) for msg in result.messages],
                "stop_reason": result.stop_reason,
            }

        except Exception as e:
            logger.error("Metric analysis failed", error=str(e))
            return {
                "status": "error",
                "error": str(e),
                "messages": [],
            }

    def get_team_summary(self) -> dict[str, Any]:
        """
        Get team configuration summary.

        Returns:
            Team summary
        """
        return {
            "team_type": "Swarm",
            "agents": [
                "prometheus_query_agent",
                "metric_analyzer_agent",
                "anomaly_detector_agent",
            ],
            "handoffs": [
                "query -> analyzer",
                "analyzer -> query",
                "analyzer -> anomaly",
                "anomaly -> analyzer",
            ],
            "tools": {
                "query_agent": len(self.prometheus_tools),
                "analyzer_agent": 0,
                "anomaly_agent": 0,
            },
        }
