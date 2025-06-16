import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt

from app.agents.core.achivement_manager import UserAchievements
from app.agents.schemas.achivement_schemas import AchievementDTO

SECRET_KEY = "g34qytgarteh4w6uj46srtjnssw46iujsyjfgjh675wui5sryjf"
ALGORITHM = "HS256"

# Lambda 환경에 맞는 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/achievments", tags=["achievments"])

user_achievement_manager = UserAchievements()

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


@router.get("/list", response_model=List[AchievementDTO])
async def get_achievements(sub: str = Depends(get_sub_from_token)):
    """
    사용자의 업적 리스트를 반환합니다.
    """
    try:
        achievements = await user_achievement_manager.get_achievements(sub)
        return achievements
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retrieve/{agent_id}", response_model=List[AchievementDTO])
async def get_achievements_by_agent_id(
    agent_id: str, sub: str = Depends(get_sub_from_token)
):
    """
    사용자의 특정 챗봇 업적 리스트를 반환합니다.
    """
    try:
        achievements = await user_achievement_manager.get_achievements_by_agent_id(
            sub, agent_id
        )
        return achievements
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
