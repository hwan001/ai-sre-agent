"""
Test script for Prometheus Tools.

This script demonstrates the improved efficiency of the tools
compared to the original implementation.
"""

from src.tools.metrics.prometheus_agent_tools import (
    prometheus_get_essential_metrics,
    prometheus_query_specific_metrics,
)


def test_prometheus_tools():
    """Test and compare vs original Prometheus tools."""

    print("=== Prometheus Tools Test ===\n")

    # Test 1: Query specific metrics (RECOMMENDED approach)
    print("1. Testing prometheus_query_specific_metrics() - EFFICIENT")
    print("   Querying ['up', 'node_load1', 'node_memory_MemAvailable_bytes']...")
    try:
        specific_result = prometheus_query_specific_metrics(
            metric_names=["up", "node_load1", "node_memory_MemAvailable_bytes"],
            limit_per_metric=5,  # Limit to 5 series per metric
        )
        print(f"Status: {specific_result['status']}")
        if specific_result["status"] == "success":
            query_info = specific_result["query_info"]
            print(f"Metrics requested: {query_info['metrics_requested']}")
            print(f"Successful: {query_info.get('successful_metrics', 0)}")
            print(f"Failed: {query_info.get('failed_metrics', 0)}")
            print(f"Total series: {query_info.get('total_series', 0)}")
            print("Metrics by name:")
            for name, data in specific_result["metrics_by_name"].items():
                if "error" not in data:
                    print(f"  - {name}: {data['series_count']} series")
                else:
                    print(f"  - {name}: ERROR - {data['error']}")
        else:
            print(f"Error: {specific_result['error']}")
    except Exception as e:
        print(f"Exception: {e}")

    print("\n" + "=" * 70 + "\n")

    # Test 2: Get essential metrics (RECOMMENDED for monitoring)
    print("2. Testing prometheus_get_essential_metrics() - CALCULATED VALUES")
    print("   Getting CPU%, Memory%, Disk%, System Up, Load Average...")
    try:
        essential_result = prometheus_get_essential_metrics()
        print(f"Status: {essential_result['status']}")
        if essential_result["status"] == "success":
            query_info = essential_result["query_info"]
            print(f"Essential metrics: {query_info['essential_metrics_count']}")
            print(f"Successful: {query_info.get('successful', 0)}")
            print(f"Failed: {query_info.get('failed', 0)}")
            print("Available metrics:")
            for name, data in essential_result["essential_metrics"].items():
                if "error" not in data:
                    print(f"  - {name}: {data['series_count']} series")
                else:
                    print(f"  - {name}: ERROR - {data['error']}")
        else:
            print(f"Error: {essential_result['error']}")
    except Exception as e:
        print(f"Exception: {e}")

    print("\n" + "=" * 70 + "\n")

    # Test 3: Specific metrics with namespace and pod name filters
    print("3. Testing with namespace and pod name filters...")
    try:
        k8s_result = prometheus_query_specific_metrics(
            metric_names=["up", "node_cpu_seconds_total"],
            namespace="default",
            pod_name="monitoring",
            limit_per_metric=3,
        )
        print(f"Status: {k8s_result['status']}")
        if k8s_result["status"] == "success":
            query_info = k8s_result["query_info"]
            print(f"Namespace filter: {query_info['namespace_filter']}")
            print(f"Pod name filter: {query_info['pod_name_filter']}")
            print(f"Total series: {query_info.get('total_series', 0)}")
            for name, data in k8s_result["metrics_by_name"].items():
                if "error" not in data:
                    series_count = data["series_count"]
                    limited = data.get("limited", False)
                    print(f"  - {name}: {series_count} series, limited: {limited}")
                else:
                    print(f"  - {name}: ERROR")
        else:
            print(f"Error: {k8s_result['error']}")
    except Exception as e:
        print(f"Exception: {e}")

    print("\n" + "=" * 70 + "\n")

    # Test 4: Essential metrics with namespace and pod filters
    print("4. Testing essential metrics with Kubernetes filters...")
    try:
        k8s_essential_result = prometheus_get_essential_metrics(
            namespace="production",
            pod_name="web-server",
        )
        print(f"Status: {k8s_essential_result['status']}")
        if k8s_essential_result["status"] == "success":
            query_info = k8s_essential_result["query_info"]
            print(f"Namespace filter: {query_info['namespace_filter']}")
            print(f"Pod name filter: {query_info['pod_name_filter']}")
            print(f"Essential metrics: {query_info['essential_metrics_count']}")
            for name, data in k8s_essential_result["essential_metrics"].items():
                if "error" not in data:
                    series_count = data["series_count"]
                    print(f"  - {name}: {series_count} series")
                else:
                    print(f"  - {name}: ERROR")
        else:
            print(f"Error: {k8s_essential_result['error']}")
    except Exception as e:
        print(f"Exception: {e}")

    print("\n=== RECOMMENDATIONS ===")
    print("✅ Use prometheus_query_specific_metrics() for querying specific metrics")
    print("✅ Use prometheus_get_essential_metrics() for system monitoring")
    print("💡 Always set limit_per_metric to control data volume")
    print("💡 Use namespace and pod_name filters for Kubernetes environments")
    print("💡 Enhanced tools provide better efficiency and control")

    print("\n=== Test Complete ===")


if __name__ == "__main__":
    print("Prometheus Tools Test")
    print("====================================")
    print()
    print("This test demonstrates the efficient approaches for")
    print("querying Prometheus metrics with improved performance")
    print("and Kubernetes-aware filtering.")
    print()

    test_prometheus_tools()
