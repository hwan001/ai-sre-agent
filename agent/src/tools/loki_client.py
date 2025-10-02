"""
Loki Log Query Plugin

This plugin provides integration with Grafana Loki for log aggregation and querying.
Uses httpx (existing dependency) for HTTP requests and integrates with AutoGen agents as tools.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field

from configs.config import get_settings

logger = structlog.get_logger()


class LogQLQuery(BaseModel):
    """LogQL query configuration."""

    query: str = Field(..., description="LogQL query string")
    start: datetime | None = Field(None, description="Query start time")
    end: datetime | None = Field(None, description="Query end time")
    limit: int = Field(1000, description="Maximum number of log entries")
    direction: str = Field(
        "backward", description="Query direction: forward or backward"
    )


class LogEntry(BaseModel):
    """Individual log entry from Loki."""

    timestamp: datetime
    line: str
    labels: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_loki_entry(cls, entry: list) -> LogEntry:
        """Create LogEntry from Loki API response format."""
        # Loki returns [timestamp_ns, log_line]
        timestamp_ns = int(entry[0])
        timestamp = datetime.fromtimestamp(timestamp_ns / 1_000_000_000)
        return cls(timestamp=timestamp, line=entry[1], labels={})


class LogStream(BaseModel):
    """Log stream from Loki query result."""

    stream: dict[str, str] = Field(description="Stream labels")
    values: list[LogEntry] = Field(description="Log entries")

    @classmethod
    def from_loki_stream(cls, stream_data: dict) -> LogStream:
        """Create LogStream from Loki API response."""
        entries = [
            LogEntry.from_loki_entry(entry) for entry in stream_data.get("values", [])
        ]
        return cls(stream=stream_data.get("stream", {}), values=entries)


class LokiQueryResult(BaseModel):
    """Complete Loki query result."""

    result_type: str
    streams: list[LogStream] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)

    def get_all_entries(self) -> list[LogEntry]:
        """Get all log entries across all streams."""
        all_entries = []
        for stream in self.streams:
            for entry in stream.values:
                entry.labels = stream.stream
                all_entries.append(entry)

        # Sort by timestamp
        return sorted(all_entries, key=lambda x: x.timestamp, reverse=True)


class LokiClient:
    """
    Loki REST API client using httpx for log querying.

    Provides methods to query logs using LogQL for SRE incident analysis.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
    ):
        """
        Initialize Loki client with configuration from settings.

        Args:
            base_url: Loki server base URL (overrides config)
            timeout: Request timeout in seconds (overrides config)
        """
        settings = get_settings()

        self.base_url = (base_url or settings.monitoring.loki_url).rstrip("/")
        self.timeout = timeout or settings.monitoring.loki_timeout

        # Setup HTTP client
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()

    async def query_range(self, logql_query: LogQLQuery) -> LokiQueryResult:
        """
        Execute a LogQL range query.

        Args:
            logql_query: LogQL query configuration

        Returns:
            Query result with log entries
        """
        # Set default time range: 1 hour if not provided
        if not logql_query.end:
            logql_query.end = datetime.now()
        if not logql_query.start:
            logql_query.start = logql_query.end - timedelta(hours=1)

        # Convert to RFC3339 format
        start_time = logql_query.start.isoformat() + "Z"
        end_time = logql_query.end.isoformat() + "Z"

        params = {
            "query": logql_query.query,
            "start": start_time,
            "end": end_time,
            "limit": logql_query.limit,
            "direction": logql_query.direction,
        }

        url = f"{self.base_url}/loki/api/v1/query_range"

        logger.info("Executing Loki query", url=url, query=logql_query.query)

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                raise Exception(f"Loki query failed: {data}")

            result_data = data.get("data", {})

            streams = [
                LogStream.from_loki_stream(stream)
                for stream in result_data.get("result", [])
            ]

            return LokiQueryResult(
                result_type=result_data.get("resultType", "streams"),
                streams=streams,
                stats=result_data.get("stats", {}),
            )

        except httpx.RequestError as e:
            logger.error("Loki query request failed", error=str(e))
            raise Exception(f"Failed to query Loki: {e}")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Loki response", error=str(e))
            raise Exception(f"Invalid JSON response from Loki: {e}")

    async def query_instant(
        self, query: str, timestamp: datetime | None = None, limit: int = 1000
    ) -> LokiQueryResult:
        """
        Execute an instant LogQL query.

        Args:
            query: LogQL query string
            timestamp: Query timestamp (default: now)
            limit: Maximum entries to return

        Returns:
            Query result with log entries
        """
        if not timestamp:
            timestamp = datetime.now()

        params = {"query": query, "time": timestamp.isoformat() + "Z", "limit": limit}

        url = f"{self.base_url}/loki/api/v1/query"

        logger.info("Executing Loki instant query", query=query)

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                raise Exception(f"Loki instant query failed: {data}")

            result_data = data.get("data", {})

            streams = [
                LogStream.from_loki_stream(stream)
                for stream in result_data.get("result", [])
            ]

            return LokiQueryResult(
                result_type=result_data.get("resultType", "streams"),
                streams=streams,
                stats=result_data.get("stats", {}),
            )

        except httpx.RequestError as e:
            logger.error("Loki instant query failed", error=str(e))
            raise Exception(f"Failed to query Loki: {e}")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


