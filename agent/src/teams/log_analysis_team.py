"""
Log Analysis Team

Swarm-based team for log analysis using HandOff pattern.
Team members collaborate by handing off work to specialists.
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


class LogAnalysisTeam:
    """
    Log analysis specialized team using Swarm pattern.

    Team structure:
    - LokiQueryAgent: Queries Grafana Loki for logs
    - LogSummarizerAgent: Analyzes logs with LLM
    - LogPatternAgent: Identifies patterns and anomalies

    Agents hand off work to each other based on expertise.
    """

    def __init__(
        self,
        model_client: ChatCompletionClient,
        loki_tools: list,
        summarizer_tools: list,
    ):
        """
        Initialize log analysis team.

        Args:
            model_client: LLM client for agents
            loki_tools: Loki query tools
            summarizer_tools: Log summarization tools
        """
        self.model_client = model_client
        self.loki_tools = loki_tools
        self.summarizer_tools = summarizer_tools

        # Create agents
        self._create_agents()

        # Create Swarm team
        self.team = Swarm(
            participants=[
                self.loki_agent,
                self.summarizer_agent,
                self.pattern_agent,
            ],
            termination_condition=MaxMessageTermination(max_messages=15),
        )

        logger.info("LogAnalysisTeam initialized")

    def _create_agents(self) -> None:
        """Create team agents."""

        # 1. Loki Query Agent - Log collection specialist
        self.loki_agent = AssistantAgent(
            name="loki_query_agent",
            description=load_prompt("loki_query_agent"),
            handoffs=["log_summarizer_agent", "log_pattern_agent"],
            model_client=self.model_client,
            tools=self.loki_tools,
        )

        # 2. Log Summarizer Agent - Analysis specialist
        self.summarizer_agent = AssistantAgent(
            name="log_summarizer_agent",
            description=load_prompt("log_summarizer_agent"),
            handoffs=["loki_query_agent", "log_pattern_agent"],
            model_client=self.model_client,
            tools=self.summarizer_tools,
        )

        # 3. Log Pattern Agent - Pattern matching specialist
        self.pattern_agent = AssistantAgent(
            name="log_pattern_agent",
            description=load_prompt("log_pattern_agent"),
            handoffs=["log_summarizer_agent"],
            model_client=self.model_client,
            tools=[],  # Pattern matching tools would go here
        )

    async def analyze(
        self, task: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Run log analysis.

        Args:
            task: Analysis task description
            context: Additional context

        Returns:
            Analysis results
        """
        logger.info("Starting log analysis", task_preview=task[:100])

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

            logger.info("Log analysis completed")

            return {
                "status": "success",
                "messages": [str(msg) for msg in result.messages],
                "stop_reason": result.stop_reason,
            }

        except Exception as e:
            logger.error("Log analysis failed", error=str(e))
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
                "loki_query_agent",
                "log_summarizer_agent",
                "log_pattern_agent",
            ],
            "handoffs": [
                "loki -> summarizer",
                "summarizer -> loki",
                "summarizer -> pattern",
                "pattern -> summarizer",
            ],
            "tools": {
                "loki_agent": len(self.loki_tools),
                "summarizer_agent": len(self.summarizer_tools),
                "pattern_agent": 0,
            },
        }
