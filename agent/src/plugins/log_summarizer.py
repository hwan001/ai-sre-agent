"""
Log Summarization Tool

This tool provides LLM-powered log analysis and summarization capabilities
for SRE incident analysis.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

import structlog
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

from configs.config import get_settings

logger = structlog.get_logger()


def create_log_summary_client() -> AzureOpenAIChatCompletionClient | None:
    """Create a dedicated model client for log summarization."""
    settings = get_settings()

    if not settings.llm.azure_openai_api_key or not settings.llm.azure_openai_endpoint:
        logger.warning("Azure OpenAI not configured, LLM log summarization disabled")
        return None

    try:
        summary_client = AzureOpenAIChatCompletionClient(
            model="gpt-4o",
            azure_deployment="gpt-4o",
            azure_endpoint=settings.llm.azure_openai_endpoint,
            api_key=settings.llm.azure_openai_api_key,
            api_version=settings.llm.azure_openai_api_version,
            seed=42,
            temperature=0.1,  # Low temperature for consistent analysis
        )
        logger.info("Log summary client created successfully")
        return summary_client
    except Exception as e:
        logger.error("Failed to create log summary client", error=str(e))
        return None


class LogSummarizerTools:
    """
    LLM-powered log analysis and summarization tools for AutoGen agents.

    Provides intelligent log analysis capabilities using LLM models
    to extract insights, patterns, and actionable recommendations.
    """

    def __init__(self, model_client: AzureOpenAIChatCompletionClient | None = None):
        """
        Initialize log summarizer tools.

        Args:
            model_client: LLM client for log summarization
        """
        self._model_client = model_client or create_log_summary_client()

    async def _summarize_logs_with_llm(
        self, logs: list[dict], context: str = "", analysis_type: str = "general"
    ) -> dict[str, Any]:
        """
        Summarize logs using LLM analysis.

        Args:
            logs: List of log entries with timestamp and message
            context: Additional context for analysis
            analysis_type: Type of analysis (general, error, performance, security)

        Returns:
            LLM-generated summary and insights
        """
        if not self._model_client:
            return {
                "error": "LLM client not available for log summarization",
                "fallback_summary": f"Found {len(logs)} log entries requiring manual analysis",
            }

        if not logs:
            return {
                "summary": "No logs provided for analysis",
                "insights": "No data available for analysis",
            }

        # Prepare log text for LLM (limit to prevent token overflow)
        log_text = "\n".join(
            [
                f"[{log.get('timestamp', 'unknown')}] {log.get('message', '')[:300]}"
                for log in logs[:100]  # Limit to 100 entries to manage token usage
            ]
        )

        # Create analysis prompt based on type
        analysis_prompts = {
            "general": self._get_general_analysis_prompt(),
            "error": self._get_error_analysis_prompt(),
            "performance": self._get_performance_analysis_prompt(),
            "security": self._get_security_analysis_prompt(),
        }

        base_prompt = analysis_prompts.get(analysis_type, analysis_prompts["general"])

        prompt = f"""
        {base_prompt}
        
        Context: {context}
        
        Logs to analyze ({len(logs)} entries):
        {log_text}
        
        Please provide your analysis in the following JSON format:
        {{
            "key_issues": ["issue1", "issue2"],
            "error_patterns": {{"pattern_name": count}},
            "severity": "critical|high|medium|low",
            "recommended_actions": ["action1", "action2"],
            "timeline_summary": "brief timeline description",
            "root_cause_analysis": "potential root causes",
            "business_impact": "impact assessment",
            "confidence_level": "high|medium|low",
            "additional_insights": "other important observations"
        }}
        """

        try:
            # AutoGen 0.7.4+ API - direct message creation
            from autogen_core.models._types import UserMessage

            # Create messages for the model
            messages = [UserMessage(content=prompt, source="user")]

            # Use the model client directly with create method
            response = await self._model_client.create(
                messages=messages, model="gpt-4o", temperature=0.1, max_tokens=1500
            )

            # Extract content from response
            if hasattr(response, "content"):
                summary_text = response.content
            elif hasattr(response, "choices") and response.choices:
                summary_text = response.choices[0].message.content
            else:
                summary_text = str(response)

            try:
                summary_data = json.loads(summary_text)
                return {
                    "llm_summary": summary_data,
                    "analyzed_logs_count": len(logs),
                    "analysis_type": analysis_type,
                    "context": context,
                    "timestamp": datetime.now().isoformat(),
                }
            except json.JSONDecodeError:
                return {
                    "llm_summary": {"raw_analysis": summary_text},
                    "analyzed_logs_count": len(logs),
                    "analysis_type": analysis_type,
                    "parsing_note": "LLM response was not valid JSON, using raw text",
                }

        except Exception as e:
            logger.error("LLM log summarization failed", error=str(e))
            return {
                "error": f"Failed to summarize logs with LLM: {str(e)}",
                "fallback_summary": f"Found {len(logs)} log entries with automated analysis unavailable",
                "analyzed_logs_count": len(logs),
            }

    def _get_general_analysis_prompt(self) -> str:
        """Get prompt for general log analysis."""
        return """
        You are a Senior SRE analyzing system logs for incident investigation.
        Analyze the provided logs and identify:
        - Key issues and anomalies
        - Patterns in errors or warnings
        - Potential system problems
        - Recommended investigation steps
        - Overall system health assessment
        """

    def _get_error_analysis_prompt(self) -> str:
        """Get prompt for error-focused analysis."""
        return """
        You are a Senior SRE focusing on error analysis in system logs.
        Analyze the provided error logs and identify:
        - Root causes of errors
        - Error frequency and trends
        - Critical vs non-critical errors
        - Cascading failure patterns
        - Immediate remediation actions needed
        Focus specifically on errors, exceptions, and failure patterns.
        """

    def _get_performance_analysis_prompt(self) -> str:
        """Get prompt for performance analysis."""
        return """
        You are a Senior SRE analyzing system logs for performance issues.
        Look for:
        - Performance degradation indicators
        - Resource utilization patterns
        - Latency and throughput issues
        - Bottlenecks and capacity problems
        - Performance optimization opportunities
        Focus on metrics, timing, and resource usage patterns.
        """

    def _get_security_analysis_prompt(self) -> str:
        """Get prompt for security-focused analysis."""
        return """
        You are a Senior SRE analyzing logs for security concerns.
        Look for:
        - Authentication and authorization failures
        - Suspicious access patterns
        - Security policy violations
        - Potential intrusion attempts
        - Compliance and audit concerns
        Focus on security events and potential threats.
        """

    async def summarize_error_logs(
        self,
        error_logs: list[dict],
        incident_context: str = "",
        time_window_minutes: int = 30,
    ) -> dict[str, Any]:
        """
        Tool: Summarize error logs with LLM-powered analysis.

        Args:
            error_logs: List of error log entries
            incident_context: Context about the incident being investigated
            time_window_minutes: Time window the logs cover

        Returns:
            LLM-powered error analysis and recommendations
        """
        context = f"""
        Error Log Analysis for SRE Incident Investigation
        Incident Context: {incident_context}
        Time Window: Last {time_window_minutes} minutes
        Total Error Logs: {len(error_logs)}
        
        This is part of an active incident investigation.
        Focus on actionable insights for immediate remediation.
        """

        return await self._summarize_logs_with_llm(
            logs=error_logs, context=context, analysis_type="error"
        )

    async def summarize_application_logs(
        self,
        app_logs: list[dict],
        application_name: str,
        analysis_focus: str = "general",
    ) -> dict[str, Any]:
        """
        Tool: Summarize application logs with contextual analysis.

        Args:
            app_logs: List of application log entries
            application_name: Name of the application
            analysis_focus: Focus area (general, performance, errors, security)

        Returns:
            Application-specific log analysis and insights
        """
        context = f"""
        Application Log Analysis
        Application: {application_name}
        Analysis Focus: {analysis_focus}
        Log Entries: {len(app_logs)}
        
        Provide insights specific to application behavior and health.
        Consider application-level patterns and business logic issues.
        """

        return await self._summarize_logs_with_llm(
            logs=app_logs, context=context, analysis_type=analysis_focus
        )

    async def analyze_log_patterns(
        self,
        log_entries: list[dict],
        pattern_description: str,
        severity_focus: str = "medium",
    ) -> dict[str, Any]:
        """
        Tool: Analyze logs for specific patterns with LLM intelligence.

        Args:
            log_entries: List of log entries to analyze
            pattern_description: Description of patterns to look for
            severity_focus: Severity level to focus on (low, medium, high, critical)

        Returns:
            Pattern analysis results with LLM insights
        """
        context = f"""
        Log Pattern Analysis
        Pattern Focus: {pattern_description}
        Severity Focus: {severity_focus}
        Log Entries: {len(log_entries)}
        
        Analyze the logs for the specified patterns and provide:
        - Pattern frequency and trends
        - Correlation with other events
        - Potential impact assessment
        - Pattern-specific recommendations
        """

        return await self._summarize_logs_with_llm(
            logs=log_entries, context=context, analysis_type="general"
        )

    async def comprehensive_log_analysis(
        self,
        all_logs: list[dict],
        incident_summary: str,
        affected_components: list[str] = None,
    ) -> dict[str, Any]:
        """
        Tool: Comprehensive log analysis across multiple sources.

        Args:
            all_logs: Combined logs from multiple sources
            incident_summary: Summary of the incident being investigated
            affected_components: List of affected system components

        Returns:
            Comprehensive cross-component log analysis
        """
        components_str = ", ".join(affected_components or ["Unknown"])

        context = f"""
        Comprehensive Multi-Component Log Analysis
        Incident Summary: {incident_summary}
        Affected Components: {components_str}
        Total Log Entries: {len(all_logs)}
        
        Provide a holistic analysis across all components:
        - Cross-component correlation
        - System-wide patterns
        - Cascading failure analysis
        - Comprehensive remediation strategy
        - Priority-based action plan
        """

        return await self._summarize_logs_with_llm(
            logs=all_logs, context=context, analysis_type="general"
        )

    async def close(self) -> None:
        """Close LLM client if owned."""
        if self._model_client and hasattr(self._model_client, "close"):
            try:
                await self._model_client.close()
            except Exception as e:
                logger.warning("Error closing log summary client", error=str(e))


def get_log_summarizer_tools(
    model_client: AzureOpenAIChatCompletionClient | None = None,
) -> list[Callable]:
    """
    Get log summarizer tools as a list of callable functions for AutoGen agents.

    Args:
        model_client: Optional LLM client for log summarization. If not provided,
                     will create a new client automatically.

    Returns:
        List of log summarizer tool functions
    """
    summarizer = LogSummarizerTools(model_client=model_client)

    return [
        summarizer.summarize_error_logs,
        summarizer.summarize_application_logs,
        summarizer.analyze_log_patterns,
        summarizer.comprehensive_log_analysis,
    ]
