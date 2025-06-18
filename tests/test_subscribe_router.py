import pytest
from fastapi.testclient import TestClient

from app.agents.schemas.user_schemas import (
    SubscriptionIn,  # Correct schema for request body
)

# Note: As per the task, tests for /api/push/{sub}/push and /api/push/vapid_key are skipped
# due to os.getenv() dependencies for VAPID keys.


def test_subscribe_success(client: TestClient):
    """
    Test successful subscription to push notifications.
    The client fixture handles mocked authentication, providing a 'test_user_id_from_router' sub.
    """
    subscription_data = {
        "endpoint": "http://0.0.0.0:8000/api/push/subscribe",
        "keys": {
            "p256dh": "BIPUL12DLfytvTajnryr2PRdAgXS3HGKiLqndGcJGabyhHheDEK3OMETdBPt8Qbm_wA_uN37EXNDTfbf_Q_3vP4=",
            "auth": "Bt2_n4WLS6awpcL4st9fXg==",
        },
    }
    # Validate that the payload matches SubscriptionIn (optional, Pydantic does this on server)
    # SubscriptionIn(**subscription_data)

    response = client.post("/api/push/subscribe", json=subscription_data)

    assert response.status_code == 200
    assert response.json() == {"message": "구독 성공"}


def test_subscribe_invalid_payload_missing_endpoint(client: TestClient):
    """
    Test subscription with missing endpoint in payload.
    """
    invalid_data = {
        "keys": {
            "p256dh": "BIPUL12DLfytvTajnryr2PRdAgXS3HGKiLqndGcJGabyhHheDEK3OMETdBPt8Qbm_wA_uN37EXNDTfbf_Q_3vP4=",
            "auth": "Bt2_n4WLS6awpcL4st9fXg==",
        }
    }
    response = client.post("/api/push/subscribe", json=invalid_data)
    assert (
        response.status_code == 422
    )  # FastAPI's default for Pydantic validation errors


def test_subscribe_invalid_payload_missing_keys(client: TestClient):
    """
    Test subscription with missing keys in payload.
    """
    invalid_data = {"endpoint": "https://example.com/push-endpoint/anotherone"}
    response = client.post("/api/push/subscribe", json=invalid_data)
    assert response.status_code == 422


def test_subscribe_invalid_payload_missing_p256dh_in_keys(client: TestClient):
    """
    Test subscription with missing p256dh within keys.
    """
    invalid_data = {
        "endpoint": "https://example.com/push-endpoint/yetanother",
        "keys": {"auth": "Bt2_n4WLS6awpcL4st9fXg=="},
    }
    response = client.post("/api/push/subscribe", json=invalid_data)
    assert response.status_code == 422


def test_subscribe_invalid_payload_missing_auth_in_keys(client: TestClient):
    """
    Test subscription with missing auth within keys.
    """
    invalid_data = {
        "endpoint": "https://example.com/push-endpoint/onemore",
        "keys": {
            "p256dh": "BIPUL12DLfytvTajnryr2PRdAgXS3HGKiLqndGcJGabyhHheDEK3OMETdBPt8Qbm_wA_uN37EXNDTfbf_Q_3vP4="
        },
    }
    response = client.post("/api/push/subscribe", json=invalid_data)
    assert response.status_code == 422


def test_subscribe_empty_payload(client: TestClient):
    """
    Test subscription with an empty JSON payload.
    """
    response = client.post("/api/push/subscribe", json={})
    assert response.status_code == 422
