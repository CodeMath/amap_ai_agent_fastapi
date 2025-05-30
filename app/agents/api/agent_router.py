# app/api/agent_router.py
import logging
from typing import List
from fastapi import APIRouter
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from agents import RunConfig, Runner
from pydantic import ValidationError

from app.agents.core.agent_manager import AgentManager
from app.agents.schemas.agent_schemas import AgentDTO
from app.agents.schemas.chat_schemas import AgentRequestDTO, ChatMessageDTO
from app.agents.schemas.map_schemas import AgentMapDTO, MapDTO


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])
manager = AgentManager()


@router.get("/list", response_model=List[AgentDTO])
async def get_agent_list():
    """
    좌표 정보를 받아서, 근처 에이전트 리스트를 반환합니다.
    """
    try:
        # 좌표 정보를 받아서, 근처 에이전트 리스트를 반환합니다.
        # agents = await manager.filter_agents(req.latitude, req.longitude)
        # if not agents:
        #     return AgentMapDTO(
        #         map=MapDTO(
        #             latitude=req.latitude,
        #             longitude=req.longitude,
        #         ),
        #         agents=[],
        #     )
        # else:
        return await manager.list_agents()

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


@router.get("{agent_id}/chat-history/{sub}/")
async def get_chat_history(sub: str, agent_id: str):
    try:
        return await manager.get_chat_history(sub, agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")


@router.post("/run-stream")
async def run_main_agent_stream(req: AgentRequestDTO):
    """
    특정 에이전트를 호출해서 스트리밍 방식으로 응답을 반환합니다.
    """
    try:
        agent = await manager.load_agent(req.agent_id)
        if not agent:
            raise HTTPException(status_code=500, detail="메인 에이전트를 찾을 수 없습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")    

    async def event_generator():
        try:
            await manager.save_chat_history(ChatMessageDTO(
                agent_id=req.agent_id,
                sub=req.sub,
                role="user",
                content=req.data,
                context=None,
                response_id=None if req.response_id is None else req.response_id,
            ))

            result = Runner.run_streamed(
                agent,
                input=req.data,
                previous_response_id=req.response_id if req.response_id else None,
                run_config=RunConfig(
                    tracing_disabled=True,
                ),
            )

            response_id = None

            # 이벤트 스트리밍
            async for event in result.stream_events():
                logger.info(
                    f"-----*-----*-----*-----*\n{event}\n-----*-----*-----*-----*"
                )
                # 응답 ID 저장 (마지막 응답에서 사용)
                if event.type == "response.completed":
                    response_id = event.response.id
                    try:
                        await manager.save_chat_history(ChatMessageDTO(
                            agent_id=req.agent_id,
                            sub=req.sub,
                            role="assistant",
                            content=event.response.output.text,
                            context=None,
                            response_id=response_id,
                        ))
                    except Exception as e:
                        logger.error(f"채팅 기록 저장 중 오류 발생: {e}")

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

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
