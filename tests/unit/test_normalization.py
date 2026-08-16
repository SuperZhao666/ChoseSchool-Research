from __future__ import annotations

import unittest

from tests.support import REPOSITORY_ROOT  # noqa: F401

from chose_school.domain.catalog_normalizer import (
    EXPECTED_CATALOG_HEADER,
    normalize_catalog_row,
)
from chose_school.domain.enums import (
    EvidenceGrade,
    Strict22408Claim,
    Strict22408Status,
)
from chose_school.domain.models import RawCatalogRow


def _row(
    overrides: dict[str, str],
    member: str = "research/22408_db_A1.csv",
    row_number: int = 2,
) -> RawCatalogRow:
    values = {column: "" for column in EXPECTED_CATALOG_HEADER}
    values.update(
        {
            "school": "测试大学",
            "college": "计算机学院",
            "program_code": "085404",
            "program_name": "计算机技术",
            "full_time_or_part_time": "全日制",
            "training_type": "专硕",
            "year": "2026",
            "retrieval_date": "2026-08-01",
        }
    )
    values.update(overrides)
    cells = tuple(values[column] for column in EXPECTED_CATALOG_HEADER)
    return RawCatalogRow(member, row_number, EXPECTED_CATALOG_HEADER, cells, values)


class CatalogNormalizationTest(unittest.TestCase):
    def test_compound_integer_is_not_coerced(self) -> None:
        normalized = normalize_catalog_row(
            _row(
                {
                    "is_strict_22408": "yes",
                    "source_level": "B",
                    "general_exam_admit_count": "115(另一名单口径107)",
                }
            )
        )

        self.assertIsNotNone(normalized.observation)
        observation = normalized.observation
        assert observation is not None
        self.assertIsNone(observation.general_exam_admit_count)
        self.assertEqual(observation.strict_claim, Strict22408Claim.YES)
        self.assertEqual(observation.strict_status, Strict22408Status.SECONDARY_ONLY)
        self.assertIn("NON_ATOMIC_INTEGER", {issue.code for issue in normalized.issues})

    def test_known_a5_shift_is_repaired_only_in_shadow(self) -> None:
        normalized = normalize_catalog_row(
            _row(
                {
                    "is_strict_22408": "yes",
                    "admit_initial_mean": "60",
                    "initial_exam_weight": "40",
                    "retest_weight": "",
                    "machine_test_weight": "",
                    "machine_test_elimination_line": "",
                    "tuition_per_year": "",
                    "study_length": "",
                    "first_choice_protection": "A",
                    "source_level": "中石油华东计院官方来源",
                    "official_source": "22408备注",
                },
                member="research/22408_db_A5.csv",
                row_number=38,
            )
        )
        observation = normalized.observation
        assert observation is not None
        self.assertIsNone(observation.admit_initial_mean)
        self.assertEqual(observation.initial_exam_weight, 0.6)
        self.assertEqual(observation.retest_weight, 0.4)
        self.assertEqual(observation.evidence_grade, EvidenceGrade.OFFICIAL)
        self.assertEqual(observation.raw_values["official_source"], "中石油华东计院官方来源")
        self.assertIn(
            "KNOWN_LEGACY_FIELD_SHIFT_REPAIRED",
            {issue.code for issue in normalized.issues},
        )

    def test_2027_notice_is_pending_not_confirmed(self) -> None:
        normalized = normalize_catalog_row(
            _row(
                {
                    "year": "2027",
                    "is_strict_22408": "是",
                    "source_level": "A",
                    "notes": "已公告改408，204+302待正式目录确认",
                }
            )
        )
        observation = normalized.observation
        assert observation is not None
        self.assertEqual(
            observation.strict_status,
            Strict22408Status.OFFICIAL_PENDING_CATALOG,
        )

    def test_mixed_letter_evidence_levels_are_recognized(self) -> None:
        normalized = normalize_catalog_row(
            _row({"source_level": "A复试方案+B名单"})
        )
        observation = normalized.observation
        assert observation is not None
        self.assertEqual(observation.evidence_grade, EvidenceGrade.OFFICIAL_MIXED)


if __name__ == "__main__":
    unittest.main()
