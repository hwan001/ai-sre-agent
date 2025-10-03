"""
Report Agent - The visualizer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from autogen_agentchat.base import Handoff

from prompts.loader import load_prompt

from .base import BaseAgent

if TYPE_CHECKING:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import AzureOpenAIChatCompletionClient


def create_report_agent(
    model_client: AzureOpenAIChatCompletionClient,
) -> AssistantAgent:
    """
    Create Report agent.

    The report agent generates visual reports on demand.

    Args:
        model_client: Azure OpenAI model client

    Returns:
        Configured report agent
    """
    handoffs = [
        Handoff(
            target="chat_orchestrator",
            description="Return to orchestrator with generated report",
        ),
    ]

    return BaseAgent.create_agent(
        name="report_agent",
        description=load_prompt("report_agent"),
        model_client=model_client,
        handoffs=handoffs,
        tools=[],  # Uses conversation history to create reports
    )
