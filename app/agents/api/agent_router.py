# app/api/agent_router.py
import asyncio
import logging
import os
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from pydantic import ValidationError

from agents import RunConfig, Runner
from app.agents.core.achivement_manager import AgentAchievements
from app.agents.core.agent_manager import AgentManager
from app.agents.core.d1_database import D1Database
from app.agents.core.user_manager import UserManager
from app.agents.schemas.achivement_schemas import (
    AchievementDTO,
    AchievementGeneratorOutput,
)
from app.agents.schemas.agent_schemas import AgentDTO, UpdatePromptDTO
from app.agents.schemas.chat_schemas import (
    AgentRequestDTO,
    AiAgentMessageDTO,
    ChatListDTO,
    ChatMessageDTO,
)
from app.agents.schemas.user_schemas import SubscriptionIn

SECRET_KEY = "g34qytgarteh4w6uj46srtjnssw46iujsyjfgjh675wui5sryjf"
ALGORITHM = "HS256"

# Lambda 환경에 맞는 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/agents", tags=["agents"])
manager = AgentManager()
achievement_manager = AgentAchievements()

security = HTTPBearer()


async def get_sub_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except Exception as e:
        raise HTTPException(status_code=401, detail="인증에 실패했습니다.")


@router.get("/list", response_model=List[AgentDTO])
async def get_agent_list(latitude: float = -90, longitude: float = -180):
    """
    좌표 정보를 받아서, 근처 에이전트 리스트를 반환합니다.
    latitude: 위도( 기본값: -90 )
    longitude: 경도( 기본값: -180 )
    현재 위치의 위도/경도 값을 기반으로 Agent 리스트를 반환합니다.

    만약 위/경도 값이 주어지지 않거나, 기본값인 경우 전체 리스트를 반환합니다.
    """
    try:
        if latitude == -90 and longitude == -180:
            agents = await manager.list_agents()
        else:
            agents = await manager.filter_agents(latitude, longitude)
        logger.info(f"agents: {agents}")
        return agents

    except ValidationError as exc:
        print(repr(exc.errors()))
        raise HTTPException(status_code=500, detail=f"{exc.errors()[0]['type']}")
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"{e}")


