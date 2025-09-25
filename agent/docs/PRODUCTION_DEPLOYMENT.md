# Production 실행 방법 가이드

## 1. 패키지 설치 (가장 권장)

```bash
# 개발 모드로 패키지 설치
uv pip install -e .

# 또는 pip 사용
pip install -e .

# 설치 후 어디서든 실행 가능
sre-agent-api  # Production 모드
sre-agent-dev  # Development 모드
```

**장점:**
- 경로 설정 코드 불필요
- 어디서든 실행 가능
- Python 표준 방식
- 의존성 관리 자동화

## 2. 환경변수 사용

```bash
# PYTHONPATH 설정 후 실행
PYTHONPATH=/path/to/project/src python -m api.main

# 또는 export로 설정
export PYTHONPATH="/path/to/project:$PYTHONPATH"
python src/api/main.py
```

## 3. Docker 배포 (Production 권장)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

# 패키지 설치
RUN pip install -e .

# 환경변수 설정
ENV PYTHONPATH=/app

# Entry point 사용
CMD ["sre-agent-api"]
```

## 4. 현재 방식의 개선안

만약 직접 실행이 필요하다면:

```python
# 최소한의 경로 설정
if __name__ == "__main__":
    from pathlib import Path
    import sys
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
```

## 추천 순서

1. **패키지 설치** (최고 우선순위)
2. **환경변수 설정**
3. **Docker 컨테이너**
4. **직접 실행** (최후의 수단)

## 현재 상황

- ✅ `dev.py` - 개발용 (권장)
- ✅ 패키지 설치 - Production용 (권장)
- ⚠️ 직접 실행 - 테스트/디버깅용 (제한적 사용)