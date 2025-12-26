from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from config import ApplicationConfig
from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork

engine = create_async_engine(ApplicationConfig.DB_URI, echo=False, future=True)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def get_unit_of_work():
    async with AsyncSessionLocal() as session:
        yield SqlAlchemyUnitOfWork(session)
