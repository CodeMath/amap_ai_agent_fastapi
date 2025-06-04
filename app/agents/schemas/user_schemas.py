from pydantic import BaseModel


class UserSignupRequest(BaseModel):
    """
    사용자 회원가입 요청 바디 스키마
    """
    username: str
    password: str