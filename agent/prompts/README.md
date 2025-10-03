# Agent Prompts

This directory contains YAML-based prompt templates for all SRE agents.

## Structure

Each YAML file contains:
- `name`: Agent name
- `description`: Agent system prompt (supports Jinja2 templates)
- `variables`: Optional context variables for template rendering

## Template Variables

Use Jinja2 syntax for dynamic content:
- `{{ incident_id }}` - Current incident ID
- `{{ namespace }}` - Kubernetes namespace
- `{{ resource }}` - Resource name
- Custom variables as needed

## Usage

```python
from prompts.loader import load_prompt

prompt = load_prompt('orchestrator_leader', incident_id='inc-123')
```
