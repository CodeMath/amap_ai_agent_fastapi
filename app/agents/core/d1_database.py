import datetime
import logging
import os
import uuid
from typing import Any, Dict, List

import httpx
from fastapi import HTTPException
from passlib.context import CryptContext

from app.agents.schemas.user_schemas import SubscriptionIn, UserSignupRequest, VapidKey

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
            "Authorization": f"Bearer {os.getenv('D1_DATABASE_TOKEN')}",
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
            response = await client.post(
                self.url, headers=self.header, json={"sql": sql, "params": params}
            )
            results = response.json()
            print(results)
            logger.info(
                f"D1 유저네임 중복 처리 쿼리 결과: {results['result'][0]['results'][0]['COUNT(*)']}"
            )
            return results["result"][0]["results"][0]["COUNT(*)"]

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
            response = await client.post(
                self.url, headers=self.header, json={"sql": sql, "params": params}
            )

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
            response = await client.post(
                self.url, headers=self.header, json={"sql": sql, "params": params}
            )
            return response.json()["result"][0]["results"][0]["sub"]

    async def get_user_info(self, username: str) -> Dict[str, Any]:
        """
        유저 정보 조회
        """
        sql = """
        SELECT sub, username, password FROM user WHERE username = ?;
        """
        params = [username]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.url, headers=self.header, json={"sql": sql, "params": params}
            )
            return response.json()["result"][0]["results"][0]

    async def check_subscription_exists(self, sub: str) -> int:
        """
        구독 정보 조회
        """
        sql = """
        SELECT COUNT(*) FROM subscription WHERE sub = ?;
        """
        params = [sub]
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.url, headers=self.header, json={"sql": sql, "params": params}
            )

            # 응답 상태 코드 확인
            if response.status_code != 200:
                logger.error(
                    f"D1 DB 쿼리 실패: {response.status_code} - {response.text}"
                )
                raise HTTPException(status_code=500, detail="데이터베이스 쿼리 실패")

            try:
                result = response.json()
                if "result" not in result or not result["result"]:
                    logger.error(f"D1 DB 응답 형식 오류: {result}")
                    return 0

                results = result["result"][0]["results"]
                if not results:
                    return 0

                return results[0]["COUNT(*)"]
            except (KeyError, IndexError) as e:
                logger.error(f"D1 DB 응답 파싱 오류: {e}, 응답: {response.text}")
                return 0

    async def save_subscription(self, sub: str, endpoint: str, keys: dict[str, str]):
        """
        구독 정보 저장
        sub: pk (uuid)
        endpoint: 구독 엔드포인트
        auth: 인증 키
        p256dh: 퍼블릭 키
        created_at: 생성일 (timestamp) 자동 삽입

        프라이머키 기준으로 중복해서 삽입하지 않도록 처리
        """
        # 프라이머키 기준으로 중복해서 삽입하지 않도록 처리
        if await self.check_subscription_exists(sub):
            raise HTTPException(
                status_code=400, detail="이미 존재하는 구독 정보입니다."
            )

        sql = """
        INSERT INTO subscription (sub, endpoint, auth, p256dh, created_at) VALUES (?, ?, ?, ?, ?);
        """
        params = [
            sub,
            endpoint,
            keys["auth"],
            keys["p256dh"],
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.url, headers=self.header, json={"sql": sql, "params": params}
            )

            # 응답 상태 코드 확인
            if response.status_code != 200:
                logger.error(
                    f"D1 DB 저장 실패: {response.status_code} - {response.text}"
                )
                raise HTTPException(status_code=500, detail="구독 정보 저장 실패")

            try:
                return response.json()
            except Exception as e:
                logger.error(f"D1 DB 저장 응답 파싱 오류: {e}, 응답: {response.text}")
                raise HTTPException(status_code=500, detail="구독 정보 저장 실패")

    async def get_subscriptions(self, sub: str) -> SubscriptionIn:
        """
        DB에서 sub에 해당하는 구독 정보를 조회합니다.
        """
        sql = """
        SELECT endpoint, auth, p256dh FROM subscription WHERE sub = ?;
        """
        params = [sub]
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.url, headers=self.header, json={"sql": sql, "params": params}
            )
            results = response.json()["result"][0]["results"]

            if not results:
                raise HTTPException(
                    status_code=404, detail="구독 정보를 찾을 수 없습니다."
                )

            result = results[0]
            return SubscriptionIn(
                endpoint=result["endpoint"],
                keys=VapidKey(
                    auth=result["auth"],
                    p256dh=result["p256dh"],
                ),
            )
