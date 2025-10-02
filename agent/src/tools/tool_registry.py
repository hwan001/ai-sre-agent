"""
Tool Registry

Central registry for all tools available to agents.
Provides tool discovery, categorization, and dynamic assignment.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog

logger = structlog.get_logger()


class ToolRegistry:
    """
    Central registry for all tools available to agents.

    Provides:
    - Tool registration by category
    - Tool discovery for agents
    - Dynamic tool assignment
    - Tool metadata management
    """

    def __init__(self):
        """Initialize tool registry."""
        self._tools: dict[str, list[Callable]] = {
            "kubernetes": [],
            "logs": [],
            "metrics": [],
            "actions": [],
            "validation": [],
        }

        self._tool_metadata: dict[str, dict[str, Any]] = {}

        logger.info("Tool registry initialized")

    def register_tool(
        self,
        category: str,
        tool: Callable,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a tool in a category.

        Args:
            category: Tool category
            tool: Tool function
            metadata: Optional tool metadata
        """
        if category not in self._tools:
            self._tools[category] = []
            logger.info("New tool category created", category=category)

        self._tools[category].append(tool)

        # Store metadata
        tool_name = tool.__name__
        if metadata:
            self._tool_metadata[tool_name] = metadata

        logger.debug(
            "Tool registered",
            category=category,
            tool=tool_name,
            has_metadata=metadata is not None,
        )

    def register_tools(
        self,
        category: str,
        tools: list[Callable],
        metadata: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """
        Register multiple tools at once.

        Args:
            category: Tool category
            tools: List of tool functions
            metadata: Optional metadata dict keyed by tool name
        """
        for tool in tools:
            tool_metadata = None
            if metadata and tool.__name__ in metadata:
                tool_metadata = metadata[tool.__name__]

            self.register_tool(category, tool, tool_metadata)

        logger.info("Multiple tools registered", category=category, count=len(tools))

    def get_tools(self, category: str) -> list[Callable]:
        """
        Get all tools in a category.

        Args:
            category: Tool category

        Returns:
            List of tool functions
        """
        tools = self._tools.get(category, [])
        logger.debug("Tools retrieved", category=category, count=len(tools))
        return tools

    def get_tools_for_agent(self, agent_type: str) -> list[Callable]:
        """
        Get recommended tools for an agent type.

        Args:
            agent_type: Type of agent

        Returns:
            List of recommended tools
        """
        tool_mapping = {
            "loki_agent": ["logs"],
            "loki_query_agent": ["logs"],
            "prometheus_agent": ["metrics"],
            "prometheus_query_agent": ["metrics"],
            "metric_analyzer_agent": ["metrics"],
            "anomaly_detector_agent": ["metrics"],
            "triage_agent": ["kubernetes"],
            "recommendation_agent": ["actions"],
            "guard_agent": ["validation"],
            "orchestrator_leader": [],  # Orchestrator doesn't use tools directly
            "log_coordinator": [],  # Coordinators delegate to sub-teams
            "metric_coordinator": [],
            "action_coordinator": [],
        }

        categories = tool_mapping.get(agent_type, [])
        tools = []

        for category in categories:
            tools.extend(self.get_tools(category))

        logger.info(
            "Tools retrieved for agent",
            agent_type=agent_type,
            categories=categories,
            tool_count=len(tools),
        )

        return tools

    def get_all_tools(self) -> list[Callable]:
        """
        Get all registered tools.

        Returns:
            List of all tools
        """
        all_tools = []
        for tools in self._tools.values():
            all_tools.extend(tools)

        return all_tools

    def get_tool_metadata(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get metadata for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool metadata or None
        """
        return self._tool_metadata.get(tool_name)

    def get_categories(self) -> list[str]:
        """
        Get all tool categories.

        Returns:
            List of category names
        """
        return list(self._tools.keys())

    def get_tools_by_name(self, tool_names: list[str]) -> list[Callable]:
        """
        Get tools by their function names.

        Args:
            tool_names: List of tool function names

        Returns:
            List of matching tools
        """
        tools = []
        all_tools = self.get_all_tools()

        for tool in all_tools:
            if tool.__name__ in tool_names:
                tools.append(tool)

        logger.debug(
            "Tools retrieved by name",
            requested=len(tool_names),
            found=len(tools),
        )

        return tools

    def get_summary(self) -> dict[str, Any]:
        """
        Get registry summary.

        Returns:
            Summary with category counts
        """
        category_counts = {
            category: len(tools) for category, tools in self._tools.items()
        }

        return {
            "total_tools": len(self.get_all_tools()),
            "total_categories": len(self._tools),
            "category_counts": category_counts,
            "tools_with_metadata": len(self._tool_metadata),
        }


# Global tool registry instance
_tool_registry: ToolRegistry | None = None
_tools_initialized: bool = False


def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry instance.

    Returns:
        Global tool registry
    """
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry


def initialize_tool_registry() -> ToolRegistry:
    """
    Initialize tool registry with all available tools.

    This should be called once at application startup.
    Subsequent calls will return the already-initialized registry without re-registering tools.

    Returns:
        Initialized tool registry
    """
    global _tools_initialized

    registry = get_tool_registry()

    # If already initialized, return existing registry
    if _tools_initialized:
        logger.info("Tool registry already initialized, skipping re-initialization")
        return registry

    logger.info("Initializing tool registry for the first time")

    try:
        # Register Loki tools
        from tools.loki_client import get_loki_tools

        loki_tools = get_loki_tools()
        registry.register_tools("logs", loki_tools)
        logger.info("Loki tools registered")

    except Exception as e:
        logger.error("Failed to register Loki tools", error=str(e))

    try:
        # Register Prometheus tools
        from tools.prometheus_plugin import get_prometheus_tools_for_agent

        prom_tools = get_prometheus_tools_for_agent()
        registry.register_tools("metrics", prom_tools)
        logger.info("Prometheus tools registered")

    except Exception as e:
        logger.error("Failed to register Prometheus tools", error=str(e))

    try:
        # Register Kubernetes tools
        from tools.kubernetes import KubernetesTools

        k8s_tools_instance = KubernetesTools()
        # Assuming KubernetesTools has a method to get tool functions
        # This may need adjustment based on actual implementation
        if hasattr(k8s_tools_instance, "get_tools"):
            k8s_tools = k8s_tools_instance.get_tools()
            registry.register_tools("kubernetes", k8s_tools)
            logger.info("Kubernetes tools registered")

    except Exception as e:
        logger.error("Failed to register Kubernetes tools", error=str(e))

    # Mark as initialized to prevent duplicate registrations
    _tools_initialized = True

    summary = registry.get_summary()
    logger.info(
        "Tool registry initialization complete",
        total_tools=summary["total_tools"],
        categories=summary["category_counts"],
    )

    return registry