@router.get("/start/{agent_id}", response_model=AgentDTO)
async def get_agent(agent_id: str):
    try:
        return await manager.get_agent(agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")


# Agent 추가, 수정, 삭제 API
@router.post("/register", response_model=AgentDTO)
async def register_agent(req: AgentDTO):
    try:
        return await manager.register_agent(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")


@router.put("/{agent_id}/update-prompt", response_model=AgentDTO)
async def update_agent_prompt(agent_id: str, req: UpdatePromptDTO):
    try:
        return await manager.update_agent_prompt(agent_id, req.prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")


@router.delete("/{agent_id}/delete")
async def delete_agent(agent_id: str):
    try:
        return await manager.delete_agent(agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")


@router.get("/{agent_id}/chat-history", response_model=List[AiAgentMessageDTO])
async def get_chat_history(agent_id: str, sub: str = Depends(get_sub_from_token)):
    try:
        history = await manager.get_chat_history(sub, agent_id)
        logger.info(f"history: {history}")
        return history
    except Exception as e:
        logger.error(f"get_chat_history error: {e}")
        raise HTTPException(status_code=500, detail=f"{e}")


@router.get("/chat/list", response_model=List[ChatListDTO])
async def get_chat_list(sub: str = Depends(get_sub_from_token)):
    try:
        return await manager.get_chat_list(sub)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")


@router.delete("/{agent_id}/delete-history")
async def delete_agent_history(agent_id: str, sub: str = Depends(get_sub_from_token)):
    try:
        result = await manager.delete_agent_history(sub, agent_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")


@router.post("/{agent_id}/add-achievements")
async def add_achievement_to_agent(agent_id: str, req: List[AchievementDTO]):
    try:
        return await manager.add_achievement_to_agent(agent_id, req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")


@router.post("/run-stream")
async def run_main_agent_stream(
    req: AgentRequestDTO, sub: str = Depends(get_sub_from_token)
):
    """
    특정 에이전트를 호출해서 스트리밍 방식으로 응답을 반환합니다.
    """
    try:
        agent = await manager.load_agent(req.agent_id)
        chat_history = await manager.get_chat_history(sub, req.agent_id)
        if not agent:
            raise HTTPException(
                status_code=500, detail="메인 에이전트를 찾을 수 없습니다."
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")

    async def event_generator():
        response_context = ""
        if req.response_id is None:
            response_id = None
        else:
            response_id = req.response_id
        try:
            await manager.save_chat_history(
                ChatMessageDTO(
                    agent_id=req.agent_id,
                    sub=sub,
                    role="user",
                    content=req.data,
                    context=None,
                    response_id=response_id,
                )
            )

            # 채팅 히스토리를 적절한 형식으로 변환
            formatted_history = []
            for msg in chat_history:
                formatted_history.append({"role": msg.role, "content": msg.content})
            formatted_history.append({"role": "user", "content": req.data})

            result = Runner.run_streamed(
                agent,
                input=formatted_history,
                previous_response_id=req.response_id if req.response_id else None,
                run_config=RunConfig(
                    tracing_disabled=True,
                ),
            )
            save_chat = False

            # 이벤트 스트리밍
            async for event in result.stream_events():
                # logger.info(
                #     f"-----*-----*-----*-----*\n{event}\n-----*-----*-----*-----*"
                # )
                # 응답 ID 저장 (마지막 응답에서 사용)
                try:
                    if response_id is None:
                        response_id = event.data.response.id
                    else:
                        response_id = req.response_id
                    logger.info(
                        f"-----*-----*-----*-----*\n{event}\n-----*-----*-----*-----*"
                    )
                    try:
                        if not save_chat:
                            save_chat = True
                            await manager.save_chat_history(
                                ChatMessageDTO(
                                    agent_id=req.agent_id,
                                    sub=sub,
                                    role="assistant",
                                    content=event.response.output.text,
                                    context=None,
                                    response_id=response_id,
                                )
                            )
                            yield f"data: RESPONSE_ID:{response_id}\n\n"

                    except Exception as e:
                        pass
                except Exception as e:
                    pass

                # 텍스트 델타 이벤트만 클라이언트에 전송
                if event.type == "raw_response_event":
                    try:
                        if event.data.type == "response.output_text.delta":
                            if event.data.delta:
                                logger.info(f"{event.data.delta}")
                                if "\n" in event.data.delta:
                                    yield "data: <br><br>\n\n"
                                else:
                                    yield f"data: {event.data.delta}\n\n"

                                response_context += event.data.delta

                    except Exception:
                        pass

            # 스트림 완료 후 응답 ID 전송 (클라이언트가 다음 요청에 사용할 수 있도록)
            if response_id:
                yield f"data: RESPONSE_ID:{response_id}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"스트리밍 중 오류 발생: {e}")
            yield f"data: ERROR:{str(e)}\n\n"
            yield "data: [RETRY]\n\n]"
            yield "data: [DONE]\n\n"

        await manager.save_chat_history(
            ChatMessageDTO(
                agent_id=req.agent_id,
                sub=sub,
                role="assistant",
                content=response_context,
                context=None,
                response_id=response_id,
            )
        )
        # 최종 저장 이후 업적 판단 로직 추가
        asyncio.create_task(
            process_achievements(
                achievement_manager=achievement_manager,
                manager=manager,
                sub=sub,
                agent_id=req.agent_id,
                formatted_history=formatted_history,
            )
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def process_achievements(
    achievement_manager, manager, sub: str, agent_id: str, formatted_history: List[Dict]
):
    """업적 판단 및 저장을 비동기로 처리"""
    try:
        if achievement_list := await achievement_manager.judge_achievements(
            agent_id, formatted_history
        ):
            await manager.add_achievement_to_user(sub, agent_id, achievement_list)
    except Exception as e:
        logger.error(f"업적 처리 중 오류 발생: {str(e)}")


@router.post(
    "/{agent_id}/generate-achievements", response_model=AchievementGeneratorOutput
)
async def generate_achievements(agent_id: str, sub: str = Depends(get_sub_from_token)):
    try:
        return await achievement_manager.generate_chat_and_achievements(agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")
