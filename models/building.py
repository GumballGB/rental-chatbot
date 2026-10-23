from typing import Literal

from pydantic import BaseModel, Field


class Building(BaseModel):

    # Basic information about the building
    building_id: str
    name: str

    # general location about the building
    address: str
    postal_code: str
    province: str
    location_id: str # For when location is stored in a separate table
    greater_region: str

    # Geographical coordinates
    longitude: float | None = Field(
        default=None, ge=-180, le=180
    )
    latitude: float | None = Field(
        default=None, ge=-90, le=90
    )

    # unit details
    number_of_units: int = Field(gt=0, description="Number of units must be greater than 0 integer.")

    # inclusions
    amenities: list[str] | None = None
    parking: Literal["outdoor", "indoor", "street", "none"]

    # Additional information
    description: str | None = None
    year_built: int | None = None