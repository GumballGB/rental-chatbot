from typing import Literal

from models.unit_enquiry import UnitEnquiry


class Enquiry(UnitEnquiry):

    # Basic information about the enquiry
    enquiry_id: str

    # Additional information
    budget_currency: Literal["CAD", "DKK"] | None = None
    received_date: str | None = None
    listing_id: str | None = None