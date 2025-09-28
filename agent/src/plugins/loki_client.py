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
        mock: bool = False,
    ):
        """
        Initialize Loki client with configuration from settings.

        Args:
            base_url: Loki server base URL (overrides config)
            timeout: Request timeout in seconds (overrides config)
            username: Basic auth username (overrides config)
            password: Basic auth password (overrides config)
        """
        settings = get_settings()

        self.base_url = (base_url or settings.monitoring.loki_url).rstrip("/")
        self.timeout = timeout or settings.monitoring.loki_timeout or 30
        self.mock = mock

        # Setup HTTP client

        if not self.mock:
            self.client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
        else:
            self.client = None
            logger.info("Loki client initialized in mock mode")

    def _generate_mock_query_result(
        self, query: str, time_window_minutes: int = 30
    ) -> LokiQueryResult:
        """Generate mock query result for testing."""
        # Create mock log entries
        mock_entries = [
            LogEntry(
                timestamp=datetime.now() - timedelta(minutes=i),
                line=f"[ERROR] Mock log entry {i}: {query} - Database connection failed",
                labels={
                    "namespace": "production",
                    "pod": "app-pod",
                    "container": "main",
                },
            )
            for i in range(1, 6)
        ]

        mock_stream = LogStream(
            stream={"namespace": "production", "pod": "app-pod"}, values=mock_entries
        )

        return LokiQueryResult(
            result_type="streams",
            streams=[mock_stream],
            stats={"summary": {"bytesTotal": 1024, "linesTotal": len(mock_entries)}},
        )

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

    def __init__(self, loki_client: LokiClient | None = None, mock: bool = False):
        """
        Initialize Loki tools.

        Args:
            loki_client: Optional Loki client instance
            mock: Use mock mode for testing
        """
        self._loki_client = loki_client
        self._client_owned = loki_client is None
        self._mock = mock

    async def _get_client(self) -> LokiClient:
        """Get or create Loki client."""
        if self._loki_client is None:
            self._loki_client = LokiClient(mock=self._mock)
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
        if self._mock:
            return {
                "tool": "analyze_pod_errors",
                "pod": pod_name,
                "namespace": namespace,
                "time_window_minutes": time_window_minutes,
                "total_entries": 15,
                "error_patterns": {"errors": 8, "exceptions": 4, "failures": 3},
                "recent_errors": [
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=5)
                        ).isoformat(),
                        "message": "java.lang.OutOfMemoryError: Java heap space",
                    },
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=10)
                        ).isoformat(),
                        "message": "ERROR: Database connection failed",
                    },
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=15)
                        ).isoformat(),
                        "message": "WARN: High CPU usage detected (85%)",
                    },
                ],
                "summary": f"Found 15 error-related log entries in the last {time_window_minutes} minutes",
                "recommendation": "Pod appears to be experiencing memory pressure and database connectivity issues",
                "mock_data": True,
            }

        client = await self._get_client()

        query = f'{{namespace="{namespace}", pod="{pod_name}"}} |~ "(?i)(error|exception|failed|panic)"'

        logql_query = LogQLQuery(
            query=query,
            start=datetime.now() - timedelta(minutes=time_window_minutes),
            limit=500,
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
        if self._mock:
            return {
                "tool": "get_application_logs",
                "app_label": app_label,
                "namespace": namespace,
                "log_level": log_level,
                "time_window_minutes": time_window_minutes,
                "total_entries": 45,
                "logs": [
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=5)
                        ).isoformat(),
                        "message": "[INFO] Application startup completed in 2.3 seconds",
                        "labels": {
                            "app": app_label,
                            "namespace": namespace or "default",
                        },
                    },
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=10)
                        ).isoformat(),
                        "message": "[ERROR] Failed to connect to database: connection timeout",
                        "labels": {
                            "app": app_label,
                            "namespace": namespace or "default",
                        },
                    },
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=15)
                        ).isoformat(),
                        "message": "[WARN] Memory usage above 80% threshold",
                        "labels": {
                            "app": app_label,
                            "namespace": namespace or "default",
                        },
                    },
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=20)
                        ).isoformat(),
                        "message": "[INFO] Processing request for user ID: 12345",
                        "labels": {
                            "app": app_label,
                            "namespace": namespace or "default",
                        },
                    },
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=25)
                        ).isoformat(),
                        "message": "[DEBUG] Cache hit for key: user_session_abc123",
                        "labels": {
                            "app": app_label,
                            "namespace": namespace or "default",
                        },
                    },
                ],
                "summary": f"Retrieved 45 log entries for app '{app_label}' showing normal operations with some database connectivity issues",
                "mock_data": True,
            }
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
            limit=limit,
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
        if self._mock:
            return {
                "tool": "search_logs_by_pattern",
                "pattern": pattern,
                "namespace": namespace,
                "time_window_minutes": time_window_minutes,
                "total_matches": 12,
                "matches": [
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=2)
                        ).isoformat(),
                        "message": f"[ERROR] {pattern} detected in payment processing module",
                        "labels": {
                            "namespace": namespace or "default",
                            "service": "payment",
                        },
                    },
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=5)
                        ).isoformat(),
                        "message": f"[WARN] Potential {pattern} in user authentication service",
                        "labels": {
                            "namespace": namespace or "default",
                            "service": "auth",
                        },
                    },
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=8)
                        ).isoformat(),
                        "message": f"[ERROR] Critical {pattern} in database connection pool",
                        "labels": {
                            "namespace": namespace or "default",
                            "service": "database",
                        },
                    },
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=12)
                        ).isoformat(),
                        "message": f"[INFO] {pattern} resolved through automatic retry mechanism",
                        "labels": {
                            "namespace": namespace or "default",
                            "service": "retry",
                        },
                    },
                    {
                        "timestamp": (
                            datetime.now() - timedelta(minutes=15)
                        ).isoformat(),
                        "message": f"[DEBUG] Monitoring {pattern} patterns in system metrics",
                        "labels": {
                            "namespace": namespace or "default",
                            "service": "monitoring",
                        },
                    },
                ],
                "summary": f"Found 12 log entries matching pattern '{pattern}' with 3 critical errors requiring attention",
                "analysis": "Pattern indicates potential systemic issue affecting multiple components",
                "mock_data": True,
            }
        client = await self._get_client()

        # Build LogQL query
        if namespace:
            query = f'{{namespace="{namespace}"}} |~ "{pattern}"'
        else:
            query = f'{{}} |~ "{pattern}"'

        logql_query = LogQLQuery(
            query=query,
            start=datetime.now() - timedelta(minutes=time_window_minutes),
            limit=limit,
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


def get_loki_tools(mock: bool = False) -> list[Callable]:
    """
    Get Loki tools as a list of callable functions for AutoGen agents.

    Args:
        mock: Use mock mode for testing

    Returns:
        List of Loki tool functions that can be used by AutoGen agents
    """
    # Create a LokiTools instance
    loki_tools_instance = LokiTools(mock=mock)

    # Return list of methods as callable tools
    return [
        loki_tools_instance.analyze_pod_errors,
        loki_tools_instance.get_application_logs,
        loki_tools_instance.search_logs_by_pattern,
    ]
