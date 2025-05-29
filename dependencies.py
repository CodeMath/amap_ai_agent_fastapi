from fastapi import Depends

from config import Settings
from loggings import setup_logging


def get_settings() -> Settings:
    return Settings()


def init_app(settings: Settings = Depends(get_settings)) -> None:
    setup_logging(settings)
