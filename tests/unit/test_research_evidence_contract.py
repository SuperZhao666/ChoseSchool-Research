"""Human-readable research evidence contract guards.

TraceId: 24d3d889-2583-42e7-8766-075fb61b4127
TraceId: 9f847dfc-f892-4055-aa56-c47d48e382b2
TraceId: 614fad46-51a8-4458-9113-dee74007a5d8
TraceId: 53b2918f-73c1-4229-8deb-82aa6150c15f
TraceId: 41b56801-de06-402a-81af-0172921d15c5
"""

from pathlib import Path
import unittest


class ResearchEvidenceContractTests(unittest.TestCase):
    def test_ouc_2024_visible_mirror_stays_direction_scoped_and_non_model(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        status = "secondary_visible_mirror_final_subject_observation"

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        data_dictionary = (repository_root / "docs" / "data-dictionary.md").read_text(
            encoding="utf-8"
        )
        subject_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admitted-subject-score-distribution-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")
        admission_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admission-data-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")

        self.assertIn(f"`{status}`", data_dictionary)
        self.assertIn("不得进入择校排序、目标分、录取概率", data_dictionary)
        self.assertIn("复试 `44=非创新计划30+创新计划14`", subject_report)
        self.assertIn("`39=非创新计划25+创新计划14`", subject_report)
        self.assertIn("| 目标方向非创新计划拟录取逐行观察", subject_report)
        self.assertIn("`317 / 328 / 332 / 335.08 / 337 / 369`", subject_report)
        self.assertIn("目录阶段计划 8 不等于最终人数", subject_report)
        self.assertIn("不算正式精确格、不能进入择校模型", subject_report)
        self.assertIn("正式最终缺失；镜像非创新拟录取 25", admission_report)
        self.assertIn("海大 2024 目标 `002-085404-01`", readme)
        self.assertNotIn("zhuanlan.zhihu.com/p/697755981", readme)
        self.assertNotIn("zhuanlan.zhihu.com/p/697755981", subject_report)

    def test_set_identification_is_documented_as_non_model_evidence(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        status = "secondary_mirror_final_subject_set_identification"

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        data_dictionary = (repository_root / "docs" / "data-dictionary.md").read_text(
            encoding="utf-8"
        )
        subject_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admitted-subject-score-distribution-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")

        self.assertIn("集合识别", readme)
        self.assertIn(f"`{status}`", data_dictionary)
        self.assertIn("禁止从同分组任选一人形成点估计", data_dictionary)
        self.assertIn("不得进入择校排序、目标分、录取概率", data_dictionary)
        self.assertIn(f"`{status}`", subject_report)
        self.assertIn("不能进入择校模型", subject_report)

    def test_blurred_final_order_identification_stays_anonymous_and_non_model(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        status = "secondary_blurred_final_order_subject_set_identification"

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        data_dictionary = (repository_root / "docs" / "data-dictionary.md").read_text(
            encoding="utf-8"
        )
        subject_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admitted-subject-score-distribution-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")

        self.assertIn(status, readme)
        self.assertIn(f"`{status}`", data_dictionary)
        self.assertIn("禁止复原或发布个人身份", data_dictionary)
        self.assertIn("不得进入择校排序、目标分、录取概率", data_dictionary)
        self.assertIn(f"`{status}`", subject_report)
        self.assertIn("8 个相容集合", subject_report)
        self.assertIn("不能复原或发布个人身份", subject_report)
        self.assertIn("不能进入择校模型", subject_report)

    def test_initial_and_college_cumulative_crossmatches_are_not_promoted_to_final(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        initial_status = "official_initial_admission_crossmatch"
        cumulative_status = (
            "official_college_cumulative_admission_crossmatch_pending_central_final"
        )
        cumulative_total_status = (
            "official_college_cumulative_admission_total_only_pending_central_final"
        )

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        data_dictionary = (repository_root / "docs" / "data-dictionary.md").read_text(
            encoding="utf-8"
        )
        subject_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admitted-subject-score-distribution-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")
        admission_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admission-data-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")

        self.assertIn(initial_status, data_dictionary)
        self.assertIn(cumulative_status, data_dictionary)
        self.assertIn(cumulative_total_status, data_dictionary)
        self.assertIn("不得省略“首榜”或升级为校级最终录取人口", data_dictionary)
        self.assertIn("禁止推断退出行、禁止称为最终录取人口", data_dictionary)
        self.assertIn("禁止反推四科或称为最终录取人口", data_dictionary)
        self.assertIn("不得进入择校排序、目标分、录取概率", data_dictionary)
        self.assertIn(initial_status, subject_report)
        self.assertIn(cumulative_status, subject_report)
        self.assertIn(cumulative_total_status, subject_report)
        self.assertIn("校级最终公示原附件尚未恢复", subject_report)
        self.assertIn("不计入 18 个正式最终精确格", readme)
        self.assertIn("原先“同时原普通退出 1 人”的说法没有现存正式原件支撑", admission_report)
        self.assertNotIn("后补普通 3，普通规模仍 52", admission_report)
        self.assertIn("院级累计为 `56=普通55+士兵1`", admission_report)


if __name__ == "__main__":
    unittest.main()
