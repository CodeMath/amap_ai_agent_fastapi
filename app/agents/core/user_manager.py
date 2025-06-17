import logging

import httpx

logger = logging.getLogger(__name__)


class UserManager:

    async def send_web_push(self, push_endpoint: str, payload: dict):
        async with httpx.AsyncClient() as client:
            try:
                await client.post(push_endpoint, json=payload)
                logger.info(f"웹 푸시 전송 성공: {payload}")
            except Exception as e:
                logger.error(f"웹 푸시 전송 실패: {e}")
