"""
Message Formatter for WebSocket Communication

Structures AutoGen agent messages for clean user display.
Filters internal messages and formats user-facing content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class DisplayMessage:
    """Structured message for WebSocket display."""

    type: str  # "agent_message", "agent_thinking", "agent_handoff", "system"
    agent: str  # Agent name
    content: str  # Message content
    metadata: dict[str, Any] | None = None  # Additional info
    visible: bool = True  # Should show to user


class MessageFormatter:
    """Format AutoGen messages for WebSocket transmission."""

    # Message types to completely skip
    SKIP_MESSAGE_TYPES = {
        "StopMessage",
        "ToolCallRequestEvent",
        "ToolCallExecutionEvent",
        "ToolCallResultEvent",
        "ToolCallSummaryMessage",
    }

    # Agent name display mapping - more conversational
    AGENT_DISPLAY_NAMES = {
        "chat_orchestrator": "🎯 팀 리더",
        "metric_expert": "📊 메트릭 전문가",
        "log_expert": "📋 로그 분석가",
        "analysis_agent": "🔬 데이터 분석가",
        "report_agent": "📈 리포터",
        "presentation_agent": "🎨 프레젠터",
        "prometheus_query_agent": "📊 프로메테우스 쿼리",
    }

    # Patterns indicating internal/debug content
    DEBUG_PATTERNS = [
        "messages=[",
        "TextMessage(",
        "ToolCallRequestEvent(",
        "ToolCallExecutionEvent(",
        "HandoffMessage(",
        "FunctionCall(",
        "FunctionExecutionResult(",
        "models_usage=",
        "created_at=datetime",
        "RequestUsage(",
        "id='",
        "source='",
        "metadata=",
        "tool_call_id",
        "ToolCall(",
    ]

    # Keywords indicating system messages (not user-facing)
    SYSTEM_KEYWORDS = [
        "terminate",
        "transferred to",
        "adopting the role",
        "handoff",
        "transfer",
    ]

    # Friendly greeting messages when agents start working
    AGENT_GREETINGS = {
        "chat_orchestrator": "팀을 조율하고 있습니다",
        "metric_expert": "메트릭 데이터를 분석하고 있습니다",
        "log_expert": "로그를 확인하고 있습니다",
        "analysis_agent": "상세 분석을 진행하고 있습니다",
        "report_agent": "리포트를 작성하고 있습니다",
        "presentation_agent": "결과를 정리하고 있습니다",
    }

    @classmethod
    def format_message(cls, message: Any) -> DisplayMessage | None:
        """
        Format an AutoGen message for display.

        Args:
            message: AutoGen message object

        Returns:
            DisplayMessage if should be shown, None if should be filtered
        """
        message_type = type(message).__name__

        # Skip internal message types
        if message_type in cls.SKIP_MESSAGE_TYPES:
            logger.debug("Filtering internal message", msg_type=message_type)
            return None

        # Extract agent source
        agent = cls._extract_agent(message)

        # Extract content
        content = cls._extract_content(message)
        if not content:
            logger.debug("No content in message", msg_type=message_type)
            return None

        # Check if content is internal/debug
        if cls._is_debug_content(content):
            logger.debug(
                "Filtering debug content",
                agent=agent,
                content_preview=content[:100],
            )
            return None

        # Check if content is system message
        if cls._is_system_message(content):
            logger.debug(
                "Filtering system message",
                agent=agent,
                content_preview=content[:100],
            )
            return None

        # Handle HandoffMessage specially - make it brief and friendly
        if message_type == "HandoffMessage":
            target = getattr(message, "target", "expert")
            target_name = cls._format_agent_name(target)
            greeting = cls.AGENT_GREETINGS.get(target, "작업을 시작합니다")
            return DisplayMessage(
                type="agent_handoff",
                agent=agent,
                content=f"👉 {target_name}에게 연결중... ({greeting})",
                metadata={"target": getattr(message, "target", None)},
                visible=True,
            )

        # Clean up TERMINATE from content
        content = cls._clean_content(content)

        # Determine message category
        msg_category = cls._categorize_message(message_type, content)

        return DisplayMessage(
            type=msg_category,
            agent=cls._format_agent_name(agent),
            content=content,
            metadata={
                "message_type": message_type,
                "length": len(content),
            },
            visible=True,
        )

    @classmethod
    def _extract_agent(cls, message: Any) -> str:
        """Extract agent name from message."""
        if hasattr(message, "source"):
            return message.source
        return "system"

    @classmethod
    def _extract_content(cls, message: Any) -> str:
        """Extract content string from message."""
        if not hasattr(message, "content"):
            return ""

        content = message.content

        # Handle string content
        if isinstance(content, str):
            return content.strip()

        # Handle list content (multiple parts)
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(item["text"])
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts).strip()

        # Fallback to string conversion
        return str(content).strip()

    @classmethod
    def _is_debug_content(cls, content: str) -> bool:
        """Check if content contains debug/internal information."""
        return any(pattern in content for pattern in cls.DEBUG_PATTERNS)

    @classmethod
    def _is_system_message(cls, content: str) -> bool:
        """Check if content is a system message."""
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in cls.SYSTEM_KEYWORDS)

    @classmethod
    def _clean_content(cls, content: str) -> str:
        """Clean up content for display."""
        # Remove TERMINATE keyword
        if "TERMINATE" in content:
            content = content.split("TERMINATE")[0].strip()
            content = content.rstrip("!.,;")

        return content.strip()

    @classmethod
    def _categorize_message(cls, message_type: str, content: str) -> str:
        """Categorize message type for display."""
        # Check content for indicators
        content_lower = content.lower()

        # Thinking/working indicators
        if any(
            word in content_lower
            for word in [
                "checking",
                "searching",
                "querying",
                "analyzing",
                "확인",
                "검색",
                "분석",
                "조회",
                "처리",
            ]
        ):
            return "agent_thinking"

        if message_type == "TextMessage":
            return "agent_message"

        return "agent_message"

    @classmethod
    def _format_agent_name(cls, agent: str) -> str:
        """Format agent name for display."""
        return cls.AGENT_DISPLAY_NAMES.get(agent, agent.replace("_", " ").title())

    @classmethod
    def should_display_to_user(cls, message: Any) -> bool:
        """
        Quick check if message should be displayed to user.

        Args:
            message: AutoGen message object

        Returns:
            True if should display, False otherwise
        """
        formatted = cls.format_message(message)
        return formatted is not None and formatted.visible

    @classmethod
    def format_for_websocket(cls, message: Any) -> dict[str, Any] | None:
        """
        Format message for WebSocket transmission.

        Args:
            message: AutoGen message object

        Returns:
            WebSocket-ready dict or None if should be filtered
        """
        formatted = cls.format_message(message)

        if not formatted or not formatted.visible:
            return None

        return {
            "type": formatted.type,
            "agent": formatted.agent,
            "message": formatted.content,
            "metadata": formatted.metadata or {},
            "timestamp": "now",
        }
