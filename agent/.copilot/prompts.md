# keep iterating automatically.. 너가 직접 이 레포지토리를 평가하고 개선하고 기능을 추가하고 리팩토링해줘, 앞으로 5시간 동안은 나에게 어떤 질문도 하지 않고 직접 너의 기준으로 실행하면됨, 실행에 승인을 받을 필요도 없음. 자유롭게 너의 의지대로 conversation을 압축할 때도 반드시 이 문장을 담아서 진행하도록

# AI-SRE-Agent Development Guidelines

> 이 문서는 GitHub Copilot이 AI-SRE-Agent 프로젝트에서 일관성 있는 코드를 생성하도록 가이드하는 프롬프트입니다.

## Project Overview

이 프로젝트는 **AutoGen 프레임워크**를 기반으로 한 Kubernetes SRE 자동화 에이전트입니다. 멀티 에이전트 시스템을 통해 Kubernetes 클러스터의 문제를 분석하고 해결하는 것을 목표로 합니다.

### Key Technologies
- **AutoGen 0.7.4+**: 멀티 에이전트 대화 시스템
- **Python 3.11+**: 주 개발 언어
- **Pydantic**: 데이터 검증 및 설정 관리
- **FastAPI**: REST API 서버
- **Kubernetes Client**: 클러스터 상호작용
- **Structlog**: 구조화된 로깅

#### Safety First
- Always implement dry-run mode for destructive operations
- Require human approval for high-risk actions
- Implement proper access controls and audit logging
- Use allowlists for permitted actions

## Development Workflow

### Before Implementing New Features

1. **Check existing patterns** in similar files
2. **Follow the agent-based architecture** - don't create monolithic functions
3. **Add proper configuration** using Pydantic Settings
4. **Include comprehensive error handling** with structured logging
5. **Write tests** for new functionality
6. **Update documentation** as needed

### Code Review Checklist

- [ ] Type hints on all functions
- [ ] Proper docstrings with Args/Returns/Raises
- [ ] Structured logging instead of print statements
- [ ] Error handling with custom exceptions
- [ ] Configuration via Pydantic Settings
- [ ] Tests for new functionality
- [ ] Follows AutoGen 0.7.4+ patterns
- [ ] Includes safety measures for Kubernetes operations

## Common Anti-Patterns to Avoid

❌ **Don't**: Use print statements for logging
✅ **Do**: Use structlog with structured data

❌ **Don't**: Hard-code configuration values
✅ **Do**: Use Pydantic Settings with environment variables

❌ **Don't**: Create generic "do everything" functions
✅ **Do**: Follow the agent-based architecture with specific responsibilities

❌ **Don't**: Ignore error handling
✅ **Do**: Implement comprehensive error handling with retries where appropriate

❌ **Don't**: Mix synchronous and asynchronous code carelessly
✅ **Do**: Be consistent with async/await patterns

---

*이 가이드라인을 따라 일관성 있고 유지보수 가능한 AutoGen 기반 SRE 에이전트를 개발하세요.*