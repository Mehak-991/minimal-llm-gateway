import pytest
from fastapi.testclient import TestClient
import respx
import httpx
from app.main import app, get_current_api_key, get_db
from app.models import VirtualKey

client = TestClient(app)

# Minimal database mock to prevent test from requiring live PostgreSQL
class MockDB:
    def execute(self, *args, **kwargs):
        class MockResult:
            rowcount = 1
        return MockResult()
    def commit(self): pass
    def add(self, *args): pass

def override_get_db():
    yield MockDB()

def override_get_current_api_key():
    return VirtualKey(id=1, key_hash="mock_hash", budget_tokens=10000, used_tokens=0)

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_api_key] = override_get_current_api_key

@pytest.fixture
def mock_groq():
    with respx.mock(assert_all_called=False) as respx_mock:
        yield respx_mock

def test_successful_request_does_not_retry(mock_groq):
    route = mock_groq.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"usage": {"total_tokens": 10}, "choices": []})
    )
    
    response = client.post("/v1/chat/completions", json={"model": "test", "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 200
    assert route.call_count == 1

def test_transient_failure_retries_once(mock_groq):
    route = mock_groq.post("https://api.groq.com/openai/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(500, json={"error": "internal error"}),
            httpx.Response(200, json={"usage": {"total_tokens": 10}, "choices": []})
        ]
    )
    
    response = client.post("/v1/chat/completions", json={"model": "test", "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 200
    assert route.call_count == 2

def test_two_failures_result_in_502(mock_groq):
    route = mock_groq.post("https://api.groq.com/openai/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(500, json={"error": "internal error"}),
            httpx.Response(500, json={"error": "internal error"}),
        ]
    )
    
    response = client.post("/v1/chat/completions", json={"model": "test", "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 502
    assert response.json()["detail"] == "Provider encountered an error and retries failed"
    assert route.call_count == 2

def test_client_error_does_not_retry(mock_groq):
    route = mock_groq.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(400, json={"error": "bad request"})
    )
    
    response = client.post("/v1/chat/completions", json={"model": "test", "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 400
    assert route.call_count == 1
    
def test_timeout_triggers_retry(mock_groq):
    route = mock_groq.post("https://api.groq.com/openai/v1/chat/completions").mock(
        side_effect=[
            httpx.TimeoutException("Timeout"),
            httpx.Response(200, json={"usage": {"total_tokens": 10}, "choices": []})
        ]
    )
    
    response = client.post("/v1/chat/completions", json={"model": "test", "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 200
    assert route.call_count == 2
