import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.db.session import get_db
from app.models.base import Base
from app.core.config import settings

# Test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)


@pytest.fixture(autouse=True)
def override_settings():
    settings.API_KEY = "test_api_key"
    settings.COHERE_API_KEY = "test_cohere_key"
    yield


@pytest_asyncio.fixture(autouse=True)
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = TestingSessionLocal()
    yield session

    await session.close()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def override_get_db_fixture(db_session):
    async def _override_get_db():
        yield db_session

    return _override_get_db


@pytest.fixture
def test_client(override_get_db_fixture):
    app.dependency_overrides[get_db] = override_get_db_fixture
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
