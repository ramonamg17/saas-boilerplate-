"""
conftest.py — Shared test fixtures.

Uses SQLite in-memory for isolation. No external services needed.
"""

import os
import pytest
import pytest_asyncio

# Override DATABASE_URL before importing anything from backend
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_placeholder"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
os.environ["RESEND_API_KEY"] = "re_test"

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from httpx import AsyncClient, ASGITransport

from backend.database import Base, get_db
from backend.main import app
from backend.models.user import User  # noqa: F401 — register models

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db):
    user = User(email="admin@example.com", name="Admin", plan="pro", is_admin=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(db):
    user = User(email="user@example.com", name="Regular User", plan="free")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def make_token(user: User) -> str:
    from backend.core.auth import create_jwt
    return create_jwt({"sub": str(user.id), "email": user.email})


def auth_headers(user: User) -> dict:
    return {"Authorization": f"Bearer {make_token(user)}"}
