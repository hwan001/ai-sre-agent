"""
Kubernetes Expert Agent - Kubernetes specialist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from autogen_agentchat.base import Handoff

from prompts.loader import load_prompt

from .base import BaseAgent

if TYPE_CHECKING:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import AzureOpenAIChatCompletionClient


def create_kubernetes_expert(
    model_client: AzureOpenAIChatCompletionClient,
    k8s_tools: list[Any],
) -> AssistantAgent:
    """
    Create Kubernetes Expert agent.

    The kubernetes expert specializes in Kubernetes cluster operations and diagnostics.

    Args:
        model_client: Azure OpenAI model client
        k8s_tools: List of Kubernetes tools

    Returns:
        Configured kubernetes expert agent
    """
    handoffs = [
        Handoff(
            target="chat_orchestrator",
            description="Return to orchestrator with Kubernetes findings",
        ),
        Handoff(
            target="metric_expert",
            description="Hand off to metric expert if resource metrics are needed",
        ),
        Handoff(
            target="log_expert",
            description="Hand off to log expert if pod logs are needed",
        ),
    ]

    return BaseAgent.create_agent(
        name="kubernetes_expert",
        description=load_prompt("kubernetes_expert_agent"),
        model_client=model_client,
        handoffs=handoffs,
        tools=k8s_tools,
    )
