import pytest
from fastapi.testclient import TestClient

from app.agents.schemas.achivement_schemas import AchievementDTO
from app.main import app

client = TestClient(app)

# 테스트용 업적 데이터
TEST_ACHIEVEMENT = {
    "id": "test-achievement-1",
    "name": "테스트 업적",
    "description": "테스트 업적 설명",
    "condition": "테스트 조건",
    "image": "테스트 이미지 URL",
    "rarity": "Common",
}

# 테스트용 사용자 ID
TEST_USER_ID = "test-user-123"
# 테스트용 에이전트 ID
TEST_AGENT_ID = "test-agent-456"


def test_get_user_achievements():
    """사용자의 모든 업적 조회 테스트"""
    response = client.get(f"/achievements/{TEST_USER_ID}")
    assert response.status_code == 200
    achievements = response.json()
    assert isinstance(achievements, list)


def test_get_user_agent_achievements():
    """사용자의 특정 에이전트 업적 조회 테스트"""
    response = client.get(f"/achievements/{TEST_USER_ID}/{TEST_AGENT_ID}")
    assert response.status_code == 200
    achievements = response.json()
    assert isinstance(achievements, list)


def test_add_achievement_to_user():
    """사용자 업적 추가 테스트"""
    achievement = AchievementDTO(**TEST_ACHIEVEMENT)
    response = client.post(
        f"/achievements/{TEST_USER_ID}/{TEST_AGENT_ID}", json=[achievement.model_dump()]
    )
    assert response.status_code == 200
    result = response.json()
    assert result.get("message") == "success"


def test_add_duplicate_achievement():
    """중복 업적 추가 테스트"""
    achievement = AchievementDTO(**TEST_ACHIEVEMENT)
    # 첫 번째 추가
    client.post(
        f"/achievements/{TEST_USER_ID}/{TEST_AGENT_ID}", json=[achievement.model_dump()]
    )
    # 두 번째 추가 (중복)
    response = client.post(
        f"/achievements/{TEST_USER_ID}/{TEST_AGENT_ID}", json=[achievement.model_dump()]
    )
    assert response.status_code == 200
    result = response.json()
    assert "이미 달성한 업적입니다" in result.get("message", "")


def test_add_multiple_achievements():
    """여러 업적 동시 추가 테스트"""
    achievements = [
        {
            "id": f"test-achievement-{i}",
            "name": f"테스트 업적 {i}",
            "description": f"테스트 업적 설명 {i}",
            "condition": f"테스트 조건 {i}",
            "image": f"테스트 이미지 URL {i}",
            "rarity": "Common",
        }
        for i in range(3)
    ]
    response = client.post(
        f"/achievements/{TEST_USER_ID}/{TEST_AGENT_ID}", json=achievements
    )
    assert response.status_code == 200
    result = response.json()
    assert result.get("message") == "success"


@pytest.mark.asyncio
async def test_achievement_limit():
    """업적 개수 제한 테스트"""
    # 31개의 업적 생성
    achievements = [
        {
            "id": f"test-achievement-{i}",
            "name": f"테스트 업적 {i}",
            "description": f"테스트 업적 설명 {i}",
            "condition": f"테스트 조건 {i}",
            "image": f"테스트 이미지 URL {i}",
            "rarity": "Common",
        }
        for i in range(31)
    ]
    response = client.post(
        f"/achievements/{TEST_USER_ID}/{TEST_AGENT_ID}", json=achievements
    )
    assert response.status_code == 200
    result = response.json()
    assert "업적이 30개만 추가됩니다" in result.get("message", "")
