import pytest_asyncio
import sqlalchemy
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from tests.fixtures.json_loader import TestDataLoader
from src.depends import get_session
from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork


@pytest_asyncio.fixture
def test_data():
    return TestDataLoader()


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Create test database engine using PostgreSQL test database"""
    # Use a test database on the same PostgreSQL instance
    test_db_url = "postgresql+asyncpg://postgres:postgres@localhost:5433/billing_test"

    engine = create_async_engine(test_db_url, echo=False, future=True)

    # Drop and recreate the public schema to ensure clean state
    async with engine.begin() as conn:
        # Drop all tables by dropping and recreating the public schema
        await conn.execute(sqlalchemy.text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(sqlalchemy.text("CREATE SCHEMA public"))
        # Create all tables
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    # Cleanup after test
    async with engine.begin() as conn:
        await conn.execute(sqlalchemy.text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(sqlalchemy.text("CREATE SCHEMA public"))

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    """Create a new database session for each test"""
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    """Create test client with database session override"""
    from src.api.app import create_app
    from config import ApplicationConfig

    app = create_app(ApplicationConfig)

    # Override the session dependency to use test session
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    # Use ASGITransport for httpx AsyncClient
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
