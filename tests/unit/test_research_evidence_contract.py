"""Human-readable research evidence contract guards.

TraceId: 24d3d889-2583-42e7-8766-075fb61b4127
TraceId: 9f847dfc-f892-4055-aa56-c47d48e382b2
TraceId: 614fad46-51a8-4458-9113-dee74007a5d8
TraceId: 53b2918f-73c1-4229-8deb-82aa6150c15f
TraceId: 41b56801-de06-402a-81af-0172921d15c5
TraceId: 1eed09ce-8e9d-4658-a547-a739fbd6d7d8
TraceId: 57871eed-618d-4719-8660-036c68436b08
TraceId: f937b29d-bae2-41b6-b5c7-3048d2fd2834
TraceId: 384a0fbe-85fd-4535-8d51-116f164f3707
TraceId: 3c432a1f-9a1e-46f0-a2f5-b39f1764266d
"""

import re
import unittest
from pathlib import Path


class ResearchEvidenceContractTests(unittest.TestCase):
    def test_lnu_2024_aggregate_constrained_intervals_stay_conditional(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        status = "secondary_aggregate_constrained_final_subject_set_identification"

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
        self.assertIn("所有相容子集都已穷举", data_dictionary)
        self.assertIn("禁止任选一个相容子集形成点估计", data_dictionary)
        self.assertIn("不得进入择校排序、目标分、录取概率", data_dictionary)
        self.assertIn("恰有 **16 个相容最终人口**", subject_report)
        self.assertIn(
            "`314 / 319.5—320 / 325 / 329.51—329.74 / 335.5 / 382`",
            subject_report,
        )
        self.assertIn(
            "`74—78 / 89—90 / 95 / 94.34—95.20 / 100 / 113`",
            subject_report,
        )
        self.assertIn("不是官方最终点分布", subject_report)
        self.assertIn("不进入择校排序、目标分、录取概率", subject_report)
        self.assertIn("条件集合区间、非正式", admission_report)
        self.assertIn("共有 16 个相容人口", admission_report)
        self.assertIn(status, readme)
        self.assertIn("不输出任一猜测点分布、不进入模型", readme)
        self.assertNotIn("101404018", readme)
        self.assertNotIn("101404018", subject_report)
        self.assertNotIn("101404018", admission_report)

    def test_ouc_2026_public_database_observation_excludes_special_plans(self) -> None:
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
        self.assertIn("普通一志愿录取名单（29/39）", subject_report)
        self.assertIn("少数民族骨干 2、退役大学生士兵 1", subject_report)
        self.assertIn("下表只取普通一志愿 29 人", subject_report)
        self.assertIn("`364 / 369 / 378 / 379.34 / 389 / 402`", subject_report)
        self.assertIn("`108 / 123 / 132 / 132.21 / 140 / 150`", subject_report)
        self.assertIn("29 个录取行的四科和全部等于初试总分", subject_report)
        self.assertIn("最低 364 也只是该第三方观察人口的历史尾部", subject_report)
        self.assertIn("公开匿名数据库标记录取 29", admission_report)
        self.assertIn("普通一志愿与 3 名特殊计划分开", admission_report)
        self.assertIn("海大 2026 目标 `002-085404-01`", readme)
        self.assertNotIn("946260907", readme)
        self.assertNotIn("946260907", subject_report)
        self.assertNotIn("946260907", admission_report)

    def test_ouc_2023_public_database_observation_stays_ordinary_and_non_model(self) -> None:
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
        self.assertIn("普通一志愿录取名单（17/21）", subject_report)
        self.assertIn("后 4 行均带同一“未被录取”红色标记", subject_report)
        self.assertIn("| 目标方向普通一志愿拟录取匿名逐行观察", subject_report)
        self.assertIn("`331 / 335 / 342 / 349.41 / 367 / 376`", subject_report)
        self.assertIn("`50 / 55 / 59 / 58.53 / 62 / 67`", subject_report)
        self.assertIn("17 行全部满足四科和等于总分", subject_report)
        self.assertIn("不算正式精确格、不进入择校模型", subject_report)
        self.assertIn("公开匿名数据库标记录取 17", admission_report)
        self.assertIn("特殊计划、校外调剂及方向 02—04 排除", admission_report)
        self.assertIn("海大 2023 目标 `002-085404-01`", readme)
        self.assertNotIn("946260907", readme)
        self.assertNotIn("946260907", subject_report)
        self.assertNotIn("946260907", admission_report)

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
        self.assertIn("不计入 20 个正式最终精确格", readme)
        self.assertIn("原先“同时原普通退出 1 人”的说法没有现存正式原件支撑", admission_report)
        self.assertNotIn("后补普通 3，普通规模仍 52", admission_report)
        self.assertIn("院级累计为 `56=普通55+士兵1`", admission_report)

    def test_nwafu_official_history_and_2026_crossmatch_stays_external(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        report = (
            repository_root
            / "docs"
            / "northwest-af-010-085410-college-incubation-project-audit-2026-08-27.md"
        ).read_text(encoding="utf-8")

        self.assertIn("`official_final_crossmatch`", report)
        self.assertIn("匹配率为 `25/25`", report)
        self.assertIn("`19/19` 一致", report)
        self.assertIn("`276 / 310 / 323 / 330.53 / 357 / 383`", report)
        self.assertIn("`75 / 100.5 / 107 / 111.63 / 131 / 139`", report)
        self.assertIn("`59 / 72.5 / 80 / 81.21 / 90.5 / 101`", report)
        self.assertIn("`278 / 316.25 / 335 / 337.81 / 354.5 / 402`", report)
        self.assertIn("`274 / 297 / 307 / 316.26 / 339 / 379`", report)
        self.assertIn("一志愿复试名单共有 120 行，其中人工智能 80 行", report)
        self.assertIn("匹配 `54/54`、初试总分冲突 0", report)
        self.assertIn("拟录取 43 与面试低于 60 分不予录取 11", report)
        self.assertIn(
            "693EAB6C3242E2D7A318C0CCBC532E14EAEF52F5C099B79E084B6B935A76FFA5",
            report,
        )
        self.assertIn("n、中位数、Q25、Q75 和四科均保持缺失", report)
        self.assertIn("当前 16 项之外", report)
        self.assertIn("不是保底", report)
        self.assertIn("不能把 19 人全部归给方向 06", report)
        self.assertIsNone(re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", report))

        self.assertIn("西北农林2023/2024总分、2025缺口与2026四科交叉续补", readme)
        self.assertIn("`25/25` 交叉", readme)
        self.assertIn("按编号 `54/54` 匹配、初试总分零冲突", readme)
        self.assertIn("处于当前 16 项之外、不并入 16 项、不是保底", readme)

    def test_swjtu_2024_official_final_subject_rows_are_not_total_only(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
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
        decision_matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        data_dictionary = (repository_root / "docs" / "data-dictionary.md").read_text(
            encoding="utf-8"
        )

        source_sha256 = (
            "38A91D798729845B2E66166EF13E1CF84F37093F23852655A2A2E8ABABA2AFCD"
        )
        input_sha256 = (
            "AAD8D1E3BDF5A6D1540FBFA9EB750D5AB77BBB38B0DA61E21C6E16D94F1D514F"
        )

        self.assertIn("20 格能够给出官方确认", subject_report)
        self.assertIn("44 格在官方口径下仍不可计算", subject_report)
        self.assertIn("| 9 | 西南交大 048—085410 | 直(15) | 直(18) |", subject_report)
        self.assertIn("2024 备注空白考试招生代理", subject_report)
        self.assertIn("`official_final_subject_rows`", subject_report)
        self.assertIn("`373 / 383 / 389.5 / 389.06 / 395 / 406`", subject_report)
        self.assertIn("`65 / 69.25 / 71.5 / 71.78 / 75.75 / 79`", subject_report)
        self.assertIn("`67 / 70.5 / 79 / 76.78 / 82 / 84`", subject_report)
        self.assertIn("`93 / 104.5 / 111 / 112.00 / 119.5 / 127`", subject_report)
        self.assertIn("`115 / 120.5 / 129 / 128.50 / 134.5 / 143`", subject_report)
        self.assertIn("`27=备注空白考试招生18+推荐免试9`", subject_report)
        self.assertIn("`18/18` 一致", subject_report)
        self.assertIn(source_sha256, subject_report)
        self.assertIn(source_sha256, admission_report)
        self.assertIn(input_sha256, subject_report)
        self.assertIn(input_sha256, admission_report)
        self.assertIn("同本人 408 可比格仍为 9", readme)
        self.assertIn("20 格能由最终名单直接分科", decision_matrix)
        self.assertIn("西南交大 2024 使用 840", decision_matrix)

        for content in (readme, subject_report, admission_report, decision_matrix):
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

    def test_ecnu_2024_total_only_population_conflict_is_preserved(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
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

        expected_population = "65 = 备注空白 63 + 退役大学生士兵 1 + 少数民族骨干 1"
        expected_stats = "`277 / 333 / 351 / 346.27 / 362.5 / 396`"
        pdf_sha256 = (
            "557FF61FF2FB2B09791F5572B60870F30C2D1EAFC56DE2FE29AAAF099A18249B"
        )
        input_sha256 = (
            "2F535DF879BC5A122644361D0533E0AA513ED60B396D4392A9913283FABC01FA"
        )

        for content in (readme, subject_report, admission_report):
            self.assertIn(expected_population, content)
            self.assertIn(expected_stats, content)
            self.assertIn("全日制非推免 64", content)
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

        self.assertIn("`official_final_total_only`", subject_report)
        self.assertIn("禁止从总分反推", subject_report)
        self.assertIn("20 个正式最终四科精确格也不因此增加", subject_report)
        self.assertIn(pdf_sha256, subject_report)
        self.assertIn(pdf_sha256, admission_report)
        self.assertIn(input_sha256, subject_report)
        self.assertIn(input_sha256, admission_report)

    def test_xju_2023_official_retest_and_final_rows_crossmatch(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
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
        decision_matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        data_dictionary = (repository_root / "docs" / "data-dictionary.md").read_text(
            encoding="utf-8"
        )

        retest_pdf_sha256 = (
            "748DD824778B579A6F9296E79BA08C80D9EA0D79C62A580CF59582877FA5BBF0"
        )
        final_pdf_sha256 = (
            "4DF4813FB82809ABB9BA2BAD3631F8A862676AC68A4F225804F32FCA95D0E446"
        )
        input_sha256 = (
            "1B8368B1A04D6A0147AC882702B8863AB764D6ADB4EA23C63448120BA001C371"
        )
        catalog_mirror_sha256 = (
            "22A1FA21E22B75463C39F92F5E4CA14A16EC3B42B03E2F835CC1DDD39FEEADF7"
        )
        catalog_row_sha256 = (
            "C13F75AF00939174E01966115033AAC07139DA711E9AFA352D2728F70A236FBB"
        )

        self.assertIn("20 格能够给出官方确认", subject_report)
        self.assertIn("44 格在官方口径下仍不可计算", subject_report)
        self.assertIn("| 11 | 新大 308—085405 | 交(普通97；含照顾98) |", subject_report)
        self.assertIn("| 2023 | 镜像重建 `101+204+302+841`；正式原件 404 | `official_final_crossmatch` | 97 |", subject_report)
        self.assertIn("`265 / 288 / 305 / 306.84 / 322 / 368`", subject_report)
        self.assertIn("`45 / 54 / 57 / 57.43 / 60 / 69`", subject_report)
        self.assertIn("`36 / 61 / 67 / 66.19 / 71 / 87`", subject_report)
        self.assertIn("`53 / 71 / 78 / 81.21 / 90 / 122`", subject_report)
        self.assertIn("`65 / 96 / 102 / 102.01 / 110 / 123`", subject_report)
        self.assertIn("`111/111`", subject_report)
        self.assertIn("目标 `085405` 为 `108/108`", subject_report)
        self.assertIn("普通拟录取 97、少民照顾 1、不录取 10", subject_report)
        self.assertIn("`secondary_full_catalog_mirror_reconstruction`", subject_report)
        self.assertIn("不是现存校方原件", subject_report)
        self.assertIn("不得升级 `official_confirmed`", subject_report)
        self.assertIn("数据结构与软件工程", subject_report)
        self.assertIn("未正式闭环；完整镜像重建为 `101+204+302+841`，非 408", admission_report)
        self.assertIn("正式目录状态仍为缺失", admission_report)
        self.assertIn("`secondary_full_catalog_mirror_reconstruction`", data_dictionary)
        self.assertIn("不是数据库枚举", data_dictionary)
        self.assertIn("不得升级为 `official_confirmed`", data_dictionary)
        self.assertIn("一志愿四科名单 108；复试结果 108", admission_report)
        self.assertIn("两份校方表按编号 `111/111`", admission_report)
        self.assertIn("当前官方精确格增至 20", readme)
        self.assertIn("新大 2023", decision_matrix)

        for digest in (retest_pdf_sha256, final_pdf_sha256, input_sha256):
            self.assertIn(digest, subject_report)
            self.assertIn(digest, admission_report)

        for digest in (catalog_mirror_sha256, catalog_row_sha256):
            self.assertIn(digest, subject_report)
            self.assertIn(digest, admission_report)

        for content in (readme, subject_report, admission_report, decision_matrix):
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )


if __name__ == "__main__":
    unittest.main()
