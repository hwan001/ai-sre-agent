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
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Handoff
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import Swarm
from autogen_core import CancellationToken
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

from prompts.loader import load_prompt
from tools.tool_registry import ToolRegistry

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

        # 1. Chat Orchestrator - The conversation router
        logger.debug("Creating chat_orchestrator agent")
        self.orchestrator = AssistantAgent(
            name="chat_orchestrator",
            description=load_prompt("chat_orchestrator"),
            model_client=self.model_client,
            handoffs=[
                Handoff(
                    target="metric_expert",
                    description="Hand off to metric expert for Prometheus queries and resource analysis",
                ),
                Handoff(
                    target="log_expert",
                    description="Hand off to log expert for Loki queries and log analysis",
                ),
                Handoff(
                    target="analysis_agent",
                    description="Hand off to analysis agent for comprehensive root cause analysis",
                ),
                Handoff(
                    target="report_agent",
                    description="Hand off to report agent when user requests a report or summary",
                ),
                Handoff(
                    target="presentation_agent",
                    description="Hand off to presentation agent to format technical data into beautiful markdown",
                ),
            ],
            tools=[],  # Orchestrator doesn't use tools directly
        )
        logger.debug("chat_orchestrator agent created with 5 handoffs")

        # 2. Metric Expert Agent - Prometheus specialist
        logger.debug("Creating metric_expert agent", tools_count=len(metric_tools))
        self.metric_expert = AssistantAgent(
            name="metric_expert",
            description=load_prompt("metric_expert_agent"),
            model_client=self.model_client,
            handoffs=[
                Handoff(
                    target="chat_orchestrator",
                    description="Return to orchestrator with metric findings",
                ),
                Handoff(
                    target="log_expert",
                    description="Hand off to log expert if logs are needed to explain metrics",
                ),
            ],
            tools=metric_tools,
        )
        logger.debug("metric_expert agent created")

        # 3. Log Expert Agent - Loki specialist
        logger.debug("Creating log_expert agent", tools_count=len(log_tools))
        self.log_expert = AssistantAgent(
            name="log_expert",
            description=load_prompt("log_expert_agent"),
            model_client=self.model_client,
            handoffs=[
                Handoff(
                    target="chat_orchestrator",
                    description="Return to orchestrator with log findings",
                ),
                Handoff(
                    target="metric_expert",
                    description="Hand off to metric expert if metrics context is needed",
                ),
            ],
            tools=log_tools,  # Logs
        )
        logger.debug("log_expert agent created")

        # 4. Analysis Agent - The synthesizer
        logger.debug("Creating analysis_agent")
        self.analysis_agent = AssistantAgent(
            name="analysis_agent",
            description=load_prompt("analysis_agent"),
            model_client=self.model_client,
            handoffs=[
                Handoff(
                    target="chat_orchestrator",
                    description="Return to orchestrator with analysis results",
                ),
                Handoff(
                    target="metric_expert",
                    description="Request additional metrics if needed for analysis",
                ),
                Handoff(
                    target="log_expert",
                    description="Request additional logs if needed for analysis",
                ),
            ],
            tools=[],  # Analysis doesn't need direct tool access
        )
        logger.debug("analysis_agent created")

        # 5. Report Agent - The visualizer
        logger.debug("Creating report_agent")
        self.report_agent = AssistantAgent(
            name="report_agent",
            description=load_prompt("report_agent"),
            model_client=self.model_client,
            handoffs=[
                Handoff(
                    target="chat_orchestrator",
                    description="Return to orchestrator with generated report",
                ),
            ],
            tools=[],  # Uses conversation history to create reports
        )
        logger.debug("report_agent created")

        # 6. Presentation Agent - The beautifier
        logger.debug("Creating presentation_agent")
        self.presentation_agent = AssistantAgent(
            name="presentation_agent",
            description=load_prompt("presentation_agent"),
            model_client=self.model_client,
            handoffs=[
                Handoff(
                    target="chat_orchestrator",
                    description="Return to orchestrator with beautifully formatted response",
                ),
            ],
            tools=[],  # Formats data from other agents
        )
        logger.debug("presentation_agent created")

        logger.info(
            "Agents created",
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

        # Create Swarm team
        team = Swarm(
            participants=[
                self.orchestrator,
                self.metric_expert,
                self.log_expert,
                self.analysis_agent,
                self.report_agent,
                self.presentation_agent,
            ],
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
            task = self._build_chat_task(user_message, conversation_context)
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

    def _build_chat_task(
        self,
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

        # Add conversation history if available (filtered and summarized)
        if conversation_context and "conversation_history" in conversation_context:
            history = conversation_context["conversation_history"]
            if history:
                task += "Previous Conversation Summary:\n"

                # Filter out tool results and keep only user/assistant messages
                filtered_history = []
                for msg in history[-10:]:  # Look at last 10 messages
                    role = msg.get("role", "")
                    content = str(msg.get("content", ""))

                    # Skip tool results and function calls (they're too verbose)
                    if role in ["tool", "function"]:
                        continue

                    # Skip messages with tool call results in content
                    if "tool_calls" in str(msg) or len(content) > 2000:
                        # Summarize very long messages
                        if role == "assistant":
                            filtered_history.append(
                                {
                                    "role": role,
                                    "content": "[Previous analysis provided]",
                                }
                            )
                        continue

                    filtered_history.append(msg)

                # Only include last 4 messages (2 exchanges)
                for msg in filtered_history[-4:]:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")

                    # Truncate long messages
                    if len(content) > 300:
                        content = content[:300] + "..."

                    task += f"{role.upper()}: {content}\n"

                task += "\n"

                logger.debug(
                    "Conversation history filtered",
                    original_count=len(history),
                    filtered_count=len(filtered_history),
                    included_count=min(4, len(filtered_history)),
                )

        task += f"Current User Question: {user_message}\n\n"

        # Add other context
        if conversation_context:
            if "namespace" in conversation_context:
                task += f"Namespace: {conversation_context['namespace']}\n"
            if "pod" in conversation_context:
                task += f"Pod: {conversation_context['pod']}\n"
            if "previous_findings" in conversation_context:
                task += f"\nPrevious Findings:\n{conversation_context['previous_findings']}\n"

        task += "\nPlease help the user by engaging the appropriate expert agents. Continue the conversation naturally based on the context."

        return task

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
        # Extract agent participation
        agents_participated = list(
            set(
                getattr(msg, "source", "unknown")
                for msg in messages
                if hasattr(msg, "source")
            )
        )

        # Get final response (last substantial message)
        final_response = self._extract_final_response(messages)

        # Extract key findings from each agent
        findings = self._extract_agent_findings(messages)

        return {
            "status": "success",
            "user_message": user_message,
            "response": final_response,
            "agents_participated": agents_participated,
            "findings": findings,
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

    def _extract_final_response(self, messages: list) -> str:
        """Extract the final response to show the user."""
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
                content = msg.content  # Don't convert to string yet
                # If content is a string, use it
                if isinstance(content, str):
                    content_clean = content.strip()
                else:
                    # If content is not a string, try to extract text
                    content_clean = str(content).strip()
            else:
                content_clean = str(msg).strip()

            # Skip empty messages
            if not content_clean:
                continue

            # Skip if this looks like a serialized message object
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
                # Remove trailing punctuation that might be left
                before_terminate = before_terminate.rstrip("!.,;")

                if len(before_terminate) > 30:
                    logger.debug(
                        "Extracted response before TERMINATE",
                        response_length=len(before_terminate),
                        source=getattr(msg, "source", "unknown"),
                    )
                    return before_terminate
                # If nothing meaningful before TERMINATE, skip this message
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

            # Skip serialized objects
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

    def _extract_agent_findings(self, messages: list) -> dict[str, list[str]]:
        """Extract findings from each agent type."""
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
            "version": "3.0.0",
            "type": "conversational",
            "framework": "AutoGen 0.7 Swarm",
            "architecture": "Dynamic HandOff-based agent collaboration",
            "agents": {
                "chat_orchestrator": "Conversation router and coordinator",
                "metric_expert": "Prometheus metrics specialist",
                "log_expert": "Loki logs specialist",
                "analysis_agent": "Root cause analysis synthesizer",
                "report_agent": "Visual report generator",
            },
            "features": [
                "Natural conversation flow",
                "Dynamic agent participation via HandOff",
                "Multiple agents can contribute to same conversation",
                "On-demand report generation",
                "Streaming support for real-time updates",
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
