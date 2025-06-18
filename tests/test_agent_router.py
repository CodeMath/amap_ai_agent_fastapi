import pytest
import uuid # Added for generating unique IDs
from fastapi.testclient import TestClient
from app.agents.schemas.agent_schemas import AgentDTO, UpdatePromptDTO
from app.agents.schemas.chat_schemas import AiAgentMessageDTO, ChatListDTO, AgentRequestDTO
from app.agents.schemas.achivement_schemas import AchievementGeneratorOutput, AchievementDTO

TEST_AGENT_ID = "test-agent-for-router-tests"
# REGISTER_AGENT_ID and SAMPLE_AGENT_PAYLOAD_FOR_REGISTER are less critical now,
# as test_get_registered_agent_after_registration will generate its own unique ID and payload.
# However, they might be used by other tests if those tests haven't been updated to create their own agents.
# For this refactoring, we focus on test_register_agent and test_get_registered_agent_after_registration.
REGISTER_AGENT_ID = "reg-then-get-agent-001" # Kept for now, can be removed if no other test uses it directly

SAMPLE_AGENT_PAYLOAD_FOR_REGISTER = { # This can serve as a base template
    "agent_id": REGISTER_AGENT_ID, # This will be overridden in the refactored test
    "name": "Test Agent Reg",
    "description": "A test agent for registration and retrieval.",
    "prompt": "You are a test agent for registration.",
    "thumbnail": "http://example.com/thumb.png",
    "tools": ["tool_id_1", "tool_id_2"],
    "model": "gpt-4",
    "latitude": 10.0,
    "longitude": 20.0,
    "achievements": [
        {
            "id": "achieve1",
            "name": "First Achievement",
            "description": "Achieved something",
            "condition": "Did a thing",
            "image": "http://example.com/achieve.png",
            "rarity": "Common"
        }
    ]
}

def test_get_agent_list_default(client: TestClient):
    response = client.get("/api/agents/list")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_agent_list_with_coords(client: TestClient):
    response = client.get("/api/agents/list?latitude=10.0&longitude=20.0")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_agent_start_not_found(client: TestClient):
    response = client.get(f"/api/agents/start/nonexistent-agent-id-12345")
    # Based on current router error handling in other routers, this might be 500.
    # A more specific 404 would be better from the API design perspective.
    # For now, we expect 500 if the agent_manager.get_agent raises an unhandled error.
    assert response.status_code == 500

