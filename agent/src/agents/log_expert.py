"""
Log Expert Agent - Loki specialist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from autogen_agentchat.base import Handoff

from prompts.loader import load_prompt

from .base import BaseAgent

if TYPE_CHECKING:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import AzureOpenAIChatCompletionClient


def create_log_expert(
    model_client: AzureOpenAIChatCompletionClient,
    log_tools: list[Any],
) -> AssistantAgent:
    """
    Create Log Expert agent.

    The log expert specializes in Loki queries and log analysis.

    Args:
        model_client: Azure OpenAI model client
        log_tools: List of Loki tools

    Returns:
        Configured log expert agent
    """
    handoffs = [
        Handoff(
            target="chat_orchestrator",
            description="Return to orchestrator with log findings",
        ),
        Handoff(
            target="metric_expert",
            description="Hand off to metric expert if metrics context is needed",
        ),
    ]

    return BaseAgent.create_agent(
        name="log_expert",
        description=load_prompt("log_expert_agent"),
        model_client=model_client,
        handoffs=handoffs,
        tools=log_tools,
    )
