"""
Prompt loader utility for loading and rendering YAML-based prompt templates.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from jinja2 import Template


class PromptLoader:
    """Load and render agent prompts from YAML files."""

    def __init__(self, prompts_dir: Optional[Path] = None):
        """
        Initialize prompt loader.

        Args:
            prompts_dir: Directory containing YAML prompt files.
                        Defaults to 'prompts/' relative to this file.
        """
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent
        self.prompts_dir = Path(prompts_dir)
        self._cache: Dict[str, Dict[str, Any]] = {}

    def load_prompt(
        self, agent_name: str, use_cache: bool = True, **template_vars: Any
    ) -> str:
        """
        Load and render a prompt template for an agent.

        Args:
            agent_name: Name of the agent (e.g., 'orchestrator_leader')
            use_cache: Whether to use cached YAML data
            **template_vars: Variables to substitute in the Jinja2 template

        Returns:
            Rendered prompt string

        Raises:
            FileNotFoundError: If prompt file doesn't exist
            ValueError: If YAML is invalid or missing required fields
        """
        # Load YAML data
        if use_cache and agent_name in self._cache:
            prompt_data = self._cache[agent_name]
        else:
            prompt_file = self.prompts_dir / f"{agent_name}.yaml"
            if not prompt_file.exists():
                raise FileNotFoundError(
                    f"Prompt file not found: {prompt_file}\n"
                    f"Available prompts: {self.list_available_prompts()}"
                )

            with open(prompt_file, "r", encoding="utf-8") as f:
                prompt_data = yaml.safe_load(f)

            if not isinstance(prompt_data, dict):
                raise ValueError(f"Invalid YAML in {prompt_file}: expected dict")

            if "description" not in prompt_data:
                raise ValueError(f"Missing 'description' field in {prompt_file}")

            if use_cache:
                self._cache[agent_name] = prompt_data

        # Merge default variables with provided ones
        default_vars = prompt_data.get("variables", {})
        merged_vars = {**default_vars, **template_vars}

        # Render template
        template = Template(prompt_data["description"])
        rendered = template.render(**merged_vars)

        return rendered

    def list_available_prompts(self) -> list[str]:
        """List all available prompt files."""
        if not self.prompts_dir.exists():
            return []
        return [f.stem for f in self.prompts_dir.glob("*.yaml") if f.stem != "__init__"]

    def clear_cache(self):
        """Clear the prompt cache."""
        self._cache.clear()

    def get_prompt_metadata(self, agent_name: str) -> Dict[str, Any]:
        """
        Get metadata about a prompt without rendering it.

        Returns dict with 'name', 'description', 'variables', etc.
        """
        prompt_file = self.prompts_dir / f"{agent_name}.yaml"
        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

        with open(prompt_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


# Global loader instance
_default_loader: Optional[PromptLoader] = None


def get_loader() -> PromptLoader:
    """Get the default global prompt loader."""
    global _default_loader
    if _default_loader is None:
        _default_loader = PromptLoader()
    return _default_loader


def load_prompt(agent_name: str, **template_vars: Any) -> str:
    """
    Convenience function to load a prompt using the default loader.

    Args:
        agent_name: Name of the agent
        **template_vars: Variables for template rendering

    Returns:
        Rendered prompt string
    """
    return get_loader().load_prompt(agent_name, **template_vars)
