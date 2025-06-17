from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    agent_sdk_url: AnyHttpUrl
    log_level: str = "INFO"
    VAPID_PRIVATE_KEY: str
    VAPID_PUBLIC_KEY: str
    VAPID_SUBJECT: str = "mailto:jadeocon2655@gmail.com"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
