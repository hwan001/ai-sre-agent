"""
Base agent configuration and common utilities.
"""

from __future__ import annotations

from typing import Any

import structlog
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Handoff
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

logger = structlog.get_logger()


class BaseAgent:
    """Base class for agent configuration."""

    @staticmethod
    def create_agent(
        name: str,
        description: str,
        model_client: AzureOpenAIChatCompletionClient,
        handoffs: list[Handoff],
        tools: list[Any] | None = None,
    ) -> AssistantAgent:
        """
        Create an AssistantAgent with common configuration.

        Args:
            name: Agent name (unique identifier)
            description: Agent description/system prompt
            model_client: Azure OpenAI model client
            handoffs: List of handoff configurations
            tools: Optional list of tools for the agent

        Returns:
            Configured AssistantAgent
        """
        logger.debug(
            "Creating agent",
            name=name,
            handoffs_count=len(handoffs),
            tools_count=len(tools) if tools else 0,
        )

        # Add Korean response instruction to system message
        enhanced_system_message = f"""{description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **CRITICAL LANGUAGE INSTRUCTION:**

**ALWAYS respond in Korean (한국어)** to the user.

- Good Example (✅): "sample-apps 네임스페이스의 Pod 상태를 확인했습니다"
- Bad Example (❌): "Checked the pod status for sample-apps namespace"

Technical terms (Pod, Running, Ready) can remain in English, but sentences must be in Korean.
"""

        agent = AssistantAgent(
            name=name,
            system_message=enhanced_system_message,  # Correct parameter for system message
            model_client=model_client,
            handoffs=handoffs,
            tools=tools or [],
        )

        logger.debug("Agent created successfully", name=name)
        return agent
