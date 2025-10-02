# SRE Agent

> AutoGen 0.7-powered multi-agent system for intelligent Kubernetes SRE operations.

## Quick Start

```bash
# 1. Setup Environment
cd agent
python -m venv venv && source venv/bin/activate
pip install -e ".[dev,azure]"

# 2. Configure Settings
cp .env.example .env
# Edit .env: Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, KUBECONFIG

# 3. Start Development Server
python dev.py
# → http://localhost:8000 (API) + Enhanced Multi-Agent Workflow ready
# → http://localhost:8000/docs (Interactive API Documentation)
# → http://localhost:8000/redoc (Alternative API Docs)

# 4. Test the Enhanced Multi-Agent System
curl -X POST http://localhost:8000/decision \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "Warning",
    "namespace": "default",
    "resource_name": "test-pod",
    "resource_kind": "Pod",
    "event_data": {"message": "Pod CrashLoopBackOff"}
  }'

# 5. Get Workflow Information
curl http://localhost:8000/workflow/info
```

## Architecture (v2.0 - Enhanced Multi-Agent)

**AutoGen 0.7 Enhanced Workflow**: Orchestrator-led multi-team collaboration for intelligent SRE operations.

```
K8s Event → Orchestrator Leader → Specialized Teams → Decision/Actions
              ↓
    🎯 Triage Agent (classifies incidents)
              ↓
    📋 Log Analysis Coordinator → Log Analysis Team (Swarm)
       ├─ Loki Query Agent (fetches logs)
       ├─ Log Summarizer Agent (summarizes patterns)
       └─ Log Pattern Agent (identifies anomalies)
              ↓
    ↓
    📊 Metric Analysis Coordinator → Metric Analysis Team (Swarm)
       ├─ Prometheus Query Agent (fetches metrics)
       ├─ Metric Analyzer Agent (analyzes trends)
       └─ Anomaly Detector Agent (detects anomalies)
              ↓
    ⚡ Action Coordinator → Action Team (Swarm)
       ├─ Recommendation Agent (suggests actions)
       ├─ Guard Agent (validates safety)
       └─ Approval Agent (final approval)
```

### Key Components (v2.0)

- **EnhancedSREWorkflow**: Orchestrator-led multi-team workflow engine
- **ContextManager**: Shared state management across all agents and teams
- **ToolRegistry**: Central tool discovery and management system
- **Specialized Teams**: Swarm-based teams with HandOff patterns
  - Log Analysis Team (3 agents with bidirectional HandOffs)
  - Metric Analysis Team (3 agents with sequential HandOffs)
  - Action Team (3 agents with validation pipeline)
- **Advanced Termination**: 5 intelligent stopping conditions
  - MaxMessageTermination (conversation length)
  - HighConfidenceTermination (confidence threshold)
  - AllTeamsReportedTermination (team completion)
  - CriticalErrorTermination (error handling)
  - TimeoutTermination (time limits)
- **Safety-First**: Multi-layer validation with guard agents
- **Real Monitoring**: Prometheus + Loki integration

### Architecture Highlights

**v2.0 Features:**
- 🎯 **Leader-based Orchestration**: MagenticOne-style coordination
- 🤝 **Swarm Teams**: HandOff-based collaboration within teams
- 📊 **Context Sharing**: WorkflowContext accessible to all agents
- 🔧 **Tool Registry**: Centralized tool management and discovery
- ⏱️ **Smart Termination**: Multiple conditions for optimal stopping
- 🔄 **Async-First**: Full async/await support throughout

## Configuration

### Environment Variables

**Required:**
- `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY` (Azure OpenAI)
- OR `OPENAI_API_KEY` (OpenAI)
- `KUBECONFIG` (Kubernetes config path)

## Architecture

**AutoGen GroupChat Workflow**: Multi-agent collaboration for intelligent SRE operations.

```
K8s Event → SREWorkflow (GroupChat) → Decision/Actions
              ↓
    🔍 Analysis Agent (diagnoses with K8s tools)
              ↓
    � Metric Analysis Agent (Prometheus monitoring)
              ↓
    �💡 Recommendation Agent (suggests actions)
              ↓
    🛡️ Guard Agent (validates safety)
              ↓
    ✅ Approval Agent (makes final decision)
              ↓
    ⚡ Execution Agent (implements actions)
    
```

### Key Components

