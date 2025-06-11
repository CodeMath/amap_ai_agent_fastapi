from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class AgentToolDTO(BaseModel):
    name: str  # 도구 이름
    description: str  # 도구 설명
    parameters: List[str]  # 도구 파라미터


class AgentDTO(BaseModel):
    agent_id: str  # 에이전트 아이디
    name: str  # 에이전트 이름
    description: str  # 에이전트 설명
    prompt: str  # 에이전트 프롬프트
    thumbnail: Optional[str]  # 에이전트 썸네일
    tools: List[Optional[str]]  # 에이전트 도구
    model: str  # 에이전트 모델
    latitude: Decimal  # 위도
    longitude: Decimal  # 경도


class UpdatePromptDTO(BaseModel):
    prompt: str  # 에이전트 프롬프트


class AgentListDTO(BaseModel):
    agents: List[AgentDTO]  # 에이전트 리스트
