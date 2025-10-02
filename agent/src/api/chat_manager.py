"""
Web Chat Manager for SRE Agent v3.0

Manages WebSocket-based conversational chat interface for Kubernetes diagnostics.
Uses AutoGen Swarm pattern with dynamic agent participation via HandOff.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from configs.config import get_settings
from workflows.chat_workflow import ChatWorkflow
from tools.tool_registry import initialize_tool_registry

logger = structlog.get_logger()


class WebChatManager:
    """WebSocket chat manager for conversational Kubernetes diagnostics."""

    MESSAGE_STREAM_DELAY = 0.1

    def __init__(self):
        """Initialize chat manager."""
        self.settings = get_settings()
        self.chat_workflow: ChatWorkflow | None = None
        self.conversation_context: dict[str, Any] = {}
        self.conversation_history: list[dict[str, str]] = (
            []
        )  # Track conversation history
        logger.info("WebChatManager initialized for v3.0 (Conversational)")

    async def initialize(self):
        """Initialize chat workflow if not already set."""
        if self.chat_workflow:
            logger.info("ChatWorkflow already initialized, skipping")
            return

        logger.info("Creating new ChatWorkflow")
        tool_registry = initialize_tool_registry()
        self.chat_workflow = ChatWorkflow(tool_registry)
        logger.info("ChatWorkflow initialized for conversational chat")

    async def handle_chat_message(
        self, user_message: str, websocket, context: dict[str, Any] | None = None
    ):
        """Handle incoming chat message with conversational workflow."""
        try:
            if not self.chat_workflow:
                await self.initialize()

            if not self.chat_workflow:
                raise ValueError("Failed to initialize ChatWorkflow")

            if context:
                self.conversation_context.update(context)

            await self._process_conversational_chat(user_message, websocket)

        except Exception as e:
            logger.error("Chat processing error", error=str(e), exc_info=True)
            await websocket.send_json(
                {"type": "error", "message": f"Analysis failed: {str(e)}"}
            )

    async def _process_conversational_chat(self, user_message: str, websocket):
        """Process conversational chat with dynamic agent participation."""
        try:
            await websocket.send_json(
                {"type": "chat_start", "message": "👋 Let me help you with that..."}
            )

            logger.info("Starting conversational chat", message=user_message[:100])

            async def stream_callback(message):
                """Handle streamed messages from agents."""
                try:
                    if not self._should_display_message(message):
                        return

                    agent_name = self._extract_agent_from_message(message)
                    content = self._extract_content_from_message(message)

                    if not content or len(content.strip()) < 10:
                        return

                    # Skip raw message objects
                    if (
                        "messages=[" in content
                        or "TextMessage(" in content
                        or "stop_reason=" in content
                    ):
                        logger.debug(
                            "Skipping raw message object in stream",
                            content_preview=content[:100],
                        )
                        return

                    formatted_content = self._format_message_content(content)

                    # Double-check after formatting
                    if not formatted_content or "messages=[" in formatted_content:
                        return

                    await websocket.send_json(
                        {
                            "type": "agent_message",
                            "agent": agent_name,
                            "message": formatted_content,
                            "timestamp": "now",
                        }
                    )
                    await asyncio.sleep(self.MESSAGE_STREAM_DELAY)

                except Exception as e:
                    logger.warning("Stream callback error", error=str(e))

            # Add conversation history to context (with smart filtering)
            context_with_history = self.conversation_context.copy()
            if self.conversation_history:
                # Keep only last 6 messages (3 exchanges) and filter out verbose ones
                filtered_history = self._filter_conversation_history(
                    self.conversation_history[-6:]
                )
                context_with_history["conversation_history"] = filtered_history
                logger.debug(
                    "Conversation history filtered for context",
                    original_count=len(self.conversation_history),
                    filtered_count=len(filtered_history),
                )

            result = await self.chat_workflow.process_chat(
                user_message=user_message,
                conversation_context=context_with_history,
                stream_callback=stream_callback,
            )

            # Store this exchange in conversation history (with size limit)
            self.conversation_history.append({"role": "user", "content": user_message})
            if result.get("response"):
                response_content = result["response"]
                # Truncate very long responses
                if len(response_content) > 1000:
                    response_content = response_content[:1000] + "... [truncated]"
                self.conversation_history.append(
                    {"role": "assistant", "content": response_content}
                )

            # Keep only last 10 messages total (5 exchanges)
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
                logger.debug("Conversation history trimmed to last 10 messages")

            self._update_conversation_context(result)

            logger.debug(
                "Sending final response to client",
                response_length=len(result.get("response", "")),
                response_preview=result.get("response", "")[:200],
                status=result.get("status"),
            )

            await self._send_chat_response(websocket, result)

        except Exception as e:
            logger.error("Conversational chat error", error=str(e), exc_info=True)
            await websocket.send_json(
                {"type": "error", "message": f"Oops, something went wrong: {str(e)}"}
            )

    def _extract_agent_from_message(self, message) -> str:
        """Extract agent name from AutoGen message object."""
        if hasattr(message, "source"):
            return self._format_agent_name(message.source)
        content = self._extract_content_from_message(message)
        if content:
            return self._extract_agent_name_from_content(content)
        return "Agent"

    def _extract_content_from_message(self, message) -> str:
        """Extract content string from AutoGen message object."""
        if hasattr(message, "content"):
            content = message.content
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        parts.append(item["text"])
                    elif isinstance(item, str):
                        parts.append(item)
                return "\n".join(parts)
            return str(content)
        return str(message)

    def _should_display_message(self, message) -> bool:
        """Check if message should be displayed to user."""
        message_type = type(message).__name__

        # Skip system/internal message types
        internal_types = [
            "StopMessage",
            "TextMessage",
            "ToolCallRequestEvent",
            "ToolCallResultEvent",
            "HandoffMessage",
        ]

        if message_type in internal_types:
            logger.debug("Skipping internal message type", msg_type=message_type)
            return False

        if hasattr(message, "content"):
            content = str(message.content).lower()

            # Skip TERMINATE and handoff messages
            skip_keywords = [
                "terminate",
                "transferred to",
                "handoff",
                "adopting the role",
            ]

            if any(skip in content for skip in skip_keywords):
                logger.debug(
                    "Skipping message with system keyword",
                    content_preview=content[:100],
                )
                return False

        return True

    def _format_message_content(self, content: str) -> str:
        """Format message content for natural display."""
        if content.strip().startswith("{") and (
            "query" in content or "metrics" in content
        ):
            try:
                data = json.loads(content) if isinstance(content, str) else content
                if "essential_metrics" in data:
                    return self._format_prometheus_result(data)
                if "error_patterns" in data or "recent_errors" in data:
                    return self._format_loki_result(data)
            except (json.JSONDecodeError, Exception):
                pass
        return content

    def _filter_conversation_history(
        self, history: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """
        Filter conversation history to reduce token usage.

        Removes verbose tool results and truncates long messages.
        """
        filtered = []
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")

            # Skip empty messages
            if not content or len(content.strip()) < 5:
                continue

            # Truncate very long messages (likely tool results)
            if len(content) > 1000:
                # Keep only the summary part, not raw data
                if role == "assistant":
                    filtered.append(
                        {"role": role, "content": "[Previous analysis provided]"}
                    )
                continue

            # Truncate moderately long messages
            if len(content) > 500:
                filtered.append({"role": role, "content": content[:500] + "..."})
            else:
                filtered.append(msg)

        logger.debug(
            "Conversation history filtered",
            original=len(history),
            filtered=len(filtered),
        )
        return filtered

    def _update_conversation_context(self, result: dict[str, Any]):
        """Update conversation context with findings from this turn."""
        findings = result.get("findings", {})
        agents_participated = result.get("agents_participated", [])

        if "previous_findings" not in self.conversation_context:
            self.conversation_context["previous_findings"] = []

        turn_summary = {
            "agents": agents_participated,
            "had_metrics": bool(findings.get("metrics")),
            "had_logs": bool(findings.get("logs")),
            "had_analysis": bool(findings.get("analysis")),
        }

        self.conversation_context["previous_findings"].append(turn_summary)
        if len(self.conversation_context["previous_findings"]) > 3:
            self.conversation_context["previous_findings"] = self.conversation_context[
                "previous_findings"
            ][-3:]

    async def _send_chat_response(self, websocket, result: dict[str, Any]):
        """Send final chat response to user."""
        response = result.get("response", "I've completed the analysis.")
        agents = result.get("agents_participated", [])

        # Clean up response if it contains raw message objects
        if "messages=[" in response or "TextMessage(" in response:
            # Extract readable content from message objects
            logger.warning(
                "Response contains raw message objects, extracting clean content",
                response_preview=response[:200],
            )
            # Try to find actual content
            import re

            content_match = re.search(r"content='([^']+)'", response)
            if content_match:
                response = content_match.group(1)
            else:
                response = "Analysis completed. Please let me know if you need more information."

        logger.info(
            "Sending chat_complete to websocket",
            response_length=len(response),
            agents_count=len(agents),
            agents=agents,
        )

        await websocket.send_json(
            {
                "type": "chat_complete",
                "message": response,
                "agents_participated": agents,
                "status": result.get("status", "success"),
            }
        )

        logger.debug("chat_complete message sent successfully")

    def _format_agent_name(self, name: str) -> str:
        """Format agent name for display."""
        name_map = {
            "chat_orchestrator": "🎯 Orchestrator",
            "metric_expert": "📊 Metric Expert",
            "log_expert": "📋 Log Expert",
            "analysis_agent": "🔬 Analyst",
            "report_agent": "📈 Reporter",
        }
        if name in name_map:
            return name_map[name]
        return name.replace("_", " ").replace(" agent", "").title()

    def _extract_agent_name_from_content(self, content: str) -> str:
        """Extract agent name from message content."""
        keywords = {
            "orchestrator": "Orchestrator",
            "metric": "Metric Expert",
            "log": "Log Expert",
            "analysis": "Analyst",
            "report": "Reporter",
        }
        content_lower = content.lower()
        for keyword, name in keywords.items():
            if keyword in content_lower[:100]:
                return name
        return "Agent"

    def _format_prometheus_result(self, data: dict) -> str:
        """Format Prometheus query results naturally."""
        metrics = data.get("essential_metrics", {})
        has_data = any(m.get("metrics") for m in metrics.values())
        if not has_data:
            namespace = data.get("query_info", {}).get("namespace_filter", "unknown")
            return f"No metric data found in {namespace} namespace."
        parts = ["Here are the current metrics:"]
        for metric_name, metric_data in metrics.items():
            metric_list = metric_data.get("metrics", [])
            if metric_list:
                parts.append(f"\n**{metric_name}:**")
                for m in metric_list[:3]:
                    instance = m.get("labels", {}).get("instance", "unknown")
                    value = m.get("value", "N/A")
                    parts.append(f"  - {instance}: {value}")
        return "\n".join(parts)

    def _format_loki_result(self, data: dict) -> str:
        """Format Loki query results naturally."""
        total = data.get("total_entries", 0)
        errors = data.get("recent_errors", [])
        if total == 0:
            return "No errors found in recent logs. System appears healthy! 👍"
        parts = [f"Found {total} log entries."]
        if errors:
            parts.append(f"\nRecent errors ({len(errors)}):")
            for err in errors[:3]:
                timestamp = err.get("timestamp", "unknown")
                message = err.get("message", "")[:100]
                parts.append(f"  - [{timestamp}] {message}")
        return "\n".join(parts)

    def clear_conversation(self):
        """Clear conversation history and context for a fresh start."""
        self.conversation_history.clear()
        self.conversation_context.clear()
        logger.info("Conversation history cleared")
