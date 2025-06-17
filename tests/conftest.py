from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from main import app


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """동기식 테스트용 TestClient"""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """비동기 테스트용 AsyncClient"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
