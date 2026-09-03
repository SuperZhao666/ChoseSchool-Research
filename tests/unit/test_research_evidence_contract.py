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
"""

import re
import unittest
from pathlib import Path


class ResearchEvidenceContractTests(unittest.TestCase):
    def test_cqu_2024_live_official_zip_upgrades_both_total_only_rows(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        trace_id = "e8b68757-b898-4ed7-b8eb-2a7031b04893"

        readme = (repository_root / "README.md").read_text(encoding="utf-8")
        start_here = (
            repository_root / "docs" / "start-here-current-conclusions.md"
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
            "`strict_match` 53、`non_strict` 29、`no_relevant_program` 9、"
            "`pending_exact_catalog` 20",
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
            "`strict_match` 53、`non_strict` 29、`no_relevant_program` 9、"
            "`pending_exact_catalog` 20",
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
        self.assertIn("| 8 | 郑大 084—085410 | 总 | 缺 | 缺 | 交(86) |", subject_report)
        self.assertIn("`337 / 354 / 368 / 369.28 / 381.75 / 427`", subject_report)
        self.assertIn("`54 / 65 / 68 / 67.35 / 70 / 76`", subject_report)
        self.assertIn("`63 / 74.25 / 79 / 78.28 / 82 / 90`", subject_report)
        self.assertIn("`94 / 117.25 / 125 / 124.16 / 132.75 / 150`", subject_report)
        self.assertIn("`79 / 96 / 99 / 99.49 / 106 / 121`", subject_report)
        self.assertIn("2023—2025 仍不能计算最终录取者四科分布", subject_report)
        self.assertIn(
            "2023—2025 的四科均值**只描述进入复试的人群，不描述最终拟录取人群**",
            subject_report,
        )
        self.assertIn("| 2023 | 77 | `336`；页面未给复试范围 |", subject_report)
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
            "`314 / 319.5—320 / 325 / 329.51—329.74 / 335.5 / 382`",
            subject_report,
        )
        self.assertIn(
            "`74—78 / 89—90 / 95 / 94.34—95.20 / 100 / 113`",
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
        self.assertIn("普通一志愿录取名单（25/32）", subject_report)
        self.assertIn("有成绩人口是 `44=普通30+创新14`", subject_report)
        self.assertIn("最终观察是 `39=普通25+创新14`", subject_report)
        self.assertIn("| 目标方向非创新计划拟录取逐行观察", subject_report)
        self.assertIn("`317 / 328 / 332 / 335.08 / 337 / 369`", subject_report)
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
        self.assertIn("`339 / 348.75 / 354.5 / 357.56 / 362.5 / 390`", subject_report)
        self.assertIn("`262 / 311.25 / 326 / 327.07 / 348.75 / 362`", subject_report)
        self.assertIn("`262 / 344.25 / 352 / 349.02 / 359.75 / 390`", subject_report)
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

        for content in (readme, subject_report):
            self.assertIn(expected_stats, content)
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
        for content in (readme, subject_report):
            self.assertIn("373【324—430】", content)
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

        for content in (readme, subject_report, start_here):
            self.assertIn(expected_stats, content)
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
            "`strict_match` 53、`non_strict` 29、`no_relevant_program` 9、"
            "`pending_exact_catalog` 20",
            national_matrix,
        )

        self.assertGreaterEqual(admission_report.count("25% 位置分数"), 16)
        self.assertGreaterEqual(admission_report.count("75% 位置分数"), 16)
        self.assertNotIn("最终初试六统计", admission_report)
        self.assertNotIn("min / Q25 / median / mean / Q75 / max", admission_report)
        self.assertNotIn("一志愿 40：`350 / 374", admission_report)


if __name__ == "__main__":
    unittest.main()
