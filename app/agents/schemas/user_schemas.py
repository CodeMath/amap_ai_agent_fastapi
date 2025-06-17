from pydantic import BaseModel


class UserSignupRequest(BaseModel):
    """
    사용자 회원가입 요청 바디 스키마
    """

    username: str
    password: str


class VapidKey(BaseModel):
    """
    VAPID 키 스키마
    """

    auth: str
    p256dh: str


class SubscriptionIn(BaseModel):
    """
    구독을 위한 요청 바디 스키마
    """

    endpoint: str
    keys: VapidKey
