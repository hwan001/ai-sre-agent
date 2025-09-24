"""
Improved Prometheus Tools with better query efficiency.

This module provides PrometheusTools that avoid inefficient OR queries
and provide better control over data volume.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
import structlog

from ..config import get_settings

logger = structlog.get_logger()


class PrometheusTools:
    """Prometheus operations toolkit with efficient querying."""

    def __init__(self, prometheus_url: str | None = None):
        """
        Initialize PrometheusTools.

        Args:
            prometheus_url: Prometheus server URL. If None, will get from settings.
        """
        self.settings = get_settings()
        self.prometheus_url = prometheus_url or getattr(
            self.settings, "prometheus_url", "http://localhost:9090"
        )
        self.client = httpx.Client(timeout=30.0)
        logger.info("Prometheus tools initialized", url=self.prometheus_url)

    def _format_datetime(self, dt: datetime) -> str:
        """Convert datetime to Prometheus timestamp format (Unix timestamp)."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return str(int(dt.timestamp()))

    def _parse_datetime_input(self, dt_input: str | datetime | int | float) -> datetime:
        """Parse various datetime input formats to datetime object."""
        if isinstance(dt_input, datetime):
            return dt_input
        elif isinstance(dt_input, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(dt_input.replace("Z", "+00:00"))
            except ValueError:
                # Try other common formats
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%H:%M:%S"]:
                    try:
                        parsed = datetime.strptime(dt_input, fmt)
                        if parsed.date() == datetime.now().date() and fmt == "%H:%M:%S":
                            # If only time is provided, use today's date
                            now = datetime.now()
                            parsed = parsed.replace(
                                year=now.year, month=now.month, day=now.day
                            )
                        return parsed.replace(tzinfo=UTC)
                    except ValueError:
                        continue
                raise ValueError(f"Unable to parse datetime: {dt_input}") from None
        elif isinstance(dt_input, (int, float)):
            return datetime.fromtimestamp(dt_input, tz=UTC)
        else:
            raise TypeError(f"Unsupported datetime type: {type(dt_input)}")

    async def query_multiple_metrics(
        self,
        metric_names: Annotated[
            list[str], "List of specific metric names to query efficiently"
        ],
        start_time: Annotated[
            str | datetime | int | float | None, "Start time for the query. Optional."
        ] = None,
        end_time: Annotated[
            str | datetime | int | float | None, "End time for the query. Optional."
        ] = None,
        hostname: Annotated[str | None, "Hostname to filter metrics. Optional."] = None,
        limit_per_metric: Annotated[
            int, "Maximum number of time series per metric (default: 50)"
        ] = 50,
        step: Annotated[str, "Query resolution step. Default: '1m'"] = "1m",
    ) -> dict[str, Any]:
        """
        Query multiple specific metrics efficiently (avoids OR queries).

        This executes separate queries for each metric, which is more efficient
        than using OR operators in PromQL.
        """
        try:
            results = {
                "status": "success",
                "query_info": {
                    "hostname_filter": hostname,
                    "metrics_requested": len(metric_names),
                    "limit_per_metric": limit_per_metric,
                },
                "metrics_by_name": {},
            }

            # Determine query endpoint based on time range
            endpoint_base = f"{self.prometheus_url}/api/v1/query"
            if start_time is not None or end_time is not None:
                endpoint_base = f"{self.prometheus_url}/api/v1/query_range"

            for metric_name in metric_names:
                try:
                    # Build query for this specific metric
                    if hostname:
                        query = f'{metric_name}{{instance=~".*{hostname}.*"}}'
                    else:
                        query = metric_name

                    # Prepare query parameters
                    params = {"query": query}

                    if start_time is not None or end_time is not None:
                        if start_time:
                            start_dt = self._parse_datetime_input(start_time)
                            params["start"] = self._format_datetime(start_dt)
                        else:
                            # Default to 1 hour ago
                            start_dt = datetime.now(UTC) - timedelta(hours=1)
                            params["start"] = self._format_datetime(start_dt)

                        if end_time:
                            end_dt = self._parse_datetime_input(end_time)
                            params["end"] = self._format_datetime(end_dt)
                        else:
                            # Default to now
                            end_dt = datetime.now(UTC)
                            params["end"] = self._format_datetime(end_dt)

                        params["step"] = step

                    logger.debug(
                        "Executing metric query",
                        metric_name=metric_name,
                        hostname=hostname,
                    )

                    # Execute the query
                    response = self.client.get(endpoint_base, params=params)
                    response.raise_for_status()

                    result = response.json()

                    if result.get("status") == "success":
                        data = result.get("data", {})
                        result_type = data.get("resultType")
                        query_results = data.get("result", [])

                        # Apply limit to prevent overwhelming response
                        limited = len(query_results) > limit_per_metric
                        if limited:
                            query_results = query_results[:limit_per_metric]

                        # Format results
                        formatted_results = []
                        for metric in query_results:
                            metric_info = {
                                "metric": metric.get("metric", {}),
                                "values": [],
                            }

                            if result_type == "vector":
                                value = metric.get("value")
                                if value:
                                    metric_info["values"] = [
                                        {"timestamp": value[0], "value": value[1]}
                                    ]
                            elif result_type == "matrix":
                                values = metric.get("values", [])
                                metric_info["values"] = [
                                    {"timestamp": ts, "value": val}
                                    for ts, val in values
                                ]

                            formatted_results.append(metric_info)

                        results["metrics_by_name"][metric_name] = {
                            "query": query,
                            "result_type": result_type,
                            "series_count": len(formatted_results),
                            "limited": limited,
                            "original_count": len(data.get("result", [])),
                            "metrics": formatted_results,
                        }

                    else:
                        error_msg = result.get("error", "Unknown error")
                        results["metrics_by_name"][metric_name] = {
                            "query": query,
                            "error": error_msg,
                        }

                except Exception as e:
                    logger.error(
                        "Error querying metric", metric_name=metric_name, error=str(e)
                    )
                    results["metrics_by_name"][metric_name] = {
                        "query": query if "query" in locals() else metric_name,
                        "error": str(e),
                    }

            # Add summary
            successful = len(
                [v for v in results["metrics_by_name"].values() if "error" not in v]
            )
            failed = len(
                [v for v in results["metrics_by_name"].values() if "error" in v]
            )
            total_series = sum(
                v.get("series_count", 0)
                for v in results["metrics_by_name"].values()
                if "series_count" in v
            )

            results["query_info"].update(
                {
                    "successful_metrics": successful,
                    "failed_metrics": failed,
                    "total_series": total_series,
                }
            )

            logger.info(
                "Multiple metrics query completed",
                successful=successful,
                failed=failed,
                total_series=total_series,
            )

            return results

        except Exception as e:
            logger.error("Failed to query multiple metrics", error=str(e))
            return {"status": "error", "error": str(e), "metrics_by_name": {}}

    async def query_essential_metrics(
        self,
        hostname: Annotated[str | None, "Hostname filter. Optional."] = None,
        start_time: Annotated[
            str | datetime | int | float | None, "Start time. Optional."
        ] = None,
        end_time: Annotated[
            str | datetime | int | float | None, "End time. Optional."
        ] = None,
        step: str = "1m",
    ) -> dict[str, Any]:
        """
        Query essential system metrics with calculated values.

        Returns CPU usage percentage, memory usage percentage, disk usage percentage,
        and system availability - all as calculated metrics rather than raw values.
        """
        try:
            # Define essential calculated metrics
            if hostname:
                essential_queries = {
                    "system_up": f'up{{instance=~".*{hostname}.*"}}',
                    "cpu_usage_percent": f'100 - (avg by (instance) (rate(node_cpu_seconds_total{{mode="idle",instance=~".*{hostname}.*"}}[5m])) * 100)',
                    "memory_usage_percent": f'(1 - (node_memory_MemAvailable_bytes{{instance=~".*{hostname}.*"}} / node_memory_MemTotal_bytes{{instance=~".*{hostname}.*"}})) * 100',
                    "disk_usage_percent": f'(1 - (node_filesystem_free_bytes{{instance=~".*{hostname}.*",fstype!="tmpfs",fstype!="overlay"}} / node_filesystem_size_bytes{{instance=~".*{hostname}.*",fstype!="tmpfs",fstype!="overlay"}})) * 100',
                    "load_average": f'node_load1{{instance=~".*{hostname}.*"}}',
                }
            else:
                essential_queries = {
                    "system_up": 'up{job="node-exporter"}',
                    "cpu_usage_percent": '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
                    "memory_usage_percent": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
                    "disk_usage_percent": '(1 - (node_filesystem_free_bytes{fstype!="tmpfs",fstype!="overlay"} / node_filesystem_size_bytes{fstype!="tmpfs",fstype!="overlay"})) * 100',
                    "load_average": "node_load1",
                }

            results = {
                "status": "success",
                "query_info": {
                    "hostname_filter": hostname,
                    "essential_metrics_count": len(essential_queries),
                    "description": "Essential system metrics with calculated percentages",
                },
                "essential_metrics": {},
            }

            # Determine endpoint
            endpoint_base = f"{self.prometheus_url}/api/v1/query"
            if start_time is not None or end_time is not None:
                endpoint_base = f"{self.prometheus_url}/api/v1/query_range"

            for metric_name, query in essential_queries.items():
                try:
                    # Prepare query parameters
                    params = {"query": query}

                    if start_time is not None or end_time is not None:
                        if start_time:
                            start_dt = self._parse_datetime_input(start_time)
                            params["start"] = self._format_datetime(start_dt)
                        else:
                            start_dt = datetime.now(UTC) - timedelta(hours=1)
                            params["start"] = self._format_datetime(start_dt)

                        if end_time:
                            end_dt = self._parse_datetime_input(end_time)
                            params["end"] = self._format_datetime(end_dt)
                        else:
                            end_dt = datetime.now(UTC)
                            params["end"] = self._format_datetime(end_dt)

                        params["step"] = step

                    # Execute query
                    response = self.client.get(endpoint_base, params=params)
                    response.raise_for_status()

                    result = response.json()

                    if result.get("status") == "success":
                        data = result.get("data", {})
                        query_results = data.get("result", [])

                        # Keep only top 10 results to avoid overwhelming response
                        if len(query_results) > 10:
                            query_results = query_results[:10]

                        formatted_results = []
                        for metric in query_results:
                            metric_info = {
                                "metric": metric.get("metric", {}),
                                "values": [],
                            }

                            if data.get("resultType") == "vector":
                                value = metric.get("value")
                                if value:
                                    metric_info["values"] = [
                                        {"timestamp": value[0], "value": value[1]}
                                    ]
                            elif data.get("resultType") == "matrix":
                                values = metric.get("values", [])
                                metric_info["values"] = [
                                    {"timestamp": ts, "value": val}
                                    for ts, val in values
                                ]

                            formatted_results.append(metric_info)

                        results["essential_metrics"][metric_name] = {
                            "query": query,
                            "series_count": len(formatted_results),
                            "metrics": formatted_results,
                        }
                    else:
                        results["essential_metrics"][metric_name] = {
                            "query": query,
                            "error": result.get("error", "Unknown error"),
                        }

                except Exception as e:
                    logger.error(
                        "Error querying essential metric",
                        metric_name=metric_name,
                        error=str(e),
                    )
                    results["essential_metrics"][metric_name] = {
                        "query": query,
                        "error": str(e),
                    }

            successful = len(
                [v for v in results["essential_metrics"].values() if "error" not in v]
            )
            failed = len(
                [v for v in results["essential_metrics"].values() if "error" in v]
            )

            results["query_info"]["successful"] = successful
            results["query_info"]["failed"] = failed

            logger.info(
                "Essential metrics query completed",
                successful=successful,
                failed=failed,
            )

            return results

        except Exception as e:
            logger.error("Failed to query essential metrics", error=str(e))
            return {"status": "error", "error": str(e)}

    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, "client"):
            self.client.close()
