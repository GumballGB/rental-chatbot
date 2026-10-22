from pydantic import BaseModel, EmailStr, Field

class Enquiry(BaseModel):

    # Basic information about the enquiry
    name: str = Field(..., description="The name of the person making the enquiry")
    email: EmailStr = Field(..., description="The email address of the person making the enquiry")
    phone: str = Field(..., description="The phone number of the person making the enquiry")

    # Additional information
    move_in_date: str = Field(..., description="The desired move-in date for the rental property")
    budget: float = Field(..., description="The budget for the rental property")

    message: str = Field(..., description="The message content of the enquiry")