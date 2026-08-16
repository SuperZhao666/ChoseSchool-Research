from __future__ import annotations

from typing import Protocol

from chose_school.domain.enums import Strict22408Claim, Strict22408Status
from chose_school.domain.models import (
    SecondaryProjectObservationInput,
    SecondaryProjectObservationResult,
)


class SecondaryProjectObservationStore(Protocol):
    """Append-only storage contract for one secondary project-year reading."""

    def add_secondary_observation(
        self,
        observation: SecondaryProjectObservationInput,
        strict_claim: Strict22408Claim,
        derived_status: Strict22408Status,
        trace_id: str,
    ) -> SecondaryProjectObservationResult: ...
