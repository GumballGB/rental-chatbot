from models.recommendation import Evidence
from pydantic import BaseModel

# For when an evidence is actually bad, the checker deemed it to be a failure, and we want to report it.
class EvidenceFailure(BaseModel):

    # index, 0 = first evidence failed, 1 = second evidence failed, 2 = third evidence failed.
    index: int

    # Which evidence item failed the check.
    evidence: Evidence
    reason: str
