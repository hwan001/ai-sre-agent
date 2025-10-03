# AI SRE Agent (v0.5)

> 자연어로 대화하는 Kubernetes 진단 AI

kubectl이나 PromQL 대신 평문으로 클러스터를 진단합니다.

```
You: "payment-service 파드가 왜 죽어?"
→ OOMKilled 확인 → Memory 2Gi로 증가 권장
```

## 기능

- **멀티 에이전트**: Orchestrator, Metric/Log Expert, Analysis, Report
- **자연어 대화**: 평문 질문/응답
- **실시간 모니터링**: Prometheus, Loki 연동
- **웹 UI**: WebSocket 기반 채팅

## 설치

```bash
cd agent
uv pip install -e ".[dev,azure]"

export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com"
export KUBECONFIG="~/.kube/config"
export PROMETHEUS_URL="http://localhost:9090"  # 선택
export LOKI_URL="http://localhost:3100"        # 선택

uv run dev.py
```

**접속**: http://localhost:8000

## 아키텍처

```
User → Orchestrator → Metric/Log Expert → Analysis → Report
```

**기술**: AutoGen 0.7.4 Swarm + Azure OpenAI GPT-4o + FastAPI

```
agent/
├── src/agents/      # AI 에이전트
├── src/tools/       # K8s/Prometheus/Loki
├── src/workflows/   # 대화 오케스트레이션
├── prompts/         # 에이전트 프롬프트
└── static/          # 웹 UI
```

## 개발

```bash
# 개발 서버
uv run dev.py

# 테스트
pytest --cov=src

# 코드 품질
black src/ && ruff check src/ --fix && mypy src/
```

## 모니터링 연동

```bash
# Prometheus
kubectl port-forward -n observability svc/prometheus 9090:9090

# Loki
kubectl port-forward -n observability svc/loki 3100:3100
```

## 배포

```bash
# Docker
docker build -t sre-agent:0.5 .
docker run -d -p 8000:8000 -e AZURE_OPENAI_API_KEY=key sre-agent:0.5

# Kubernetes
kubectl apply -f k8s/deployment.yaml
```

## AutoGen 예제

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

client = AzureOpenAIChatCompletionClient(model="gpt-4o", azure_endpoint=endpoint, api_key=key)
agent = AssistantAgent(name="expert", model_client=client, system_message="...")
```

Tool 등록:
```python
from typing import Annotated

async def query_prometheus(
    query: Annotated[str, "PromQL query"],
    lookback: Annotated[str, "Time range"] = "5m"
) -> dict:
    pass
```

## 환경 변수

| 변수 | 필수 | 설명 |
|------|------|------|
| AZURE_OPENAI_API_KEY | ✅ | API 키 |
| AZURE_OPENAI_ENDPOINT | ✅ | 엔드포인트 |
| KUBECONFIG | ✅ | K8s 설정 |
| PROMETHEUS_URL | ❌ | Prometheus |
| LOKI_URL | ❌ | Loki |

## 링크

- [AutoGen](https://microsoft.github.io/autogen/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Prometheus](https://prometheus.io/docs/)

---

**Version**: 0.5.0 | **Framework**: AutoGen 0.7.4+
