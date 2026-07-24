import uuid
from datetime import datetime
from app.core.neo4j_db import neo4j_manager
from app.models.claim import Claim
from app.models.user import User
from app.models.vehicle import Vehicle


async def sync_claim_to_graph(claim: Claim, claimant: User, vehicle: Vehicle):
    """
    Syncs the relational data to the Neo4j graph.
    Creates/Merges nodes for Claimant, Phone, Vehicle, Location, and Claim.
    Creates relationships between them.
    """
    query = """
    // 1. Merge Claimant
    MERGE (c:Claimant {id: $claimant_id})
    SET c.email = $claimant_email, c.name = $claimant_name

    // 2. Merge Phone (if available)
    MERGE (p:Phone {number: $phone})
    MERGE (c)-[:HAS_PHONE]->(p)

    // 3. Merge Vehicle
    MERGE (v:Vehicle {id: $vehicle_id})
    SET v.registration_number = $vehicle_reg

    // 4. Merge Location (using incident_location as proxy for Garage/Location)
    MERGE (l:Location {name: $location_name})

    // 5. Merge Claim
    MERGE (cl:Claim {id: $claim_id})
    SET cl.status = $claim_status, 
        cl.severity = $claim_severity, 
        cl.date = $claim_date

    // 6. Create Relationships
    MERGE (c)-[:FILED]->(cl)
    MERGE (c)-[:OWNS]->(v)
    MERGE (cl)-[:INVOLVES]->(v)
    MERGE (cl)-[:AT_LOCATION]->(l)
    """

    parameters = {
        "claimant_id": str(claimant.id),
        "claimant_email": claimant.email,
        "claimant_name": claimant.full_name,
        "phone": claimant.phone if claimant.phone else "UNKNOWN",
        "vehicle_id": str(vehicle.id),
        "vehicle_reg": vehicle.registration_number,
        "location_name": claim.incident_location.lower() if claim.incident_location else "unknown",
        "claim_id": str(claim.id),
        "claim_status": claim.status.value if claim.status else "submitted",
        "claim_severity": claim.severity.value if claim.severity else "unknown",
        "claim_date": claim.incident_date.isoformat() if claim.incident_date else datetime.now().isoformat()
    }

    async with neo4j_manager.get_session() as session:
        await session.run(query, parameters)


async def check_fraud_rings(claim_id: uuid.UUID) -> dict:
    """
    Checks for fraud rings related to a specific claim.
    Returns a dictionary with a 'score' and a list of 'flags'.
    """
    fraud_score = 0.0
    flags = []

    # 1. Shared Identity Ring: Same phone number, different claimants
    shared_phone_query = """
    MATCH (cl:Claim {id: $claim_id})<-[:FILED]-(c1:Claimant)-[:HAS_PHONE]->(p:Phone)<-[:HAS_PHONE]-(c2:Claimant)
    WHERE p.number <> 'UNKNOWN' AND c1.id <> c2.id
    RETURN count(DISTINCT c2) as shared_count
    """

    # 2. Repeat Offender: Multiple claims on the same vehicle
    repeat_vehicle_query = """
    MATCH (cl:Claim {id: $claim_id})-[:INVOLVES]->(v:Vehicle)<-[:INVOLVES]-(other_cl:Claim)
    WHERE cl.id <> other_cl.id
    RETURN count(DISTINCT other_cl) as repeat_count
    """

    # 3. Suspicious Hotspot: Same location, high number of severe claims
    hotspot_query = """
    MATCH (cl:Claim {id: $claim_id})-[:AT_LOCATION]->(l:Location)<-[:AT_LOCATION]-(other_cl:Claim)
    WHERE cl.id <> other_cl.id AND other_cl.severity IN ['moderate', 'severe']
    RETURN count(DISTINCT other_cl) as hotspot_count
    """

    async with neo4j_manager.get_session() as session:
        # Check Shared Phone
        res = await session.run(shared_phone_query, {"claim_id": str(claim_id)})
        record = await res.single()
        if record and record["shared_count"] > 0:
            flags.append(f"Graph Fraud: Phone number shared with {record['shared_count']} other claimant(s).")
            fraud_score += 0.4

        # Check Repeat Vehicle
        res = await session.run(repeat_vehicle_query, {"claim_id": str(claim_id)})
        record = await res.single()
        if record and record["repeat_count"] > 0:
            flags.append(f"Graph Fraud: Vehicle involved in {record['repeat_count']} other claim(s).")
            fraud_score += 0.3

        # Check Hotspot Location
        res = await session.run(hotspot_query, {"claim_id": str(claim_id)})
        record = await res.single()
        if record and record["hotspot_count"] > 2: # More than 2 other severe claims at this location
            flags.append(f"Graph Fraud: Suspicious location hotspot ({record['hotspot_count']} other severe claims).")
            fraud_score += 0.2

    return {
        "score": min(fraud_score, 1.0),
        "flags": flags
    }
