"""Neo4j wire contract and durable SQL projection recovery; no live-server claims."""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import AsyncMock, patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
import httpx
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker

class ProjectionTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.env=patch.dict(os.environ,{"DATABASE_URL":"sqlite+aiosqlite:///:memory:",
                                      "SECRET_KEY":"test-only","DEBUG":"false"})
        cls.env.start()
        global Neo4jProjection,claim_payload,synchronize_pending,GraphProjection,ClaimStatus,Base
        from app.services.graph_projection import Neo4jProjection,claim_payload,synchronize_pending
        from app.models.graph_projection import GraphProjection
        from app.models.claim import ClaimStatus
        from app.core.database import Base
    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
    def settings(self):
        return SimpleNamespace(NEO4J_HTTP_URL="http://graph.test:7474",NEO4J_DATABASE="neo4j",
            NEO4J_USER="test",NEO4J_PASSWORD="test-only",GRAPH_BACKEND="neo4j")
    async def test_query_uses_parameters_and_rejects_embedded_errors(self):
        requests=[]
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(202,json={"data":{"fields":["ok"],"values":[[1]]}})
        with patch("app.services.graph_projection.get_settings",return_value=self.settings()):
            client=Neo4jProjection(httpx.MockTransport(handler))
            await client.query("RETURN $user_value AS ok",{"user_value":"quotes ' stay data"})
        self.assertEqual(requests[0]["statement"],"RETURN $user_value AS ok")
        self.assertEqual(requests[0]["parameters"]["user_value"],"quotes ' stay data")
        def bad(request):return httpx.Response(200,json={"errors":[{"code":"failed"}]})
        with patch("app.services.graph_projection.get_settings",return_value=self.settings()):
            client=Neo4jProjection(httpx.MockTransport(bad))
            with self.assertRaises(RuntimeError):await client.query("RETURN 1")
    async def test_graph_reads_actual_neo4j_response(self):
        def handler(request):
            return httpx.Response(202,json={"data":{"fields":["source","target","relation"],"values":[
                [{"id":"c","kind":"claim","label":"c"},{"id":"v","kind":"vehicle","label":"v"},"same_vehicle"]]}})
        with patch("app.services.graph_projection.get_settings",return_value=self.settings()):
            graph=await Neo4jProjection(httpx.MockTransport(handler)).graph()
        self.assertEqual(graph["backend"],"neo4j")
        self.assertEqual(len(graph["nodes"]),2)
        self.assertEqual(graph["edges"][0]["relation"],"same_vehicle")
    async def test_upsert_has_unique_ids_and_replaces_stale_relations(self):
        requests=[]
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(202,json={"data":{"fields":[],"values":[]}})
        payload={"claim_id":"c","nodes":[{"id":"c","kind":"claim","label":"c","status":"flagged"}],
                 "edges":[{"source":"c","target":"other","relation":"exact_file"}],"updated_at":"test"}
        with patch("app.services.graph_projection.get_settings",return_value=self.settings()):
            client=Neo4jProjection(httpx.MockTransport(handler))
            await client.upsert(payload);await client.upsert(payload)
        self.assertIn("CREATE CONSTRAINT",requests[0]["statement"])
        self.assertEqual(len(requests),3)
        self.assertEqual(requests[1]["parameters"],payload)
        self.assertIn("DELETE relationship",requests[1]["statement"])
    async def test_failed_projection_remains_pending_and_can_recover(self):
        engine=create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions=async_sessionmaker(engine,expire_on_commit=False)
        try:
            async with sessions() as db:
                record=GraphProjection(claim_id=uuid.uuid4(),payload={"claim_id":"test"},attempts=0)
                db.add(record);await db.commit()
                projection=SimpleNamespace(upsert=AsyncMock(side_effect=RuntimeError("offline")))
                with patch("app.services.graph_projection.get_settings",return_value=self.settings()):
                    result=await synchronize_pending(db,projection)
                    self.assertEqual(result["failed"],1)
                    self.assertIsNone(record.applied_at)
                    self.assertEqual(record.attempts,1)
                    projection.upsert=AsyncMock()
                    result=await synchronize_pending(db,projection)
                    self.assertEqual(result["applied"],1)
                    self.assertIsNotNone(record.applied_at)
                    self.assertIsNone(record.last_error)
                    self.assertEqual(record.attempts,2)
        finally:await engine.dispose()
    def test_payload_contains_only_observed_links(self):
        owner=uuid.uuid4();vehicle=uuid.uuid4()
        claim=SimpleNamespace(id=uuid.uuid4(),claimant_id=owner,vehicle_id=vehicle,status=ClaimStatus.FLAGGED,
            fraud_flags={"_indicators":[{"evidence":{"matches":[{"claim_id":"prior","match_type":"exact_file"}]}}]})
        payload=claim_payload(claim)
        self.assertEqual(len(payload["nodes"]),3)
        self.assertEqual({item["relation"] for item in payload["edges"]},{"same_claimant","same_vehicle","exact_file"})
        self.assertNotIn("fraud_score",payload)

if __name__=="__main__":unittest.main()
