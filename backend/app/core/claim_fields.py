from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class StructuredFields(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    incident_severity: Literal["Minor Damage", "Major Damage", "Total Loss", "Trivial Damage"]
    incident_type: Literal["Single Vehicle Collision", "Multi-vehicle Collision", "Vehicle Theft", "Parked Car"]
    insured_hobbies: str = Field(min_length=1, max_length=100)
    total_claim_amount: float = Field(ge=0, le=1e10)
    vehicle_claim: float = Field(ge=0, le=1e10)
    umbrella_limit: float = Field(ge=-1e6, le=1e10)
    policy_annual_premium: float = Field(ge=0, le=1e8)
