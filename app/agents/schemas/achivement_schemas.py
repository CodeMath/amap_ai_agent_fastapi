from typing import List

from pydantic import BaseModel

from app.agents.schemas.chat_schemas import AiAgentMessageDTO


class AchievementDTO(BaseModel):
    id: str  # 업적 아이디
    name: str  # 업적 이름
    description: str  # 업적 설명
    image: str  # 업적 이미지
    rarity: str  # 업적 등급 (common, rare, epic, legend)
    condition: str  # 업적 조건


class AchievementGeneratorOutput(BaseModel):
    chat_history: List[AiAgentMessageDTO]
    achievements: List[AchievementDTO]
