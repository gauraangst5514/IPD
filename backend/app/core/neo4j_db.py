from neo4j import AsyncGraphDatabase
from typing import Optional
from app.core.config import get_settings

settings = get_settings()

class Neo4jManager:
    def __init__(self):
        self.driver = None

    async def connect(self):
        """Initialize the Neo4j driver."""
        if not self.driver:
            self.driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )

    async def close(self):
        """Close the Neo4j driver."""
        if self.driver:
            await self.driver.close()
            self.driver = None

    def get_session(self):
        """Get an async session from the driver."""
        if not self.driver:
            raise RuntimeError("Neo4j driver is not initialized")
        return self.driver.session()

neo4j_manager = Neo4jManager()
