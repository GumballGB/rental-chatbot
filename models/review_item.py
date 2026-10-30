from dataclasses import dataclass

from models.enquiry import Enquiry
from models.recommendation import Recommendation
from models.review import Review


class ReviewLoadError(ValueError):
    """A review item has a missing, unreadable, invalid, or mismatched file."""

@dataclass(frozen=True)
class ReviewItem:
    """A review together with the enquiry and recommendation being reviewed."""

    review: Review
    enquiry: Enquiry
    recommendation: Recommendation
