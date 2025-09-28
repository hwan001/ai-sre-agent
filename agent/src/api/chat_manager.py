"""
Web Chat Manager for SRE Agent.

Manages multi-agent conversations and individual agent interactions
for the web-based chat interface.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import structlog
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import CancellationToken
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

from agents.metric_analyze_agent import MetricAnalyzeAgent
from configs.config import get_settings
from workflows.sre_workflow import SREWorkflow

logger = structlog.get_logger()


class WebChatManager:
    """웹 채팅 매니저 - Multi-Agent SRE Workflow와 개별 Agent 모드 지원"""

    # Agent conversation limits
    MAX_INDIVIDUAL_MESSAGES = 10
    MAX_INDIVIDUAL_TURNS = 5

    # Streaming and UI constants
    STEP_DELAY_SECONDS = 1.5
    TEAM_PROGRESS_DELAY_SECONDS = 0.5
    MIN_MEANINGFUL_MESSAGE_LENGTH = 10

    # Model configuration
    DEFAULT_TEMPERATURE = 0.1
    DEFAULT_SEED = 42

    def __init__(self):
        self.settings = get_settings()
        self.sre_workflow = None
        self.individual_agents = {}

    async def initialize_agent(self):
        """SRE Workflow 및 개별 에이전트 초기화"""
        if self.sre_workflow:
            return  # 이미 초기화됨

        try:
            # SRE Workflow 초기화 (팀채팅용)
            self.sre_workflow = SREWorkflow()

            # 개별 에이전트 초기화
            await self._initialize_individual_agents()

            logger.info(
                "Multi-Agent SRE Workflow and individual agents initialized for web chat"
            )
        except Exception as e:
            logger.error(f"Failed to initialize agents: {e}")
            raise

    async def _initialize_individual_agents(self):
        """개별 에이전트들 초기화"""
        try:
            # Azure OpenAI 설정
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_api_version = os.getenv(
                "AZURE_OPENAI_API_VERSION", "2024-12-01-preview"
            )

            if not azure_api_key or not azure_endpoint:
                raise ValueError("Azure OpenAI configuration missing")

            # MetricAnalyzeAgent 생성
            metric_model_client = AzureOpenAIChatCompletionClient(
                model="gpt-4o",
                azure_deployment="gpt-4o",
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=azure_api_version,
                seed=self.DEFAULT_SEED,
                temperature=self.DEFAULT_TEMPERATURE,
            )

            self.individual_agents["metric_analyze_agent"] = {
                "agent": MetricAnalyzeAgent(
                    name="metric_analyze_agent",
                    model_client=metric_model_client,
                ),
                "display_name": "📈 **Metric Analyze Agent**",
                "description": "Prometheus 메트릭 데이터 전문 분석",
            }

            # 향후 다른 에이전트들 추가 예시
            # self.individual_agents["analysis_agent"] = {
            #     "agent": AnalysisAgent(...),
            #     "display_name": "📊 **Analysis Agent**",
            #     "description": "시스템 분석 및 진단"
            # }

            logger.info("Individual agents initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize individual agents: {e}")
            raise

    async def chat_with_agent_streaming(
        self,
        user_message: str,
        websocket,
        chat_mode: str = "team",
        agent_type: str = "metric_analyze_agent",
    ):
        """Multi-Agent 팀 또는 개별 Agent와 스트리밍 대화"""
        try:
            if not self.sre_workflow:
                await self.initialize_agent()

            if not self.sre_workflow:
                raise ValueError("Failed to initialize SRE Workflow")

            if chat_mode == "team":
                await self._process_team_chat_streaming(user_message, websocket)
            elif chat_mode == "individual":
                await self._process_individual_agent_chat(
                    user_message, websocket, agent_type
                )
            else:
                # 기본값은 팀채팅
                await self._process_team_chat_streaming(user_message, websocket)

        except Exception as e:
            logger.error(f"Streaming chat error: {e}")
            await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))

    async def _process_team_chat_streaming(self, user_message: str, websocket):
        """SREWorkflow를 그대로 실행 (프롬프트 추가 없이)"""
        try:
            # SRE Workflow 실행
            if not self.sre_workflow:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "error": "SRE Workflow가 초기화되지 않았습니다.",
                        }
                    )
                )
                return

            # 웹 채팅용 이벤트 데이터 구성
            event_data = {
                "type": "user_chat",
                "message": user_message,
                "context": "web_chat_team",
                "timestamp": "now",
            }

            # 분석 시작 알림
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "team_start",
                        "message": "🚀 Multi-Agent 팀 분석 시작...",
                        "mode": "team",
                    }
                )
            )

            # SREWorkflow의 process_incident를 그대로 실행 (추가 프롬프트 없이)
            result = await self.sre_workflow.process_incident(
                event_data=event_data,
                namespace=None,  # 웹 채팅에서는 None
                resource_name=None,  # 웹 채팅에서는 None
            )

            # 팀 대화 결과를 스트리밍으로 전송
            if result.get("full_conversation"):
                for i, message_str in enumerate(result["full_conversation"]):
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "team_message",
                                "agent": "team",
                                "message": message_str,
                                "sequence": i + 1,
                                "total": len(result["full_conversation"]),
                            }
                        )
                    )

                    # 메시지 간 약간의 딜레이
                    await asyncio.sleep(self.TEAM_PROGRESS_DELAY_SECONDS)
            else:
                # 단일 응답 전송
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "team_message",
                            "agent": "team",
                            "message": result.get(
                                "reasoning", "Team analysis completed"
                            ),
                            "sequence": 1,
                            "total": 1,
                        }
                    )
                )

            # 최종 완료 알림
            message_count = (
                len(result.get("full_conversation", []))
                if result.get("full_conversation")
                else 1
            )
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "team_complete",
                        "message": "🎉 Multi-Agent 팀 분석이 완료되었습니다!",
                        "summary": f"총 {message_count}개의 메시지로 협업 분석을 완료했습니다.",
                    }
                )
            )

        except Exception as e:
            logger.error(f"Team chat streaming error: {e}")
            await websocket.send_text(
                json.dumps(
                    {"type": "error", "error": f"팀 채팅 처리 중 오류: {str(e)}"}
                )
            )

    async def _process_individual_agent_chat(
        self, user_message: str, websocket, agent_type: str = "metric_analyze_agent"
    ):
        """개별 에이전트와 직접 대화 - 에이전트 직접 호출"""
        try:
            # 선택된 에이전트 가져오기
            agent_info = self.individual_agents.get(agent_type)

            if not agent_info:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "error": f"에이전트 '{agent_type}'를 찾을 수 없습니다.",
                        }
                    )
                )
                return

            agent = agent_info["agent"]
            display_name = agent_info["display_name"]

            # 에이전트 시작 알림
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "individual_start",
                        "agent": agent_type,
                        "message": f"{display_name}와 개별 대화 시작...",
                        "mode": "individual",
                    }
                )
            )

            # MetricAnalyzeAgent와 실시간 스트리밍 대화
            try:
                # 단일 에이전트로 구성된 팀 생성
                single_agent_team = RoundRobinGroupChat(
                    participants=[agent],
                    termination_condition=MaxMessageTermination(
                        max_messages=self.MAX_INDIVIDUAL_MESSAGES
                    ),
                    max_turns=self.MAX_INDIVIDUAL_TURNS,
                )

                # 실시간 스트리밍을 위한 비동기 실행
                cancellation_token = CancellationToken()

                # 에이전트 실행을 백그라운드에서 시작
                execution_task = asyncio.create_task(
                    single_agent_team.run(
                        task=user_message, cancellation_token=cancellation_token
                    )
                )

                # 실시간 상태 업데이트 (스트리밍 효과)
                step_messages = [
                    "🔍 사용자 요청을 분석하고 있습니다...",
                    "📊 Prometheus 메트릭 도구를 준비하고 있습니다...",
                    "🔧 필수 시스템 메트릭을 수집하고 있습니다...",
                    "📈 메트릭 데이터를 분석하고 있습니다...",
                    "✨ 분석 결과를 정리하고 있습니다...",
                ]

                # 진행 상태를 실시간으로 전송
                for i, step_message in enumerate(step_messages):
                    if not execution_task.done():
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "individual_progress",
                                    "agent": agent_type,
                                    "display_name": display_name,
                                    "message": step_message,
                                    "step": i + 1,
                                    "total_steps": len(step_messages),
                                }
                            )
                        )
                        # 각 단계별 딜레이
                        await asyncio.sleep(self.STEP_DELAY_SECONDS)
                    else:
                        break

                # 에이전트 실행 완료 대기
                try:
                    task_result = await execution_task
                except Exception as exec_error:
                    raise exec_error

                # 최종 결과 처리
                if task_result.messages:
                    # 마지막 몇 개의 의미있는 메시지만 전송
                    meaningful_messages = []
                    for message in task_result.messages:
                        content_attr = getattr(message, "content", None)
                        if (
                            content_attr
                            and isinstance(content_attr, str)
                            and len(content_attr.strip())
                            > self.MIN_MEANINGFUL_MESSAGE_LENGTH
                        ):
                            meaningful_messages.append(content_attr)

                    # 의미있는 응답이 있으면 전송
                    if meaningful_messages:
                        # 가장 완성된 마지막 응답을 전송
                        final_response = meaningful_messages[-1]
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "individual_response",
                                    "agent": agent_type,
                                    "display_name": display_name,
                                    "response": final_response,
                                    "sequence": 1,
                                    "total": 1,
                                }
                            )
                        )
                    else:
                        # 의미있는 응답이 없으면 대체 메시지
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "individual_response",
                                    "agent": agent_type,
                                    "display_name": display_name,
                                    "response": "🤖 메트릭 분석이 완료되었습니다. Prometheus 도구를 사용하여 시스템 상태를 확인했습니다.",
                                    "sequence": 1,
                                    "total": 1,
                                }
                            )
                        )
                else:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "individual_response",
                                "agent": agent_type,
                                "display_name": display_name,
                                "response": "분석을 완료했으나 응답을 생성할 수 없습니다. 다시 시도해주세요.",
                                "sequence": 1,
                                "total": 1,
                            }
                        )
                    )

            except Exception as e:
                logger.error(f"Agent direct call error: {e}")
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "individual_response",
                            "agent": agent_type,
                            "display_name": display_name,
                            "response": f"에이전트 호출 중 오류가 발생했습니다: {str(e)}",
                            "sequence": 1,
                            "total": 1,
                        }
                    )
                )

            # 완료 알림
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "individual_complete",
                        "agent": agent_type,
                        "message": f"{display_name} 분석 완료 ✅",
                    }
                )
            )

        except Exception as e:
            logger.error(f"Individual agent chat error: {e}")
            await websocket.send_text(
                json.dumps(
                    {"type": "error", "error": f"개별 에이전트 채팅 오류: {str(e)}"}
                )
            )

    async def chat_with_agent(self, user_message: str) -> dict[str, Any]:
        """Multi-Agent 팀과 대화"""
        try:
            if not self.sre_workflow:
                await self.initialize_agent()

            if not self.sre_workflow:
                raise ValueError("Failed to initialize SRE Workflow")

            # SRE Workflow를 사용한 Multi-Agent 처리
            # 웹 채팅의 경우 고정된 namespace/resource 대신 일반적인 컨텍스트 사용
            event_data = {
                "type": "user_chat",
                "message": user_message,
                "timestamp": "now",
                "severity": "info",
            }

            # 웹 채팅에서는 namespace/resource_name을 사용자가 지정하지 않으므로 None으로 전달
            result = await self.sre_workflow.process_incident(
                event_data=event_data,
                namespace=None,  # 사용자가 지정하지 않음
                resource_name=None,  # 사용자가 지정하지 않음
            )

            # 응답 포맷 변환
            response = result.get("reasoning", "Multi-agent analysis completed")

            return {
                "success": True,
                "response": response,
                "agent_status": self._get_agent_status(result),
            }

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"죄송합니다. Multi-Agent 시스템에서 오류가 발생했습니다: {e}",
            }

    def _get_agent_status(self, workflow_result: dict[str, Any]) -> dict[str, Any]:
        """Multi-Agent 워크플로우 상태 정보"""
        if not self.sre_workflow:
            return {"initialized": False}

        try:
            agents_info = []
            if hasattr(self.sre_workflow, "agents"):
                for agent_name, agent in self.sre_workflow.agents.items():
                    agents_info.append(
                        {
                            "name": agent_name,
                            "type": agent.__class__.__name__,
                            "status": "active",
                        }
                    )

            return {
                "initialized": True,
                "workflow_type": "Multi-Agent SRE",
                "active_agents": agents_info,
                "decision": workflow_result.get("decision", "processing"),
                "confidence": workflow_result.get("confidence", 0.0),
            }
        except Exception as e:
            logger.warning(f"Failed to get agent status: {e}")
            return {"initialized": True, "status_error": str(e)}
