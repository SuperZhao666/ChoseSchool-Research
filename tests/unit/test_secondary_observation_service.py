from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

from tests.support import REPOSITORY_ROOT  # noqa: F401

from chose_school.business.secondary_observation_service import (
    SecondaryObservationService,
)
from chose_school.domain.enums import Strict22408Claim, Strict22408Status
from chose_school.domain.errors import ValidationError
from chose_school.domain.models import (
    SecondaryProjectObservationInput,
    SecondaryProjectObservationResult,
)


class _RecordingStore:
    def __init__(self) -> None:
        self.call = None

    def add_secondary_observation(
        self, observation, strict_claim, derived_status, trace_id
    ) -> SecondaryProjectObservationResult:
        self.call = (observation, strict_claim, derived_status, trace_id)
        return SecondaryProjectObservationResult(7, derived_status, True)


class SecondaryObservationServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = _RecordingStore()
        settings = SimpleNamespace(
            strict_politics_code="101",
            strict_english_code="204",
            strict_math_code="302",
            strict_professional_code="408",
        )
        self.service = SecondaryObservationService(self.store, settings)

    def test_complete_claim_is_secondary_only_and_never_official(self) -> None:
        result = self.service.add_observation(_input(), "trace-secondary")
        self.assertEqual(result.status, Strict22408Status.SECONDARY_ONLY)
        self.assertEqual(self.store.call[1], Strict22408Claim.YES)
        self.assertEqual(self.store.call[2], Strict22408Status.SECONDARY_ONLY)

    def test_absent_subject_claim_is_unverified(self) -> None:
        result = self.service.add_observation(
            replace(
                _input(),
                politics_code=None,
                english_code=None,
                math_code=None,
                professional_code=None,
            ),
            "trace-secondary-none",
        )
        self.assertEqual(result.status, Strict22408Status.UNVERIFIED)
        self.assertEqual(self.store.call[1], Strict22408Claim.UNKNOWN)

    def test_partial_subject_contract_and_bad_hash_are_rejected(self) -> None:
        with self.assertRaises(ValidationError) as partial:
            self.service.add_observation(
                replace(_input(), professional_code=None),
                "trace-partial",
            )
        self.assertEqual(
            partial.exception.error_code,
            "PARTIAL_SECONDARY_SUBJECT_CONTRACT",
        )
        with self.assertRaises(ValidationError) as bad_hash:
            self.service.add_observation(
                replace(_input(), source_content_sha256="bad"),
                "trace-hash",
            )
        self.assertEqual(bad_hash.exception.error_code, "INVALID_SOURCE_SHA256")


def _input() -> SecondaryProjectObservationInput:
    return SecondaryProjectObservationInput(
        school="中国科学技术大学",
        college="计算机科学与技术学院",
        program_code="085404",
        program_name="计算机技术",
        admission_year=2025,
        source_title="灰灰考研院校数据汇总",
        source_url="https://example.com/huihui/ustc-2025",
        source_institution="灰灰考研",
        source_content_sha256="a" * 64,
        applicable_year=2025,
        published_date=date(2025, 4, 1),
        retrieved_date=date(2026, 8, 3),
        source_excerpt="计算机技术：101、204、302、408。",
        project_identity_basis="页面同时列出学校、学院、专业代码和专业名称。",
        politics_code="101",
        english_code="204",
        math_code="302",
        professional_code="408",
        study_mode="全日制",
    )


if __name__ == "__main__":
    unittest.main()
