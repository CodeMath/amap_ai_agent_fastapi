import httpx
import datetime
import hashlib
import os
import logging
import uuid
from fastapi import Request, Depends, HTTPException
from typing import Any, Dict
from passlib.context import CryptContext
from app.agents.schemas.user_schemas import UserSignupRequest


# 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 비밀번호 해시 알고리즘(PBKDF2 + SHA256) 사용
pwd_context = CryptContext(schemes=["django_pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    평문 비밀번호가 해시된 비밀번호와 일치하는지 검증
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    비밀번호 해싱 (Django PBKDF2 + SHA256)
    """
    return pwd_context.hash(password)


class D1Database:
    def __init__(self):
        self.header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('D1_DATABASE_TOKEN')}"
        }
        self.url = os.getenv("D1_DATABASE_QUERY_URL")

    async def check_username_exists(self, username: str) -> int:
        """
        유저네임 중복 처리
        """
        sql = """
        SELECT COUNT(*) FROM user WHERE username = ?;
        """
        params = [username]

        logger.info(f"D1 유저네임 중복 처리 쿼리 실행: {sql}")

        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, headers=self.header, json={"sql": sql, "params": params})
            results = response.json()
            print(results)
            logger.info(f"D1 유저네임 중복 처리 쿼리 결과: {results['result'][0]['results'][0]['COUNT(*)']}")
            return results['result'][0]['results'][0]['COUNT(*)']

    async def user_signup(self, body: UserSignupRequest) -> Any:
        """
        유저: 삽입 쿼리 실행
        user 테이블
        sub(pk): 고유값 (uuid)
        username: 유저 이름
        password: 비밀번호 (sha256) 해시값 처리
        joined_at: 가입일 (timestamp) 자동 삽입
        refer_code: 추천코드( 랜덤 문자열: 8자 )
        """
        sub = str(uuid.uuid4())
        joined_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        refer_code = str(uuid.uuid4())[:8]
        hash_password = get_password_hash(body.password)

        sql = """
        INSERT INTO user (sub, username, password, joined_at, refer_code) VALUES (?, ?, ?, ?, ?);
        """
        params = [sub, body.username, hash_password, joined_at, refer_code]
        logger.info(f"D1 삽입 쿼리 파라미터: {params}")
        logger.info(f"D1 삽입 쿼리 실행: {sql}")
        # 유저네임 중복 처리
        if await self.check_username_exists(body.username) > 0:
            raise HTTPException(status_code=400, detail="이미 존재하는 유저네임입니다.")

        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, headers=self.header, json={"sql": sql, "params": params})

            return response.json()

    async def get_user_sub(self, username: str) -> Any:
        """
        유저 정보 조회
        """
        sql = """
        SELECT sub FROM user WHERE username = ?;
        """
        params = [username]

        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, headers=self.header, json={"sql": sql, "params": params})
            return response.json()['result'][0]['results'][0]['sub']

    async def get_user_info(self, username: str) -> Dict[str, Any]:
        """
        유저 정보 조회
        """
        sql = """
        SELECT sub, username, password FROM user WHERE username = ?;
        """
        params = [username]

        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, headers=self.header, json={"sql": sql, "params": params})
            return response.json()['result'][0]['results'][0]