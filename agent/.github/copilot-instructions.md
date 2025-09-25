You are building an AI agent using Autogen 0.7 to assist with debugging Kubernetes observability tools. Your goal is to help the agent identify and reason about missing or fragmented monitoring signals across various tools (e.g., Prometheus, Grafana, OpenTelemetry, etc.).

Instructions:
1. Follow Autogen 0.7 design patterns strictly (e.g., AssistantAgent, UserProxyAgent, GroupChatManager).
2. Prioritize agentic design: agents should collaborate, delegate, and reason about observability gaps.
3. If Autogen does not support a required feature, search PyPI for popular libraries (updated within the last 12 months) to fill the gap.
4. Avoid using deprecated or inactive packages.
5. Focus on modular and reusable components that can be extended for future observability tools.
6. Include examples of how the agent can:
   - Detect missing metrics or logs.
   - Suggest instrumentation improvements.
   - Correlate signals across tools.
   - Generate debugging hypotheses based on partial data.

Output format:
- Python code snippets following Autogen 0.7.
- Comments explaining agent roles and reasoning.
- Suggestions for external libraries (with update history).
