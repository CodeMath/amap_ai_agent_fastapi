import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from mangum import Mangum

from app.agents.api.achievement_router import router as achievement_router
from app.agents.api.agent_router import router as agent_router
from app.agents.api.user_router import public_router
from dependencies import init_app

SECRET_KEY: str = "g34qytgarteh4w6uj46srtjnssw46iujsyjfgjh675wui5sryjf"
ALGORITHM: str = "HS256"

# Lambda 환경에 맞는 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 로그 포맷 설정
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

# 기존 로거들도 동일한 레벨로 설정
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).setLevel(logging.INFO)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Authorization 헤더의 JWT 토큰을 검증하여 사용자 정보를 반환합니다.
    """
    token: str = credentials.credentials
    try:
        payload: Dict[str, Any] = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="잘못된 인증 토큰입니다.",
            )
        logger.info(f"인증된 사용자 ID: {user_id}")
        return payload
    except JWTError as e:
        logger.error(f"JWT 검증 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 검증 실패",
        )


app = FastAPI(on_startup=[init_app])

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # 실제 운영 환경에서는 특정 도메인만 허용하도록 수정해야 합니다
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*", "Authorization", "Content-Type"],
    expose_headers=["Authorization"],
    max_age=3600,
)

# API 라우터 등록
protected_router = APIRouter(
    prefix="/api",
    dependencies=[Depends(get_current_user)],
)
protected_router.include_router(agent_router)
protected_router.include_router(achievement_router)

# URL 라우터 등록
app.include_router(protected_router)
# 회원가입/로그인 URL 라우터
app.include_router(public_router)

# AWS Lambda 환경에 맞는 람다 핸들러 설정
handler = Mangum(app)
