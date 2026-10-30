"""Short-lived TLS PostgreSQL connections for durable serverless ML evidence."""
import os
from contextlib import contextmanager

@contextmanager
def connection():
    import psycopg2
    url=os.environ['IMAGE_DATABASE_URL'].replace('postgresql+asyncpg://','postgresql://')
    db=psycopg2.connect(url,connect_timeout=15)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
