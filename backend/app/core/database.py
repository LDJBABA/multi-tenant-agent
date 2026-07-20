from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings

#创建异步数据库引擎
engine = create_async_engine(settings.database_url, echo=settings.app_debug)

#Session 工厂，每次调用产生一个数据库会话
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session