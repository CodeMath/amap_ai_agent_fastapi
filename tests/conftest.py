from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from main import app, get_current_user
# Import all versions of get_sub_from_token
from app.agents.api.achievement_router import get_sub_from_token as achievement_get_sub_from_token
from app.agents.api.agent_router import get_sub_from_token as agent_get_sub_from_token
from app.agents.api.subsrbe_router import get_sub_from_token as subsrbe_get_sub_from_token


def mock_get_current_user():
    return {"sub": "test_user_id", "username": "testuser", "scopes": []}

def mock_get_sub_from_token(): # This mock will be used for all three
    return "test_user_id_from_router"

@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """동기식 테스트용 TestClient"""
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[achievement_get_sub_from_token] = mock_get_sub_from_token
    app.dependency_overrides[agent_get_sub_from_token] = mock_get_sub_from_token
    app.dependency_overrides[subsrbe_get_sub_from_token] = mock_get_sub_from_token
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """비동기 테스트용 AsyncClient"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
