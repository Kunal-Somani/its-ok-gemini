import pytest
import uuid

@pytest.mark.asyncio
async def test_create_task_unauthorized(test_client):
    response = test_client.post("/api/v1/tasks/ready", json={
        "task_name": "test", 
        "email": "a@b.com", 
        "nonce": "nonce123", 
        "instruction": "test"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_create_task_success(test_client):
    headers = {"X-Api-Key": "test_api_key"}
    payload = {
        "task_name": "test task", 
        "email": "a@b.com", 
        "nonce": "nonce123", 
        "instruction": "test instruction"
    }
    response = test_client.post("/api/v1/tasks/ready", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["task_name"] == "test task"
    assert data["status"] == "QUEUED"

@pytest.mark.asyncio
async def test_create_task_idempotency(test_client):
    headers = {"X-Api-Key": "test_api_key"}
    payload = {
        "task_name": "test task", 
        "email": "a@b.com", 
        "nonce": "nonce_duplicate", 
        "instruction": "test instruction"
    }
    r1 = test_client.post("/api/v1/tasks/ready", headers=headers, json=payload)
    assert r1.status_code == 200
    r2 = test_client.post("/api/v1/tasks/ready", headers=headers, json=payload)
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]

@pytest.mark.asyncio
async def test_get_tasks(test_client):
    headers = {"X-Api-Key": "test_api_key"}
    response = test_client.get("/api/v1/tasks", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_get_task_not_found(test_client):
    headers = {"X-Api-Key": "test_api_key"}
    fake_uuid = str(uuid.uuid4())
    response = test_client.get(f"/api/v1/tasks/{fake_uuid}", headers=headers)
    assert response.status_code == 404
