import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.github_service import GithubService
import httpx

@pytest.fixture
def github_service():
    return GithubService("test_owner", "test_repo")

@patch("app.services.github_service.jwt.encode", return_value="test_jwt")
@pytest.mark.asyncio
async def test_get_installation_access_token(mock_jwt, github_service):
    mock_client = AsyncMock()
    mock_client.get.return_value.status_code = 200
    mock_client.get.return_value.json.return_value = [{"id": 123}]
    
    mock_client.post.return_value.status_code = 201
    mock_client.post.return_value.json.return_value = {"token": "test_token"}

    with patch("httpx.AsyncClient", return_value=mock_client):
        token = await github_service.get_installation_access_token()
        assert token == "test_token"

@pytest.mark.asyncio
async def test_create_repo_if_not_exists_exists(github_service):
    with patch.object(github_service, "get_installation_access_token", return_value="token"):
        mock_client = AsyncMock()
        mock_client.get.return_value.status_code = 200
        mock_client.get.return_value.json.return_value = {"html_url": "https://github.com/test_owner/test_repo"}
        with patch("httpx.AsyncClient", return_value=mock_client):
            url = await github_service.create_repo_if_not_exists("test repo")
            assert url == "https://github.com/test_owner/test_repo"

@pytest.mark.asyncio
async def test_create_repo_if_not_exists_create_new(github_service):
    with patch.object(github_service, "get_installation_access_token", return_value="token"):
        mock_client = AsyncMock()
        get_resp = MagicMock()
        get_resp.status_code = 404
        mock_client.get.return_value = get_resp

        post_resp = MagicMock()
        post_resp.status_code = 201
        post_resp.json.return_value = {"html_url": "https://github.com/test_owner/test_repo"}
        mock_client.post.return_value = post_resp

        with patch("httpx.AsyncClient", return_value=mock_client):
            url = await github_service.create_repo_if_not_exists("test repo")
            assert url == "https://github.com/test_owner/test_repo"

@pytest.mark.asyncio
async def test_enable_pages_via_api_success(github_service):
    with patch.object(github_service, "get_installation_access_token", return_value="token"):
        mock_client = AsyncMock()
        mock_client.post.return_value.status_code = 201
        mock_client.post.return_value.json.return_value = {"html_url": "https://test_owner.github.io/test_repo"}
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            url = await github_service.enable_pages_via_api()
            assert url == "https://test_owner.github.io/test_repo"
