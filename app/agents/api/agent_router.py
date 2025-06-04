# app/api/agent_router.py
import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from agents import RunConfig, Runner
from pydantic import ValidationError

from app.agents.core.agent_manager import AgentManager
from app.agents.schemas.agent_schemas import AgentDTO
from app.agents.schemas.chat_schemas import AgentRequestDTO, ChatMessageDTO
from app.agents.schemas.map_schemas import AgentMapDTO, MapDTO

SECRET_KEY = "g34qytgarteh4w6uj46srtjnssw46iujsyjfgjh675wui5sryjf"
ALGORITHM = "HS256"

# Lambda 환경에 맞는 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/agents", tags=["agents"])
manager = AgentManager()

security = HTTPBearer()


async def get_sub_from_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
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


@router.get("/start/{agent_id}")
async def get_agent(agent_id: str):
    try:
        return await manager.get_agent(agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")

# Agent 추가, 수정, 삭제 API
@router.post("/register")
async def register_agent(req: AgentDTO):
    try:
        return await manager.register_agent(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")

@router.put("/update_prompt/{agent_id}")
async def update_agent_prompt(agent_id: str, prompt: str):
    try:
        return await manager.update_agent_prompt(agent_id, prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")

@router.delete("/delete/{agent_id}")
async def delete_agent(agent_id: str):
    try:
        return await manager.delete_agent(agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")


@router.get("/{agent_id}/chat-history")
async def get_chat_history(agent_id: str, sub: str = Depends(get_sub_from_token)):
    try:
        history = await manager.get_chat_history(sub, agent_id)
        logger.info(f"history: {history}")
        return history
    except Exception as e:
        logger.error(f"get_chat_history error: {e}")
        raise HTTPException(status_code=500, detail=f"{e}")


@router.post("/run-stream")
async def run_main_agent_stream(req: AgentRequestDTO, sub: str = Depends(get_sub_from_token)):
    """
    특정 에이전트를 호출해서 스트리밍 방식으로 응답을 반환합니다.
    """
    try:
        agent = await manager.load_agent(req.agent_id)
        chat_history = await manager.get_chat_history(sub, req.agent_id)
        if not agent:
            raise HTTPException(status_code=500, detail="메인 에이전트를 찾을 수 없습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")    

    async def event_generator():
        response_context = ""
        try:
            await manager.save_chat_history(ChatMessageDTO(
                agent_id=req.agent_id,
                sub=sub,
                role="user",
                content=req.data,
                context=None,
                response_id=None if req.response_id is None else req.response_id,
            ))

            result = Runner.run_streamed(
                agent,
                input=str(chat_history + [{"role": "user", "content": req.data}]),
                previous_response_id=req.response_id if req.response_id else None,
                run_config=RunConfig(
                    tracing_disabled=True,
                ),
            )
            save_chat = False
            response_id = None

            # 이벤트 스트리밍
            async for event in result.stream_events():
                logger.info(
                    f"-----*-----*-----*-----*\n{event}\n-----*-----*-----*-----*"
                )
                # 응답 ID 저장 (마지막 응답에서 사용)
                try:
                    response_id = event.data.response.id
                    logger.info(f">>>>> response_id: {response_id}")
                    try:
                        if not save_chat:
                            save_chat = True
                            await manager.save_chat_history(ChatMessageDTO(
                                agent_id=req.agent_id,
                                sub=sub,
                                role="assistant",
                                content=event.response.output.text,
                                context=None,
                                response_id=response_id,
                            ))
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
        
        await manager.save_chat_history(ChatMessageDTO(
            agent_id=req.agent_id,
            sub=sub,
            role="assistant",
            content=response_context,
            context=None,
            response_id=response_id,
        ))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
