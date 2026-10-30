"""Neo4j is a derived projection; SQL remains the durable claim record.

Uses the Neo4j 5.26 Query API. Writes are parameterized and idempotent.
Pending SQL outbox entries survive Neo4j outages and can be retried/rebuilt.
"""
from datetime import datetime, timezone
import httpx
from sqlalchemy import select
from app.core.config import get_settings
from app.models.graph_projection import GraphProjection

def claim_payload(claim):
    cid=str(claim.id)
    nodes=[
        {"id":cid,"kind":"claim","label":cid[:8],"status":claim.status.value},
        {"id":"claimant:"+str(claim.claimant_id),"kind":"claimant","label":"claimant "+str(claim.claimant_id)[:8],"status":""},
        {"id":"vehicle:"+str(claim.vehicle_id),"kind":"vehicle","label":"vehicle "+str(claim.vehicle_id)[:8],"status":""},
    ]
    edges=[{"source":cid,"target":node["id"],"relation":"same_"+node["kind"]} for node in nodes[1:]]
    for item in (claim.fraud_flags or {}).get("_indicators",[]):
        for match in (item.get("evidence") or {}).get("matches",[]):
            if match.get("claim_id") and match["claim_id"]!=cid:
                edges.append({"source":cid,"target":match["claim_id"],"relation":match["match_type"]})
    unique={(e["source"],e["target"],e["relation"]):e for e in edges}
    return {"claim_id":cid,"nodes":nodes,"edges":list(unique.values()),
            "updated_at":datetime.now(timezone.utc).isoformat()}

async def enqueue_claim(claim,db):
    if get_settings().GRAPH_BACKEND!="neo4j":return
    record=await db.get(GraphProjection,claim.id)
    if record is None:
        record=GraphProjection(claim_id=claim.id,payload=claim_payload(claim),attempts=0)
        db.add(record)
    else:
        record.payload=claim_payload(claim)
    record.updated_at=datetime.now(timezone.utc)
    record.applied_at=None;record.last_error=None
    await db.flush()

class Neo4jProjection:
    def __init__(self,transport=None):
        self.settings=get_settings()
        self.transport=transport
        self.schema_ready=False

    async def query(self,statement,parameters=None):
        settings=self.settings
        async with httpx.AsyncClient(timeout=8,transport=self.transport,
                auth=(settings.NEO4J_USER,settings.NEO4J_PASSWORD)) as client:
            response=await client.post(
                settings.NEO4J_HTTP_URL.rstrip("/")+"/db/"+settings.NEO4J_DATABASE+"/query/v2",
                json={"statement":statement,"parameters":parameters or {}},
                headers={"Accept":"application/json"})
            response.raise_for_status()
            result=response.json()
            if result.get("errors"):raise RuntimeError("neo4j_query_failed")
            return result.get("data",{})

    async def health(self):
        await self.query("RETURN 1 AS ready")
        return {"status":"healthy","backend":"neo4j"}

    async def upsert(self,payload):
        if not self.schema_ready:
            await self.query("CREATE CONSTRAINT evidence_node_id IF NOT EXISTS FOR (node:EvidenceNode) REQUIRE node.id IS UNIQUE")
            self.schema_ready=True
        await self.query("""
        UNWIND $nodes AS node
        MERGE (n:EvidenceNode {id: node.id})
        SET n.kind=node.kind,n.label=node.label,n.status=node.status,
            n.updated_at=$updated_at
        WITH count(n) AS updated
        MATCH (claim:EvidenceNode {id: $claim_id})
        OPTIONAL MATCH (claim)-[old:RELATED]->()
        WITH collect(old) AS previous
        FOREACH (relationship IN previous | DELETE relationship)
        WITH size(previous) AS deleted
        UNWIND $edges AS edge
        MATCH (source:EvidenceNode {id:edge.source})
        MERGE (target:EvidenceNode {id:edge.target})
        ON CREATE SET target.kind='claim',target.label=substring(edge.target,0,8)
        MERGE (source)-[relationship:RELATED {relation:edge.relation}]->(target)
        RETURN count(relationship) AS relationships
        """,payload)

    async def graph(self):
        result=await self.query("""
        MATCH (claim:EvidenceNode {kind:'claim'})
        WITH claim ORDER BY claim.updated_at DESC LIMIT 200
        OPTIONAL MATCH (claim)-[relationship:RELATED]->(target:EvidenceNode)
        RETURN properties(claim) AS source,properties(target) AS target,
               relationship.relation AS relation
        """)
        nodes={};edges=[]
        for source,target,relation in result.get("values",[]):
            nodes[source["id"]]=source
            if target:
                nodes[target["id"]]=target
                if relation:edges.append({"source":source["id"],"target":target["id"],"relation":relation})
        return {"nodes":list(nodes.values()),"edges":edges,"limit":200,"backend":"neo4j",
                "warning":"Observed claim/entity/photo links support review; they do not establish a fraud ring."}

async def synchronize_pending(db,projection=None):
    if get_settings().GRAPH_BACKEND!="neo4j":return {"status":"not_configured"}
    projection=projection or Neo4jProjection()
    records=(await db.execute(select(GraphProjection).where(GraphProjection.applied_at.is_(None))
                             .order_by(GraphProjection.updated_at).limit(100))).scalars().all()
    applied=0;failed=0
    for record in records:
        record.attempts+=1
        try:
            await projection.upsert(record.payload)
            record.applied_at=datetime.now(timezone.utc);record.last_error=None;applied+=1
        except Exception as error:
            record.last_error=type(error).__name__;failed+=1
        await db.commit()
    return {"status":"degraded" if failed else "healthy","applied":applied,"failed":failed}
