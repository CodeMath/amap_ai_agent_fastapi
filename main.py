import logging
from typing import Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import JWTError, jwt

from dependencies import init_app
from app.agents.api.agent_router import router as agent_router

SECRET_KEY: str = "g34qytgarteh4w6uj46srtjnssw46iujsyjfgjh675wui5sryjf"
ALGORITHM: str = "HS256"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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

class JwtUserForm(BaseModel):
    """
    JWT 발급을 위한 사용자 정보 입력 폼
    """
    sub: str
    password: str

public_router = APIRouter(tags=["public"])

@public_router.post("/login", dependencies=[])
async def login(req: JwtUserForm) -> Dict[str, str]:
    """
    JWT를 발급하는 로그인 엔드포인트
    """
    if req.sub != "codemath" or req.password != "!Q2w3e4r5t":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자 정보가 올바르지 않습니다.",
        )
    access_token: str = jwt.encode({"sub": req.sub}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": access_token, "token_type": "Bearer"}

protected_router = APIRouter(
    prefix="/api",
    dependencies=[Depends(get_current_user)],
)
protected_router.include_router(agent_router)

app = FastAPI(on_startup=[init_app])
app.include_router(public_router)
app.include_router(protected_router)