"""
Message processing utilities for chat workflow.

Handles message extraction, formatting, and context summarization.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


class MessageProcessor:
    """Utility class for processing chat messages."""

    @staticmethod
    def extract_final_response(messages: list) -> str:
        """
        Extract the final response to show the user.

        Args:
            messages: List of all conversation messages

        Returns:
            Final response string
        """
        if not messages:
            return "No response generated"

        # Get last substantial message, skipping StopMessage and TERMINATE
        for msg in reversed(messages):
            # Skip StopMessage types
            msg_type = type(msg).__name__
            if msg_type in ["StopMessage", "HandoffMessage"]:
                logger.debug("Skipping system message type", msg_type=msg_type)
                continue

            # Get content safely
            if hasattr(msg, "content"):
                content = msg.content
                if isinstance(content, str):
                    content_clean = content.strip()
                else:
                    content_clean = str(content).strip()
            else:
                content_clean = str(msg).strip()

            # Skip empty messages
            if not content_clean:
                continue

            # Skip serialized message objects
            if (
                content_clean.startswith("messages=[")
                or "TextMessage(" in content_clean
            ):
                logger.warning(
                    "Skipping serialized message object",
                    content_preview=content_clean[:100],
                )
                continue

            # If message contains TERMINATE, extract the part before it
            if "TERMINATE" in content_clean:
                before_terminate = content_clean.split("TERMINATE")[0].strip()
                before_terminate = before_terminate.rstrip("!.,;")

                if len(before_terminate) > 30:
                    logger.debug(
                        "Extracted response before TERMINATE",
                        response_length=len(before_terminate),
                        source=getattr(msg, "source", "unknown"),
                    )
                    return before_terminate
                continue

            # Found a good response (no TERMINATE)
            if len(content_clean) > 30:
                logger.debug(
                    "Final response extracted",
                    source=getattr(msg, "source", "unknown"),
                    length=len(content_clean),
                )
                return content_clean

        # Fallback: try to find any non-empty message
        for msg in reversed(messages):
            msg_type = type(msg).__name__
            if msg_type == "StopMessage":
                continue

            content = str(msg.content) if hasattr(msg, "content") else str(msg)
            content_clean = content.replace("TERMINATE", "").strip()

            if "messages=[" in content_clean or "TextMessage(" in content_clean:
                continue

            if len(content_clean) > 20:
                logger.warning(
                    "Using fallback response extraction",
                    content_preview=content_clean[:100],
                )
                return content_clean

        logger.warning("No suitable response found in messages")
        return "Analysis completed. Please let me know if you need more information."

    @staticmethod
    def extract_agent_findings(messages: list) -> dict[str, list[str]]:
        """
        Extract findings from each agent type.

        Args:
            messages: List of all conversation messages

        Returns:
            Dictionary mapping agent types to their findings
        """
        findings = {
            "metrics": [],
            "logs": [],
            "analysis": [],
            "report": [],
            "presentation": [],
        }

        for msg in messages:
            # Skip system message types
            msg_type = type(msg).__name__
            if msg_type in [
                "StopMessage",
                "HandoffMessage",
                "ToolCallRequestEvent",
                "ToolCallResultEvent",
            ]:
                continue

            source = getattr(msg, "source", "")
            content = str(msg.content) if hasattr(msg, "content") else str(msg)

            # Skip short, system messages, or TERMINATE
            if len(content) < 100 or "TERMINATE" in content:
                continue

            # Categorize by agent
            if source == "metric_expert":
                findings["metrics"].append(content)
            elif source == "log_expert":
                findings["logs"].append(content)
            elif source == "analysis_agent":
                findings["analysis"].append(content)
            elif source == "report_agent":
                findings["report"].append(content)
            elif source == "presentation_agent":
                findings["presentation"].append(content)

        logger.debug(
            "Agent findings extracted",
            metrics_count=len(findings["metrics"]),
            logs_count=len(findings["logs"]),
            analysis_count=len(findings["analysis"]),
            report_count=len(findings["report"]),
            presentation_count=len(findings["presentation"]),
        )

        return findings

    @staticmethod
    def extract_context_summary(messages: list) -> str | None:
        """
        Extract context summary from orchestrator's messages.

        Orchestrator can provide a compressed summary marked with special tags
        for efficient history management.

        Args:
            messages: All conversation messages

        Returns:
            Compressed summary if provided, None otherwise
        """
        for msg in reversed(messages):
            source = getattr(msg, "source", "")
            if source != "chat_orchestrator":
                continue

            content = str(msg.content) if hasattr(msg, "content") else ""

            # Check for summary markers
            if "[CONTEXT_SUMMARY]" in content:
                try:
                    summary_tag = "[CONTEXT_SUMMARY]"
                    start = content.index(summary_tag) + len(summary_tag)
                    end = content.index("[/CONTEXT_SUMMARY]")
                    summary = content[start:end].strip()

                    logger.debug(
                        "Context summary extracted from orchestrator",
                        summary_length=len(summary),
                    )
                    return summary
                except (ValueError, IndexError):
                    logger.warning("Failed to parse context summary markers")
                    continue

        return None

    @staticmethod
    def build_task(
        user_message: str,
        conversation_context: dict[str, Any] | None,
    ) -> str:
        """
        Build chat task with context and conversation history.

        Args:
            user_message: User's message
            conversation_context: Previous conversation context including history

        Returns:
            Formatted task for the team
        """
        task = ""

        # Add conversation history if available
        if conversation_context and "conversation_history" in conversation_context:
            history = conversation_context["conversation_history"]
            if history and len(history) > 1:
                task += "📋 Previous Conversation Context:\n"
                task += "=" * 50 + "\n"

                # Get last meaningful exchanges (skip current message)
                recent_history = history[:-1][-6:]

                for msg in recent_history:
                    role = msg.get("role", "unknown")
                    content = str(msg.get("content", ""))

                    # Clean up content
                    if len(content) > 500:
                        content = content[:500] + "..."

                    if role == "user":
                        task += f"\n👤 USER: {content}\n"
                    elif role == "assistant":
                        task += f"🤖 ASSISTANT: {content}\n"

                task += "=" * 50 + "\n\n"

                logger.debug(
                    "Conversation history included",
                    messages_included=len(recent_history),
                    total_history=len(history),
                )

        task += f"📍 Current User Question: {user_message}\n\n"

        # Add other context
        if conversation_context:
            if "namespace" in conversation_context:
                task += f"🎯 Target Namespace: {conversation_context['namespace']}\n"
            if "pod" in conversation_context:
                task += f"🎯 Target Pod: {conversation_context['pod']}\n"
            if "previous_findings" in conversation_context:
                task += (
                    f"\n💡 Key Findings from Previous Analysis:\n"
                    f"{conversation_context['previous_findings']}\n"
                )

        task += "\n" + "=" * 50 + "\n"
        task += (
            "🤝 Instructions: Review the conversation context above "
            "and help the user with their current question.\n"
        )
        task += (
            "If this is a follow-up request (like 'show related metrics'), "
            "use the previous context to provide relevant analysis.\n"
        )

        # Add explicit validation for follow-up metric requests
        metric_keywords = [
            "관련 매트릭",
            "관련 메트릭",
            "매트릭도",
            "메트릭도",
            "related metric",
        ]
        if any(keyword in user_message.lower() for keyword in metric_keywords):
            task += "\n⚠️ CRITICAL: This is a follow-up metric request.\n"
            task += "BEFORE transferring to metric_expert, you MUST:\n"
            task += "1. Read the Previous Conversation Context above\n"
            task += "2. Identify: Namespace, Pod name, Error message\n"
            task += "3. Show USER a summary: " "'이전 분석 내용을 확인해보니: [요약]'\n"
            task += (
                "4. Transfer to metric_expert WITH "
                "[CONTEXT] and [REQUESTED METRICS] sections\n"
            )
            task += (
                "5. DO NOT use generic queries like "
                "prometheus_get_essential_metrics without pod_name\n"
            )

        return task

    @staticmethod
    def get_agents_participated(messages: list) -> list[str]:
        """
        Extract list of agents that participated in the conversation.

        Args:
            messages: List of all conversation messages

        Returns:
            List of unique agent names
        """
        return list(
            set(
                getattr(msg, "source", "unknown")
                for msg in messages
                if hasattr(msg, "source")
            )
        )
