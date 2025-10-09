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

    type: str  # "agent_message", "agent_thinking", "agent_handoff", "system", "internal"
    agent: str  # Agent name
    content: str  # Message content
    metadata: dict[str, Any] | None = None  # Additional info
    collapsed: bool = False  # Should start collapsed (for internal messages)


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
    # These are internal coordination messages between agents
    SYSTEM_KEYWORDS = [
        "transferred to",
        "adopting the role",
        "📍 current user question:",  # Task format from MessageProcessor
        "📋 previous conversation context:",  # Conversation history context
        "🤝 instructions:",  # Instructions to agents
        "====================",  # Task separators
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
            DisplayMessage categorized by type (all visible, some collapsed by default)
        """
        message_type = type(message).__name__

        # Only skip truly internal tool execution messages
        if message_type in cls.SKIP_MESSAGE_TYPES:
            return None

        # Extract agent source and content
        agent = cls._extract_agent(message)
        content = cls._extract_content(message)

        if not content:
            return None

        # Determine if this is an internal coordination message
        is_internal = cls._is_internal_message(content, agent)

        # Handle HandoffMessage specially - show agent transition
        if message_type == "HandoffMessage":
            target = getattr(message, "target", "expert")
            return DisplayMessage(
                type="agent_handoff",
                agent=cls._format_agent_name(agent),
                content=f"→ {cls._format_agent_name(target)}",
                metadata={
                    "from_agent": agent,
                    "to_agent": target,
                },
                collapsed=False,  # Always show handoffs
            )

        # Categorize message
        if is_internal:
            msg_type = "internal"
            collapsed = True  # Internal messages start collapsed
        elif agent == "chat_orchestrator":
            msg_type = "agent_message"
            collapsed = False  # Orchestrator messages always visible
        else:
            msg_type = "agent_message"
            collapsed = False  # Expert messages visible by default

        # Clean content (remove TERMINATE, etc)
        content = cls._clean_content(content)

        # Skip if content is empty after cleaning
        if not content:
            return None

        return DisplayMessage(
            type=msg_type,
            agent=cls._format_agent_name(agent),
            content=content,
            metadata={
                "message_type": message_type,
                "original_agent": agent,
                "length": len(content),
            },
            collapsed=collapsed,
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
    def _is_internal_message(cls, content: str, agent: str) -> bool:
        """
        Check if this is an internal coordination message.
        These messages start collapsed but are still visible.
        """
        # User source messages are internal task formatting
        if agent == "user":
            return True

        content_lower = content.lower()

        # Use SYSTEM_KEYWORDS for consistency
        return any(keyword.lower() in content_lower for keyword in cls.SYSTEM_KEYWORDS)

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
        Now all messages are displayed (some collapsed).

        Args:
            message: AutoGen message object

        Returns:
            True if should display, False otherwise
        """
        formatted = cls.format_message(message)
        return formatted is not None

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

        if not formatted:
            return None

        result = {
            "type": formatted.type,
            "agent": formatted.agent,
            "message": formatted.content,
            "collapsed": formatted.collapsed,  # Whether to start collapsed
            "timestamp": "now",
        }

        # Add handoff-specific fields
        if formatted.type == "agent_handoff" and formatted.metadata:
            result["from_agent"] = formatted.metadata.get("from_agent")
            result["to_agent"] = formatted.metadata.get("to_agent")

        return result
