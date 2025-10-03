"""
Agent Factory - Centralized agent creation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from .analysis_agent import create_analysis_agent
from .log_expert import create_log_expert
from .metric_expert import create_metric_expert
from .orchestrator import create_orchestrator
from .presentation_agent import create_presentation_agent
from .report_agent import create_report_agent

if TYPE_CHECKING:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

logger = structlog.get_logger()


class AgentFactory:
    """
    Factory for creating all agents in the system.

    Centralizes agent creation logic and manages dependencies.
    """

    def __init__(
        self,
        model_client: AzureOpenAIChatCompletionClient,
        metric_tools: list[Any],
        log_tools: list[Any],
    ):
        """
        Initialize agent factory.

        Args:
            model_client: Azure OpenAI model client
            metric_tools: List of Prometheus tools
            log_tools: List of Loki tools
        """
        self.model_client = model_client
        self.metric_tools = metric_tools
        self.log_tools = log_tools

        logger.debug(
            "AgentFactory initialized",
            metric_tools_count=len(metric_tools),
            log_tools_count=len(log_tools),
        )

    def create_all_agents(
        self,
    ) -> dict[str, AssistantAgent]:
        """
        Create all agents for the workflow.

        Returns:
            Dictionary mapping agent names to agent instances
        """
        logger.info("Creating all agents")

        agents = {
            "orchestrator": create_orchestrator(self.model_client),
            "metric_expert": create_metric_expert(
                self.model_client,
                self.metric_tools,
            ),
            "log_expert": create_log_expert(
                self.model_client,
                self.log_tools,
            ),
            "analysis_agent": create_analysis_agent(self.model_client),
            "report_agent": create_report_agent(self.model_client),
            "presentation_agent": create_presentation_agent(self.model_client),
        }

        logger.info(
            "All agents created",
            agents=list(agents.keys()),
        )

        return agents

    def get_agent_list(self) -> list[AssistantAgent]:
        """
        Get list of all agents in order.

        Returns:
            List of all agent instances
        """
        agents = self.create_all_agents()
        return [
            agents["orchestrator"],
            agents["metric_expert"],
            agents["log_expert"],
            agents["analysis_agent"],
            agents["report_agent"],
            agents["presentation_agent"],
        ]
