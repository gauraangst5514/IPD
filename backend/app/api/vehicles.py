from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.vehicle import Vehicle

router = APIRouter()


class VehicleCreateRequest(BaseModel):
    registration_number: str  # e.g., MH02AB1234
    make: str
    model: str
    variant: Optional[str] = None
    year: int
    color: Optional[str] = None
    fuel_type: Optional[str] = None
    policy_number: Optional[str] = None
    policy_type: Optional[str] = None
    insurer: Optional[str] = None


class VehicleResponse(BaseModel):
    id: str
    registration_number: str
    make: str
    model: str
    variant: Optional[str]
    year: int
    color: Optional[str]
    fuel_type: Optional[str]
    policy_number: Optional[str]
    policy_type: Optional[str]
    insurer: Optional[str]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=VehicleResponse)
async def register_vehicle(
    request: VehicleCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Register a vehicle for the current user."""
    # Check if registration number already exists
    existing = await db.execute(
        select(Vehicle).where(Vehicle.registration_number == request.registration_number.upper())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Vehicle already registered")

    vehicle = Vehicle(
        owner_id=uuid.UUID(current_user["user_id"]),
        registration_number=request.registration_number.upper(),
        make=request.make,
        model=request.model,
        variant=request.variant,
        year=request.year,
        color=request.color,
        fuel_type=request.fuel_type,
        policy_number=request.policy_number,
        policy_type=request.policy_type,
        insurer=request.insurer,
    )
    db.add(vehicle)
    await db.flush()

    return VehicleResponse(
        id=str(vehicle.id),
        registration_number=vehicle.registration_number,
        make=vehicle.make,
        model=vehicle.model,
        variant=vehicle.variant,
        year=vehicle.year,
        color=vehicle.color,
        fuel_type=vehicle.fuel_type,
        policy_number=vehicle.policy_number,
        policy_type=vehicle.policy_type,
        insurer=vehicle.insurer,
    )


@router.get("", response_model=list[VehicleResponse])
async def list_vehicles(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List vehicles owned by the current user."""
    result = await db.execute(
        select(Vehicle).where(Vehicle.owner_id == uuid.UUID(current_user["user_id"]))
    )
    vehicles = result.scalars().all()

    return [
        VehicleResponse(
            id=str(v.id),
            registration_number=v.registration_number,
            make=v.make,
            model=v.model,
            variant=v.variant,
            year=v.year,
            color=v.color,
            fuel_type=v.fuel_type,
            policy_number=v.policy_number,
            policy_type=v.policy_type,
            insurer=v.insurer,
        )
        for v in vehicles
    ]
