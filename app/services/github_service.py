import base64
import shutil
import tempfile
import time
from contextlib import contextmanager
from typing import Dict, Any

import httpx
from jose import jwt
from git import Repo, Actor
from git.exc import GitCommandError
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class GitHubServiceError(Exception):
    """Exception raised for errors in the GitHub Service."""

    pass


@contextmanager
def temporary_clone_dir():
    """Context manager for safely handling temporary git directories."""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


class GitManager:
    """Manages local Git operations including clone, commit, and push."""

    def __init__(self, repo_url: str, token: str, temp_dir: str):
        # Embed token into HTTPS URL for programmatic authentication
        if "https://" in repo_url:
            self.repo_url = repo_url.replace(
                "https://", f"https://x-access-token:{token}@"
            )
        else:
            self.repo_url = repo_url

        self.temp_dir = temp_dir
        self.repo = None

    def clone(self):
        """Clones the repository. Handles both populated and empty remote repos."""
        try:
            logger.info("git_clone_start", temp_dir=self.temp_dir)
            self.repo = Repo.clone_from(self.repo_url, self.temp_dir)
        except GitCommandError as e:
            # Fallback for some environments where cloning a truly empty repo might throw
            logger.warning("git_clone_failed_trying_init", error=str(e))
            self.repo = Repo.init(self.temp_dir)
            self.repo.create_remote("origin", self.repo_url)

    def add_all(self):
        """Stages all changes in the temporary directory."""
        self.repo.git.add(A=True)

    def commit(
        self,
        message: str = "feat: automated code generation update",
        author_name: str = "Gemini Worker",
        author_email: str = "bot@archon.local",
    ):
        """Commits changes with a conventional message and ensures the branch is 'main'."""
        actor = Actor(author_name, author_email)

        # We must commit before we can reliably rename an unborn branch in all git versions
        self.repo.index.commit(message, author=actor, committer=actor)

        # Explicitly rename current HEAD to 'main'
        self.repo.git.branch("-M", "main")
        logger.info("git_commit_success", message=message, branch="main")

    def push(self):
        """Pushes the commits to the origin's main branch."""
        logger.info("git_push_start", branch="main")
        try:
            self.repo.git.push("-u", "origin", "main")
            logger.info("git_push_success")
        except GitCommandError as e:
            logger.error("git_push_failed", error=str(e))
            raise GitHubServiceError(f"Failed to push to remote: {str(e)}")


class GitHubService:
    def __init__(self):
        self.app_id = settings.GITHUB_APP_ID
        self.username = settings.GITHUB_USERNAME

        try:
            # The key must be base64 encoded when passed to env vars to preserve newlines
            self.private_key = base64.b64decode(settings.GITHUB_PRIVATE_KEY_B64).decode(
                "utf-8"
            )
        except Exception as e:
            logger.error("github_private_key_decode_error", error=str(e))
            self.private_key = ""

    def _generate_jwt(self) -> str:
        """Generates an RS256 JWT for GitHub App Authentication."""
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + (10 * 60), "iss": self.app_id}
        # Encode the token using python-jose
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    async def get_installation_access_token(self) -> str:
        """Exchanges the JWT for a short-lived Installation Access Token."""
        jwt_token = self._generate_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        async with httpx.AsyncClient() as client:
            # 1. Fetch the installation ID corresponding to the target user
            inst_url = f"https://api.github.com/users/{self.username}/installation"
            inst_resp = await client.get(inst_url, headers=headers)

            if inst_resp.status_code != 200:
                logger.error(
                    "github_installation_fetch_failed",
                    status=inst_resp.status_code,
                    body=inst_resp.text,
                )
                raise GitHubServiceError(
                    f"Failed to find installation for {self.username}"
                )

            installation_id = inst_resp.json()["id"]

            # 2. Issue the access token for this specific installation
            token_url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
            token_resp = await client.post(token_url, headers=headers)

            if token_resp.status_code != 201:
                logger.error(
                    "github_token_generation_failed",
                    status=token_resp.status_code,
                    body=token_resp.text,
                )
                raise GitHubServiceError("Failed to generate access token from GitHub")

            return token_resp.json()["token"]

    async def create_repo_if_not_exists(
        self, repo_name: str, access_token: str
    ) -> Dict[str, Any]:
        """Creates a public repository on GitHub if it doesn't already exist."""
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        async with httpx.AsyncClient() as client:
            # Check existence first
            check_url = f"https://api.github.com/repos/{self.username}/{repo_name}"
            check_resp = await client.get(check_url, headers=headers)

            if check_resp.status_code == 200:
                logger.info("repo_already_exists", repo_name=repo_name)
                return check_resp.json()
            elif check_resp.status_code != 404:
                raise GitHubServiceError(
                    f"Unexpected error checking repo existence: {check_resp.text}"
                )

            # If 404, Create repository via User endpoints (since app is installed on a user account)
            create_url = "https://api.github.com/user/repos"
            payload = {
                "name": repo_name,
                "private": False,
                "auto_init": False,  # Ensure we have an empty slate
                "description": "Auto-generated project via archon",
            }
            create_resp = await client.post(create_url, headers=headers, json=payload)

            if create_resp.status_code != 201:
                raise GitHubServiceError(
                    f"Failed to create repo {repo_name}: {create_resp.text}"
                )

            logger.info("repo_created_successfully", repo_name=repo_name)
            return create_resp.json()

    async def enable_pages_via_api(self, repo_name: str, access_token: str) -> None:
        """Enables GitHub Pages configured to target the root of the 'main' branch."""
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        async with httpx.AsyncClient() as client:
            url = f"https://api.github.com/repos/{self.username}/{repo_name}/pages"
            payload = {"source": {"branch": "main", "path": "/"}}

            resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code in (201, 204):
                logger.info("github_pages_enabled", repo_name=repo_name)
            elif resp.status_code == 409:
                logger.info(
                    "github_pages_already_enabled_or_conflict", repo_name=repo_name
                )
            else:
                logger.error(
                    "github_pages_enable_failed",
                    status=resp.status_code,
                    response=resp.text,
                )
                raise GitHubServiceError(f"Failed to enable GitHub pages: {resp.text}")


github_service = GitHubService()