- **SREWorkflow**: Business logic layer managing multi-agent workflows
- **GroupChatManager**: AutoGen's native orchestrator for agent conversations
- **KubernetesTools**: Real K8s API integration with function calling
- **Analysis Agent**: Pattern matching and symptom correlation with evidence
- **Metric Analysis Agent**: Specialized Prometheus monitoring and analysis
- **Multi-Agent Decision**: Collaborative reasoning through structured conversations
- **Safety-First**: Dry-run mode, human approval, and action validation

## Configuration

### Environment Variables

**Required:**
- `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY` (Azure OpenAI)
- OR `OPENAI_API_KEY` (OpenAI)
- `KUBECONFIG` (Kubernetes config path)

**Optional:**
- `PROMETHEUS_URL` - Prometheus metrics endpoint
- `LOKI_URL` - Grafana Loki logs endpoint
- `ENABLE_DRY_RUN=true` - Safety mode (default)
- `REQUIRE_HUMAN_APPROVAL=true` - Human-in-the-loop (default)

### Workflow Configuration

The enhanced workflow is configured through environment variables and `EnhancedSREWorkflow`:

```python
from workflows.sre_workflow import EnhancedSREWorkflow

# Initialize workflow
workflow = EnhancedSREWorkflow()

# Process incident
result = await workflow.process_incident(
    event_data={"message": "Pod CrashLoopBackOff"},
    namespace="production",
    resource_name="api-server",
)

# Get workflow info
info = workflow.get_workflow_info()
print(f"Architecture: {info['architecture']}")
print(f"Teams: {list(info['teams'].keys())}")
```

See [ENHANCED_WORKFLOW_GUIDE.md](ENHANCED_WORKFLOW_GUIDE.md) for detailed configuration options.

**LLM Settings**: Configured in `src/config.py` with model selection per agent
**Agent Behavior**: Defined in `src/workflows/sre_workflow.py` using GroupChatManager
**Tool Registration**: Kubernetes tools auto-registered with function calling
**Safety Guards**: Built into workflow logic and tool execution

Example agent config in `configs/agents.yaml.example`:
```yaml
workflow:
  max_turns: 10
  timeout_seconds: 300
  require_consensus: true
  human_in_loop_actions:
    - "delete_resources"
    - "scale_down_critical"
```

## API Documentation

### Interactive Documentation (FastAPI)

When running the development server, FastAPI automatically provides interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
  - Interactive API testing interface
  - Request/response examples
  - Schema validation

- **ReDoc**: http://localhost:8000/redoc
  - Clean, readable API documentation
  - Generated from OpenAPI schema

### API Endpoints

- `GET /health` - Health check
- `POST /decide` - Multi-agent decision endpoint (called by K8s Operator)
- `POST /execute` - Action execution with safety guards

### Example Usage

```bash
# Health check
curl http://localhost:8000/health

# Decision request (simulates K8s Operator call)
curl -X POST http://localhost:8000/decide \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "Warning",
    "namespace": "production",
    "resource_name": "web-app",
    "resource_kind": "Pod",
    "event_data": {"reason": "FailedMount", "message": "Volume mount failed"}
  }'
```

**💡 Tip**: Use the interactive docs at http://localhost:8000/docs to:
- Test API endpoints with a web interface
- See request/response schemas
- Understand the AutoGen multi-agent workflow
- View real-time validation and examples

**Response**: Multi-agent analysis with decision, confidence, and recommended actions.

##  Real-time Agent Conversation

Chat directly with specialized agents using AutoGen 0.7+ features:

**Web-based Chat (New!):**
```bash
# Browser-based chat interface
python web_chat.py
# → http://localhost:8001/ (Beautiful web UI)
# → Real-time WebSocket communication
# → Agent status monitoring dashboard
```

## Development

### Install & Run
```bash
# Install with dev dependencies
pip install -e ".[dev,azure]"

# Development server with hot reload + debug logs
python dev.py
# ✅ API: http://localhost:8000
# ✅ Docs: http://localhost:8000/docs (Swagger UI)
# ✅ Docs: http://localhost:8000/redoc (ReDoc)


# Web-based chat interface (New!)
python web_chat.py
# ✅ Beautiful browser-based chat UI
# ✅ Real-time WebSocket communication
# ✅ Agent status monitoring dashboard
# ✅ http://localhost:8001/ access

# Or direct API start (production mode)
python -m src.api.main
```

