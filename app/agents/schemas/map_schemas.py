from typing import List
from decimal import Decimal
from pydantic import BaseModel

from app.agents.schemas.agent_schemas import AgentDTO


class MapDTO(BaseModel):
    latitude: Decimal  # 위도
    longitude: Decimal  # 경도


class AgentMapDTO(BaseModel):
    map: MapDTO  # 맵 정보
    agents: List[AgentDTO]  # 맵 에이전트 리스트
