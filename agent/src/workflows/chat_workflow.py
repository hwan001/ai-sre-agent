"""
Chat-Based SRE Workflow

A conversational workflow for Kubernetes diagnostics using AutoGen 0.7 Swarm pattern.
Agents dynamically join conversations based on user needs through HandOff coordination.

Architecture:
- ChatOrchestrator: Routes conversations and engages specialized agents
- MetricExpertAgent: Prometheus metrics specialist
- LogExpertAgent: Loki logs specialist
- AnalysisAgent: Synthesizes findings and performs root cause analysis
- ReportAgent: Generates visual reports on demand

Key Features:
- Natural conversation flow with dynamic agent participation
- HandOff-based agent collaboration (no rigid team structure)
- Multiple agents can contribute to the same conversation
- Report generation on user request
"""

from __future__ import annotations

import os
from typing import Any

import structlog
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import Swarm
from autogen_core import CancellationToken
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

from agents.factory import AgentFactory
from tools.tool_registry import ToolRegistry
from utils.message_processor import MessageProcessor

logger = structlog.get_logger()


class ChatWorkflow:
    """
    Conversational workflow for Kubernetes diagnostics.

    Uses AutoGen Swarm pattern where ChatOrchestrator dynamically
    engages specialist agents through HandOff based on conversation flow.

    Example conversation flow:
    1. User: "Why is my pod crashing?"
    2. Orchestrator → MetricExpert: Check resource usage
    3. Orchestrator → LogExpert: Find crash logs
    4. Orchestrator → AnalysisAgent: Synthesize findings
    5. User: "Give me a report"
    6. Orchestrator → ReportAgent: Generate visual report
    """

    def __init__(self, tool_registry: ToolRegistry):
        """
        Initialize chat workflow.

        Args:
            tool_registry: Registry containing all available tools
        """
        logger.info("Initializing ChatWorkflow")

        self.tool_registry = tool_registry

        # Azure OpenAI configuration
        self.azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_api_version = os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-12-01-preview"
        )

        logger.debug(
            "Azure OpenAI configuration loaded",
            endpoint=self.azure_endpoint,
            api_version=self.azure_api_version,
            has_api_key=bool(self.azure_api_key),
        )

        if not self.azure_api_key or not self.azure_endpoint:
            raise ValueError(
                "Azure OpenAI configuration missing. "
                "Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT"
            )

        # Create model client
        logger.debug(
            "Creating Azure OpenAI model client",
            model="gpt-4o",
            temperature=0.3,
            parallel_tool_calls=False,
        )
        self.model_client = AzureOpenAIChatCompletionClient(
            model="gpt-4o",
            azure_deployment="gpt-4o",
            azure_endpoint=self.azure_endpoint,
            api_key=self.azure_api_key,
            api_version=self.azure_api_version,
            seed=42,
            temperature=0.3,  # Slightly creative for natural conversation
            parallel_tool_calls=False,
        )
        logger.debug("Model client created successfully")

        # Create agents (reusable across requests)
        self._create_agents()

        logger.info("ChatWorkflow initialized successfully")

    def _create_agents(self) -> None:
        """Create all agents with HandOff configurations."""
        logger.debug("Starting agent creation")

        # Get tools from registry
        metric_tools = self.tool_registry.get_tools("metrics")
        log_tools = self.tool_registry.get_tools("logs")
        logger.debug(
            "Tools retrieved from registry",
            metric_tools_count=len(metric_tools),
            log_tools_count=len(log_tools),
        )

        # Create agent factory
        logger.debug("Creating agent factory")
        self.agent_factory = AgentFactory(
            model_client=self.model_client,
            metric_tools=metric_tools,
            log_tools=log_tools,
        )

        logger.info(
            "Agents ready to be created on demand",
            agents=[
                "chat_orchestrator",
                "metric_expert",
                "log_expert",
                "analysis_agent",
                "report_agent",
                "presentation_agent",
            ],
        )

    def _create_team(self) -> Swarm:
        """
        Create a fresh Swarm team with all agents.

        Creates a new team instance for each request to avoid
        concurrent execution issues.

        Returns:
            New Swarm team instance
        """

        # Termination conditions: stop on TERMINATE or max 20 messages
        termination = MaxMessageTermination(max_messages=20) | TextMentionTermination(
            "TERMINATE"
        )

        logger.debug(
            "Creating Swarm team with termination conditions",
            max_messages=20,
            terminate_on_keyword=True,
        )

        # Get fresh agent instances
        agent_list = self.agent_factory.get_agent_list()

        # Create Swarm team
        team = Swarm(
            participants=agent_list,
            termination_condition=termination,
        )

        logger.debug("Fresh Swarm team created for request")

        return team

    async def process_chat(
        self,
        user_message: str,
        conversation_context: dict[str, Any] | None = None,
        stream_callback=None,
    ) -> dict[str, Any]:
        """
        Process a chat message using the Swarm workflow.

        Args:
            user_message: User's question or request
            conversation_context: Optional context from previous messages
            stream_callback: Optional callback for real-time streaming

        Returns:
            Chat response with agent contributions

        Example:
            ```python
            workflow = ChatWorkflow(tool_registry)

            async def callback(msg):
                print(f"Agent: {msg}")

            result = await workflow.process_chat(
                user_message="Why is my pod using so much CPU?",
                stream_callback=callback
            )
            ```
        """
        logger.info("Processing chat message", message=user_message[:100])
        logger.debug(
            "Chat processing started",
            message_length=len(user_message),
            has_context=bool(conversation_context),
            has_stream_callback=bool(stream_callback),
        )

        try:
            # Create a fresh Swarm team for this request
            # This ensures no conflicts with concurrent requests
            logger.debug("Creating Swarm team for request")
            team = self._create_team()
            logger.debug("Swarm team created successfully")

            # Build task with context
            task = MessageProcessor.build_task(user_message, conversation_context)
            logger.debug("Task built", task_length=len(task))

            # Run Swarm team with streaming
            logger.debug("Starting Swarm team execution with streaming")
            messages = []
            async for message in team.run_stream(
                task=task,
                cancellation_token=CancellationToken(),
            ):
                messages.append(message)

                # Stream to callback if provided
                if stream_callback:
                    await stream_callback(message)

                # Log each agent message with details
                msg_source = getattr(message, "source", "unknown")
                msg_content = (
                    str(message.content)
                    if hasattr(message, "content")
                    else str(message)
                )
                logger.debug(
                    "Agent message received",
                    source=msg_source,
                    message_length=len(msg_content),
                    message_preview=(
                        msg_content[:200] if len(msg_content) > 200 else msg_content
                    ),
                    total_messages=len(messages),
                )

            # Process results
            logger.debug("Processing chat results", total_messages=len(messages))
            result = self._process_chat_results(messages, user_message)

            logger.info(
                "Chat processing completed",
                agents_participated=result.get("agents_participated"),
                findings_count=sum(len(v) for v in result.get("findings", {}).values()),
            )
            logger.debug(
                "Chat result details",
                response_length=len(result.get("response", "")),
                response_preview=result.get("response", "")[:200],
                agents=result.get("agents_participated"),
                findings={k: len(v) for k, v in result.get("findings", {}).items()},
            )

            return result

        except Exception as e:
            logger.error("Chat processing failed", error=str(e), exc_info=True)
            logger.debug("Exception details", exception_type=type(e).__name__)
            return {
                "status": "error",
                "error": str(e),
                "response": f"I encountered an error: {str(e)}",
                "agents_participated": [],
            }

    def _process_chat_results(
        self,
        messages: list,
        user_message: str,
    ) -> dict[str, Any]:
        """
        Process chat results from Swarm team.

        Args:
            messages: All messages from the conversation
            user_message: Original user message

        Returns:
            Structured chat response
        """
        # Extract information using MessageProcessor
        agents_participated = MessageProcessor.get_agents_participated(messages)
        final_response = MessageProcessor.extract_final_response(messages)
        findings = MessageProcessor.extract_agent_findings(messages)
        context_summary = MessageProcessor.extract_context_summary(messages)

        return {
            "status": "success",
            "user_message": user_message,
            "response": final_response,
            "agents_participated": agents_participated,
            "findings": findings,
            "context_summary": context_summary,
            "messages": messages,
            "full_conversation": [
                {
                    "agent": getattr(msg, "source", "unknown"),
                    "content": (
                        str(msg.content) if hasattr(msg, "content") else str(msg)
                    ),
                }
                for msg in messages
            ],
        }

    async def close(self) -> None:
        """Close workflow resources."""
        logger.info("Closing ChatWorkflow")
        try:
            await self.model_client.close()
        except Exception as e:
            logger.warning("Error closing model client", error=str(e))
        logger.info("ChatWorkflow closed")

    def get_workflow_info(self) -> dict[str, Any]:
        """Get workflow information."""
        return {
            "version": "3.1.0",  # Updated after refactoring
            "type": "conversational",
            "framework": "AutoGen 0.7 Swarm",
            "architecture": "Dynamic HandOff-based agent collaboration",
            "code_organization": {
                "agents": "src/agents/ - Modular agent definitions",
                "factory": "AgentFactory - Centralized agent creation",
                "message_processing": "MessageProcessor - Utility for message handling",
                "workflow": "ChatWorkflow - Main orchestration logic",
            },
            "agents": {
                "chat_orchestrator": "Conversation router and coordinator",
                "metric_expert": "Prometheus metrics specialist",
                "log_expert": "Loki logs specialist",
                "analysis_agent": "Root cause analysis synthesizer",
                "report_agent": "Visual report generator",
                "presentation_agent": "Markdown formatter",
            },
            "features": [
                "Natural conversation flow",
                "Dynamic agent participation via HandOff",
                "Multiple agents can contribute to same conversation",
                "On-demand report generation",
                "Streaming support for real-time updates",
                "Modular and maintainable architecture",
            ],
        }


# Convenience function
def create_chat_workflow(tool_registry: ToolRegistry) -> ChatWorkflow:
    """
    Create a chat workflow instance.

    Args:
        tool_registry: Tool registry with Prometheus, Loki, etc.

    Returns:
        Configured ChatWorkflow

    Example:
        ```python
        from tools.tool_registry import initialize_tool_registry

        registry = initialize_tool_registry()
        workflow = create_chat_workflow(registry)

        result = await workflow.process_chat("Show me high CPU pods")
        await workflow.close()
        ```
    """
    return ChatWorkflow(tool_registry)
