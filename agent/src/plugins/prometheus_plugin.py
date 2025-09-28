"""
AutoGen Agent Integration for PrometheusTools.

This module provides helper functions to integrate PrometheusTools
with AutoGen Assistant Agents.
"""

from datetime import datetime
from typing import Annotated, Any

from .prometheus_client import PrometheusTools

# Global instance for reuse across agent calls
_prometheus_tools_instance: PrometheusTools | None = None


def get_prometheus_tools(prometheus_url: str | None = None) -> PrometheusTools:
    """Get or create an PrometheusTools instance."""
    global _prometheus_tools_instance
    if _prometheus_tools_instance is None:
        _prometheus_tools_instance = PrometheusTools(prometheus_url)
    return _prometheus_tools_instance


# AutoGen agent tool functions
async def prometheus_query_specific_metrics(
    metric_names: Annotated[
        list[str], "List of metric names to query (e.g., ['up', 'node_load1'])"
    ],
    start_time: Annotated[
        str | datetime | int | float | None, "Start time for metrics query"
    ] = None,
    end_time: Annotated[
        str | datetime | int | float | None, "End time for metrics query"
    ] = None,
    namespace: Annotated[str | None, "Kubernetes namespace filter"] = None,
    pod_name: Annotated[str | None, "Pod name filter (supports wildcards)"] = None,
    limit_per_metric: Annotated[int, "Maximum time series per metric"] = 50,
    step: Annotated[str, "Query resolution step (e.g., '1m', '5m')"] = "1m",
    prometheus_url: Annotated[str | None, "Prometheus server URL"] = None,
) -> dict[str, Any]:
    """
    Query specific Prometheus metrics efficiently.

    This function executes separate queries for each metric, avoiding inefficient
    OR queries and providing better control over data volume.

    Args:
        metric_names: List of metric names to query (e.g., ['up', 'node_load1'])
        start_time: Start time. Optional.
        end_time: End time. Optional.
        namespace: Kubernetes namespace filter. Optional.
        pod_name: Pod name filter. Optional.
        limit_per_metric: Max time series per metric (default: 50)
        step: Query resolution step (default: '1m')
        prometheus_url: Prometheus server URL. Optional.

    Returns:
        Dictionary with metrics organized by name, avoiding data overload.
    """
    tools = get_prometheus_tools(prometheus_url)
    return await tools.query_multiple_metrics(
        metric_names,
        start_time,
        end_time,
        namespace,
        pod_name,
        limit_per_metric,
        step,
    )


async def prometheus_get_essential_metrics(
    namespace: Annotated[str | None, "Kubernetes namespace filter"] = None,
    pod_name: Annotated[str | None, "Pod name filter (supports wildcards)"] = None,
    start_time: Annotated[
        str | datetime | int | float | None, "Start time for metrics query"
    ] = None,
    end_time: Annotated[
        str | datetime | int | float | None, "End time for metrics query"
    ] = None,
    step: Annotated[str, "Query resolution step (e.g., '1m', '5m')"] = "1m",
    prometheus_url: Annotated[str | None, "Prometheus server URL"] = None,
) -> dict[str, Any]:
    """
    Get essential system metrics with calculated percentages.

    Returns CPU usage %, memory usage %, disk usage %, system availability,
    and load averages - all pre-calculated and limited in volume.

    Args:
        namespace: Kubernetes namespace filter. Optional.
        pod_name: Pod name filter. Optional.
        start_time: Start time. Optional.
        end_time: End time. Optional.
        step: Query resolution step (default: '1m')
        prometheus_url: Prometheus server URL. Optional.

    Returns:
        Dictionary with essential calculated metrics, limited data volume.
    """
    tools = get_prometheus_tools(prometheus_url)
    return await tools.query_essential_metrics(
        namespace, pod_name, start_time, end_time, step
    )


async def prometheus_get_metric_names(
    namespace: Annotated[str | None, "Filter metrics by namespace"] = None,
    pod_name: Annotated[str | None, "Filter metrics by pod name pattern"] = None,
    metric_name: Annotated[
        str | None, "Filter metrics by name pattern (supports * and ?)"
    ] = None,
    limit: Annotated[int, "Maximum number of metric names to return"] = 1000,
    prometheus_url: Annotated[str | None, "Prometheus server URL"] = None,
) -> dict[str, Any]:
    """
    Get list of available metric names from Prometheus.

    This function queries the Prometheus /api/v1/label/__name__/values endpoint
    to retrieve all available metric names. Can optionally filter by namespace,
    pod name, and metric name pattern.

    Args:
        namespace: Filter metrics by namespace. Optional.
        pod_name: Filter metrics by pod name pattern. Optional.
        metric_name: Filter metrics by name pattern (supports * and ?). Optional.
        limit: Maximum number of metric names to return (default: 1000).
        prometheus_url: Prometheus server URL. Optional.

    Returns:
        Dictionary containing available metric names and filter information.
    """
    tools = get_prometheus_tools(prometheus_url)
    return await tools.get_metric_names(namespace, pod_name, metric_name, limit)


async def prometheus_get_targets(
    prometheus_url: Annotated[
        str | None, "Prometheus server URL. If None, uses default from settings"
    ] = None,
) -> dict[str, Any]:
    """
    Get information about Prometheus targets (scraped endpoints).

    This function queries the Prometheus /api/v1/targets endpoint to retrieve
    information about all targets being scraped by Prometheus, including
    their health status, discovery labels, and scrape information.

    Args:
        prometheus_url: Prometheus server URL. If None, uses default from settings.

    Returns:
        Dictionary containing targets information organized by job.
    """
    tools = get_prometheus_tools(prometheus_url)
    return await tools.get_targets()


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
        # Enhanced metric discovery and targets functionality
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
       namespace="production",
       pod_name="web-server",
       limit_per_metric=50
   )

2. Get essential system metrics with calculated values:
   prometheus_get_essential_metrics(
       namespace="production", 
       pod_name="database"
   )

3. Discover available metrics:
   prometheus_get_metric_names(
       namespace="production",
       pod_name="web-server",
       limit=500
   )

4. Query metrics with time range:
   prometheus_query_specific_metrics(
       metric_names=['node_cpu_seconds_total'],
       start_time="2024-01-01 10:00:00",
       end_time="2024-01-01 11:00:00",
       step="5m"
   )

5. Use with custom Prometheus URL:
   prometheus_query_specific_metrics(
       metric_names=['up'],
       prometheus_url="http://monitoring.example.com:9090"
   )

Response Format:
All functions return a dictionary with:
- status: "success" or "error"
- For success: query_info, metrics data organized by metric name
- For error: error message and context

Benefits of Enhanced Tools:
- Individual queries per metric (no inefficient OR queries)
- Configurable data limits (limit_per_metric parameter)
- Pre-calculated percentages for system monitoring
- Better error handling per metric
- Reduced Prometheus server load
- Kubernetes-aware filtering by namespace and pod name
- Metric discovery functionality for observability gap analysis
"""


if __name__ == "__main__":
    print(PROMETHEUS_TOOLS_USAGE_EXAMPLES)
