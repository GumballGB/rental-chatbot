from pydantic import BaseModel, EmailStr, Field

class UnitEnquiry(BaseModel):
    # Basic information about the enquiry
    name: str = "no name provided"
    email: EmailStr | None = None
    phone: str | None = None

    # Additional information
    move_in_date: str | None = None
    budget: int | None = None

    message: str = "no message provided"