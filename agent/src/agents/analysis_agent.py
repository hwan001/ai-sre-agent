"""
Analysis Agent - The synthesizer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from autogen_agentchat.base import Handoff

from prompts.loader import load_prompt

from .base import BaseAgent

if TYPE_CHECKING:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import AzureOpenAIChatCompletionClient


def create_analysis_agent(
    model_client: AzureOpenAIChatCompletionClient,
) -> AssistantAgent:
    """
    Create Analysis agent.

    The analysis agent synthesizes findings and performs root cause analysis.

    Args:
        model_client: Azure OpenAI model client

    Returns:
        Configured analysis agent
    """
    handoffs = [
        Handoff(
            target="chat_orchestrator",
            description="Return to orchestrator with analysis results",
        ),
        Handoff(
            target="metric_expert",
            description="Request additional metrics if needed for analysis",
        ),
        Handoff(
            target="log_expert",
            description="Request additional logs if needed for analysis",
        ),
    ]

    return BaseAgent.create_agent(
        name="analysis_agent",
        description=load_prompt("analysis_agent"),
        model_client=model_client,
        handoffs=handoffs,
        tools=[],  # Analysis doesn't need direct tool access
    )
