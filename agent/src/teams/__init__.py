"""
Teams Package

Provides specialized multi-agent teams using AutoGen Swarm pattern.
Each team focuses on specific aspects of SRE incident response.
"""

from __future__ import annotations

from .action_team import ActionTeam
from .log_analysis_team import LogAnalysisTeam
from .metric_analysis_team import MetricAnalysisTeam

__all__ = [
    "LogAnalysisTeam",
    "MetricAnalysisTeam",
    "ActionTeam",
]
