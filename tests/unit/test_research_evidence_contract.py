# 2026-09-05 南农/南师正式2026目录闭合计数同步。TraceId: 7c5b11ea-c254-4da0-a308-c3f4ebd46e00
"""Human-readable research evidence contract guards.

TraceId: 499b5c6e-b2bc-416c-a150-4bf78e49bc56
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
TraceId: 18288fa6-72d8-4607-807f-c03f70e7fe10
TraceId: 354ae7cf-cbdf-4de2-92fd-f360614bd8f5
TraceId: 390f2ab9-0292-4917-b9de-668dc4cfc4f5
TraceId: 8294c615-2632-40f8-895e-6a6e97e53e3c
TraceId: c8739003-06f9-42aa-afa7-19c695d499be
TraceId: e4b04e95-6ee9-429c-af7e-bf968f994e3b
TraceId: cf9326a5-7264-4933-a775-1ed920ab7b90
TraceId: 305d7a30-52fe-4eba-aee8-5df5b12d7e84
TraceId: bc355657-202a-485b-9946-0dad9431ffa7
TraceId: 5d118da0-df5f-478c-8c5b-241928aefc20
TraceId: 988e7aaf-e6e4-4c3a-b0c3-060a233b7d34
TraceId: 71ada3c0-bc77-4c87-a775-1719068abddb
TraceId: 635a5050-f87e-48d7-826d-228a901f4822
TraceId: 6edc56ed-eaf7-416a-b33b-dcd3f41d2fbf
TraceId: e8b68757-b898-4ed7-b8eb-2a7031b04893
TraceId: 7b006898-b827-4b91-ae64-8b6ba249c8ab
TraceId: 75947e87-7d7d-4e86-b03c-89c5f4420488
TraceId: ad850349-4a37-463f-b394-d6e87dbcef02
TraceId: 71923d87-4ec8-46e4-9109-22abddb570be
TraceId: aa7f1d0f-feff-4803-957b-7df040afefb4
TraceId: baf83616-d5f6-40ed-b08d-e87a4aa49a9b
TraceId: 043cb2c4-05bf-4a4b-a42d-0549e03be0cc
TraceId: 378c27e9-2951-45ba-b200-11c72a1938c0
TraceId: a71dcf2f-c136-4847-9959-6eb16320d839
TraceId: 6a309b90-7927-4e4e-8d64-b630a826f375
TraceId: d9de62d0-e46b-4dd0-a840-04afc1862904
TraceId: aa374621-7293-419e-b79e-f7b12c71df22
TraceId: e9125069-3c41-4cef-acdc-28ced5300b60
"""

import csv
import re
import unittest
from pathlib import Path