# Helper function for generating unique agent IDs
def generate_unique_agent_id(prefix="testagent"):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def test_register_agent(client: TestClient):
    unique_agent_id = generate_unique_agent_id("regtest")
    new_agent_data = {
        "agent_id": unique_agent_id,
        "name": "New Agent For Register Test",
        "description": "Description for new agent for register test",
        "prompt": "Prompt for new agent for register test",
        "thumbnail": "http://example.com/thumb2.png",
        "tools": ["tool_id_3"],
        "model": "gpt-3.5-turbo",
        "latitude": 30.0, # Pydantic will convert to Decimal
        "longitude": 40.0, # Pydantic will convert to Decimal
        "achievements": []
    }
    response = client.post("/api/agents/register", json=new_agent_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == new_agent_data["name"]
    assert response_data["agent_id"] == unique_agent_id
    # FastAPI/Pydantic typically serialize Decimal as string in JSON response
    assert response_data["latitude"] == str(new_agent_data["latitude"])
    assert response_data["longitude"] == str(new_agent_data["longitude"])

def test_register_agent_invalid_payload(client: TestClient):
    response = client.post("/api/agents/register", json={"name": "only name, missing fields"})
    assert response.status_code == 422 # FastAPI validation error

def test_get_registered_agent_after_registration(client: TestClient):
    agent_id_for_this_test = generate_unique_agent_id("getreg")

    # Use a copy of the sample payload and override with unique ID and any other specifics
    # Ensuring latitude/longitude are numbers as Pydantic handles conversion from JSON numbers to Decimal
    payload_for_this_test = {
        **SAMPLE_AGENT_PAYLOAD_FOR_REGISTER, # Spread existing defaults
        "agent_id": agent_id_for_this_test, # Override with unique ID
        "name": "Test Agent for GetReg",
        "latitude": 10.0, # Use number
        "longitude": 20.0, # Use number
        # Ensure other fields from SAMPLE_AGENT_PAYLOAD_FOR_REGISTER are appropriate
        # or define them explicitly here.
        "description": "A test agent for get after registration.",
        "prompt": "You are a test agent for get after registration.",
        "thumbnail": "http://example.com/thumb_getreg.png",
        "tools": ["tool_getreg_1"],
        "model": "gpt-3.5-turbo",
        "achievements": []
    }

    # Register the agent
    post_response = client.post("/api/agents/register", json=payload_for_this_test)
    assert post_response.status_code == 200, f"Registration failed: {post_response.text}"

    # Try to get the registered agent
    get_response = client.get(f"/api/agents/start/{agent_id_for_this_test}")
    assert get_response.status_code == 200
    response_data = get_response.json()
    assert response_data["agent_id"] == agent_id_for_this_test
    assert response_data["name"] == payload_for_this_test["name"]
    assert response_data["latitude"] == str(payload_for_this_test["latitude"])
    assert response_data["longitude"] == str(payload_for_this_test["longitude"])

AGENT_ID_FOR_UPDATE_PROMPT_TEST = "agent-for-update-prompt-test-001" # These can remain fixed if helpers manage state
AGENT_FOR_UPDATE_PROMPT_PAYLOAD = {
    "agent_id": AGENT_ID_FOR_UPDATE_PROMPT_TEST, "name": "UpdatePromptAgent",
    "description": "Agent for testing prompt updates.", "prompt": "Initial prompt.",
    "thumbnail": "http://example.com/thumb_update.png", "tools": [], "model": "gpt-3",
    "latitude": 50.0, "longitude": 60.0, "achievements": []
}

def test_update_agent_prompt_success(client: TestClient):
    # Register agent for this test
    reg_response = client.post("/api/agents/register", json=AGENT_FOR_UPDATE_PROMPT_PAYLOAD)
    if reg_response.status_code == 500 and "already exists" in reg_response.text.lower():
        # Agent might exist from a previous run, this is acceptable for update test
        pass
    else:
        assert reg_response.status_code == 200, f"Failed to register agent for update test: {reg_response.text}"

    update_data = {"prompt": "New updated prompt content"}
    response = client.put(f"/api/agents/{AGENT_ID_FOR_UPDATE_PROMPT_TEST}/update-prompt", json=update_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["prompt"] == "New updated prompt content"
    assert response_data["agent_id"] == AGENT_ID_FOR_UPDATE_PROMPT_TEST

def test_update_agent_prompt_not_found(client: TestClient):
    response = client.put("/api/agents/nonexistentagent123abc/update-prompt", json={"prompt": "Doesn't matter"})
    assert response.status_code == 500

def test_update_agent_prompt_invalid_payload(client: TestClient):
    # Register agent for this test (or ensure it exists)
    reg_response = client.post("/api/agents/register", json=AGENT_FOR_UPDATE_PROMPT_PAYLOAD)
    if reg_response.status_code == 500 and "already exists" in reg_response.text.lower():
        pass # Acceptable if already exists
    else:
        assert reg_response.status_code == 200, f"Failed to register agent for invalid payload update test: {reg_response.text}"

    response = client.put(f"/api/agents/{AGENT_ID_FOR_UPDATE_PROMPT_TEST}/update-prompt", json={"wrong_field": "abc"})
    assert response.status_code == 422


AGENT_ID_TO_DELETE = "delete-me-agent-for-test-001"
AGENT_TO_DELETE_PAYLOAD = {
    "agent_id": AGENT_ID_TO_DELETE, "name": "DeleteMeAgent",
    "description": "Agent specifically for delete testing.", "prompt": "Delete me.",
    "thumbnail": "http://example.com/thumb_delete.png", "tools": [], "model": "gpt-3",
    "latitude": 70.0, "longitude": 80.0, "achievements": []
}

def test_delete_agent_success(client: TestClient):
    # Register the agent to be deleted
    reg_response = client.post("/api/agents/register", json=AGENT_TO_DELETE_PAYLOAD)
    if reg_response.status_code == 500 and "already exists" in reg_response.text.lower():
        # If it already exists from a failed previous run, that's okay, we can still try to delete it.
        pass
    else:
        assert reg_response.status_code == 200, f"Failed to register agent for delete test: {reg_response.text}"

    delete_response = client.delete(f"/api/agents/{AGENT_ID_TO_DELETE}/delete")
    assert delete_response.status_code == 200 # Assuming 200 from the router which returns manager's response

    # Optional: Verify it's gone
    get_response = client.get(f"/api/agents/start/{AGENT_ID_TO_DELETE}")
    assert get_response.status_code == 500 # Expecting 500 as per current error handling for not found

def test_delete_agent_not_found(client: TestClient):
    response = client.delete("/api/agents/nonexistentagent-to-delete-123/delete")
    assert response.status_code == 500


AGENT_ID_FOR_ACHIEVEMENTS_TEST = "agent-for-achievements-test-001"
AGENT_FOR_ACHIEVEMENTS_PAYLOAD = {
    "agent_id": AGENT_ID_FOR_ACHIEVEMENTS_TEST, "name": "AchievementsAgent",
    "description": "Agent for testing adding achievements.", "prompt": "Achieve things.",
    "thumbnail": "http://example.com/thumb_ach.png", "tools": [], "model": "gpt-3",
    "latitude": 90.0, "longitude": 100.0, "achievements": []
}

TEST_ACHIEVEMENT_PAYLOAD = {
    "id": "agent-ach-test-1", "name": "Agent Test Achievement One",
    "description": "Description for agent test achievement",
    "condition": "Condition for agent test achievement",
    "image": "http://example.com/ach_img.png", "rarity": "Rare"
}

def test_add_achievements_to_agent_success(client: TestClient):
    # Register agent for this test
    reg_response = client.post("/api/agents/register", json=AGENT_FOR_ACHIEVEMENTS_PAYLOAD)
    if reg_response.status_code == 500 and "already exists" in reg_response.text.lower():
        pass # Acceptable if already exists
    else:
        assert reg_response.status_code == 200, f"Failed to register agent for achievements test: {reg_response.text}"

    response = client.post(f"/api/agents/{AGENT_ID_FOR_ACHIEVEMENTS_TEST}/add-achievements", json=[TEST_ACHIEVEMENT_PAYLOAD])
    assert response.status_code == 200
    # The actual response from manager.add_achievement_to_agent is not defined in problem,
    # so we'll just check for success status. If it returns data, assertions can be added.
    # e.g. assert response.json() == {"message": "success"} or similar

def test_add_achievements_to_agent_not_found(client: TestClient):
    response = client.post("/api/agents/nonexistentagent-for-ach-123/add-achievements", json=[TEST_ACHIEVEMENT_PAYLOAD])
    assert response.status_code == 500

def test_add_achievements_invalid_payload(client: TestClient):
    # Register agent for this test
    reg_response = client.post("/api/agents/register", json=AGENT_FOR_ACHIEVEMENTS_PAYLOAD)
    if reg_response.status_code == 500 and "already exists" in reg_response.text.lower():
        pass # Acceptable
    else:
        assert reg_response.status_code == 200, f"Failed to register agent for invalid achievement payload test: {reg_response.text}"

    response = client.post(f"/api/agents/{AGENT_ID_FOR_ACHIEVEMENTS_TEST}/add-achievements", json=[{"wrong_field": "xyz"}])
    assert response.status_code == 422

# Agent and payload for chat history tests
AGENT_ID_FOR_CHAT_TESTS = "agent-for-chat-tests-001"
AGENT_FOR_CHAT_TESTS_PAYLOAD = {
    "agent_id": AGENT_ID_FOR_CHAT_TESTS, "name": "ChatHistoryTestAgent",
    "description": "Agent for testing chat history endpoints.", "prompt": "Let's chat.",
    "thumbnail": "http://example.com/thumb_chat.png", "tools": [], "model": "gpt-3",
    "latitude": 10.1, "longitude": 20.2, "achievements": []
}

# Helper to register the agent for chat tests, ignoring if already exists
def register_chat_test_agent(client: TestClient):
    reg_response = client.post("/api/agents/register", json=AGENT_FOR_CHAT_TESTS_PAYLOAD)
    if reg_response.status_code == 500 and "already exists" in reg_response.text.lower():
        pass # Agent already exists, which is fine for these tests
    else:
        assert reg_response.status_code == 200, f"Failed to register agent for chat tests: {reg_response.text}"


def test_get_chat_history_success(client: TestClient):
    register_chat_test_agent(client)
    response = client.get(f"/api/agents/{AGENT_ID_FOR_CHAT_TESTS}/chat-history")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # If data is not empty, each item should conform to AiAgentMessageDTO
    # For now, we just check if it's a list. Detailed validation of AiAgentMessageDTO items
    # would require knowing the exact structure or having a Pydantic model for validation here.
    # Example if we had Pydantic models available for testing:
    # if data:
    #     AiAgentMessageDTO(**data[0])


def test_get_chat_history_agent_not_found(client: TestClient):
    response = client.get("/api/agents/nonexistentagent-chathistory/chat-history")
    assert response.status_code == 500


def test_get_chat_list_success(client: TestClient):
    # This endpoint doesn't depend on a specific agent_id in the path,
    # it depends on the authenticated user (mocked by client fixture).
    response = client.get("/api/agents/chat/list")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Similarly, if data is not empty, items should conform to ChatListDTO.
    # Example:
    # if data:
    #     ChatListDTO(**data[0])


def test_delete_agent_history_success(client: TestClient):
    register_chat_test_agent(client)
    response = client.delete(f"/api/agents/{AGENT_ID_FOR_CHAT_TESTS}/delete-history")
    assert response.status_code == 200
    # The router returns the result of manager.delete_agent_history(sub, agent_id)
    # We don't know its exact success structure, so just check status 200.
    # If a specific JSON response is expected, add assertion for it:
    # assert response.json() == {"message": "History deleted"} or similar


def test_delete_agent_history_agent_not_found(client: TestClient):
    response = client.delete("/api/agents/nonexistentagent-delhistory/delete-history")
    assert response.status_code == 500

# Agent and payload for Stream tests
AGENT_ID_FOR_STREAM_TESTS = "agent-for-stream-tests-001"
AGENT_FOR_STREAM_TESTS_PAYLOAD = {
    "agent_id": AGENT_ID_FOR_STREAM_TESTS, "name": "StreamTestAgent",
    "description": "Agent for testing run-stream endpoint.", "prompt": "Stream something.",
    "thumbnail": "http://example.com/thumb_stream.png", "tools": ["some_tool"], "model": "gpt-3.5-turbo", # Assuming tools can be simple strings
    "latitude": 12.3, "longitude": 45.6, "achievements": []
}

def register_stream_test_agent(client: TestClient):
    reg_response = client.post("/api/agents/register", json=AGENT_FOR_STREAM_TESTS_PAYLOAD)
    if reg_response.status_code == 500 and "already exists" in reg_response.text.lower():
        pass
    else:
        assert reg_response.status_code == 200, f"Failed to register agent for stream tests: {reg_response.text}"

def test_run_stream_success(client: TestClient):
    register_stream_test_agent(client)
    agent_request_payload = AgentRequestDTO(agent_id=AGENT_ID_FOR_STREAM_TESTS, data="Hello agent for stream", response_id=None)

    response = client.post("/api/agents/run-stream", json=agent_request_payload.model_dump())

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    # Basic check for stream content, this is not a full validation of the stream.
    # TestClient accumulates the streamed chunks in response.text.
    assert "data:" in response.text
    assert "[DONE]" in response.text

def test_run_stream_agent_not_found(client: TestClient):
    agent_request_payload = AgentRequestDTO(agent_id="nonexistent-stream-agent-123", data="Hello", response_id=None)
    response = client.post("/api/agents/run-stream", json=agent_request_payload.model_dump())
    assert response.status_code == 500

def test_run_stream_invalid_payload(client: TestClient):
    response = client.post("/api/agents/run-stream", json={"wrong_field": "xyz"}) # Missing agent_id and data
    assert response.status_code == 422


# Agent and payload for Generate Achievements tests
AGENT_ID_FOR_GEN_ACH_TESTS = "agent-for-gen-ach-tests-001"
AGENT_FOR_GEN_ACH_TESTS_PAYLOAD = {
    "agent_id": AGENT_ID_FOR_GEN_ACH_TESTS, "name": "GenAchTestAgent",
    "description": "Agent for testing generate-achievements endpoint.", "prompt": "Generate achievements for me.",
    "thumbnail": "http://example.com/thumb_gen_ach.png", "tools": [], "model": "gpt-4",
    "latitude": 78.9, "longitude": 101.1, "achievements": []
}

def register_gen_ach_test_agent(client: TestClient):
    reg_response = client.post("/api/agents/register", json=AGENT_FOR_GEN_ACH_TESTS_PAYLOAD)
    if reg_response.status_code == 500 and "already exists" in reg_response.text.lower():
        pass
    else:
        assert reg_response.status_code == 200, f"Failed to register agent for generate achievement tests: {reg_response.text}"

def test_generate_achievements_success(client: TestClient):
    register_gen_ach_test_agent(client)
    response = client.post(f"/api/agents/{AGENT_ID_FOR_GEN_ACH_TESTS}/generate-achievements")
    assert response.status_code == 200
    response_data = response.json()
    # Validate against AchievementGeneratorOutput schema
    assert "chat_history" in response_data
    assert "achievements" in response_data
    assert isinstance(response_data["chat_history"], list)
    assert isinstance(response_data["achievements"], list)
    # If achievements list is not empty, validate first item against AchievementDTO
    if response_data["achievements"]:
        achievement = response_data["achievements"][0]
        AchievementDTO(**achievement) # Will raise ValidationError if non-compliant
    # If chat_history list is not empty, validate first item against AiAgentMessageDTO
    if response_data["chat_history"]:
        chat_message = response_data["chat_history"][0]
        AiAgentMessageDTO(**chat_message) # Will raise ValidationError if non-compliant


def test_generate_achievements_agent_not_found(client: TestClient):
    response = client.post("/api/agents/nonexistent-gen-ach-agent-123/generate-achievements")
    assert response.status_code == 500
