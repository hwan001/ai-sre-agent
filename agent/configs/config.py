"""
Configuration management using Pydantic Settings with dotenv support.

This module provides centralized configuration for the SRE Agent,
loading settings from environment variables and .env files.
"""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Set up basic logging
logger = logging.getLogger(__name__)

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Load environment variables from .env file
# First load from project root, then from current directory
env_files = [
    PROJECT_ROOT / ".env",
    Path(".env"),
]

for env_file in env_files:
    if env_file.exists():
        logger.info(f"Loading environment variables from {env_file}")
        load_dotenv(env_file, override=False)
    else:
        logger.debug(f"Environment file {env_file} not found")


class LLMSettings(BaseSettings):
    """LLM provider configuration."""

    # Azure OpenAI settings (currently the only LLM provider)
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2024-02-15-preview"

    # General settings
    temperature: float = 0.3
    max_tokens: int = 1000
    timeout_seconds: int = 60

    @field_validator("azure_openai_endpoint")
    @classmethod
    def validate_azure_endpoint(cls, v):
        if v and not v.startswith("https://"):
            raise ValueError("Azure OpenAI endpoint must start with https://")
        return v


class KubernetesSettings(BaseSettings):
    """Kubernetes configuration."""

    kubeconfig: str | None = None
    namespace: str = "default"
    in_cluster: bool = False
    timeout_seconds: int = 30

    model_config = SettingsConfigDict(env_prefix="K8S_")


class APISettings(BaseSettings):
    """API server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_prefix="API_")


class SafetySettings(BaseSettings):
    """Safety and security configuration."""

    # Note: 안전장치 기능들이 현재 미구현 상태
    # 향후 구현 시 아래 설정들을 활성화할 예정

    # enable_dry_run: bool = True
    # require_human_approval: bool = True
    # max_concurrent_actions: int = 3
    # action_timeout_seconds: int = 300

    # Rate limiting
    # rate_limit_window_minutes: int = 5
    # rate_limit_max_actions: int = 10

    # Allow-list file path
    allowlist_file: str = "configs/allowlist.yaml"


class MonitoringSettings(BaseSettings):
    """Monitoring integration settings."""

    prometheus_url: str = "http://prometheus:9090"

    # Loki settings
    loki_url: str = "http://loki:3100"
    loki_mock: bool = True


class AzureSettings(BaseSettings):
    """Azure integration settings."""

    # Note: Azure Key Vault 연동은 현재 미구현 상태
    # 향후 구현 시 아래 설정들을 활성화할 예정

    # key_vault_url: str | None = None
    # client_id: str | None = None
    # client_secret: str | None = None
    # tenant_id: str | None = None

    model_config = SettingsConfigDict(env_prefix="AZURE_")


class DevelopmentSettings(BaseSettings):
    """Development and debugging settings."""

    debug: bool = False
    enable_debug_logs: bool = False
    test_mode: bool = False
    mock_k8s_api: bool = False


class Settings(BaseSettings):
    """Main application settings."""

    # Sub-configurations
    llm: LLMSettings = Field(default_factory=LLMSettings)
    kubernetes: KubernetesSettings = Field(default_factory=KubernetesSettings)
    api: APISettings = Field(default_factory=APISettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    azure: AzureSettings = Field(default_factory=AzureSettings)
    development: DevelopmentSettings = Field(default_factory=DevelopmentSettings)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings (useful for testing)."""
    global _settings
    _settings = Settings()
    return _settings
