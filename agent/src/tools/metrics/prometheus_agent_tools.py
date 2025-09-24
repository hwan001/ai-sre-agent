"""
AutoGen Agent Integration for PrometheusTools.

This module provides helper functions to integrate PrometheusTools
with AutoGen Assistant Agents.
"""

import asyncio
from datetime import datetime
from typing import Any

from .prometheus import PrometheusTools

# Global instance for reuse across agent calls
_prometheus_tools_instance: PrometheusTools | None = None


def get_prometheus_tools(prometheus_url: str | None = None) -> PrometheusTools:
    """Get or create an PrometheusTools instance."""
    global _prometheus_tools_instance
    if _prometheus_tools_instance is None:
        _prometheus_tools_instance = PrometheusTools(prometheus_url)
    return _prometheus_tools_instance


# AutoGen agent tool functions
def prometheus_query_specific_metrics(
    metric_names: list[str],
    start_time: str | datetime | int | float | None = None,
    end_time: str | datetime | int | float | None = None,
    hostname: str | None = None,
    limit_per_metric: int = 50,
    step: str = "1m",
    prometheus_url: str | None = None,
) -> dict[str, Any]:
    """
    Query specific Prometheus metrics efficiently.

    This function executes separate queries for each metric, avoiding inefficient
    OR queries and providing better control over data volume.

    Args:
        metric_names: List of metric names to query (e.g., ['up', 'node_load1'])
        start_time: Start time. Optional.
        end_time: End time. Optional.
        hostname: Hostname filter. Optional.
        limit_per_metric: Max time series per metric (default: 50)
        step: Query resolution step (default: '1m')
        prometheus_url: Prometheus server URL. Optional.

    Returns:
        Dictionary with metrics organized by name, avoiding data overload.
    """
    tools = get_prometheus_tools(prometheus_url)
    return asyncio.run(
        tools.query_multiple_metrics(
            metric_names, start_time, end_time, hostname, limit_per_metric, step
        )
    )


def prometheus_get_essential_metrics(
    hostname: str | None = None,
    start_time: str | datetime | int | float | None = None,
    end_time: str | datetime | int | float | None = None,
    step: str = "1m",
    prometheus_url: str | None = None,
) -> dict[str, Any]:
    """
    Get essential system metrics with calculated percentages.

    Returns CPU usage %, memory usage %, disk usage %, system availability,
    and load averages - all pre-calculated and limited in volume.

    Args:
        hostname: Hostname filter. Optional.
        start_time: Start time. Optional.
        end_time: End time. Optional.
        step: Query resolution step (default: '1m')
        prometheus_url: Prometheus server URL. Optional.

    Returns:
        Dictionary with essential calculated metrics, limited data volume.
    """
    tools = get_prometheus_tools(prometheus_url)
    return asyncio.run(
        tools.query_essential_metrics(hostname, start_time, end_time, step)
    )


def prometheus_get_metric_names(
    hostname: str | None = None, prometheus_url: str | None = None
) -> dict[str, Any]:
    """
    Get list of available metric names from Prometheus.

    Note: This is a placeholder implementation. The original metric names
    functionality was removed with the deprecated PrometheusTools class.

    Args:
        hostname: Filter metrics by hostname pattern. Optional.
        prometheus_url: Prometheus server URL. Optional.

    Returns:
        Dictionary containing placeholder response.
    """
    return {
        "status": "success",
        "total_metrics": 0,
        "hostname_filter": hostname,
        "metrics": [],
        "note": (
            "Metric names listing not implemented in enhanced version. "
            "Use specific metric names instead."
        ),
    }


def prometheus_get_targets(prometheus_url: str | None = None) -> dict[str, Any]:
    """
    Get information about Prometheus targets (scraped endpoints).

    Note: This is a placeholder implementation. The original targets
    functionality was removed with the deprecated PrometheusTools class.

    Args:
        prometheus_url: Prometheus server URL. Optional.

    Returns:
        Dictionary containing placeholder response.
    """
    return {
        "status": "success",
        "summary": {
            "active_targets": 0,
            "dropped_targets": 0,
            "healthy_targets": 0,
            "unhealthy_targets": 0,
        },
        "active_targets": [],
        "note": (
            "Targets listing not implemented in enhanced version. "
            "Focus on specific metrics instead."
        ),
    }


# Tool registration helper for AutoGen agents
def get_prometheus_tools_for_agent() -> list:
    """
    Get recommended Prometheus tools for AutoGen agents.

    Returns enhanced tools that avoid data overload and inefficient queries.

    Returns:
        List of recommended tool functions for AutoGen agent registration.
    """
    return [
        prometheus_query_specific_metrics,
        prometheus_get_essential_metrics,
        # Note: get_metric_names and get_targets return placeholder responses
        prometheus_get_metric_names,
        prometheus_get_targets,
    ]


# Example usage documentation
PROMETHEUS_TOOLS_USAGE_EXAMPLES = """
 Prometheus Tools Usage Examples for AutoGen Agents
===========================================================

RECOMMENDED: Use efficient enhanced tools for better performance

1. Query specific metrics efficiently:
   prometheus_query_specific_metrics(
       metric_names=['up', 'node_load1', 'node_memory_MemAvailable_bytes'],
       hostname="web-server-01",
       limit_per_metric=50
   )

2. Get essential system metrics with calculated values:
   prometheus_get_essential_metrics(hostname="database-01")

3. Query metrics with time range:
   prometheus_query_specific_metrics(
       metric_names=['node_cpu_seconds_total'],
       start_time="2024-01-01 10:00:00",
       end_time="2024-01-01 11:00:00",
       step="5m"
   )

4. Use with custom Prometheus URL:
   prometheus_query_specific_metrics(
       metric_names=['up'],
       prometheus_url="http://monitoring.example.com:9090"
   )

Response Format:
All functions return a dictionary with:
- status: "success" or "error"
- For success: query_info, metrics data organized by metric name
- For error: error message and context

Benefits of  Tools:
- Individual queries per metric (no inefficient OR queries)
- Configurable data limits (limit_per_metric parameter)
- Pre-calculated percentages for system monitoring
- Better error handling per metric
- Reduced Prometheus server load
"""


if __name__ == "__main__":
    print(PROMETHEUS_TOOLS_USAGE_EXAMPLES)
