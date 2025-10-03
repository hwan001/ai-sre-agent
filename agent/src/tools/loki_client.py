"""
Loki Log Query Client

Official Loki HTTP API implementation for log querying and analysis.
Based on Grafana Loki API documentation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog

from configs.config import get_settings

logger = structlog.get_logger()


class LokiClient:
    """
    Loki HTTP API client for querying logs.

    Implements official Loki API endpoints:
    - GET /loki/api/v1/query_range: Query logs within a range of time
    - GET /loki/api/v1/query: Query logs at a single point in time
    - GET /loki/api/v1/labels: Get available labels
    - GET /loki/api/v1/label/<name>/values: Get label values
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
    ):
        """
        Initialize Loki client.

        Args:
            base_url: Loki server base URL (default: from config)
            timeout: Request timeout in seconds (default: from config)
        """
        settings = get_settings()

        self.base_url = (base_url or settings.monitoring.loki_url).rstrip("/")
        self.timeout = timeout or settings.monitoring.loki_timeout

        self.client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))

        logger.info(
            "Loki client initialized",
            base_url=self.base_url,
            timeout=self.timeout,
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()

    async def query_range(
        self,
        query: str,
        start: datetime | str | int,
        end: datetime | str | int,
        limit: int = 100,
        direction: str = "backward",
    ) -> dict[str, Any]:
        """
        Query logs within a range of time.

        Official endpoint: GET /loki/api/v1/query_range

        Args:
            query: LogQL query string (REQUIRED)
            start: Start time as datetime, RFC3339 string, or Unix timestamp (REQUIRED)
            end: End time as datetime, RFC3339 string, or Unix timestamp (REQUIRED)
            limit: Max number of entries to return (default: 100)
            direction: Sort order - "forward" or "backward" (default: "backward")

        Returns:
            API response with status, data (resultType, result), and stats
        """
        # Convert timestamps to nanosecond Unix epoch
        start_ns = self._to_nanosecond_timestamp(start)
        end_ns = self._to_nanosecond_timestamp(end)

        params = {
            "query": query,
            "start": start_ns,
            "end": end_ns,
            "limit": limit,
            "direction": direction,
        }

        url = f"{self.base_url}/loki/api/v1/query_range"

        logger.info(
            "Executing Loki query_range",
            query=query,
            start=start_ns,
            end=end_ns,
            limit=limit,
            direction=direction,
        )

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                error_msg = f"Loki query failed: {data}"
                logger.error("Loki query failed", response=data)
                raise Exception(error_msg)

            logger.info(
                "Loki query successful",
                result_type=data.get("data", {}).get("resultType"),
                result_count=len(data.get("data", {}).get("result", [])),
            )

            return data

        except httpx.RequestError as e:
            logger.error("Loki query request failed", error=str(e), url=url)
            raise Exception(f"Failed to query Loki: {e}")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Loki response", error=str(e))
            raise Exception(f"Invalid JSON response from Loki: {e}")

    async def query_instant(
        self,
        query: str,
        time: datetime | str | int | None = None,
        limit: int = 100,
        direction: str = "backward",
    ) -> dict[str, Any]:
        """
        Query logs at a single point in time (instant query).

        Official endpoint: GET /loki/api/v1/query

        Args:
            query: LogQL query string (REQUIRED)
            time: Query time as datetime, RFC3339 string, or Unix timestamp (default: now)
            limit: Max number of entries to return (default: 100)
            direction: Sort order - "forward" or "backward" (default: "backward")

        Returns:
            API response with status, data (resultType, result), and stats
        """
        # Default to now if time not provided
        if time is None:
            time = datetime.now(UTC)

        time_ns = self._to_nanosecond_timestamp(time)

        params = {
            "query": query,
            "time": time_ns,
            "limit": limit,
            "direction": direction,
        }

        url = f"{self.base_url}/loki/api/v1/query"

        logger.info(
            "Executing Loki instant query",
            query=query,
            time=time_ns,
            limit=limit,
            direction=direction,
        )

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                error_msg = f"Loki instant query failed: {data}"
                logger.error("Loki instant query failed", response=data)
                raise Exception(error_msg)

            logger.info(
                "Loki instant query successful",
                result_type=data.get("data", {}).get("resultType"),
                result_count=len(data.get("data", {}).get("result", [])),
            )

            return data

        except httpx.RequestError as e:
            logger.error("Loki instant query failed", error=str(e), url=url)
            raise Exception(f"Failed to query Loki: {e}")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Loki response", error=str(e))
            raise Exception(f"Invalid JSON response from Loki: {e}")

    def _to_nanosecond_timestamp(self, time_value: datetime | str | int) -> str:
        """
        Convert various time formats to nanosecond Unix epoch string.

        Args:
            time_value: Time as datetime, RFC3339 string, or Unix timestamp

        Returns:
            Nanosecond Unix epoch as string
        """
        if isinstance(time_value, datetime):
            # Ensure UTC timezone
            if time_value.tzinfo is None:
                time_value = time_value.replace(tzinfo=UTC)
            return str(int(time_value.timestamp() * 1_000_000_000))

        elif isinstance(time_value, str):
            # Try parsing as RFC3339
            try:
                dt = datetime.fromisoformat(time_value.replace("Z", "+00:00"))
                return str(int(dt.timestamp() * 1_000_000_000))
            except ValueError:
                # Assume it's already a nanosecond timestamp string
                return time_value

        elif isinstance(time_value, int):
            # If it looks like seconds (< year 3000), convert to nanoseconds
            if time_value < 32503680000:
                return str(time_value * 1_000_000_000)
            # Otherwise assume it's already nanoseconds
            return str(time_value)

        else:
            raise ValueError(f"Unsupported time format: {type(time_value)}")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("Loki client closed")


class LokiTools:
    """
    High-level Loki tools for AutoGen agents.

    Provides simplified, agent-friendly methods for common log analysis tasks.
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

    async def search_logs(
        self,
        query: str,
        time_minutes: int = 30,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Search logs using LogQL query.

        This is the primary tool for searching logs. Use LogQL syntax.

        Args:
            query: LogQL query (e.g., '{namespace="default"}')
            time_minutes: How many minutes back to search (default: 30)
            limit: Maximum log entries to return (default: 100)

        Returns:
            Dictionary with logs and summary

        Example:
            search_logs(query='{namespace="default"} |= "error"')
        """
        logger.info(
            "[TOOL CALL] search_logs",
            query=query,
            time_minutes=time_minutes,
            limit=limit,
        )

        client = await self._get_client()

        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(minutes=time_minutes)

        try:
            result = await client.query_range(
                query=query,
                start=start_time,
                end=end_time,
                limit=limit,
                direction="backward",
            )

            # Parse response
            data = result.get("data", {})
            streams = data.get("result", [])

            # Extract log entries
            entries = []
            total_entries = 0

            for stream in streams:
                stream_labels = stream.get("stream", {})
                values = stream.get("values", [])
                total_entries += len(values)

                for value in values:
                    # value is [timestamp_ns, log_line]
                    timestamp_ns = int(value[0])
                    log_line = value[1]

                    # Convert nanoseconds to datetime
                    timestamp = datetime.fromtimestamp(
                        timestamp_ns / 1_000_000_000, tz=UTC
                    )

                    entries.append(
                        {
                            "timestamp": timestamp.isoformat(),
                            "labels": stream_labels,
                            "message": log_line,
                        }
                    )

            # Sort by timestamp (most recent first)
            entries.sort(key=lambda x: x["timestamp"], reverse=True)

            # 🔥 OPTIMIZATION: Don't return all logs to LLM
            # Instead, return statistics + samples only

            # Group by labels for analysis
            log_by_pod = {}
            log_by_namespace = {}
            error_patterns = {}

            for entry in entries:
                labels = entry["labels"]
                pod_name = labels.get("pod", labels.get("pod_name", "unknown"))
                namespace = labels.get("namespace", "unknown")
                message = entry["message"].lower()

                # Count by pod
                log_by_pod[pod_name] = log_by_pod.get(pod_name, 0) + 1

                # Count by namespace
                log_by_namespace[namespace] = log_by_namespace.get(namespace, 0) + 1

                # Detect error patterns
                for pattern in [
                    "error",
                    "exception",
                    "failed",
                    "panic",
                    "fatal",
                    "warning",
                ]:
                    if pattern in message:
                        error_patterns[pattern] = error_patterns.get(pattern, 0) + 1

            # Get top samples (최대 10개만)
            sample_entries = entries[:10]

            summary_msg = (
                f"Found {total_entries} log entries across {len(streams)} "
                f"streams in the last {time_minutes} minutes"
            )

            return {
                "tool": "search_logs",
                "query": query,
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "minutes": time_minutes,
                },
                "statistics": {
                    "total_streams": len(streams),
                    "total_entries": total_entries,
                    "by_pod": dict(
                        sorted(log_by_pod.items(), key=lambda x: x[1], reverse=True)[
                            :10
                        ]
                    ),
                    "by_namespace": dict(
                        sorted(
                            log_by_namespace.items(), key=lambda x: x[1], reverse=True
                        )
                    ),
                    "error_patterns": dict(
                        sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)
                    ),
                },
                "samples": sample_entries,  # Only 10 samples instead of all logs
                "summary": summary_msg,
                "note": f"Showing {len(sample_entries)} samples out of {total_entries} total entries. Use statistics for analysis.",
            }

        except Exception as e:
            logger.error("search_logs failed", error=str(e), query=query)
            return {
                "tool": "search_logs",
                "error": str(e),
                "query": query,
                "summary": f"Failed to search logs: {str(e)}",
            }

    async def get_error_logs(
        self,
        namespace: str | None = None,
        pod: str | None = None,
        app: str | None = None,
        time_minutes: int = 30,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Get error logs from pods/apps.

        Searches for: error, exception, failed, panic, fatal.

        Args:
            namespace: Kubernetes namespace (optional)
            pod: Pod name or pattern (optional)
            app: App label value (optional)
            time_minutes: How many minutes back (default: 30)
            limit: Maximum log entries (default: 50)

        Returns:
            Dictionary with error logs and analysis

        Example:
            get_error_logs(namespace="observability")
        """
        logger.info(
            "[TOOL CALL] get_error_logs",
            namespace=namespace,
            pod=pod,
            app=app,
            time_minutes=time_minutes,
        )

        # Build LogQL query
        label_filters = []

        if namespace:
            label_filters.append(f'namespace="{namespace}"')
        if pod:
            label_filters.append(f'pod=~"{pod}.*"')
        if app:
            label_filters.append(f'app="{app}"')

        # If no filters, query all logs
        if label_filters:
            query = "{" + ",".join(label_filters) + "}"
        else:
            query = "{}"

        # Add regex filter for error patterns (case-insensitive)
        query += ' |~ "(?i)(error|exception|failed|panic|fatal)"'

        # Use search_logs tool
        result = await self.search_logs(
            query=query,
            time_minutes=time_minutes,
            limit=limit,
        )

        # Add error pattern analysis
        if "entries" in result and not result.get("error"):
            error_types = {
                "error": 0,
                "exception": 0,
                "failed": 0,
                "panic": 0,
                "fatal": 0,
            }

            # Group by pod for better analysis
            pod_errors = {}

            for entry in result["entries"]:
                message_lower = entry["message"].lower()

                # Count error types
                for error_type in error_types:
                    if error_type in message_lower:
                        error_types[error_type] += 1

                # Group by pod
                pod_name = entry.get("labels", {}).get("pod", "unknown")
                if pod_name not in pod_errors:
                    pod_errors[pod_name] = {
                        "count": 0,
                        "sample_messages": [],
                        "labels": entry.get("labels", {}),
                    }

                pod_errors[pod_name]["count"] += 1

                # Store sample messages (up to 3 per pod)
                if len(pod_errors[pod_name]["sample_messages"]) < 3:
                    pod_errors[pod_name]["sample_messages"].append(
                        {
                            "timestamp": entry["timestamp"],
                            "message": entry["message"],
                        }
                    )

            result["error_patterns"] = error_types
            result["pod_breakdown"] = pod_errors
            result["tool"] = "get_error_logs"

        return result

    async def get_pod_logs(
        self,
        namespace: str,
        pod: str,
        time_minutes: int = 30,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Get logs from a specific pod.

        Args:
            namespace: Kubernetes namespace (REQUIRED)
            pod: Pod name or pattern (REQUIRED)
            time_minutes: How many minutes back (default: 30)
            limit: Maximum log entries (default: 100)

        Returns:
            Dictionary with pod logs

        Example:
            get_pod_logs(namespace="default", pod="nginx-abc123")
        """
        logger.info(
            "[TOOL CALL] get_pod_logs",
            namespace=namespace,
            pod=pod,
            time_minutes=time_minutes,
        )

        # Build LogQL query for specific pod
        query = f'{{namespace="{namespace}", pod=~"{pod}.*"}}'

        result = await self.search_logs(
            query=query,
            time_minutes=time_minutes,
            limit=limit,
        )

        if not result.get("error"):
            result["tool"] = "get_pod_logs"
            result["pod"] = pod
            result["namespace"] = namespace

        return result

    async def close(self) -> None:
        """Close resources."""
        if self._loki_client and self._client_owned:
            await self._loki_client.close()


def get_loki_tools() -> list:
    """
    Get Loki tools for AutoGen agents.

    Returns:
        List of Loki tool functions
    """
    loki_tools_instance = LokiTools()

    return [
        loki_tools_instance.search_logs,
        loki_tools_instance.get_error_logs,
        loki_tools_instance.get_pod_logs,
    ]
