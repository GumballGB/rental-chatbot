
from pydantic import BaseModel, Field


class Location(BaseModel):
    
    # Basic information about the location
    location_id: str
    name: str
    alternative_names: list[str] | None = None

    # general location about the building
    country: str
    province: str
    nearby_landmarks: list[str] | None = None
    nearby_transportation: list[str] | None = None


    # Geographical coordinates
    center_longitude: float | None = Field(
        default=None, ge=-180, le=180
    )
    center_latitude: float | None = Field(
        default=None, ge=-90, le=90
    )