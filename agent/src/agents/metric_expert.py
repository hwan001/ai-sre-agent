"""
Metric Expert Agent - Prometheus specialist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from autogen_agentchat.base import Handoff

from prompts.loader import load_prompt

from .base import BaseAgent

if TYPE_CHECKING:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import AzureOpenAIChatCompletionClient


def create_metric_expert(
    model_client: AzureOpenAIChatCompletionClient,
    metric_tools: list[Any],
) -> AssistantAgent:
    """
    Create Metric Expert agent.

    The metric expert specializes in Prometheus queries and resource analysis.

    Args:
        model_client: Azure OpenAI model client
        metric_tools: List of Prometheus tools

    Returns:
        Configured metric expert agent
    """
    handoffs = [
        Handoff(
            target="chat_orchestrator",
            description="Return to orchestrator with metric findings",
        ),
        Handoff(
            target="log_expert",
            description="Hand off to log expert if logs are needed to explain metrics",
        ),
    ]

    return BaseAgent.create_agent(
        name="metric_expert",
        description=load_prompt("metric_expert_agent"),
        model_client=model_client,
        handoffs=handoffs,
        tools=metric_tools,
    )
