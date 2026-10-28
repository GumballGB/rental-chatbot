# Application-owned result linking a recommendation to its triage run.

from dataclasses import dataclass
from uuid import UUID

from models.recommendation import Recommendation

# We want this class to be frozen and not be able to modify its attributes after creation,
# so we use the @dataclass decorator with frozen=True.
@dataclass(frozen=True)
class TriageResult:

    # The identifier
    run_id: UUID
    recommendation: Recommendation
