"""
Web Chat Manager for SRE Agent v3.0

Conversational Multi-Agent SRE System.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from configs.config import get_settings
from tools.tool_registry import initialize_tool_registry
from utils.message_formatter import MessageFormatter
from workflows.chat_workflow import ChatWorkflow

logger = structlog.get_logger()


class WebChatManager:
    """Conversational Multi-Agent SRE System Chat Manager."""

    MESSAGE_STREAM_DELAY = 0.1

    def __init__(self):
        """Initialize chat manager."""
        self.settings = get_settings()
        self.chat_workflow: ChatWorkflow | None = None
        self.conversation_context: dict[str, Any] = {}
        self.conversation_history: list[dict[str, str]] = []

        logger.info("WebChatManager initialized")

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
            # Ensure chat_workflow is initialized
            if not self.chat_workflow:
                raise ValueError("ChatWorkflow not initialized")

            await websocket.send_json(
                {"type": "chat_start", "message": "👋 Let me help you with that..."}
            )

            logger.info("Starting conversational chat", message=user_message[:100])

            # Add user message to history
            self.conversation_history.append({"role": "user", "content": user_message})

            # Prepare conversation context with history
            # History is already managed (orchestrator summaries + recent messages)
            # Just keep last 6 messages (3 exchanges) to avoid token overflow
            recent_history = (
                self.conversation_history[-6:]
                if len(self.conversation_history) > 6
                else self.conversation_history
            )

            context_with_history = {
                **self.conversation_context,
                "conversation_history": recent_history,
            }

            async def stream_callback(message):
                """Handle streamed messages from agents using MessageFormatter."""
                try:
                    # Use MessageFormatter to structure the message
                    formatted = MessageFormatter.format_for_websocket(message)

                    if not formatted:
                        # Message was filtered out
                        return

                    # Send structured message to websocket
                    await websocket.send_json(formatted)
                    await asyncio.sleep(self.MESSAGE_STREAM_DELAY)

                except Exception as e:
                    logger.warning("Stream callback error", error=str(e))

            # Process the chat WITH HISTORY
            result = await self.chat_workflow.process_chat(
                user_message=user_message,
                conversation_context=context_with_history,
                stream_callback=stream_callback,
            )

            # Extract orchestrator's summary from result if available
            # This allows orchestrator to compress its own understanding of history
            orchestrator_summary = result.get("context_summary")

            if orchestrator_summary:
                # If orchestrator provided a summary, store that instead of
                # full response. This keeps history lean while preserving
                # key information
                self.conversation_history.append(
                    {
                        "role": "assistant",
                        "content": orchestrator_summary,
                        "type": "summary",  # Mark as summary for tracking
                    }
                )
            elif result.get("response"):
                # No summary provided, store full response
                self.conversation_history.append(
                    {"role": "assistant", "content": result["response"]}
                )

            # Keep only last 10 messages to avoid unbounded growth
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

            # Send final response
            await self._send_chat_response(websocket, result)

        except Exception as e:
            logger.error("Conversational chat error", error=str(e), exc_info=True)
            await websocket.send_json(
                {"type": "error", "message": f"Oops, something went wrong: {str(e)}"}
            )

    async def _send_chat_response(self, websocket, result: dict[str, Any]):
        """Send final chat response to user."""
        response = result.get("response", "I've completed the analysis.")
        agents = result.get("agents_participated", [])

        logger.info(
            "Sending chat_complete to websocket",
            response_length=len(response),
            agents_count=len(agents),
            agents=agents,
        )

        response_data = {
            "type": "chat_complete",
            "message": response,
            "agents_participated": [a for a in agents if a != "user"],
        }

        await websocket.send_json(response_data)

        logger.debug("chat_complete message sent successfully")
