"""
Action Team

Swarm-based team for action recommendation and validation.
Ensures safe and effective remediation actions.
"""

from __future__ import annotations

from typing import Any, Sequence

import structlog
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.teams import Swarm
from autogen_core import CancellationToken
from autogen_core.models import ChatCompletionClient

from prompts.loader import load_prompt

logger = structlog.get_logger()


class ActionTeam:
    """
    Action recommendation team using Swarm pattern.

    Team structure:
    - RecommendationAgent: Suggests remediation actions
    - GuardAgent: Validates action safety
    - ApprovalAgent: Makes final approval decision

    Workflow: Recommendation -> Guard -> Approval
    """

    def __init__(
        self,
        model_client: ChatCompletionClient,
        action_tools: list | None = None,
    ):
        """
        Initialize action team.

        Args:
            model_client: LLM client for agents
            action_tools: Optional action execution tools
        """
        self.model_client = model_client
        self.action_tools = action_tools or []

        # Create agents
        self._create_agents()

        # Create Swarm team
        self.team = Swarm(
            participants=[
                self.recommendation_agent,
                self.guard_agent,
                self.approval_agent,
            ],
            termination_condition=MaxMessageTermination(max_messages=10),
        )

        logger.info("ActionTeam initialized")

    def _create_agents(self) -> None:
        """Create team agents."""

        # 1. Recommendation Agent - Action suggestion specialist
        self.recommendation_agent = AssistantAgent(
            name="recommendation_agent",
            description=load_prompt("recommendation_agent"),
            handoffs=["guard_agent"],
            model_client=self.model_client,
            tools=self.action_tools,
        )

        # 2. Guard Agent - Safety validation specialist
        self.guard_agent = AssistantAgent(
            name="guard_agent",
            description=load_prompt("guard_agent"),
            handoffs=["recommendation_agent", "approval_agent"],
            model_client=self.model_client,
            tools=[],
        )

        # 3. Approval Agent - Final decision specialist
        self.approval_agent = AssistantAgent(
            name="approval_agent",
            description=load_prompt("approval_agent"),
            model_client=self.model_client,
            tools=[],
        )

    async def evaluate(
        self, findings: dict[str, Any], context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Evaluate findings and recommend actions.

        Args:
            findings: Analysis findings from log/metric teams
            context: Additional context

        Returns:
            Action recommendations and approval
        """
        logger.info("Starting action evaluation")

        try:
            # Build task from findings
            task = self._build_task(findings, context)

            # Run the swarm team
            result = await self.team.run(
                task=task,
                cancellation_token=CancellationToken(),
            )

            logger.info("Action evaluation completed")

            # Extract decision from messages
            decision = self._extract_decision(result.messages)

            return {
                "status": "success",
                "decision": decision,
                "messages": [str(msg) for msg in result.messages],
                "stop_reason": result.stop_reason,
            }

        except Exception as e:
            logger.error("Action evaluation failed", error=str(e))
            return {
                "status": "error",
                "error": str(e),
                "decision": {
                    "approval": "REJECTED",
                    "confidence": 0.0,
                    "reasoning": f"Evaluation failed: {e}",
                },
            }

    def _build_task(
        self, findings: dict[str, Any], context: dict[str, Any] | None
    ) -> str:
        """
        Build task description from findings.

        Args:
            findings: Analysis findings
            context: Additional context

        Returns:
            Task description
        """
        task = """Based on the following incident analysis, recommend and validate remediation actions.

**Analysis Findings:**
"""

        # Add log findings if available
        if "log_analysis" in findings:
            task += f"\n**Log Analysis:**\n{findings['log_analysis']}\n"

        # Add metric findings if available
        if "metric_analysis" in findings:
            task += f"\n**Metric Analysis:**\n{findings['metric_analysis']}\n"

        # Add general findings
        if "summary" in findings:
            task += f"\n**Summary:**\n{findings['summary']}\n"

        # Add context
        if context:
            task += f"\n**Context:**\n{context}\n"

        task += """
**Your Task:**
1. recommendation_agent: Suggest appropriate remediation actions
2. guard_agent: Validate actions for safety
3. approval_agent: Make final decision

Proceed with the workflow."""

        return task

    def _extract_decision(self, messages: Sequence[Any]) -> dict[str, Any]:
        """
        Extract final decision from messages.

        Args:
            messages: Team messages

        Returns:
            Decision details
        """
        if not messages:
            return {
                "approval": "REJECTED",
                "confidence": 0.0,
                "reasoning": "No decision made",
            }

        # Get last message (should be from approval agent)
        last_message = messages[-1]
        content = str(last_message.content)

        # Parse decision
        decision = {
            "approval": "REQUIRES_HUMAN_APPROVAL",
            "confidence": 0.5,
            "reasoning": content,
        }

        # Extract approval status
        content_upper = content.upper()
        if "DECISION: APPROVED" in content_upper:
            if "CAUTION" in content_upper:
                decision["approval"] = "APPROVED_WITH_CAUTION"
            else:
                decision["approval"] = "APPROVED"
        elif "DECISION: REJECTED" in content_upper:
            decision["approval"] = "REJECTED"

        # Extract confidence
        import re

        conf_match = re.search(r"CONFIDENCE[:\s]+(\d+\.?\d*)", content_upper)
        if conf_match:
            decision["confidence"] = float(conf_match.group(1))

        return decision

    def get_team_summary(self) -> dict[str, Any]:
        """
        Get team configuration summary.

        Returns:
            Team summary
        """
        return {
            "team_type": "Swarm",
            "agents": [
                "recommendation_agent",
                "guard_agent",
                "approval_agent",
            ],
            "handoffs": [
                "recommendation -> guard",
                "guard -> recommendation (if needed)",
                "guard -> approval",
            ],
            "workflow": "Sequential validation pipeline",
        }
