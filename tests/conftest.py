import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.agents.api.achievement_router import (
    get_sub_from_token as achievement_get_sub_from_token,
)
from app.agents.api.agent_router import get_sub_from_token as agent_get_sub_from_token
from app.agents.api.subsrbe_router import (
    get_sub_from_token as subsrbe_get_sub_from_token,
)
from main import app, get_current_user


# Mock D1Database for testing
class MockD1Database:
    def __init__(self):
        self.subscriptions = {}

    async def check_subscription_exists(self, sub: str) -> int:
        return 1 if sub in self.subscriptions else 0

    async def save_subscription(self, sub: str, endpoint: str, keys):
        self.subscriptions[sub] = {
            "endpoint": endpoint,
            "auth": keys.auth,
            "p256dh": keys.p256dh,
        }
        return {"success": True}

    async def get_subscriptions(self, sub: str):
        if sub not in self.subscriptions:
            raise Exception("구독 정보를 찾을 수 없습니다.")

        from app.agents.schemas.user_schemas import SubscriptionIn, VapidKey

        return SubscriptionIn(
            endpoint=self.subscriptions[sub]["endpoint"],
            keys=VapidKey(
                auth=self.subscriptions[sub]["auth"],
                p256dh=self.subscriptions[sub]["p256dh"],
            ),
        )


# Mock UserManager for testing
class MockUserManager:
    async def send_web_push(self, endpoint: str, payload: dict):
        return {"success": True}


@pytest.fixture
def mock_d1_database(monkeypatch):
    """Mock D1Database for testing"""
    mock_db = MockD1Database()

    # Patch the D1Database class
    from app.agents.core import d1_database

    monkeypatch.setattr(d1_database, "D1Database", lambda: mock_db)

    return mock_db


@pytest.fixture
def mock_user_manager(monkeypatch):
    """Mock UserManager for testing"""
    mock_manager = MockUserManager()

    # Patch the UserManager class
    from app.agents.core import user_manager

    monkeypatch.setattr(user_manager, "UserManager", lambda: mock_manager)

    return mock_manager


@pytest.fixture
def client(mock_d1_database, mock_user_manager) -> Generator:
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client(
    mock_d1_database, mock_user_manager
) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# Mock authentication functions
def mock_get_sub_from_token():
    return "test_user_id_from_router"


def mock_get_d1_database():
    return MockD1Database()


def mock_get_user_manager():
    return MockUserManager()


# Override the authentication dependencies
app.dependency_overrides[agent_get_sub_from_token] = mock_get_sub_from_token
app.dependency_overrides[achievement_get_sub_from_token] = mock_get_sub_from_token
app.dependency_overrides[subsrbe_get_sub_from_token] = mock_get_sub_from_token
app.dependency_overrides[get_current_user] = mock_get_sub_from_token

# Override the database dependencies
from app.agents.api.subsrbe_router import get_d1_database, get_user_manager

app.dependency_overrides[get_d1_database] = mock_get_d1_database
app.dependency_overrides[get_user_manager] = mock_get_user_manager
