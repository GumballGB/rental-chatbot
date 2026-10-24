from typing import Literal

from models.unit_enquiry import UnitEnquiry


class Enquiry(UnitEnquiry):

    # Basic information about the enquiry
    enquiry_id: str

    # Additional information
    budget_currency: Literal["CAD", "DKK"] | None = None
    received_date: str | None = None
    listing_id: str | None = None

    def __init__(self, **data):
        super().__init__(**data)
        self.enquiry_id = data.get("enquiry_id")
        self.budget_currency = data.get("budget_currency")
        self.received_date = data.get("received_date")
        self.listing_id = data.get("listing_id")