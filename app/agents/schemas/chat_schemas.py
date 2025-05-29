from typing import Any, Optional

from pydantic import BaseModel

# Chat 요청, 응답 베이스 모델


class ChatMessageDTO(BaseModel):
    agent_id: str  # 에이전트 아이디
    role: str  # 메시지 역할 (user, assistant)
    sub: str  # 사용자 uuid
    content: str  # 메시지 내용
    context: Any  # 이미지 및 미디어 컨텍스트
    timestamp: Optional[str] = None  # 메시지 생성 시간
    response_id: Optional[str] = None  # 이전 응답 id


class AiAgentMessageDTO(BaseModel):
    role: str  # 메시지 역할 (user, assistant)
    content: str  # 메시지 내용


class AgentRequestDTO(BaseModel):
    sub: str  # 사용자 uuid
    agent_id: str  # 에이전트 아이디
    data: Any  # 메시지 내용
    response_id: Optional[str] = None  # 이전 응답 id


class AgentResponseDTO(BaseModel):
    content: str  # 에이전트 메시지 내용
    context: Any  # 이미지 및 미디어 컨텍스트


class AgentAPIResponseDTO(BaseModel):
    data: AgentResponseDTO
    response_id: Optional[str] = None  # 이전 응답 id