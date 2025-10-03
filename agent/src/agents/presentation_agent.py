"""
Presentation Agent - The beautifier.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from autogen_agentchat.base import Handoff

from prompts.loader import load_prompt

from .base import BaseAgent

if TYPE_CHECKING:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import AzureOpenAIChatCompletionClient


def create_presentation_agent(
    model_client: AzureOpenAIChatCompletionClient,
) -> AssistantAgent:
    """
    Create Presentation agent.

    The presentation agent formats technical data into beautiful markdown.

    Args:
        model_client: Azure OpenAI model client

    Returns:
        Configured presentation agent
    """
    handoffs = [
        Handoff(
            target="chat_orchestrator",
            description="Return to orchestrator with beautifully formatted response",
        ),
    ]

    return BaseAgent.create_agent(
        name="presentation_agent",
        description=load_prompt("presentation_agent"),
        model_client=model_client,
        handoffs=handoffs,
        tools=[],  # Formats data from other agents
    )
