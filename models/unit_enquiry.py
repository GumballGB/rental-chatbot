from pydantic import BaseModel, EmailStr

class UnitEnquiry(BaseModel):
    
    # Basic information about the enquiry
    enquiry_id: str
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None

    # Additional information
    move_in_date: str | None = None
    budget: int | None = None
    received_date: str | None = None
    message: str | None = None
    listing_id: str | None = None