class LokiTools:
    """
    Loki integration tools for AutoGen agents.

    Provides tool functions that can be used by SRE agents
    for log analysis during incident investigation.
    """

    def __init__(self, loki_client: LokiClient | None = None):
        """
        Initialize Loki tools.

        Args:
            loki_client: Optional Loki client instance
        """
        self._loki_client = loki_client
        self._client_owned = loki_client is None

    async def _get_client(self) -> LokiClient:
        """Get or create Loki client."""
        if self._loki_client is None:
            self._loki_client = LokiClient()
        return self._loki_client

    async def analyze_pod_errors(
        self, namespace: str, pod_name: str, time_window_minutes: int = 30
    ) -> dict[str, Any]:
        """
        Tool: Analyze error logs for a specific pod.

        Args:
            namespace: Kubernetes namespace
            pod_name: Pod name
            time_window_minutes: Time window to analyze

        Returns:
            Analysis result with error patterns
        """
        logger.debug(
            "[TOOL CALL] analyze_pod_errors started",
            namespace=namespace,
            pod_name=pod_name,
            time_window_minutes=time_window_minutes,
        )
        client = await self._get_client()

        query = f'{{namespace="{namespace}", pod="{pod_name}"}} |~ "(?i)(error|exception|failed|panic)"'
        logger.debug("Loki query generated", query=query)

        logql_query = LogQLQuery(
            query=query,
            start=datetime.now() - timedelta(minutes=time_window_minutes),
            end=datetime.now(),
            limit=500,
            direction="backward",
        )

        try:
            async with client:
                result = await client.query_range(logql_query)
                entries = result.get_all_entries()

                # Simple error pattern analysis
                error_patterns = {}
                recent_errors = []

                for entry in entries:
                    line_lower = entry.line.lower()
                    recent_errors.append(
                        {
                            "timestamp": entry.timestamp.isoformat(),
                            "message": entry.line[:200],  # Truncate long messages
                        }
                    )

                    if "error" in line_lower:
                        error_patterns["errors"] = error_patterns.get("errors", 0) + 1
                    if "exception" in line_lower:
                        error_patterns["exceptions"] = (
                            error_patterns.get("exceptions", 0) + 1
                        )
                    if "failed" in line_lower:
                        error_patterns["failures"] = (
                            error_patterns.get("failures", 0) + 1
                        )
                    if "panic" in line_lower:
                        error_patterns["panics"] = error_patterns.get("panics", 0) + 1

                return {
                    "tool": "analyze_pod_errors",
                    "pod": pod_name,
                    "namespace": namespace,
                    "time_window_minutes": time_window_minutes,
                    "total_entries": len(entries),
                    "error_patterns": error_patterns,
                    "recent_errors": recent_errors[:10],  # Latest 10 errors
                    "summary": f"Found {len(entries)} error-related log entries in the last {time_window_minutes} minutes",
                }
        except Exception as e:
            logger.error("Pod error analysis failed", error=str(e), pod=pod_name)
            return {
                "tool": "analyze_pod_errors",
                "error": str(e),
                "pod": pod_name,
                "namespace": namespace,
            }

    async def get_application_logs(
        self,
        app_label: str,
        namespace: str | None = None,
        log_level: str | None = None,
        time_window_minutes: int = 60,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Tool: Get application logs filtered by label and level.

        Args:
            app_label: Application label value
            namespace: Kubernetes namespace (optional)
            log_level: Log level filter (optional)
            time_window_minutes: Time window to query
            limit: Maximum log entries to return

        Returns:
            Application logs with metadata
        """
        client = await self._get_client()

        # Build LogQL query
        label_filters = [f'app="{app_label}"']

        if namespace:
            label_filters.append(f'namespace="{namespace}"')

        query = "{" + ",".join(label_filters) + "}"

        if log_level:
            query += f' | json | level="{log_level.upper()}"'

        logql_query = LogQLQuery(
            query=query,
            start=datetime.now() - timedelta(minutes=time_window_minutes),
            end=datetime.now(),
            limit=limit,
            direction="backward",
        )

        try:
            async with client:
                result = await client.query_range(logql_query)
                entries = result.get_all_entries()

                log_data = []
                for entry in entries:
                    log_data.append(
                        {
                            "timestamp": entry.timestamp.isoformat(),
                            "message": entry.line,
                            "labels": entry.labels,
                        }
                    )

                return {
                    "tool": "get_application_logs",
                    "app_label": app_label,
                    "namespace": namespace,
                    "log_level": log_level,
                    "time_window_minutes": time_window_minutes,
                    "total_entries": len(entries),
                    "logs": log_data,
                    "summary": f"Retrieved {len(entries)} log entries for app '{app_label}'",
                }
        except Exception as e:
            logger.error(
                "Application log retrieval failed", error=str(e), app=app_label
            )
            return {
                "tool": "get_application_logs",
                "error": str(e),
                "app_label": app_label,
                "namespace": namespace,
            }

    async def search_logs_by_pattern(
        self,
        pattern: str,
        namespace: str | None = None,
        time_window_minutes: int = 30,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Tool: Search logs by regex pattern.

        Args:
            pattern: Regex pattern to search for
            namespace: Kubernetes namespace filter (optional)
            time_window_minutes: Time window to search
            limit: Maximum log entries to return

        Returns:
            Matching log entries
        """
        client = await self._get_client()

        # Build LogQL query
        if namespace:
            query = f'{{namespace="{namespace}"}} |~ "{pattern}"'
        else:
            query = f'{{}} |~ "{pattern}"'

        logql_query = LogQLQuery(
            query=query,
            start=datetime.now() - timedelta(minutes=time_window_minutes),
            end=datetime.now(),
            limit=limit,
            direction="backward",
        )

        try:
            async with client:
                result = await client.query_range(logql_query)
                entries = result.get_all_entries()

                matches = []
                for entry in entries:
                    matches.append(
                        {
                            "timestamp": entry.timestamp.isoformat(),
                            "message": entry.line,
                            "labels": entry.labels,
                        }
                    )

                return {
                    "tool": "search_logs_by_pattern",
                    "pattern": pattern,
                    "namespace": namespace,
                    "time_window_minutes": time_window_minutes,
                    "total_matches": len(entries),
                    "matches": matches,
                    "summary": f"Found {len(entries)} log entries matching pattern '{pattern}'",
                }
        except Exception as e:
            logger.error("Log pattern search failed", error=str(e), pattern=pattern)
            return {
                "tool": "search_logs_by_pattern",
                "error": str(e),
                "pattern": pattern,
                "namespace": namespace,
            }

    async def close(self) -> None:
        """Close resources."""
        if self._loki_client and self._client_owned:
            await self._loki_client.close()


# Global Loki tools instance
_loki_tools: LokiTools | None = None


def get_loki_tools() -> list[Callable]:
    """
    Get Loki tools as a list of callable functions for AutoGen agents.

    Returns:
        List of Loki tool functions that can be used by AutoGen agents
    """
    # Create a LokiTools instance
    loki_tools_instance = LokiTools()

    # Return list of methods as callable tools
    return [
        loki_tools_instance.analyze_pod_errors,
        loki_tools_instance.get_application_logs,
        loki_tools_instance.search_logs_by_pattern,
    ]
