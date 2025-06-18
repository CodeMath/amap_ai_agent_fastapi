import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from pywebpush import WebPushException, webpush

from app.agents.core.d1_database import D1Database
from app.agents.core.user_manager import UserManager
from app.agents.schemas.user_schemas import SubscriptionIn

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


SECRET_KEY: str = "g34qytgarteh4w6uj46srtjnssw46iujsyjfgjh675wui5sryjf"
ALGORITHM: str = "HS256"

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


async def get_d1_database() -> D1Database:
    """D1Database 의존성 주입"""
    return D1Database()


async def get_user_manager() -> UserManager:
    """UserManager 의존성 주입"""
    return UserManager()


router = APIRouter(prefix="/push", tags=["push"])


@router.post("/{sub}/push", name="user_push")
async def user_push(
    sub: str, payload: dict, request: Request, db: D1Database = Depends(get_d1_database)
):
    """
    특정 사용자에게 웹 푸시 전송
    """
    # 동적으로 자신의 라우트를 사용하여 푸시 엔드포인트 생성
    try:
        subs = await db.get_subscriptions(sub)
        push_payload = {"user": sub, **payload}
    except Exception as e:
        logger.error(f"오류: {e}")
        raise HTTPException(status_code=400, detail=f"구독 정보 조회 중 오류: {e}")

    try:
        webpush(
            subscription_info=subs.model_dump(),
            data=json.dumps(push_payload),
            vapid_private_key=os.getenv("VAPID_PRIVATE_KEY"),
            vapid_claims={"sub": os.getenv("VAPID_SUBJECT")},
        )
        return {"message": "웹 푸시 전송 완료"}
    except WebPushException as e:
        logger.error(f"웹 푸시 전송 실패: {e}")
        raise HTTPException(status_code=500, detail="웹 푸시 전송 중 오류")


@router.get("/vapid_key", summary="VAPID 공개키 조회/구독을 위한")
async def get_vapid_public_key():
    """
    클라이언트가 Push 구독을 위해 VAPID 공개키를 조회합니다.
    """
    return {"publicKey": os.getenv("VAPID_PUBLIC_KEY")}


@router.post("/subscribe")
async def subscribe(
    subscription: SubscriptionIn,
    sub: str = Depends(get_sub_from_token),
    db: D1Database = Depends(get_d1_database),
):
    """
    브라우저 Push 구독 정보를 저장합니다.
    """
    try:
        await db.save_subscription(sub, subscription.endpoint, subscription.keys)
        logger.info(f"구독 정보 저장: user={sub}, endpoint={subscription.endpoint}")
    except Exception as e:
        logger.error(f"구독 저장 실패: {e}")
        raise HTTPException(status_code=500, detail="구독 저장 중 오류")
    return {"message": "구독 성공"}
