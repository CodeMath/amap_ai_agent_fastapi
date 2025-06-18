import pytest
from fastapi.testclient import TestClient

from app.agents.schemas.achivement_schemas import AchievementDTO

# 테스트용 에이전트 ID
TEST_AGENT_ID = "test-agent-456"


def test_get_user_achievements(client: TestClient):
    """사용자의 모든 업적 조회 테스트"""
    response = client.get("/api/achievements/list")
    assert response.status_code == 200
    achievements = response.json()
    assert isinstance(achievements, list)


def test_get_user_agent_achievements(client: TestClient):
    """사용자의 특정 에이전트 업적 조회 테스트"""
    response = client.get(f"/api/achievements/retrieve/{TEST_AGENT_ID}")
    assert response.status_code == 200
    achievements = response.json()
    assert isinstance(achievements, list)
