"""
Chat Orchestrator Agent - The conversation router.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from autogen_agentchat.base import Handoff

from prompts.loader import load_prompt

from .base import BaseAgent

if TYPE_CHECKING:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import AzureOpenAIChatCompletionClient


def create_orchestrator(
    model_client: AzureOpenAIChatCompletionClient,
) -> AssistantAgent:
    """
    Create Chat Orchestrator agent.

    The orchestrator routes conversations and engages specialized agents
    through HandOff coordination.

    Args:
        model_client: Azure OpenAI model client

    Returns:
        Configured orchestrator agent
    """
    handoffs = [
        Handoff(
            target="metric_expert",
            description="Hand off to metric expert for Prometheus queries and resource analysis",
        ),
        Handoff(
            target="log_expert",
            description="Hand off to log expert for Loki queries and log analysis",
        ),
        Handoff(
            target="analysis_agent",
            description="Hand off to analysis agent for comprehensive root cause analysis",
        ),
        Handoff(
            target="report_agent",
            description="Hand off to report agent when user requests a report or summary",
        ),
        Handoff(
            target="presentation_agent",
            description="Hand off to presentation agent to format technical data into beautiful markdown",
        ),
    ]

    return BaseAgent.create_agent(
        name="chat_orchestrator",
        description=load_prompt("chat_orchestrator"),
        model_client=model_client,
        handoffs=handoffs,
        tools=[],  # Orchestrator doesn't use tools directly
    )
