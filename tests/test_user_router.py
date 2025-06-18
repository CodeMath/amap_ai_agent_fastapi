import pytest
from fastapi.testclient import TestClient
from app.agents.schemas.user_schemas import UserSignupRequest # UserSignupRequest might not be directly used if tests pass dicts
import uuid

# Helper function for unique usernames
def generate_unique_username():
    return f"testuser_{uuid.uuid4().hex[:8]}"

# Tests for POST /users/signup
def test_signup_success(client: TestClient):
    username = generate_unique_username()
    password = "testpassword123"
    response = client.post("/users/signup", json={"username": username, "password": password})
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == username
    assert "sub" in data
    assert uuid.UUID(data["sub"], version=4) # Check if 'sub' is a valid UUID

def test_signup_username_already_exists(client: TestClient):
    username = generate_unique_username()
    password = "testpassword123"
    # First signup
    response1 = client.post("/users/signup", json={"username": username, "password": password})
    assert response1.status_code == 200
    # Second attempt
    response2 = client.post("/users/signup", json={"username": username, "password": password})
    assert response2.status_code == 400
    assert "이미 존재하는 유저네임입니다." in response2.json()["detail"]

def test_signup_invalid_payload_missing_username(client: TestClient):
    response = client.post("/users/signup", json={"password": "somepassword"})
    assert response.status_code == 422

def test_signup_invalid_payload_missing_password(client: TestClient):
    response = client.post("/users/signup", json={"username": generate_unique_username()})
    assert response.status_code == 422

# Tests for POST /users/signin
def test_signin_success(client: TestClient):
    username = generate_unique_username()
    password = "testpassword123"
    # Sign up user first
    signup_response = client.post("/users/signup", json={"username": username, "password": password})
    assert signup_response.status_code == 200 # Ensure setup is correct

    # Attempt signin
    signin_response = client.post("/users/signin", json={"username": username, "password": password}) # JSON data for signin
    assert signin_response.status_code == 200
    data = signin_response.json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"
    assert "sub" in data
    assert uuid.UUID(data["sub"], version=4) # Check if 'sub' is a valid UUID

def test_signin_user_not_found(client: TestClient):
    username = generate_unique_username()
    response = client.post("/users/signin", json={"username": username, "password": "anypassword"}) # JSON data
    assert response.status_code == 400 # Based on current router, it's 400 for general login failure
    # The detail message "로그인에 실패했습니다." is generic.
    # If the user_manager.login_user specifically raises "존재하지 않는 유저네임입니다.", that would be better to assert.
    # For now, "로그인에 실패했습니다." is based on the router's current exception handling for login.
    assert "로그인에 실패했습니다." in response.json()["detail"]


def test_signin_incorrect_password(client: TestClient):
    username = generate_unique_username()
    correct_password = "correctpassword"
    # Sign up user
    signup_response = client.post("/users/signup", json={"username": username, "password": correct_password})
    assert signup_response.status_code == 200

    # Attempt signin with wrong password
    response = client.post("/users/signin", json={"username": username, "password": "wrongpassword"}) # JSON data
    assert response.status_code == 400 # Based on current router, it's 400
    assert "비밀번호가 일치하지 않습니다." in response.json()["detail"]

def test_signin_invalid_payload_missing_username(client: TestClient):
    response = client.post("/users/signin", json={"password": "somepassword"}) # JSON data
    assert response.status_code == 422

def test_signin_invalid_payload_missing_password(client: TestClient):
    response = client.post("/users/signin", json={"username": generate_unique_username()}) # JSON data
    assert response.status_code == 422

# Note: Tests for /users/me, /users/subscriptions, /users/achievements were removed
# as these endpoints are not defined in the current user_router.py or main.py routing.
# If they are intended to exist, they would likely be under an authenticated /api/users/... path.