class ResearchEvidenceContractTests(unittest.TestCase):
    def test_nwafu_selection_aggregate_preserves_denominators_and_unknowns(self) -> None:
        """TraceId: 6bc35b0b-6e98-4911-ba21-e598141e85c5.

        Guard a dangerous data failure: changing the denominator or treating
        unmatched outcomes as rejections can make a low-score fraction misleading.
        This checks public aggregate consistency, not the underlying PDF evidence.
        """
        root = Path(__file__).resolve().parents[2]
        path = root / "docs/nwafu-2026-retest-selection-aggregate-2026-09-05.csv"
        with path.open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        self.assertTrue(rows)
        self.assertFalse({"candidate_id", "candidate_name", "姓名", "考生编号"} & rows[0].keys())
        counts = ("N_listed", "K_observed", "A_provisional", "B_reserve", "R_interview_fail", "U_unmatched")
        bands = {"<300", "300-319", "320-339", "340-359", ">=360"}
        groups = {(r["admission_year"], r["college_code"], r["program_code"]) for r in rows}
        for group in groups:
            cohort = [r for r in rows if (r["admission_year"], r["college_code"], r["program_code"]) == group]
            states = [r for r in cohort if r["record_type"] == "cohort_status"]
            by_band = {r["score_band"]: r for r in states}
            self.assertEqual(len(states), len(by_band))
            self.assertEqual(set(by_band), bands | {"ALL"})
            total = by_band["ALL"]
            for row in states:
                n, k, a, b, rejected, unknown = (int(row[c]) for c in counts)
                self.assertTrue(all(v >= 0 for v in (n, k, a, b, rejected, unknown)))
                self.assertEqual(k, a + b + rejected)
                self.assertEqual(n, k + unknown)
                self.assertIn("面试不合格，不予录取", row["note"])
                self.assertAlmostEqual(float(row["A_over_N_listed"]), a / n, places=9)
                self.assertAlmostEqual(float(row["A_over_K_observed"]), a / k, places=9)
            for field in counts:
                self.assertEqual(sum(int(by_band[b][field]) for b in bands), int(total[field]))
            compositions = [r for r in cohort if r["record_type"] == "admitted_composition"]
            self.assertEqual({r["score_band"] for r in compositions}, {"<300", "<320"})
            for row in compositions:
                selected = ["<300"] if row["score_band"] == "<300" else ["<300", "300-319"]
                self.assertEqual(int(row["numerator"]), sum(int(by_band[b]["A_provisional"]) for b in selected))
                self.assertEqual(int(row["denominator"]), int(total["A_provisional"]))
                self.assertEqual(row["A_over_N_listed"], "")
            ranks = [r for r in cohort if r["record_type"] == "initial_rank_displacement"]
            self.assertEqual({r["metric"] for r in ranks}, {"top_n_not_admitted", "beyond_n_admitted"})
            for row in ranks:
                self.assertEqual(row["K_observed"], total["K_observed"])
                self.assertEqual(row["rank_threshold_n"], total["A_provisional"])
                lower, upper = int(row["count_lower"]), int(row["count_upper"])
                self.assertLessEqual(0, lower)
                self.assertLessEqual(lower, upper)
                self.assertLessEqual(upper, min(int(row["rank_threshold_n"]), int(row["K_observed"]) - int(row["rank_threshold_n"])))
                self.assertEqual(row["N_listed"], "")
            self.assertEqual(ranks[0]["count_lower"], ranks[1]["count_lower"])
            self.assertEqual(ranks[0]["count_upper"], ranks[1]["count_upper"])

    def test_cqu_2024_live_official_zip_upgrades_both_total_only_rows(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        trace_id = "e8b68757-b898-4ed7-b8eb-2a7031b04893"

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        start_here = (
            repository_root / "docs" / "start-here-current-conclusions.md"
        ).read_text(encoding="utf-8")
        national_matrix = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        admission_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admission-data-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")
        subject_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admitted-subject-score-distribution-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")

        for content in (readme, start_here, admission_report, subject_report):
            self.assertIn(trace_id, content)
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

        for content in (readme, admission_report, subject_report):
            self.assertIn("official_final_total_only", content)
            self.assertIn(
                "https://yz.cqu.edu.cn/upload/202405/21165e8c.zip", content
            )
            self.assertIn("90 页", content)
            self.assertIn("1673845 字节", content.replace(",", ""))
            self.assertIn(
                "3DFA591B2BE2ECF8D3267E4BD62650D8FDE9D50A9866B81B3A99C4B605C5FF3C",
                content,
            )
            self.assertIn("68 = 无专项67 + 退役大学生士兵计划1", content)

        self.assertIn(
            "| 2024 | 正式全日制、专项栏为“无” | 25 | 317 | 324 | "
            "340 | 341.04 | 351 | 390 |",
            admission_report,
        )

        self.assertIn("不增加现有 21 个正式最终四科精确格", subject_report)
        self.assertIn("代码级名单没有方向字段", admission_report)

    def test_cqu_2026_controlled_service_does_not_become_public_subject_rows(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        trace_id = "635a5050-f87e-48d7-826d-228a901f4822"

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        admission_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admission-data-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")
        subject_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admitted-subject-score-distribution-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")

        for content in (readme, admission_report, subject_report):
            self.assertIn(trace_id, content)
            self.assertIn("受控考生服务系统访问边界", content)
            self.assertIn("107 人二手子集", content)
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

        self.assertIn("公开逐行表缺失", admission_report)
        self.assertIn("不能要求无关个人提供账号", admission_report)
        self.assertIn(
            "受控考生服务系统访问边界下的 `official_final_total_only`",
            subject_report,
        )
        self.assertIn("正式最终四科统计仍不可计算", subject_report)

    def test_cqu_2023_wayback_digest_upgrades_total_only_not_subject_rows(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        trace_id = "6edc56ed-eaf7-416a-b33b-dcd3f41d2fbf"

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        admission_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admission-data-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")
        subject_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admitted-subject-score-distribution-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")

        for content in (readme, admission_report, subject_report):
            self.assertIn(trace_id, content)
            self.assertIn("KRIIGQG2I4CNST6ZEFIFIOUC4IRVJAZX", content)
            self.assertIn("54508340DA4704D94FD92150543A82E223548337", content)
            self.assertIn("official_final_total_only", content)
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

        self.assertIn("20230918084224", admission_report)
        self.assertIn("2067421 字节", admission_report)
        self.assertIn("252 页", admission_report)
        self.assertIn(
            "2D2E34A2812DEF5B7C928AFA497FAFA060C6AEAC71AEF1D081C191A8A4C15090",
            admission_report,
        )
        self.assertIn("不增加现有 21 个正式最终四科精确格", subject_report)

    def test_upc_085405_keeps_retest_final_special_and_fairness_boundaries(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        report_path = (
            repository_root
            / "docs"
            / "china-university-of-petroleum-east-china-007-085405-four-year-score-special-and-fairness-audit-2026-09-01.md"
        )

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        national = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        linyi = (
            repository_root
            / "docs"
            / "linyi-2026-postgraduate-destination-985-211-audit-2026-08-20.md"
        ).read_text(encoding="utf-8")
        report = report_path.read_text(encoding="utf-8")

        self.assertIn("2023—2025 正式目录均为 `101+204+302+859", report)
        self.assertIn("2026 是本项目首届", report)
        self.assertIn("**326、332、337、301**", report)
        self.assertIn("**83、60、63、66**", report)
        self.assertIn("2024 同线一志愿复试人口，`n=72`", report)
        self.assertIn("`332 / 355 / 356.38 / 399`", report)
        self.assertIn("2025 同线一志愿复试人口，`n=86`", report)
        self.assertIn("`337 / 356 / 358.36 / 411`", report)
        self.assertIn("首轮拟录取者", report)
        self.assertIn("`331 / 366 / 365.69 / 405`", report)
        self.assertIn("复试人口**，不是最终拟录取人口", report)
        self.assertIn("不是攻防上机", report)
        self.assertIn("软件学院专项录取的考生", report)
        self.assertIn("公平性保持 `insufficient`", report)
        self.assertIn("不并入当前 16 项", report)
        self.assertIn(report_path.name, readme)
        self.assertIn(
            "中国石油大学（华东）青岛软件学院、计算机科学与技术学院 `007-085405`（临沂同源优先扩展）",
            matrix,
        )
        self.assertIn(report_path.name, national)
        self.assertIn(report_path.name, linyi)
        self.assertIn("图片归属仍保持 unknown", linyi)
        self.assertIsNone(re.search(r"\b\d{15}\b", report))

    def test_whut_085405_keeps_four_year_location_score_and_fairness_boundaries(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        report_path = (
            repository_root
            / "docs"
            / "wuhan-university-of-technology-010-085405-four-year-score-campus-and-fairness-audit-2026-09-01.md"
        )

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        national = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        linyi = (
            repository_root
            / "docs"
            / "linyi-2026-postgraduate-destination-985-211-audit-2026-08-20.md"
        ).read_text(encoding="utf-8")
        report = report_path.read_text(encoding="utf-8")

        self.assertIn("2023、2024、2025、2026 正式目录都写明", report)
        self.assertIn("当年襄阳只在复试阶段计划出现", report)
        self.assertIn("`338 / 364 / 365.93 / 412`", report)
        self.assertIn("校本部 29 人初试总分最低／中位／平均／最高为 `343 / 368 / 369.34 / 415`", report)
        self.assertIn("襄阳 14 人为 `315 / 352.5 / 354.79 / 404`", report)
        self.assertIn("海南 21 人为 `307 / 357 / 355.29 / 389`", report)
        self.assertIn("`330 / 346 / 347.41 / 371`", report)
        self.assertIn("`351 / 不可计算 / 369.09 / 不可计算`", report)
        self.assertIn("属于进入复试的人群，不是最终录取人群", report)
        self.assertIn("`official_final_total_only`", report)
        self.assertIn("不是攻防", report)
        self.assertIn("襄阳 `1+2`", report)
        self.assertIn("海南当前 `0.5+2.5`", report)
        self.assertIn("公平性仍为 `insufficient`", report)
        self.assertIn("不并入当前 16 项", report)
        self.assertIn(report_path.name, readme)
        self.assertIn(report_path.name, matrix)
        self.assertIn(report_path.name, national)
        self.assertIn(report_path.name, linyi)
        self.assertIn("不能反推该校不录取临沂大学学生", linyi)
        self.assertIsNone(re.search(r"\b\d{15}\b", report))

    def test_scnu_ai_college_keeps_year_direction_score_and_fairness_boundaries(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        report_path = (
            repository_root
            / "docs"
            / "south-china-normal-university-041-085405-085410-four-year-score-campus-and-fairness-audit-2026-09-01.md"
        )

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        national = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        linyi = (
            repository_root
            / "docs"
            / "linyi-2026-postgraduate-destination-985-211-audit-2026-08-20.md"
        ).read_text(encoding="utf-8")
        report = report_path.read_text(encoding="utf-8")

        self.assertIn("2023 年正式目录中是 `101+204+302+933", report)
        self.assertIn("2025、2026 才连续为严格 `101+204+302+408`", report)
        self.assertIn("`311 / 338 / 342.32 / 387`", report)
        self.assertIn("`326 / 367 / 363.29 / 403`", report)
        self.assertIn("2025 `085410` 01—03／非 04 人口", report)
        self.assertIn("`310 / 330.5 / 333.39 / 385`", report)
        self.assertIn("2025 `085410-04` 一志愿", report)
        self.assertIn("一志愿 3＋调剂 8＝11", report)
        self.assertIn("2026 `085410`", report)
        self.assertIn("`327 / 356 / 359.11 / 403`", report)
        self.assertIn("初试、程序设计上机、综合素质分别折最终约 `50% / 25% / 25%`", report)
        self.assertIn("不是“攻防上机”", report)
        self.assertIn("培养与住宿均安排在佛山校区南海校园", report)
        self.assertIn("公平性保持 `insufficient`", report)
        self.assertIn("先研究 `085405`，再研究 `085410` 普通 01—03", report)
        self.assertIn("不并入当前 16 项", report)
        self.assertIn(report_path.name, readme)
        self.assertIn(report_path.name, matrix)
        self.assertIn(report_path.name, national)
        self.assertIn(report_path.name, linyi)
        self.assertIn("不能反推学校不录取临沂大学学生", linyi)
        self.assertIsNone(re.search(r"\b\d{15}\b", report))

    def test_hzau_085404_keeps_predecessor_special_final_and_fairness_boundaries(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        report_path = (
            repository_root
            / "docs"
            / "huazhong-agricultural-university-317-085404-085400-four-year-score-special-and-fairness-audit-2026-09-01.md"
        )

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        national = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        report = report_path.read_text(encoding="utf-8")

        self.assertIn("2023、2024 正式目录是 `085400 电子信息`", report)
        self.assertIn("2025、2026 才拆成 `085404 计算机技术`", report)
        self.assertIn("`295 / 322 / 323.81 / 394`", report)
        self.assertIn("`283 / 333.5 / 335.53 / 377`", report)
        self.assertIn("`303 / 333 / 330.65 / 376`", report)
        self.assertIn("`326 / 349 / 355.50 / 397`", report)
        self.assertIn("卓工 8 人和士兵 3 人", report)
        self.assertIn("仍可能混有卓工", report)
        self.assertIn("2024、2025 目标最终表当前缺失", report)
        self.assertIn("不是攻防上机", report)
        self.assertIn("公平性保持 `insufficient`", report)
        self.assertIn("不并入当前 16 项", report)
        self.assertIn(report_path.name, readme)
        self.assertIn(report_path.name, matrix)
        self.assertIn(report_path.name, national)
        self.assertIsNone(re.search(r"\b\d{15}\b", report))

    def test_changan_target_projects_keep_subject_special_final_and_fairness_boundaries(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        report_path = (
            repository_root
            / "docs"
            / "changan-university-006-085405-085404-022-085400-four-year-score-subject-special-and-fairness-audit-2026-09-01.md"
        )

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        national = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        report = report_path.read_text(encoding="utf-8")

        self.assertIn("信息工程学院两条主线在 2023—2025 考 `846 计算机类学科基础`", report)
        self.assertIn("2024 数据院保留 `pending_exact_catalog`", report)
        self.assertIn("2026 才正式切换为 408", report)
        self.assertIn("`356 / 368 / 374.06 / 410`", report)
        self.assertIn("`361 / 370 / 372.04 / 399`", report)
        self.assertIn("`346 / 369 / 370.10 / 402`", report)
        self.assertIn("2023 是 `N/A`", report)
        self.assertIn("`343 / 350.5 / 355.20 / 373`", report)
        self.assertIn("退役士兵、1 名少民骨干", report)
        self.assertIn("专项低分不并入普通人口", report)
        self.assertIn("不是网络安全攻防", report)
        self.assertIn("公平性保持 `insufficient`", report)
        self.assertIn("不并入当前 16 项", report)
        self.assertIn(report_path.name, readme)
        self.assertIn(report_path.name, matrix)
        self.assertIn(report_path.name, national)
        self.assertIsNone(re.search(r"\b\d{15}\b", report))

    def test_sicau_085400_keeps_subject_final_retest_and_fairness_boundaries(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        report_path = (
            repository_root
            / "docs"
            / "sichuan-agricultural-university-419-085400-four-year-score-subject-campus-and-fairness-audit-2026-09-01.md"
        )

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        national = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        report = report_path.read_text(encoding="utf-8")

        self.assertIn("2023—2025 正式第四科均为 `866 数据结构`", report)
        self.assertIn("只有 2026 才首次改为 408", report)
        self.assertIn("`324 / 320 / 330 / 307`", report)
        self.assertIn("`325 / 361 / 364.05 / 414`", report)
        self.assertIn("`321 / 337 / 341.92 / 386`", report)
        self.assertIn("不得用 38、计划 26 或推免 0 代替最终人口", report)
        self.assertIn("不得用计划 31、推免 2、复试线 307 生成最终分布", report)
        self.assertIn("不是攻防上机", report)
        self.assertIn("公平性保持 `insufficient`", report)
        self.assertIn("`conditional_research`", report)
        self.assertIn("不并入当前 16 项", report)
        self.assertIn(report_path.name, readme)
        self.assertIn(report_path.name, matrix)
        self.assertIn(report_path.name, national)
        self.assertIsNone(re.search(r"\b\d{15}\b", report))

    def test_swu_085400_keeps_subject_special_final_and_fairness_boundaries(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        report_path = (
            repository_root
            / "docs"
            / "southwest-university-321-085400-four-year-score-subject-special-and-fairness-audit-2026-09-01.md"
        )

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        national = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        report = report_path.read_text(encoding="utf-8")

        self.assertIn("2023、2024 是 `907 计算机基础与数字电路`", report)
        self.assertIn("2025、2026 是 `891 计算机基础与数字电路`", report)
        self.assertIn("四年普通主线复试门槛依次可观察为 `330 / 300 / 311 / 281`", report)
        self.assertIn("报考 289、录取 120", report)
        self.assertIn("最低 298、平均 356、最高 423", report)
        self.assertIn("`111 + 5 专项`，合计 116", report)
        self.assertIn("完全不是攻防上机", report)
        self.assertIn("公平性保持 `insufficient`", report)
        self.assertIn("2026 学校级：`non_strict`", report)
        self.assertIn("2027 项目线索：`pending_exact_catalog`", report)
        self.assertIn("不并入当前 16 项", report)
        self.assertIn(report_path.name, readme)
        self.assertIn(report_path.name, matrix)
        self.assertIn(report_path.name, national)
        self.assertIn(
            "`strict_match` 56、`non_strict` 29、`no_relevant_program` 9、"
            "`pending_exact_catalog` 17",
            national,
        )
        self.assertIn("| 96 | 西南大学 | `non_strict` |", national)
        self.assertIsNone(re.search(r"\b\d{15}\b", report))

    def test_nefu_085404_085405_closes_2026_and_keeps_history_separate(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        report_path = (
            repository_root
            / "docs"
            / "northeast-forestry-university-012-085404-085405-four-year-score-subject-special-and-fairness-audit-2026-09-01.md"
        )

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        national = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        report = report_path.read_text(encoding="utf-8")

        self.assertIn("2023—2024 目标项目考 `921", report)
        self.assertIn("2025—2026 才改为 408", report)
        self.assertIn("`273 / 293 / 303 / 328`", report)
        self.assertIn("`273 / 273 / 260 / 322`", report)
        self.assertIn("`101+204+302+408`", report)
        self.assertIn("结构化面试", report)
        self.assertIn("更不是攻防上机", report)
        self.assertIn("公平性结论只能是 `insufficient`", report)
        self.assertIn("`regional_conditional_research`", report)
        self.assertIn("不并入当前 16 项", report)
        self.assertIn(report_path.name, readme)
        self.assertIn(report_path.name, matrix)
        self.assertIn(report_path.name, national)
        self.assertIn("| 40 | 东北林业大学 | `strict_match` |", national)
        self.assertIn(
            "`strict_match` 56、`non_strict` 29、`no_relevant_program` 9、"
            "`pending_exact_catalog` 17",
            national,
        )
        for content in (report, readme, matrix, national):
            self.assertIsNone(re.search(r"\b\d{15}\b", content))

    def test_jiangnan_expansion_keeps_catalog_direction_and_fairness_boundaries(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        report_path = (
            repository_root
            / "docs"
            / "jiangnan-university-031-085405-four-year-score-direction-and-fairness-audit-2026-09-01.md"
        )

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        national = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        linyi = (
            repository_root
            / "docs"
            / "linyi-2026-postgraduate-destination-985-211-audit-2026-08-20.md"
        ).read_text(encoding="utf-8")
        report = report_path.read_text(encoding="utf-8")

        self.assertIn("2023—2025 正式目录均为 `101+204+302+851", report)
        self.assertIn("首届 408 人群", report)
        self.assertIn("严格状态仍保持 `pending_exact_catalog`", report)
        self.assertIn("2024 为 `58/58`、2025 为 `67/67`、2026 为 `51/51`", report)
        self.assertIn("`350 / 368.5 / 371.02 / 419`", report)
        self.assertIn("`84 / 101.5 / 101.46 / 120`", report)
        self.assertIn("不能改写成“最终已录取”", report)
        self.assertIn("`03 网络软件与安全`", report)
        self.assertIn("方向 03 与本人边界冲突，必须排除", report)
        self.assertIn("公平性结论只能是 `insufficient`", report)
        self.assertIn("不生成冲稳保、目标分或录取概率", report)
        self.assertIn(report_path.name, readme)
        self.assertIn("江南大学人工智能与计算机学院 `031-085405`（高压条件扩展）", matrix)
        self.assertIn("状态保持 `pending_exact_catalog`", matrix)
        self.assertIn(report_path.name, national)
        self.assertIn(report_path.name, linyi)
        self.assertIn("不能反向证明图片个案就是该专硕", linyi)
        self.assertIsNone(re.search(r"\b\d{15}\b", report))
        self.assertNotIn("faiusr.com", report)

    def test_imu_expansion_keeps_retest_final_and_fairness_boundaries(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        report_path = (
            repository_root
            / "docs"
            / "inner-mongolia-university-009-085404-085411-four-year-score-and-fairness-audit-2026-09-01.md"
        )

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        report = report_path.read_text(encoding="utf-8")

        self.assertIn("2024、2025、2026 三个招生年度", report)
        self.assertIn("2023 第四科是 892；2024—2026 才是 408", report)
        self.assertIn("复试四科均值绝不能冒充最终录取者四科分布", report)
        self.assertIn("原文 `398［254—358］`，均值无效", report)
        self.assertIn("不会擅自猜成 298", report)
        self.assertIn("官方线 251；二手页误写 250", report)
        self.assertIn("`106+2专项调剂`", report)
        self.assertIn("不能说“友好”", report)
        self.assertIn("当前公平性结论必须保持 `insufficient`", report)
        self.assertIn("不并入当前 16 项", report)
        self.assertIn("不生成个人录取概率、目标分或冲稳保结论", report)
        self.assertIn(report_path.name, readme)
        self.assertIn("没有擅自改成 298", readme)
        self.assertIn("公平性结论均保持 `insufficient`", readme)
        self.assertIn("内蒙古大学计算机学院 `085404`（临沂同源扩展）", matrix)
        self.assertIn("内蒙古大学计算机学院 `085411`（临沂同源扩展）", matrix)
        self.assertIn("已判不可用且不猜 298", matrix)
        self.assertNotIn("085412 网络与信息安全`（临沂同源扩展）", matrix)

    def test_zzu_2026_official_final_subject_crossmatch_closes_exact_grid(
        self,
    ) -> None:
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

        for expected in (
            "BFCBC8890242491DC73F50FECF8391174C977335B66610B041F7D9DF3925242D",
            "3D8C78C055B63EA2B8BA8159AEF472993A3B271F973C53A3F8EF120E1E7A49C2",
            "4C7838E779CFF9A8AEDB2594200E396CBC3DD55C8259908A6E7C7BC6363128C6",
            "B7A1CCBCB39E8566E01D71724A04CDBB72FAC2FBF12B3DB61B03476B07A92E7B",
            "D55FCD932578B4AFA0CD13C1D39E1A5723E91F6F0AD11C97F713A9630FBFF767",
        ):
            self.assertIn(expected, subject_report)

        self.assertIn("一志愿复试名册 101 行与学院结果表 `101/101`", subject_report)
        self.assertIn("目标在第 125—127 页跨页分布为 `19+62+5=86` 行", subject_report)
        self.assertIn("最终总分 `86/86` 与名册一致", subject_report)
        self.assertIn("四科和 `86/86` 等于总分", subject_report)
        self.assertIn("`official_final_crossmatch`", subject_report)
        # TraceId: 12b10116-09ad-4a8a-b786-73ec9056d13d. Retained official
        # 2024/2025 finals provide totals only; no additional four-subject grid.
        self.assertIn("| 8 | 郑大 084—085410 | 总 | 总 | 总 | 交(86) |", subject_report)
        self.assertIn(
            "| P1 | 初试总分 | 337 | 354 | 368 | 369.28 | 381.75 | 427 |",
            subject_report,
        )
        self.assertIn(
            "| P1 | 政治 | 54 | 65 | 68 | 67.35 | 70 | 76 |",
            subject_report,
        )
        self.assertIn(
            "| P1 | 英语二 | 63 | 74.25 | 79 | 78.28 | 82 | 90 |",
            subject_report,
        )
        self.assertIn(
            "| P1 | 数学二 | 94 | 117.25 | 125 | 124.16 | 132.75 | 150 |",
            subject_report,
        )
        self.assertIn(
            "| P1 | 408 | 79 | 96 | 99 | 99.49 | 106 | 121 |",
            subject_report,
        )
        self.assertIn("2023—2025 仍不能计算最终录取者四科分布", subject_report)
        self.assertIn(
            "2023—2025 的四科均值**只描述进入复试的人群，不描述最终拟录取人群**",
            subject_report,
        )
        self.assertIn(
            "| 2023 | 77 | 页面未给 | 336 | 页面未给 | 68 | 76 | 104 | 90 |",
            subject_report,
        )
        self.assertIn("与校方最终人口不一致", subject_report)
        self.assertIn("拟录取最高 413 高于复试最高 403", subject_report)
        self.assertIn("不进入择校排序、目标分或录取概率", subject_report)
        self.assertIn("当前官方精确格成为 21、严格 22408 同卷格成为 10", readme)
        self.assertIn("旧库的 85 人来自跨页漏取 1 行", subject_report)
        self.assertIn("旧主张没有删除，而是追加 `unresolved` 裁决", subject_report)
        self.assertIn("21 格能够给出官方确认", subject_report)
        self.assertIn("43 格在官方口径下仍不可计算", subject_report)
        self.assertIn("21 格中有 10 格", subject_report)
        self.assertIn("当前 21 格能由最终名单直接分科", decision_matrix)
        self.assertIn("数据库保留旧主张并追加 `unresolved`", admission_report)

        for content in (readme, subject_report, admission_report, decision_matrix):
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

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
            "| 初试总分 | 314 | 319.5—320 | 325 | 329.51—329.74 | 335.5 | 382 |",
            subject_report,
        )
        self.assertIn(
            "| 408 | 74—78 | 89—90 | 95 | 94.34—95.20 | 100 | 113 |",
            subject_report,
        )
        self.assertIn("不是官方最终点分布", subject_report)
        self.assertIn("不进入择校排序、目标分、录取概率", subject_report)
        self.assertIn(
            "| 2024 | 16 个相容最终集合 | 35 | 314 | 319.5—320 | 325 | "
            "329.51—329.74 | 335.5 | 382 | 每列为所有相容集合的固定值或严格区间 |",
            admission_report,
        )
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
        self.assertIn(
            "| P1 | 初试总分 | 364 | 369 | 378 | 379.34 | 389 | 402 |",
            subject_report,
        )
        self.assertIn(
            "| P1 | 数学二 | 108 | 123 | 132 | 132.21 | 140 | 150 |",
            subject_report,
        )
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
        self.assertIn("| P1 | 目标方向普通一志愿拟录取匿名逐行观察", subject_report)
        self.assertIn(
            "| P1 | 初试总分 | 331 | 335 | 342 | 349.41 | 367 | 376 |",
            subject_report,
        )
        self.assertIn(
            "| P1 | 政治 | 50 | 55 | 59 | 58.53 | 62 | 67 |",
            subject_report,
        )
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
        self.assertIn("普通一志愿录取名单（25/32）", subject_report)
        self.assertIn("有成绩人口是 `44=普通30+创新14`", subject_report)
        self.assertIn("最终观察是 `39=普通25+创新14`", subject_report)
        self.assertIn("| P1 | 目标方向非创新计划拟录取逐行观察", subject_report)
        self.assertIn(
            "| P1 | 初试总分 | 317 | 328 | 332 | 335.08 | 337 | 369 |",
            subject_report,
        )
        self.assertIn("目录阶段计划 8、复试实施细则计划表镜像中的统考 23 + 创新 14", subject_report)
        self.assertIn("不算正式精确格、不能进入择校模型", subject_report)
        self.assertIn("名单口径 46、有成绩口径 44", admission_report)
        self.assertIn("同期完整名单 PDF 镜像 39 = 备注空白 25 + 创新计划 14", admission_report)
        self.assertIn("初始计划镜像为统考 23 + 创新 14", admission_report)
        self.assertIn("96 页、715789 字节", admission_report)
        self.assertIn(
            "070C808118232C7E0E5326EDF3C637EA327E167810F407895CCF89C8A014851B",
            admission_report,
        )
        self.assertIn("表内不含初试总分或四科分列", admission_report)
        self.assertIn("39=备注空白25+创新人才培养计划14", subject_report)
        self.assertIn("只加强“最终人口是 25+14”的旁证", subject_report)
        self.assertIn("海大 2024 目标 `002-085404-01`", readme)
        self.assertNotIn("zhuanlan.zhihu.com/p/697755981", readme)
        self.assertNotIn("zhuanlan.zhihu.com/p/697755981", subject_report)

    def test_ouc_2025_cross_page_mirror_restores_only_degraded_population_and_scores(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        status = "secondary_visible_mirror_final_subject_observation"

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        data_dictionary = (repository_root / "docs" / "data-dictionary.md").read_text(
            encoding="utf-8"
        )
        admission_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admission-data-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")
        subject_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admitted-subject-score-distribution-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")
        start_here = (
            repository_root / "docs" / "start-here-current-conclusions.md"
        ).read_text(encoding="utf-8")
        public_docs = "\n".join((readme, admission_report, subject_report, start_here))

        self.assertIn(f"`{status}`", data_dictionary)
        self.assertIn("不得进入择校排序、目标分、录取概率", data_dictionary)
        self.assertIn("66 页、794115 字节", subject_report)
        self.assertIn(
            "67BEB14A15D24322711EA39269577D707C1CEB1295D4205017A83A5E8271679C",
            subject_report,
        )
        self.assertIn("`50=12+38`", subject_report)
        self.assertIn("此前 38 是只数物理第 8 页", subject_report)
        self.assertIn("29 个“创新人才培养计划”备注行", subject_report)
        self.assertIn("`创新14 + 其余36`", subject_report)
        self.assertIn(
            "| P1 | 初试总分 | 339 | 348.75 | 354.5 | 357.56 | 362.5 | 390 |",
            subject_report,
        )
        self.assertIn(
            "| P2 | 初试总分 | 262 | 311.25 | 326 | 327.07 | 348.75 | 362 |",
            subject_report,
        )
        self.assertIn(
            "| P3 | 初试总分 | 262 | 344.25 | 352 | 349.02 | 359.75 | 390 |",
            subject_report,
        )
        self.assertIn(
            "710FD9BB88904A8DDA4A9C48ECBC041F4508D85B7CEF5C5280142E1C46F309E3",
            subject_report,
        )
        self.assertIn(
            "D9C1A19C58A8DB6843F50595B901A6A4F1B953A5BCFCED7CB12842B99B096FA9",
            subject_report,
        )
        self.assertIn(
            "BEE3CD0042CED03AD229A5C81592739CC5FC78A819EC301E0209E9DFEF6082C7",
            subject_report,
        )
        self.assertIn("正式状态仍是 `official_retest_subject_rows_only`", subject_report)
        self.assertIn("普通 36 + 创新 14", start_here)
        self.assertIn("跨页错误", readme)
        self.assertNotIn("ncstatic.clewm.net", public_docs)
        self.assertNotIn("qr61.cn", public_docs)
        self.assertIsNone(re.search(r"\b104235\d{9}\b", public_docs))

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
        self.assertIn("不计入当前正式最终精确格", readme)
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

        self.assertIn("21 格能够给出官方确认", subject_report)
        self.assertIn("43 格在官方口径下仍不可计算", subject_report)
        self.assertIn("| 9 | 西南交大 048—085410 | 直(15) | 直(18) |", subject_report)
        self.assertIn("2024 备注空白考试招生代理", subject_report)
        self.assertIn("`official_final_subject_rows`", subject_report)
        self.assertIn(
            "| P2 | 初试总分 | 373 | 383 | 389.5 | 389.06 | 395 | 406 |",
            subject_report,
        )
        self.assertIn(
            "| P2 | 政治 | 65 | 69.25 | 71.5 | 71.78 | 75.75 | 79 |",
            subject_report,
        )
        self.assertIn(
            "| P2 | 英语 | 67 | 70.5 | 79 | 76.78 | 82 | 84 |",
            subject_report,
        )
        self.assertIn(
            "| P2 | 数学 | 93 | 104.5 | 111 | 112.00 | 119.5 | 127 |",
            subject_report,
        )
        self.assertIn(
            "| P2 | 业务课二 | 115 | 120.5 | 129 | 128.50 | 134.5 | 143 |",
            subject_report,
        )
        self.assertIn("`27=备注空白考试招生18+推荐免试9`", subject_report)
        self.assertIn("`18/18` 一致", subject_report)
        self.assertIn(source_sha256, subject_report)
        self.assertIn(source_sha256, admission_report)
        self.assertIn(input_sha256, subject_report)
        self.assertIn(input_sha256, admission_report)
        self.assertIn("该格本身不增加严格 22408 同卷计数", readme)
        self.assertIn("21 格能由最终名单直接分科", decision_matrix)
        self.assertIn("西南交大 2024 又直接含四科但使用 840", decision_matrix)

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
            self.assertIn("全日制非推免 64", content)
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

        self.assertIn(expected_stats, readme)
        self.assertIn(
            "| P1 | 初试总分 | 277 | 333 | 351 | 346.27 | 362.5 | 396 |",
            subject_report,
        )
        self.assertIn(
            "| 2024 | 校级公示中全日制备注空白代理人口 | 63 | 277 | "
            "333 | 351 | 346.27 | 362.5 | 396 |",
            admission_report,
        )

        self.assertIn("`official_final_total_only`", subject_report)
        self.assertIn("禁止从总分反推", subject_report)
        self.assertIn("现有正式最终四科精确格也不因此增加", subject_report)
        self.assertIn(pdf_sha256, subject_report)
        self.assertIn(pdf_sha256, admission_report)
        self.assertIn(input_sha256, subject_report)
        self.assertIn(input_sha256, admission_report)

    def test_ecnu_2023_learning_modes_are_preserved_and_not_split_from_mixed_list(self) -> None:
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
        start_here = (
            repository_root / "docs" / "start-here-current-conclusions.md"
        ).read_text(encoding="utf-8")
        decision_matrix = (
            repository_root / "docs" / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")

        trace_id = "aa1622ae-aa5b-406a-b0a2-80621d87cbbd"
        final_pdf_sha256 = (
            "3D04911AE5315FB0AB28152385EB88F0DA68B83FAFB8DB744E848DC8191A390A"
        )

        for content in (readme, subject_report, admission_report, start_here):
            self.assertIn(trace_id, content)
            self.assertIn("全日制报考 325、录取 52", content)
            self.assertIn("非全日制报考 211、录取 70", content)
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

        self.assertIn(trace_id, decision_matrix)
        self.assertIn("全日制是报考 325、录取 52", decision_matrix)
        self.assertIn("非全日制是报考 211、录取 70", decision_matrix)

        for content in (readme, subject_report, admission_report, start_here):
            self.assertIn("122", content)
            self.assertIn("52+70", content)
            self.assertIn("不能", content)

        self.assertIn(final_pdf_sha256, subject_report)
        self.assertIn(final_pdf_sha256, admission_report)
        self.assertIn("正式分科状态继续为 `missing`", subject_report)
        for content in (readme, subject_report, admission_report):
            self.assertIn("secondary_conflicted_aggregate_lead", content)
            self.assertIn("21非全+70调剂", content)
            self.assertIn("冲突", content)
        self.assertIn("373【324—430】", readme)
        self.assertIn(
            "| 页面拟录取栏 | 52 | 324 | 373 | 430 |",
            subject_report,
        )
        self.assertIn(
            "拟录取写为 52 人、初试平均分 373、最低分 324、最高分 430",
            admission_report,
        )
        self.assertIsNone(
            re.search(r"(?<!非)全日制报考 211、录取 70", admission_report)
        )
        self.assertNotIn("非全日制报考 325、录取 52", admission_report)

    def test_ecnu_2025_hidden_official_pdf_restores_total_only_population(self) -> None:
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
        start_here = (
            repository_root / "docs" / "start-here-current-conclusions.md"
        ).read_text(encoding="utf-8")
        decision_matrix = (
            repository_root / "docs" / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")

        expected_population = (
            "67 = 备注空白 64 + 少数民族骨干 1 + 退役大学生士兵 2"
        )
        expected_stats = "`289 / 336 / 352.5 / 350.13 / 364.75 / 402`"
        readability_trace_id = "aa374621-7293-419e-b79e-f7b12c71df22"
        trace_id = "ff640f6c-7242-4569-bbc2-860756e89ece"
        pdf_sha256 = (
            "D0BC7227380EAC69AF655828071B175D9D4B847F6C4CB29787A245105513C45E"
        )
        input_sha256 = (
            "864640992C66B19B35020DA13040909D98E044926B7FA8E014560C174D92B68C"
        )

        for content in (readme, subject_report, admission_report, start_here):
            self.assertIn(expected_population, content)
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

        self.assertIn(expected_stats, readme)
        self.assertNotIn(expected_stats, start_here)
        self.assertIn(readability_trace_id, start_here)
        self.assertIn(
            "| 2025 | `135-085404-01` 全日制、备注空白的普通一志愿录取者 "
            "| 64 | 289 | 336 | 352.5 | 350.13 | 364.75 | 402 |",
            start_here,
        )
        self.assertIsNone(
            re.search(
                r"(?<![\d.])\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?){5}(?![\d.])",
                start_here,
            )
        )
        self.assertIn(
            "| P2 | 初试总分 | 289 | 336 | 352.5 | 350.13 | 364.75 | 402 |",
            subject_report,
        )
        self.assertIn(
            "| 2025 | 普通一志愿／全日制备注空白人口 | 64 | 289 | "
            "336 | 352.5 | 350.13 | 364.75 | 402 |",
            admission_report,
        )

        for content in (subject_report, admission_report):
            self.assertIn(pdf_sha256, content)
            self.assertIn(input_sha256, content)
            self.assertIn("`official_final_total_only`", content)

        for content in (subject_report, admission_report, start_here, decision_matrix):
            self.assertIn(trace_id, content)

        self.assertIn(
            "| 5 | 华东师大 135—085404-01 | 缺 | 总 | 总 | 复 |",
            subject_report,
        )
        self.assertIn("2025 原表只有总分、无四科", decision_matrix)
        self.assertIn("2026 最终普通分布仍缺", decision_matrix)

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

        self.assertIn("21 格能够给出官方确认", subject_report)
        self.assertIn("43 格在官方口径下仍不可计算", subject_report)
        self.assertIn("| 11 | 新大 308—085405 | 交(普通97；含照顾98) |", subject_report)
        self.assertIn("| P1 | 2023 | 镜像重建 `101+204+302+841`；正式原件 404 | `official_final_crossmatch` | 97 |", subject_report)
        self.assertIn(
            "| P1 | 初试总分 | 265 | 288 | 305 | 306.84 | 322 | 368 |",
            subject_report,
        )
        self.assertIn(
            "| P1 | 政治 | 45 | 54 | 57 | 57.43 | 60 | 69 |",
            subject_report,
        )
        self.assertIn(
            "| P1 | 外语 | 36 | 61 | 67 | 66.19 | 71 | 87 |",
            subject_report,
        )
        self.assertIn(
            "| P1 | 业务课一 | 53 | 71 | 78 | 81.21 | 90 | 122 |",
            subject_report,
        )
        self.assertIn(
            "| P1 | 业务课二 | 65 | 96 | 102 | 102.01 | 110 | 123 |",
            subject_report,
        )
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
        self.assertIn("当前官方精确格成为 21、严格 22408 同卷格成为 10", readme)
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

    def test_shanghai_university_four_year_route_audit_stays_project_scoped(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        report_name = (
            "shanghai-university-008-085405-085410-423-085410-"
            "four-year-score-subject-route-and-fairness-audit-2026-09-02.md"
        )

        report = (repository_root / "docs" / report_name).read_text(encoding="utf-8")
        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        decision_matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        national_matrix = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        linyi = (
            repository_root
            / "docs"
            / "linyi-2026-postgraduate-destination-985-211-audit-2026-08-20.md"
        ).read_text(encoding="utf-8")

        self.assertIn("2025→2026 一年上升 43 分", report)
        self.assertIn("`359 / 367 / 378 / 377.95 / 386 / 406`", report)
        self.assertIn("`334 / 347.5 / 362.5 / 363.60 / 376 / 423`", report)
        self.assertIn("`116 / 130 / 136 / 135.44 / 141 / 150`", report)
        self.assertIn("2023 `423-085400` 两方向混合普通人口", report)
        self.assertIn("不能发布严格 408 人口的分科分布", report)
        self.assertIn("初试最多贡献 250 分，即 **62.5%**", report)
        self.assertIn("不是攻防", report)
        self.assertIn("公平性只能保持 `insufficient`", report)
        self.assertIn("`008-085405 → 423-085410 → 008-085410`", decision_matrix)

        for content in (
            readme,
            decision_matrix,
            national_matrix,
            linyi,
        ):
            self.assertIn(report_name, content)

        for content in (
            report,
            readme,
            decision_matrix,
            national_matrix,
            linyi,
        ):
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

    def test_hunan_audit_and_admission_report_are_human_readable(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        trace_id = "7b006898-b827-4b91-ae64-8b6ba249c8ab"
        report_name = (
            "hunan-university-085400-four-year-score-subject-retest-training-"
            "and-fairness-audit-2026-09-03.md"
        )

        report = (repository_root / "docs" / report_name).read_text(encoding="utf-8")
        admission_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admission-data-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")
        subject_report = (
            repository_root
            / "docs"
            / "current-16-four-year-admitted-subject-score-distribution-audit-2026-08-31.md"
        ).read_text(encoding="utf-8")
        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        docs_readme = (repository_root / "docs" / "README.md").read_text(
            encoding="utf-8"
        )
        report_index = (
            repository_root / "docs" / "research-report-index.md"
        ).read_text(encoding="utf-8")
        start_here = (
            repository_root / "docs" / "start-here-current-conclusions.md"
        ).read_text(encoding="utf-8")
        decision_matrix = (
            repository_root
            / "docs"
            / "current-candidate-decision-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")
        national_matrix = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")

        for content in (
            report,
            admission_report,
            readme,
            docs_readme,
            report_index,
            start_here,
            decision_matrix,
            national_matrix,
        ):
            self.assertIn(trace_id, content)
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

        self.assertIn("`101+204+302+866`", report)
        self.assertIn("第四科：`866 → 408`", report)
        self.assertIn("2027 仍是 `pending_exact_catalog`", report)
        self.assertIn(
            "| 2026 | 合并后的 `085400 电子信息` | 105 | 368 | 368 | "
            "396 | 396.10 | 437 |",
            report,
        )
        self.assertIn("**不是攻防上机**", report)
        self.assertIn("公平性证据只能保持 `insufficient`", report)
        self.assertIn(report_name, readme)
        self.assertIn(report_name, report_index)
        self.assertIn(report_name, start_here)
        self.assertIn(report_name, decision_matrix)
        self.assertIn(report_name, national_matrix)
        self.assertIn("| 80 | 湖南大学 | `non_strict` |", national_matrix)
        self.assertIn(
            "`strict_match` 56、`non_strict` 29、`no_relevant_program` 9、"
            "`pending_exact_catalog` 17",
            national_matrix,
        )

        self.assertGreaterEqual(admission_report.count("25% 位置分数"), 16)
        self.assertGreaterEqual(admission_report.count("75% 位置分数"), 16)
        self.assertNotIn("最终初试六统计", admission_report)
        self.assertNotIn("min / Q25 / median / mean / Q75 / max", admission_report)
        self.assertNotIn("一志愿 40：`350 / 374", admission_report)
        self.assertNotIn("331 / 374 / 383 / 385.24 / 397 / 426", admission_report)
        self.assertIn(
            "| 2023 | 全年口径，含 1 名士兵调剂 | 41 | 331 | 374 | 383 | "
            "385.24 | 397 | 426 |",
            admission_report,
        )
        self.assertIsNone(
            re.search(
                r"(?<![\d.])\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?){5}(?![\d.])",
                admission_report,
            )
        )
        self.assertIn(
            "六项分数逐列标注与统计人口复核 TraceId："
            "`0ddbe3d5-27d4-4d36-8db6-1ac3e63d14c7`",
            admission_report,
        )
        self.assertIn(
            "厦门大学复试门槛字段中文化 TraceId："
            "`58d50d3d-0f4d-422e-b612-bf4c0c568265`",
            admission_report,
        )
        self.assertIn(
            "总分 343；政治 50；英语二 50；数学二 75；408 75",
            admission_report,
        )
        self.assertNotIn("单科 50/50/75/75", admission_report)
        self.assertNotIn("`min/Q25/median/mean/Q75/max`", readme)
        self.assertNotIn("331/374/383/385.24/397/426", readme)
        self.assertIn(
            "样本人数、最低分、25% 位置分数、中位数、平均分、"
            "75% 位置分数、最高分、证据状态",
            readme,
        )
        self.assertIn(
            "分科统计逐字段表格化 TraceId："
            "`ad850349-4a37-463f-b394-d6e87dbcef02`",
            subject_report,
        )
        self.assertNotIn("min / Q25 / median / mean / Q75 / max", subject_report)
        self.assertNotIn("Q25", subject_report)
        self.assertNotIn("Q75", subject_report)
        self.assertIn(
            "| P1 | 初试总分 | 350 | 374 | 383.5 | 386.60 | 397 | 426 |",
            subject_report,
        )
        self.assertIsNone(
            re.search(
                r"(?<![\d.])\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?){5}(?![\d.])",
                subject_report,
            )
        )

    def test_2027_first_switch_408_report_labels_every_subject_field(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        trace_id = "93ced22b-88eb-4dca-a6a1-1c011927c364"
        report_name = (
            "2027-first-switch-408-985-software-engineering-audit-2026-09-03.md"
        )

        report = (repository_root / "docs" / report_name).read_text(encoding="utf-8")
        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        docs_readme = (repository_root / "docs" / "README.md").read_text(
            encoding="utf-8"
        )
        report_index = (
            repository_root / "docs" / "research-report-index.md"
        ).read_text(encoding="utf-8")
        start_here = (
            repository_root / "docs" / "start-here-current-conclusions.md"
        ).read_text(encoding="utf-8")

        national_matrix = (
            repository_root
            / "docs"
            / "national-211-strict-22408-status-matrix-2026-08-24.md"
        ).read_text(encoding="utf-8")

        self.assertIn(trace_id, report)
        for content in (readme, docs_readme, report_index, start_here):
            self.assertIn(trace_id, content)
            self.assertIn(report_name, content)

        for content in (report, readme, docs_readme, report_index, start_here):
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

        for field in (
            "第一科：政治",
            "第二科：外语",
            "第三科：数学",
            "第四科：专业基础",
        ):
            self.assertIn(field, report)

        self.assertIn("专业名称是否就是“软件工程”", report)
        self.assertIn("二手线索待校方原件", report)
        self.assertIn("禁止升级为官方确认", report)
        self.assertIn("人数、最低分、25% 位置分数、中位数、平均分、75% 位置分数、最高分", report)
        self.assertIn("大连理工大学软件学院两个“软件工程”项目", report)
        self.assertIn("`083500 软件工程`", report)
        self.assertIn("`085405 软件工程`", report)
        self.assertIn("34c13d86-9c45-438e-aa42-cdf7b5a3c9c6", report)
        self.assertIn("六所 985、八条具体项目线", report)
        self.assertIn("2026 动态目录 `083500 软件工程`", report)
        self.assertIn("49bae1da-d9b5-425f-a00a-8ced92b066d9", report)
        self.assertIn("49bae1da-d9b5-425f-a00a-8ced92b066d9", start_here)
        self.assertIn(
            "| 2024 | `085405 软件工程` | 全日制 `01 智能软件` | "
            "45 | 45 | 70 | 75 | 350 | 82 |",
            report,
        )
        self.assertIn(
            "| 2026 | `085405 软件工程` | 全日制 `01 智能软件` | "
            "45 | 45 | 70 | 75 | 372 | 83 |",
            report,
        )
        self.assertIn(
            "| 2026 | 开发区校区软件学院 | 专业学位、全日制 | "
            "321 | 86 |",
            report,
        )
        self.assertIn("这六个字段继续写“缺失”", report)
        self.assertIn(
            "| 2026 | 372 | 83 | 321 | 86 |",
            start_here,
        )
        self.assertIn("`887 软件工程`", report)
        self.assertIn("四条项目线当前都只是监测项，不是已改考项目", report)
        self.assertIn("043cb2c4-05bf-4a4b-a42d-0549e03be0cc", report)
        self.assertIn("043cb2c4-05bf-4a4b-a42d-0549e03be0cc", start_here)
        self.assertIn(
            "| 招生年度 | 专业代码与名称 | 人口类型 | 招生计划总数 | "
            "已录取推免生人数 | 留给统考或后续环节的剩余计划 | "
            "进入复试人数 | 政治单科线 | 外语单科线 | "
            "业务课一单科线 | 业务课二单科线 | 复试总分线 | 口径说明 |",
            report,
        )
        self.assertIn(
            "| 2024 | `085405 软件工程` | 普通全日制 | 173 | 81 | 92 | "
            "129 | 50 | 50 | 70 | 70 | 315 |",
            report,
        )
        self.assertIn(
            "| 2026 | `085405 软件工程` | 普通全日制 | 173 | 71 | 102 | "
            "126 | 45 | 45 | 70 | 70 | 375 |",
            report,
        )
        self.assertIn(
            "| 招生年度 | 统计人口 | 样本人数 | 最低分 | 25% 位置分数 | "
            "中位数 | 平均分 | 75% 位置分数 | 最高分 | 证据状态与人口边界 |",
            report,
        )
        self.assertIn(
            "| 2025 | `085405` 全日制最终名单，包含 2 名退役大学生士兵专项 | "
            "92 | 350 | 367 | 377 | 377.33 | 386.25 | 415 |",
            report,
        )
        self.assertIn(
            "| 2026 | `085405` 全日制最终名单 | 102 | 376 | 393.25 | "
            "403.5 | 405.57 | 415.75 | 449 |",
            report,
        )
        self.assertIn("不能用复试名单替代拟录取名单", report)
        self.assertIn("2027 年硕士研究生招生初试自命题科目变更公告（陆续更新）", report)
        self.assertIn("没有软件学院", report)
        self.assertIn("页面标题明确写着“陆续更新”", report)
        self.assertIn("F7A031810293F0A7D08DC47F36675638B37F78D6DDD817497C94C066FB2491DF", report)
        self.assertIn(
            "| 2024 | 最终名单未恢复 | 缺失 | 缺失 | 缺失 | 缺失 | "
            "缺失 | 缺失 | 缺失 |",
            start_here,
        )
        self.assertIn(
            "| 2026 | `085405` 全日制最终名单 | 102 | 376 | 393.25 | "
            "403.5 | 405.57 | 415.75 | 449 |",
            start_here,
        )
        self.assertIn("列出的 6 个单位也不含软件学院", start_here)
        self.assertIn("71923d87-4ec8-46e4-9109-22abddb570be", report)
        self.assertIn("2027 年招生目录尚未开放", report)
        self.assertIn("直接访问 `083500` 和 `085405` 两条目标项目页也都显示“暂无数据”", report)
        self.assertIn("专业名称就是“软件工程”，但 2026 已经考 408", report)
        self.assertNotIn("专业名称虽然是 `085405 软件工程`，但 2026 已经考 408", report)
        self.assertIn("| 学校与培养单位 | 专业代码 | 2026 学习方式／范围 |", report)
        self.assertIn("华东师范大学软件工程学院", report)
        self.assertIn("四川大学计算机学院（软件学院）", report)
        self.assertIn("南开大学软件学院", report)
        self.assertIn("东南大学软件学院", report)
        self.assertIn("吉林大学卓越工程师学院（珠海）", report)
        self.assertIn("吉林大学珠海研究院", report)
        self.assertIn("天津大学软件学院", report)
        self.assertIn("`101 思想政治理论` | `201 英语（一）` | `302 数学（二）` | `408 计算机学科专业基础`", report)
        self.assertIn("aa7f1d0f-feff-4803-957b-7df040afefb4", report)
        self.assertIn("499b5c6e-b2bc-416c-a150-4bf78e49bc56", report)
        self.assertIn("acecc253-f52c-4885-9a8f-3f14839bc3e0", report)
        self.assertIn("acecc253-f52c-4885-9a8f-3f14839bc3e0", start_here)
        self.assertIn("263ece8c-b427-45d4-b6b1-afa97c9ca56d", report)
        self.assertIn("8ccca1ee-01d1-406c-8c82-952cf55d3fb3", report)
        self.assertIn("8ccca1ee-01d1-406c-8c82-952cf55d3fb3", start_here)
        self.assertIn("dbd14d88-74e9-4958-803e-f59bea28b3b7", report)
        self.assertIn("dbd14d88-74e9-4958-803e-f59bea28b3b7", start_here)
        self.assertIn("d48e4252-4798-4385-82c4-b081e4f7f080", report)
        self.assertIn("d48e4252-4798-4385-82c4-b081e4f7f080", start_here)
        self.assertIn("2026-07-16 发布、适用于 2027 的 `085405` 改考公告", report)
        self.assertIn("证据等级继续保持二手", report)
        self.assertIn("2027 年研究生招生专业目录还未正式公布", report)
        self.assertIn("没有被公共存档抓到", report)
        self.assertIn("不能绕过证书校验后把页面当成可信原件", report)
        self.assertIn("首页“硕士研究生招生章程及专业目录”入口仍指向 `2026/index.html`", report)
        self.assertIn("`2027/24.html` 与 `2027/index.html` 均返回 HTTP 404", report)
        self.assertIn("这不是对 7 月学院调整线索的否定证据", report)
        self.assertIn("两个 2027 目录直达地址均返回 404", start_here)
        self.assertIn("https://www.51kywang.com/51kaoyanwang/wap_doc/31119000.html", report)
        self.assertIn("7 月 17 日更可能是转载日期", report)
        self.assertIn("哈尔滨工业大学计算学部", report)
        self.assertIn("中央民族大学信息工程学院", report)
        self.assertIn("目录计划 29 人", report)
        self.assertIn("国防科技大学计算机学院", report)
        self.assertIn("`0835 软件工程`（校方目录保留四位代码）", report)
        self.assertIn("浙江大学计算机科学与技术学院", report)
        self.assertIn("普通统考目录拟招 5 人", report)
        self.assertNotIn("111/243/751/408", report)
        self.assertIn("强军单考另用政治 `111`、外语 `243`、数学 `751`、第四科 `408`", report)
        self.assertIn("电子科技大学信息与软件工程学院", report)
        self.assertIn("电子科技大学数学科学学院", report)
        self.assertIn("电子科技大学（深圳）高等研究院", report)
        self.assertIn("**非全日制**；目录拟招 3 人", report)
        self.assertIn("目录拟招 144 人", report)
        self.assertIn("浙江大学软件学院 `085400 电子信息` 的“软件工程”方向", report)
        self.assertIn("上海交通大学计算机学院 `081200` 的软件工程方向", report)
        self.assertIn("复旦大学计算与智能创新学院 `085400 电子信息`", report)
        self.assertIn("方向 16 是非全日制", report)
        self.assertIn("北京大学软件与微电子学院 `085400 电子信息`", report)
        self.assertIn("2026 招生说明列为全日制，总名额 60 人", report)
        self.assertIn("北京航空航天大学软件学院 | `083500 软件工程`", report)
        self.assertIn("专业统考计划 14 人", report)
        self.assertIn("专业统考计划 15 人", report)
        self.assertIn("专业统考计划 88 人", report)
        self.assertIn("东北大学软件学院 | `083500 软件工程`", report)
        self.assertIn("统考计划 8 人", report)
        self.assertIn("统考计划 42 人", report)
        self.assertIn("统考计划 2 人", report)
        self.assertIn("统考计划 34 人", report)
        self.assertIn("统考计划 21 人", report)
        self.assertIn(
            "同济大学计算机科学与技术学院（软件学院） | `085405 软件工程`",
            report,
        )
        self.assertIn(
            "同济大学工程类专业学位研究生教育管理中心 | `085405 软件工程`",
            report,
        )
        self.assertIn("**`888 工程能力综合`，不是 408**", report)
        self.assertIn("学院总计划 236 人是 4 个专业代码合计", report)
        self.assertIn("厦门大学信息学院软件工程系 | `085405 软件工程`", report)
        self.assertIn("2026 暂定统考计划 13 人", report)
        self.assertIn("厦门大学电影学院数字媒体技术系 | `085405 软件工程`", report)
        self.assertIn("2026 暂定统考计划 11 人", report)
        self.assertIn("山东大学软件学院 | `083500 软件工程`", report)
        self.assertIn("2026 统考计划 4 人", report)
        self.assertIn("山东大学软件学院 | `085405 软件工程`", report)
        self.assertIn("2026 统考计划 21 人", report)
        self.assertIn("中国海洋大学信息科学与工程学部", report)
        self.assertIn("2026 统考计划 14 人", report)
        self.assertIn("中国海洋大学卓越工程师学院", report)
        self.assertIn("2026 统考计划 3 人", report)
        self.assertIn("F0211 程序设计实践（上机）", report)
        self.assertIn("统考计划 19 人、非全日制计划 0 人、拟接收推免 27 人", report)
        self.assertIn("目录列专业计划 102 人", report)
        self.assertIn("目录列专业计划 10 人", report)
        self.assertIn("不能把 102 和 10 合成“统考 112 人”", report)
        self.assertIn("目录计划原值 37 人", report)
        self.assertIn("普通统考方向的基础计划原值 10 人", report)
        self.assertIn("目录基础计划原值 180 人", report)
        self.assertIn("baf83616-d5f6-40ed-b08d-e87a4aa49a9b", report)
        self.assertIn("南京大学软件学院 | `083500 软件工程`", report)
        self.assertIn("南京大学软件学院 | `085405 软件工程`", report)
        self.assertIn("南京大学智能软件与工程学院 | `085405 软件工程`", report)
        self.assertIn("2026 目录计划原值 205 人", report)
        self.assertIn("2026 目录计划原值 56 人", report)
        self.assertIn("自 2025 级起已由 842 改为 408", report)
        self.assertIn("6855B285C9A20531396C2ABE642B7910C59F10CF2B41A41DFB5F60218CCC043E", report)
        self.assertIn("物理第 42、53 页已经逐页渲染核对", report)
        self.assertIn("公告只点名 `083500`", report)
        self.assertIn("软件学院 `085405` 全日制；智能软件与工程学院 `085405` 全日制", start_here)
        self.assertIn("目录计划原值分别为 205、56", start_here)
        self.assertIn("d932312e-ed92-4fef-9d18-3731e772a8ef", report)
        self.assertIn("固定 39 所 985 母表补漏", report)
        self.assertIn("中国人民大学信息学院（专业学位）`085400 电子信息—01 软件工程领域`", start_here)
        self.assertIn("信息学院（专业学位）`085400 电子信息—01 软件工程领域`", report)
        self.assertIn("46A7DE7AD58CE87CF886572279020BFEF18ED355322150C7FC3F2EEDB1C7F15C", report)
        self.assertIn("658DA97AE1FF143E697A247C5F70AC98B685EADCBC956229E192C760D5274F97", report)
        self.assertIn("795AA5317159AE910DDE3290B93B0A55251C6FABC48DB03C543A6918E0E76E84", report)
        self.assertIn("中南大学 `085405` 只有授权专业存在性、没有同项目四科闭环", report)
        self.assertIn("软件工程是母代码下的培养方向，没有独立 `085405` 初试行", report)
        self.assertIn("系统专业仅供参考", report)
        self.assertIn("两院现有 2026 科目原件均按母代码 `085400 电子信息` 招生", start_here)
        self.assertNotIn("南京大学、中南大学、哈尔滨工业大学", report)
        for school in (
            "北京大学", "中国人民大学", "清华大学", "北京航空航天大学", "北京理工大学",
            "中国农业大学", "北京师范大学", "中央民族大学", "南开大学", "天津大学",
            "大连理工大学", "东北大学", "吉林大学", "哈尔滨工业大学", "复旦大学",
            "同济大学", "上海交通大学", "华东师范大学", "南京大学", "东南大学",
            "浙江大学", "中国科学技术大学", "厦门大学", "山东大学", "中国海洋大学",
            "武汉大学", "华中科技大学", "湖南大学", "中南大学", "国防科技大学",
            "中山大学", "华南理工大学", "四川大学", "电子科技大学", "重庆大学",
            "西安交通大学", "西北工业大学", "西北农林科技大学", "兰州大学",
        ):
            self.assertIn(school, report)
        self.assertIn(
            "092C5F4FBB9DFBE155E1C04D4C36BC83042A4FD0A8C5AB9113D534ADC6B02108",
            report,
        )
        for vague_placeholder in (
            "全日制范围按目录另核",
            "培养单位和方向仍需逐线拆分",
            "按正式目录方向另核",
            "培养单位按正式目录另核",
        ):
            self.assertNotIn(vague_placeholder, report)
        self.assertIn("已经在 2026 考 408 的精确软件工程项目怎样拆开", start_here)
        self.assertIn("同校同名不等于同科目", start_here)
        self.assertIn("暂定统考计划 13", start_here)
        self.assertIn("暂定统考计划 11", start_here)
        self.assertNotIn("精确名称的软件工程学硕，但改考发生在 2026 | 中央民族大学", report)
        self.assertIn("aa7f1d0f-feff-4803-957b-7df040afefb4", start_here)
        self.assertIn("精确名称·校方已官宣", report)
        self.assertIn("清华大学全球创新学院", report)
        self.assertIn("清华大学网络研究院 `085400` 已官宣 826 改 408", report)
        self.assertIn(
            "北京航空航天大学杭州国际创新研究院 `085405 软件工程`",
            report,
        )
        self.assertIn("中法航空双学位专项", report)
        self.assertIn(
            "专业名称精确、四科匹配，但属于 2027 新项目",
            report,
        )
        self.assertIn("兰州大学 `085405` 校方首改公告恢复", report)
        self.assertIn("由 `806 计算机专业基础` 改为 `408 计算机学科专业基础`", report)
        self.assertIn(
            "https://yz.lzu.edu.cn/shuoshishengzhaosheng/shuoshijianzhang/"
            "2026/0617/333466.html",
            report,
        )
        self.assertIn("9a453746-78d9-4dc8-a0ba-39da6dbf0d2d", report)
        self.assertIn("用户已经明确“兰州大学不报”", report)
        self.assertIn("不进入候选、排序、目标分或录取概率模型", report)
        self.assertNotIn("当前最贴合本人备考合同的校方已官宣首改项目", report)
        self.assertIn("4273ac00-27ee-4abc-ab9e-225947ff7ab5", report)
        self.assertIn("75947e87-7d7d-4e86-b03c-89c5f4420488", report)
        self.assertIn("46607f86-5f05-4bb0-962d-4914d4754bf7", report)
        self.assertIn(
            "2023—2025 拟录取名单在 `085400` 下明确单列过“软件工程”方向",
            report,
        )
        self.assertIn("2026 合并项目不再拆方向", report)
        self.assertIn("南开大学软件学院 `085400 电子信息` 的软件工程方向", report)
        self.assertIn("中央民族大学信息工程学院 | `083500 软件工程`", report)
        self.assertIn("c9bb0dd7-2b3b-40f2-891d-7fbc8b45e5df", report)
        self.assertIn("65d9ab9d-06d6-4a7e-bb52-7ad55fa9c3d1", report)
        self.assertIn("南京大学软件学院 `083500 软件工程`", report)
        self.assertIn("2027 年**仅招收推荐免试研究生**", report)
        self.assertIn("智能软件与工程学院的 `085405 软件工程`", report)
        self.assertIn("湖南大学网络空间安全学院 `085400` 已官宣 866 改 408", report)
        self.assertIn("不能和湖南大学计算机学院项目混为一项", report)
        self.assertIn("业务课考试科目保持不变", report)
        self.assertIn("不能把计算机学院公共课调整误写成软件学院", report)
        self.assertIn("中国科学技术大学环境科学与光电技术学院", report)
        self.assertIn("校方明确写的是 2027 新增招生专业", report)
        self.assertIn("| 6 | 北京航空航天大学 | `strict_match` |", national_matrix)
        self.assertIn("021 软件学院", national_matrix)
        self.assertIn("75947e87-7d7d-4e86-b03c-89c5f4420488", national_matrix)
        self.assertIsNone(re.search(r"`\d{3}\+\d{3}\+\d{3}\+\d{3}`", report))
        self.assertNotIn("min / Q25 / median / mean / Q75 / max", report)

    def test_cqu_024_085405_four_year_scores_are_field_labeled_and_population_safe(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        trace_id = "378c27e9-2951-45ba-b200-11c72a1938c0"
        report = (
            repository_root
            / "docs"
            / "2027-first-switch-408-985-software-engineering-audit-2026-09-03.md"
        ).read_text(encoding="utf-8")
        start_here = (
            repository_root / "docs" / "start-here-current-conclusions.md"
        ).read_text(encoding="utf-8")

        for content in (report, start_here):
            self.assertIn(trace_id, content)
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

        self.assertIn(
            "| 招生年度 | 统计人口 | 样本人数 | 最低分 | 25% 位置分数 | "
            "中位数 | 平均分 | 75% 位置分数 | 最高分 | 证据边界 |",
            report,
        )
        self.assertIn(
            "| 2023 | `024-085405`、全日制、专项计划栏均为“无” | 59 | "
            "321 | 341.5 | 356 | 357.95 | 374 | 439 |",
            report,
        )
        self.assertIn(
            "| 2024 | `024-085405`、全日制、专项计划栏为“无” | 43 | "
            "342 | 367 | 381 | 381.19 | 398.5 | 424 |",
            report,
        )
        self.assertIn(
            "| 2025 | `024-085405`、全日制、专项计划栏为“无” | 93 | "
            "309 | 346 | 362 | 361.48 | 378 | 420 |",
            report,
        )
        self.assertIn(
            "| 2026 | `024-085405`、全日制、专项计划栏均为“无” | 81 | "
            "339 | 372 | 389 | 387.48 | 403 | 434 |",
            report,
        )
        self.assertIn(
            "| 2026 | 大数据与软件学院 `085405` 二次划线 | 45 | 45 | "
            "70 | 70 | 320 |",
            report,
        )
        self.assertIn("2023—2025 年学院二次划线表都没有列出本项目", report)
        self.assertIn("最终名单人数与目录计划不一致时，原样保留差异", report)
        self.assertIn("不给政治、外语、数学和专业课的分科成绩", report)
        self.assertIn("这是普通程序设计上机，不是网络安全攻防", report)
        self.assertIn("未要求把电子竞赛证书自行打印成纸质证书", report)
        self.assertIn(
            "D9DB01E13BCF1254653BC9A82712537F06DFBF3EA7160FE617C6810F0209E815",
            report,
        )
        self.assertIn(
            "| 2026 | 320 | 全日制、专项计划栏均为“无” | 81 | 339 | "
            "372 | 389 | 387.48 | 403 | 434 |",
            start_here,
        )
        self.assertIn("四份最终表都没有政治、英语、数学、专业课分列", start_here)
        self.assertIsNone(
            re.search(
                r"(?<![\d.])\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?){5}(?![\d.])",
                report,
            )
        )

    def test_bit_085405_four_year_scores_are_stage_separated_and_field_labeled(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        trace_id = "71dd931b-3118-4f98-a515-c76ebb4cef92"
        recovered_trace_id = "d9de62d0-e46b-4dd0-a840-04afc1862904"
        indexed_2026_trace_id = "e9125069-3c41-4cef-acdc-28ced5300b60"
        report = (
            repository_root
            / "docs"
            / "2027-first-switch-408-985-software-engineering-audit-2026-09-03.md"
        ).read_text(encoding="utf-8")
        start_here = (
            repository_root / "docs" / "start-here-current-conclusions.md"
        ).read_text(encoding="utf-8")

        for content in (report, start_here):
            self.assertIn(trace_id, content)
            self.assertIn(recovered_trace_id, content)
            self.assertIn(indexed_2026_trace_id, content)
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

        self.assertIn("复试名单不能替代拟录取名单", report)
        self.assertIn(
            "| 招生年度 | 普通复试总分线 | 普通全日制进入复试人数 | "
            "普通全日制复试阶段名额 | 复试名单另列专项人数 |",
            report,
        )
        self.assertIn("| 2023 | 330 | 115 | 68 | 2 | 8 |", report)
        self.assertIn("| 2024 | 352 | 118 | 78 | 3 | 11 |", report)
        self.assertIn("| 2025 | 330 | 117 | 84 | 4 | 2 |", report)
        self.assertIn("| 2026 | 341 | 109 | 70 | 5 | 0 |", report)
        self.assertIn(
            "| 招生年度 | 统计人口 | 样本人数 | 最低分 | 25% 位置分数 | "
            "中位数 | 平均分 | 75% 位置分数 | 最高分 | "
            "能否当作最终录取分布 |",
            report,
        )
        self.assertIn(
            "| 2026 | `085405` 普通全日制复试名单 | 109 | 341 | 354 | "
            "374 | 375.80 | 395 | 424 | 不能 |",
            report,
        )
        self.assertIn(
            "| 招生年度 | 成绩字段 | 样本人数 | 最低分 | 25% 位置分数 | "
            "中位数 | 平均分 | 75% 位置分数 | 最高分 |",
            report,
        )
        self.assertIn(
            "| 2024 | `085405` 普通全日制最终拟录取者 | 初试总分 | "
            "78 | 355 | 373 | 383.5 | 386.04 | 398 | 431 |",
            report,
        )
        self.assertIn(
            "| 2024 | `085405` 普通全日制最终拟录取者 | "
            "复试成绩（百分制） | 78 | 69.5 | 78.23 | 81.05 | 81.55 | "
            "84.6 | 93.5 |",
            report,
        )
        self.assertIn(
            "2023 | 已定位校方第一、第二、第三批旧公示入口", report
        )
        self.assertIn(
            "| 2025 | 学院现站附件已撤；已从公共网页存档恢复校方原 PDF | "
            "**90** | **能** |",
            report,
        )
        self.assertIn(
            "2026 | 校方原 PDF 当前 404；已从该校方 URL 的完整公开搜索索引恢复全表 94 行",
            report,
        )
        self.assertIn(
            "| 2025 | `085405` 普通全日制最终拟录取者 | 初试总分 | "
            "90 | 330 | 350.25 | 364.5 | 364.97 | 376 | 422 |",
            report,
        )
        self.assertIn(
            "| 2025 | `085405` 普通全日制最终拟录取者 | "
            "复试成绩（百分制） | 90 | 66.425 | 77.138 | 82.525 | "
            "82.176 | 87.475 | 94.600 |",
            report,
        )
        self.assertIn(
            "| 2026 | `085405` 普通全日制最终拟录取者；公开搜索索引恢复 | "
            "初试总分 | 70 | 341 | 364 | 388 | 383.11 | 402.75 | 424 |",
            report,
        )
        self.assertIn(
            "| 2026 | `085405` 普通全日制最终拟录取者；公开搜索索引恢复 | "
            "复试成绩（百分制） | 70 | 67.7 | 77.775 | 81.45 | 81.424 | "
            "85.2 | 92.6 |",
            report,
        )
        self.assertIn(
            "| 普通全日制合计 | 70 | **70** | **0** |",
            report,
        )
        self.assertIn("未恢复原文件字节", report)
        self.assertIn(
            "| 普通全日制合计 | 84 | **90** | **+6** |",
            report,
        )
        self.assertIn("3 名退役计划、1 名骨干计划", report)
        self.assertIn(
            "0665147E8CC01CD0C307AAD7F090D565AD6D4142AA12C96DB11ECEBE926F39E4",
            report,
        )
        self.assertIn("普通 C/C++ 程序设计上机", report)
        self.assertIn("不是网络安全攻防上机", report)
        self.assertIn(
            "| 2024 | 352 | 118 | 78 | 3 | 11 | "
            "不能；最终表另行统计 |",
            start_here,
        )
        self.assertIn(
            "| 2024 | `085405` 普通全日制最终拟录取者 | 初试总分 | "
            "78 | 355 | 373 | 383.5 | 386.04 | 398 | 431 |",
            start_here,
        )
        self.assertIn(
            "| 2025 | `085405` 普通全日制最终拟录取者 | 初试总分 | "
            "90 | 330 | 350.25 | 364.5 | 364.97 | 376 | 422 |",
            start_here,
        )
        self.assertIn(
            "| 2026 | `085405` 普通全日制最终拟录取者；公开搜索索引恢复 | "
            "初试总分 | 70 | 341 | 364 | 388 | 383.11 | 402.75 | 424 |",
            start_here,
        )
        self.assertIsNone(
            re.search(
                r"(?<![\d.])\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?){5}(?![\d.])",
                report,
            )
        )

    def test_tsinghua_software_professional_history_is_code_safe_and_field_labeled(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        trace_id = "a71dcf2f-c136-4847-9959-6eb16320d839"
        report = (
            repository_root
            / "docs"
            / "2027-first-switch-408-985-software-engineering-audit-2026-09-03.md"
        ).read_text(encoding="utf-8")
        start_here = (
            repository_root / "docs" / "start-here-current-conclusions.md"
        ).read_text(encoding="utf-8")

        for content in (report, start_here):
            self.assertIn(trace_id, content)
            self.assertIsNone(
                re.search(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])", content)
            )

        self.assertIn(
            "2023 年还以 `085400 电子信息—01 软件工程（工程）` 招生",
            report,
        )
        self.assertIn("它不是同一专业代码", report)
        self.assertIn(
            "| 招生年度 | 当年报名专业与方向 | 目录阶段计划 | "
            "复试细则中的调整后计划 | 普通考生进入复试人数 | "
            "普通考生最终拟录取人数 | 另列专项人数 | 当前证据边界 |",
            report,
        )
        self.assertIn(
            "| 2025 | `085405 软件工程—01 软件工程（专业学位）`，全日制 | "
            "8 | **13** | 20 | **13** | 复试 1 人、最终 1 人，均为士兵计划 |",
            report,
        )
        self.assertIn(
            "| 2026 | `085405 软件工程—01 智能软件工程（专业学位）`，全日制 | "
            "10 | **19** | 缺失 | 缺失 | 缺失 |",
            report,
        )
        self.assertIn(
            "| 招生年度 | 适用人口 | 复试总分线 | 政治单科线 | "
            "外语单科线 | 数学一单科线 | 业务课二单科线 |",
            report,
        )
        self.assertIn(
            "| 2025 | `085405` 普通复试名单 | 20 | 325 | 332.75 | "
            "346.5 | 348.90 | 360.5 | 390 |",
            report,
        )
        self.assertIn(
            "| 2025 | `085405` 普通最终拟录取者 | 初试总分 | 13 | "
            "325 | 348 | 360 | 356.85 | 371 | 390 |",
            report,
        )
        self.assertIn("4 小时上机考试", report)
        self.assertIn("这里没有网络安全攻防项目", report)
        self.assertIn("公开复试名单和最终名单当前未恢复", report)
        self.assertIn(
            "| 2023 | `085400 电子信息—软件工程（工程）` | "
            "8／未公布调整数 | 335 | 14 | 11 | 372 |",
            start_here,
        )
        self.assertIn(
            "| 2026 | `085405 智能软件工程` | 10／**19** | 330 | "
            "缺失 | 缺失 | 缺失 |",
            start_here,
        )
        self.assertIsNone(
            re.search(
                r"(?<![\d.])\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?){5}(?![\d.])",
                report,
            )
        )

    def test_2027_same_name_non_985_spillover_is_field_labeled_and_excluded(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        trace_id = "6a309b90-7927-4e4e-8d64-b630a826f375"
        report = (
            repository_root
            / "docs"
            / "2027-first-switch-408-985-software-engineering-audit-2026-09-03.md"
        ).read_text(encoding="utf-8")

        self.assertIn(trace_id, report)
        self.assertIn(
            "| 学校与项目 | 2027 变化性质 | 第一科：政治 | 第二科：外语 | "
            "第三科：数学 | 第四科：专业基础 | 为什么不进入本人的 985 首改候选池 |",
            report,
        )
        self.assertIn("北京科技大学数理学院 `085405 软件工程`", report)
        self.assertIn("第四科由 `879 数据结构` 改为 `408`", report)
        self.assertIn("青海师范大学 `0835 软件工程`", report)
        self.assertIn("不能擅自细化成 `083500`", report)
        self.assertIn("西南大学计算机与信息科学学院、软件学院", report)
        self.assertIn("仅招非全日制定向就业生源", report)
        self.assertIn("学校不是 985、项目是新增而非首改", report)
        self.assertNotIn(
            "青海师范大学 `083500 软件工程`",
            report,
        )


if __name__ == "__main__":
    unittest.main()
