from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, Field


class Listing(BaseModel):

    # Basic information about the listing
    listing_id: str
    listing_name: str
    monthly_rent: int = Field(ge=0, description="Monthly rent must be a non-negative integer.")
    currency: Literal["CAD", "DKK"]

    # listing details
    bedrooms: float = Field(ge=0, description="Number of bedrooms must be a non-negative float.")
    bathrooms: float = Field(gt=0, description="Number of bathrooms must be a non-negative float.")
    layout: str | None = None # Quebec layout (e.g., 3 1/2, 4 1/2, etc.)

    # listing availability status
    availability_status: Literal["available", "unavailable", "pending"] = "available"
    available_date: Date | None = None

    # inclusions
    inclusions: list[str] | None = None
    pets_allowed: bool

    # Additional information
    description: str | None = None

    # Attached building information
    building_id: str