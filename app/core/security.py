import secrets
import hmac
from fastapi import HTTPException, Header
from app.core.config import settings
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def create_api_key() -> str:
    return secrets.token_urlsafe(32)


def verify_api_key(api_key: str) -> bool:
    return hmac.compare_digest(api_key, settings.API_KEY)


async def get_api_key(x_api_key: str = Header(...)) -> str:
    if not verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key
