from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# Handle SQLite vs PostgreSQL
connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False}

database_url = settings.DATABASE_URL
if database_url.startswith(('postgres://','postgresql://')):
    import ssl
    from sqlalchemy.engine import make_url
    url=make_url(database_url).set(drivername='postgresql+asyncpg')
    query=dict(url.query)
    if query.pop('sslmode',None) in {'require','verify-full','verify-ca'}:
        connect_args['ssl']=ssl.create_default_context()
    query.pop('channel_binding',None)
    database_url=url.set(query=query)
    connect_args['statement_cache_size']=0

engine = create_async_engine(
    database_url,
    echo=settings.DEBUG,
    connect_args=connect_args,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Create all tables (for dev without Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
