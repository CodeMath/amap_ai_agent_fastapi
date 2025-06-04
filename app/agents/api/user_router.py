import hashlib
import logging
from fastapi import APIRouter, status, Depends, HTTPException
from passlib.context import CryptContext

from typing import Any, Dict
from app.agents.schemas.user_schemas import UserSignupRequest
from app.agents.core.d1_database import D1Database, verify_password
from jose import jwt

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


SECRET_KEY: str = "g34qytgarteh4w6uj46srtjnssw46iujsyjfgjh675wui5sryjf"
ALGORITHM: str = "HS256"
# 비밀번호 해시 알고리즘(PBKDF2 + SHA256) 사용
pwd_context = CryptContext(schemes=["django_pbkdf2_sha256"], deprecated="auto")

public_router = APIRouter(prefix="/users", tags=["users"])


@public_router.post("/signup")
async def signup(body: UserSignupRequest):
    """
    사용자 회원가입
    """
    # D1Database 인스턴스 생성
    d1_db = D1Database()
    try:
        # 중복 체크
        validate_username = await d1_db.check_username_exists(body.username)
        if validate_username > 0:
            raise HTTPException(status_code=400, detail="이미 존재하는 유저네임입니다.")

        # 회원가입
        result = await d1_db.user_signup(body)
        logger.info(f"회원가입 완료: {result}")
        user_sub = await d1_db.get_user_sub(body.username)
        return {"username": body.username, "sub": user_sub}
    except Exception as e:
        logger.error(f"회원가입 중 예외 발생: {e}")
        # username 중복 등 오류 처리
        raise HTTPException(status_code=400, detail=f"{e} 회원가입에 실패했습니다.")


@public_router.post("/signin")
async def signin(req: UserSignupRequest) -> Dict[str, str]:
    """
    JWT를 발급하는 로그인 엔드포인트
    """
    d1_db = D1Database()
    try:
        user_info = await d1_db.get_user_info(req.username)
        if not user_info or not verify_password(req.password, user_info['password']):
            raise HTTPException(status_code=400, detail="비밀번호가 일치하지 않습니다.")
    except Exception as e:
        logger.error(f"로그인 중 예외 발생: {e}")
        raise HTTPException(status_code=400, detail=f"{e} 로그인에 실패했습니다.")

    access_token: str = jwt.encode({"sub": user_info['sub']}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": access_token, "token_type": "Bearer", "sub": user_info['sub']}
