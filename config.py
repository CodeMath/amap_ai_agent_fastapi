from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    agent_sdk_url: AnyHttpUrl
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
