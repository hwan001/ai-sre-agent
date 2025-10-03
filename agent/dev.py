#!/usr/bin/env python3
"""
Development runner for SRE Agent.

Quick script to start the agent with development settings.
"""

import os
import sys
from pathlib import Path

import structlog
import uvicorn

# Add both project root and src to Python path for proper imports
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

# Import after path setup
from configs.config import get_settings  # noqa: E402

# Get log level from environment (LOG_MODE or LOG_LEVEL)
log_mode = os.getenv("LOG_MODE", os.getenv("LOG_LEVEL", "INFO")).upper()
log_level_map = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "WARN": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}
log_level = log_level_map.get(log_mode, 20)  # Default to INFO

# Configure development logging with environment-based level
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Set the standard library logging level based on environment
import logging

logging.basicConfig(level=log_level, format="%(message)s")
logging.getLogger().setLevel(log_level)


def main():
    """Run the development server."""
    settings = get_settings()

    ## Print all settings for verification
    # model_dic = settings.model_dump()
    # for group in model_dic.keys():
    #     for key, value in model_dic[group].items():
    #         print(f"{key}: {value}")

    # Override settings for development
    settings.api.reload = True
    settings.development.debug = True
    settings.development.enable_debug_logs = True

    logger = structlog.get_logger()
    log_mode = os.getenv("LOG_MODE", os.getenv("LOG_LEVEL", "INFO")).upper()
    logger.info(
        "Starting SRE Agent in development mode",
        host=settings.api.host,
        port=settings.api.port,
        log_level=log_mode,
    )

    # Start the server
    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        reload_dirs=["src"],
        log_level=settings.api.log_level.lower(),
    )


if __name__ == "__main__":
    main()
