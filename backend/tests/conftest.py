import os
os.environ['APP_ENV'] = 'development'
os.environ['DEBUG'] = 'false'
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
os.environ['SMTP_HOST'] = ''

import uuid
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.database import Base
import app.models


@pytest_asyncio.fixture
async def factory(tmp_path):
    url = os.getenv('TEST_DATABASE_URL')
    schema = 'audit_' + uuid.uuid4().hex
    if url:
        admin = create_async_engine(url)
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA {schema}'))
        engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
    else:
        engine = create_async_engine('sqlite+aiosqlite:///' + str(tmp_path / 'test.db'))
        @event.listens_for(engine.sync_engine, 'connect')
        def foreign_keys(conn, record):
            conn.execute('PRAGMA foreign_keys=ON')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
    if url:
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        await admin.dispose()