### Testing
```bash
# Run all tests
pytest --cov=src tests/

# Test specific components
pytest tests/test_sre_workflow.py -v
pytest tests/test_kubernetes_tools.py -v
```

### Code Quality
```bash
# Format and lint
black src/ && ruff check src/ --fix

# Type checking
mypy src/

# Pre-commit hooks
pre-commit install && pre-commit run --all-files
```

### AutoGen Development Guide

이 프로젝트는 **AutoGen 하이브리드 구조**를 사용한 멀티 에이전트 시스템입니다. v0.2 호환성과 최신 0.7.4+ 기능을 함께 활용합니다.

#### AutoGen 패키지 구조

**설치된 패키지:**
- `pyautogen` - v0.2 호환 API (기존 GroupChat, AssistantAgent 등)
- `autogen-agentchat` - 새로운 에이전트 시스템 (0.7.4+)
- `autogen-ext[openai]` - 모델 클라이언트와 확장 기능

#### AutoGen 핵심 개념

AutoGen에서는 **"Orchestrator"라는 공식 용어가 없습니다**. 대신 다음 구조를 사용:

```python

# 21. v0.7.4+ 스타일 (최신 기능)
from autogen_agentchat.agents import AssistantAgent as NewAssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

# 2. 하이브리드 Workflow (추천)
class SREWorkflow:
    def __init__(self):
        self.agents = self._create_agents()      # v0.2 호환
        self.group_chat = self._create_group_chat()  # v0.2 안정성
        self.manager = self._create_manager()    # GroupChatManager

    def _create_manager(self) -> GroupChatManager:
        return GroupChatManager(
            groupchat=self.group_chat,
            llm_config={"model": "gpt-4", "temperature": 0.0}
        )
```

#### 에이전트 작성 패턴

**v0.7.4+ 최신 방식** :
```python
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
class ModernAnalysisAgent(AssistantAgent):
    def __init__(self, name: str, **kwargs):
        model_client = OpenAIChatCompletionClient(model="gpt-4")
        super().__init__(name=name, model_client=model_client, **kwargs)
        # 새로운 도구 등록 방식 (0.7.4+)
```

#### 도구(Tools) 작성 패턴

**타입 어노테이션 필수** (AutoGen function calling):
```python
from typing import Annotated

async def get_pod_status(
    namespace: Annotated[str, "Kubernetes namespace"],
    pod_name: Annotated[str, "Pod name to check"] | None = None,
) -> dict[str, Any]:
    """
    Get pod status information.

    Args:
        namespace: Kubernetes namespace
        pod_name: Specific pod name (optional)

    Returns:
        Pod status information
    """
    # 구현...
```

#### 워크플로우 실행 패턴 (AutoGen 0.7.4+)

**비동기 처리 + 새로운 GroupChat 기능**:
```python
async def process_incident(self, event_data: dict) -> dict:
    initial_message = f"분석해주세요: {event_data}"

    # AutoGen 0.7.4+ GroupChat 설정
    group_chat = GroupChat(
        agents=list(self.agents.values()),
        messages=[],
        max_round=10,
        speaker_selection_method="auto",
        allow_repeat_speaker=False,  # 새로운 기능
        send_introductions=True,     # 에이전트 소개
    )

    result = await self.manager.a_initiate_chat(
        self.agents["analysis"],
        message=initial_message,
        max_turns=10
    )

    return self._extract_decision(result)
```

#### 개발 시 주의사항 (하이브리드 환경)

1. **패키지 선택**: v0.2 호환(`autogen`) vs 신버전(`autogen-agentchat`) 구분
2. **Function Calling**: `Annotated` 타입 힌트 필수 (두 버전 공통)
3. **Model Client**: 신버전은 `OpenAIChatCompletionClient` 등 명시적 클라이언트 필요
4. **Error Handling**: 버전별로 다른 예외 처리 패턴
5. **Async/Await**: 모든 LLM 호출은 비동기 권장
6. **Message History**: GroupChat이 대화 히스토리 자동 관리
7. **Migration Path**: v0.2 → v0.7.4+ 점진적 전환 가능

#### 디버깅 팁

```python
# 1. 에이전트 대화 로그 확인
import structlog
logger = structlog.get_logger()

# 2. 개발 모드에서 mock 사용
if self.settings.development.mock_k8s_api:
    return self._mock_pod_status(namespace, pod_name)

# 3. GroupChat 메시지 히스토리 검사
print(f"Messages: {self.group_chat.messages}")
```

### Project Structure