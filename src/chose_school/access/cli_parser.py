from __future__ import annotations

import argparse
from datetime import date
from typing import Sequence

from chose_school.domain.enums import (
    AchievementCategory,
    AchievementParticipationType,
    AchievementScopeLevel,
    AchievementStage,
    AchievementVerificationStatus,
    ApplicantContextDimension,
    EvidenceDocumentType,
    EvidenceGrade,
    FairnessReviewConclusion,
    MachineScoringMethod,
    MachineTestDifficulty,
    MockDifficulty,
    MockInvalidReasonCode,
    MockPaperFamily,
    PolicyEventStatus,
    PolicyEventType,
    PreferenceAcceptanceLevel,
    PreferenceDimension,
    Strict22408Status,
)
from chose_school.domain.fact_registry import FACT_DATA_TYPES, STATISTICAL_FACT_METHODS


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return create_parser().parse_args(argv)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chose-school",
        description="可追溯、可审计的本地考研择校数据库",
    )
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--database", help="覆盖 SQLite 数据库路径")
    parser.add_argument("--json", action="store_true", help="输出紧凑 JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_catalog_commands(subparsers)
    _add_official_observation_command(subparsers)
    _add_secondary_observation_command(subparsers)
    _add_policy_event_commands(subparsers)
    _add_fact_commands(subparsers)
    _add_verification_command(subparsers)
    _add_assessment_commands(subparsers)
    _add_candidate_commands(subparsers)
    _add_maintenance_commands(subparsers)
    return parser


def _add_catalog_commands(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser("init", help="初始化或升级数据库")
    import_parser = subparsers.add_parser("import-kimi", help="导入 Kimi 研究归档")
    import_parser.add_argument("archive", help="Kimi ZIP 路径")
    subparsers.add_parser("summary", help="显示数据库概况")

    project_parser = subparsers.add_parser("projects", help="查询项目观测记录")
    project_parser.add_argument("--year", type=int)
    project_parser.add_argument(
        "--status",
        choices=[status.value for status in Strict22408Status],
    )
    project_parser.add_argument("--school")
    project_parser.add_argument("--limit", type=int, default=100)
    project_parser.add_argument(
        "--raw-imported",
        action="store_true",
        help="显式查看未裁决的原始导入影子值；默认只展示证据裁决后的安全视图",
    )

    issue_parser = subparsers.add_parser("issues", help="查询数据质量问题")
    issue_parser.add_argument("--severity", choices=("info", "warning", "error"))
    issue_parser.add_argument(
        "--status", choices=("open", "resolved", "wont_fix"), default="open"
    )
    issue_parser.add_argument("--limit", type=int, default=100)

    resolution_parser = subparsers.add_parser(
        "issue-resolve", help="用明确说明关闭一条质量问题"
    )
    resolution_parser.add_argument("--issue-id", type=int, required=True)
    resolution_parser.add_argument("--note", required=True)


def _add_fact_commands(subparsers: argparse._SubParsersAction) -> None:
    fact_add = subparsers.add_parser(
        "fact-add", help="为一个项目年度观测追加字段级证据主张"
    )
    fact_add.add_argument("--observation-id", type=int, required=True)
    fact_add.add_argument("--fact-key", choices=sorted(FACT_DATA_TYPES), required=True)
    fact_add.add_argument("--value", required=True)
    fact_add.add_argument(
        "--evidence-grade",
        choices=[grade.value for grade in EvidenceGrade],
        required=True,
    )
    _add_source_arguments(fact_add, source_url_required=False, source_hash_required=False)
    fact_add.add_argument("--population-scope", required=True)
    fact_add.add_argument("--statistic-scope", required=True)
    fact_add.add_argument(
        "--derivation-operator",
        choices=["subtract"],
    )
    fact_add.add_argument(
        "--derivation-left-fact-key",
        choices=sorted(FACT_DATA_TYPES),
    )
    fact_add.add_argument("--derivation-left-value", type=int)
    fact_add.add_argument(
        "--derivation-right-fact-key",
        choices=sorted(FACT_DATA_TYPES),
    )
    fact_add.add_argument("--derivation-right-value", type=int)
    fact_add.add_argument(
        "--sample-size",
        type=int,
        help="成绩分布所用匿名样本行数；成绩统计事实必填",
    )
    fact_add.add_argument(
        "--calculation-method-key",
        choices=sorted(set(STATISTICAL_FACT_METHODS.values())),
        help="冻结的统计计算方法版本；成绩统计事实必填",
    )
    fact_add.add_argument(
        "--calculation-input-sha256",
        help="规范化匿名输入序列的 64 位小写 SHA-256；成绩统计事实必填",
    )
    fact_add.add_argument("--note")

    fact_resolve = subparsers.add_parser(
        "fact-resolve", help="追加一条事实裁决并选定可信主张"
    )
    fact_resolve.add_argument("--claim-id", type=int, required=True)
    fact_resolve.add_argument("--reason", required=True)
    fact_unresolve = subparsers.add_parser(
        "fact-unresolve", help="按现有主张定位事实身份，并追加一条当前未裁决事件"
    )
    fact_unresolve.add_argument("--claim-id", type=int, required=True)
    fact_unresolve.add_argument("--reason", required=True)
    facts = subparsers.add_parser("facts", help="查看观测的字段级主张和当前裁决")
    facts.add_argument("--observation-id", type=int, required=True)
    conflicts = subparsers.add_parser("fact-conflicts", help="查看未裁决的字段冲突")
    conflicts.add_argument("--limit", type=int, default=100)


def _add_official_observation_command(
    subparsers: argparse._SubParsersAction,
) -> None:
    observation = subparsers.add_parser(
        "official-observation-add",
        help="从正式目录追加一个具有不可变来源链的项目年度观测",
    )
    observation.add_argument("--school", required=True)
    observation.add_argument("--college", required=True)
    observation.add_argument("--program-code", required=True)
    observation.add_argument("--program-name", required=True)
    observation.add_argument("--admission-year", type=int, required=True)
    observation.add_argument("--politics", required=True)
    observation.add_argument("--english", required=True)
    observation.add_argument("--math", required=True)
    observation.add_argument("--professional", required=True)
    observation.add_argument("--direction")
    observation.add_argument("--campus")
    observation.add_argument("--training-location")
    observation.add_argument("--study-mode")
    observation.add_argument("--training-type")
    observation.add_argument("--admission-type")
    observation.add_argument("--degree-type")
    observation.add_argument("--training-arrangement")
    _add_source_arguments(
        observation,
        source_url_required=True,
        source_hash_required=True,
        source_institution_required=True,
    )
    observation.add_argument("--note")


def _add_secondary_observation_command(
    subparsers: argparse._SubParsersAction,
) -> None:
    observation = subparsers.add_parser(
        "secondary-observation-add",
        help="从二级汇总追加项目年度观测；永不形成官方目录确认",
    )
    observation.add_argument("--school", required=True)
    observation.add_argument("--college", required=True)
    observation.add_argument("--program-code", required=True)
    observation.add_argument("--program-name", required=True)
    observation.add_argument("--admission-year", type=int, required=True)
    observation.add_argument("--politics")
    observation.add_argument("--english")
    observation.add_argument("--math")
    observation.add_argument("--professional")
    observation.add_argument("--direction")
    observation.add_argument("--campus")
    observation.add_argument("--training-location")
    observation.add_argument("--study-mode")
    observation.add_argument("--training-type")
    observation.add_argument("--admission-type")
    observation.add_argument("--degree-type")
    observation.add_argument("--training-arrangement")
    observation.add_argument("--source-title", required=True)
    observation.add_argument("--source-url", required=True)
    observation.add_argument("--source-institution", required=True)
    observation.add_argument("--source-content-sha256", required=True)
    observation.add_argument("--applicable-year", type=int, required=True)
    observation.add_argument("--published-date", required=True)
    observation.add_argument("--retrieved-date", required=True)
    observation.add_argument("--source-excerpt", required=True)
    observation.add_argument("--project-identity-basis", required=True)
    observation.add_argument("--note")


def _add_verification_command(subparsers: argparse._SubParsersAction) -> None:
    verification = subparsers.add_parser(
        "verify-exam", help="用一份可追溯官方来源追加四科核验"
    )
    verification.add_argument("--observation-id", type=int, required=True)
    verification.add_argument("--politics", required=True)
    verification.add_argument("--english", required=True)
    verification.add_argument("--math", required=True)
    verification.add_argument("--professional", required=True)
    _add_source_arguments(verification, source_url_required=True, source_hash_required=True)
    verification.add_argument("--note")


def _add_policy_event_commands(subparsers: argparse._SubParsersAction) -> None:
    policy_add = subparsers.add_parser(
        "policy-event-add",
        help="追加一条正式政策公告；科目调整公告始终待正式目录确认",
    )
    policy_add.add_argument("--school", required=True)
    policy_add.add_argument("--observation-id", type=int)
    policy_add.add_argument("--effective-year", type=int, required=True)
    policy_add.add_argument(
        "--event-type",
        choices=[event_type.value for event_type in PolicyEventType],
        required=True,
    )
    policy_add.add_argument("--scope-text", required=True)
    policy_add.add_argument("--title", required=True)
    policy_add.add_argument("--description", required=True)
    policy_add.add_argument("--announced-on", required=True)
    policy_add.add_argument("--source-title", required=True)
    policy_add.add_argument("--source-url", required=True)
    policy_add.add_argument("--source-institution", required=True)
    policy_add.add_argument(
        "--source-document-type",
        choices=[EvidenceDocumentType.OFFICIAL_NOTICE.value],
        required=True,
    )
    policy_add.add_argument("--source-content-sha256", required=True)
    policy_add.add_argument("--applicable-year", type=int, required=True)
    policy_add.add_argument("--published-date")
    policy_add.add_argument(
        "--retrieved-date",
        default=date.today().isoformat(),
    )
    policy_add.add_argument("--supersedes-event-id", type=int)
    policy_add.add_argument("--note")

    policy_list = subparsers.add_parser(
        "policy-events",
        help="查询政策事件历史；结果不能用于确认严格22408",
    )
    policy_list.add_argument("--year", type=int)
    policy_list.add_argument("--school")
    policy_list.add_argument("--observation-id", type=int)
    policy_list.add_argument(
        "--event-type",
        choices=[event_type.value for event_type in PolicyEventType],
    )
    policy_list.add_argument(
        "--status",
        choices=[PolicyEventStatus.PENDING_DIRECTORY.value],
    )
    policy_list.add_argument("--current-only", action="store_true")
    policy_list.add_argument("--limit", type=int, default=100)


def _add_source_arguments(
    parser: argparse.ArgumentParser,
    source_url_required: bool,
    source_hash_required: bool,
    source_institution_required: bool = False,
) -> None:
    parser.add_argument("--source-title", required=True)
    parser.add_argument("--source-url", required=source_url_required)
    parser.add_argument(
        "--source-institution",
        required=source_institution_required,
    )
    parser.add_argument(
        "--source-document-type",
        choices=[document_type.value for document_type in EvidenceDocumentType],
        required=True,
    )
    parser.add_argument("--source-content-sha256", required=source_hash_required)
    parser.add_argument("--applicable-year", type=int, required=True)
    parser.add_argument("--published-date")
    parser.add_argument("--retrieved-date", default=date.today().isoformat())


def _add_assessment_commands(subparsers: argparse._SubParsersAction) -> None:
    preference_add = subparsers.add_parser(
        "preference-add",
        help="追加一条可追溯的个人择校接受边界",
    )
    preference_add.add_argument(
        "--dimension",
        choices=[dimension.value for dimension in PreferenceDimension],
        required=True,
    )
    preference_add.add_argument("--subject", required=True)
    preference_add.add_argument(
        "--acceptance",
        choices=[level.value for level in PreferenceAcceptanceLevel],
        required=True,
    )
    preference_add.add_argument(
        "--value-json",
        default="{}",
        help="JSON对象；学费上限需给amount、basis和currency",
    )
    preference_add.add_argument("--note")

    preferences = subparsers.add_parser(
        "preferences",
        help="查看当前个人择校接受边界或追加历史",
    )
    preferences.add_argument(
        "--dimension",
        choices=[dimension.value for dimension in PreferenceDimension],
    )
    preferences.add_argument("--subject")
    preferences.add_argument("--history", action="store_true")

    subparsers.add_parser(
        "preference-readiness",
        help="按个人择校偏好v2合同检查23个原子回答的完整度与冲突",
    )

    context_add = subparsers.add_parser(
        "context-add",
        help="追加一条定性个人现状；不得用它代替严格限时分数",
    )
    context_add.add_argument(
        "--dimension",
        choices=[dimension.value for dimension in ApplicantContextDimension],
        required=True,
    )
    context_add.add_argument("--subject", required=True)
    context_add.add_argument("--value-json", required=True)
    context_add.add_argument("--note")

    contexts = subparsers.add_parser(
        "contexts",
        help="查看当前个人现状或追加历史",
    )
    contexts.add_argument(
        "--dimension",
        choices=[dimension.value for dimension in ApplicantContextDimension],
    )
    contexts.add_argument("--subject")
    contexts.add_argument("--history", action="store_true")

    achievement_add = subparsers.add_parser(
        "achievement-add",
        help="追加一条个人成果及其不可变证据文件快照",
    )
    achievement_add.add_argument("--key", required=True)
    achievement_add.add_argument(
        "--category",
        choices=[category.value for category in AchievementCategory],
        required=True,
    )
    achievement_add.add_argument("--title", required=True)
    achievement_add.add_argument("--issuer", required=True)
    achievement_add.add_argument("--year", type=int, required=True)
    achievement_add.add_argument("--period", required=True)
    achievement_add.add_argument(
        "--awarded-on",
        help="仅在证据给出完整年月日时填写；月级日期保留在 --period",
    )
    achievement_add.add_argument(
        "--scope-level",
        choices=[scope.value for scope in AchievementScopeLevel],
        required=True,
    )
    achievement_add.add_argument(
        "--stage",
        choices=[stage.value for stage in AchievementStage],
        required=True,
    )
    achievement_add.add_argument("--result", required=True)
    achievement_add.add_argument(
        "--participation-type",
        choices=[kind.value for kind in AchievementParticipationType],
        required=True,
    )
    achievement_add.add_argument("--team-name")
    achievement_add.add_argument("--details-json", default="{}")
    achievement_add.add_argument(
        "--verification-status",
        choices=[status.value for status in AchievementVerificationStatus],
        required=True,
    )
    achievement_add.add_argument(
        "--evidence-json",
        required=True,
        help=(
            "JSON数组；每项包含来源、SHA-256、大小、取得/复核日期、"
            "核验方法、证据等级、状态、主张和 relationship"
        ),
    )
    achievement_add.add_argument("--note")

    achievements = subparsers.add_parser(
        "achievements",
        help="查看当前个人成果账本或追加历史",
    )
    achievements.add_argument(
        "--category",
        choices=[category.value for category in AchievementCategory],
    )
    achievements.add_argument("--year", type=int)
    achievements.add_argument("--key")
    achievements.add_argument("--history", action="store_true")

    fairness_add = subparsers.add_parser(
        "fairness-review-add",
        help="为精确项目年度观测追加公平性审查和不可变证据快照",
    )
    fairness_add.add_argument("--observation-id", type=int, required=True)
    fairness_add.add_argument(
        "--conclusion",
        choices=[conclusion.value for conclusion in FairnessReviewConclusion],
        required=True,
    )
    fairness_add.add_argument("--summary", required=True)
    fairness_add.add_argument(
        "--evidence-json",
        default="[]",
        help="JSON数组；非insufficient结论至少需要一条带内容哈希的证据快照",
    )

    fairness_list = subparsers.add_parser(
        "fairness-reviews",
        help="查看当前项目级公平性审查或追加历史",
    )
    fairness_list.add_argument("--observation-id", type=int)
    fairness_list.add_argument("--history", action="store_true")

    mock_parser = subparsers.add_parser(
        "mock-add",
        help="兼容记录旧版精确分套卷；仅标记legacy_unverified，不进入v2评估窗口",
    )
    mock_parser.add_argument("--date", required=True)
    mock_parser.add_argument("--paper", required=True)
    mock_parser.add_argument("--politics", type=float, required=True)
    mock_parser.add_argument("--english", type=float, required=True)
    mock_parser.add_argument("--math", type=float, required=True)
    mock_parser.add_argument("--cs408", type=float, required=True)
    mock_parser.add_argument("--attempt", type=int, default=1)
    mock_parser.add_argument("--strict-timed", action="store_true")
    mock_parser.add_argument("--note")

    mock_ledger_add = subparsers.add_parser(
        "mock-ledger-add",
        help="按v2协议追加一次两天四科完整套卷账本记录",
    )
    mock_ledger_add.add_argument("--start-date", required=True)
    mock_ledger_add.add_argument("--end-date", required=True)
    mock_ledger_add.add_argument("--paper", required=True)
    mock_ledger_add.add_argument("--paper-key", required=True)
    mock_ledger_add.add_argument("--paper-source", required=True)
    mock_ledger_add.add_argument("--paper-content-sha256")
    mock_ledger_add.add_argument(
        "--paper-family",
        choices=[paper_family.value for paper_family in MockPaperFamily],
        required=True,
    )
    mock_ledger_add.add_argument(
        "--difficulty",
        choices=[difficulty.value for difficulty in MockDifficulty],
        required=True,
    )
    mock_ledger_add.add_argument("--scoring-rule-key", required=True)
    mock_ledger_add.add_argument(
        "--subject-results-json",
        required=True,
        help=(
            "JSON对象，键必须为101、204、302、408；每科记录attendance_status、"
            "score_lower、score_upper、started_at、ended_at和可选note"
        ),
    )
    mock_ledger_add.add_argument("--attempt", type=int, default=1)
    for protocol_flag in (
        "--first-exposure",
        "--complete-paper-set",
        "--strict-schedule",
        "--authentic-time-slots",
        "--strict-timed",
        "--consulted-materials",
        "--received-assistance",
        "--paused-timer",
        "--reviewed-answers-early",
    ):
        mock_ledger_add.add_argument(
            protocol_flag,
            action=argparse.BooleanOptionalAction,
            required=True,
            help="必须显式选择该事实或对应的 --no-* 选项，禁止依赖默认值",
        )
    mock_ledger_add.add_argument(
        "--invalid-reason-code",
        choices=[reason.value for reason in MockInvalidReasonCode],
    )
    mock_ledger_add.add_argument("--invalid-reason-note")
    mock_ledger_add.add_argument("--note")

    mock_sessions = subparsers.add_parser(
        "mock-sessions",
        help="查询v2套卷账本；旧版记录仅在显式指定时显示",
    )
    mock_sessions.add_argument("--include-legacy", action="store_true")
    mock_sessions.add_argument("--eligible-only", action="store_true")
    mock_sessions.add_argument("--session-id", type=int)
    mock_sessions.add_argument("--limit", type=int, default=100)

    mock_exclude = subparsers.add_parser(
        "mock-exclude",
        help="为套卷会话追加排除事件，不修改或删除原始记录",
    )
    mock_exclude.add_argument("--session-id", type=int, required=True)
    mock_exclude.add_argument("--reason", required=True)

    subparsers.add_parser(
        "assessment",
        help="汇总最近五次严格四科套卷，并报告跨目录、偏好、名额和复试门禁",
    )

    machine_add = subparsers.add_parser(
        "machine-add",
        help="追加一次限时机试原始记录；低分和无通过题也必须如实保留",
    )
    machine_add.add_argument("--date", required=True)
    machine_add.add_argument(
        "--duration",
        "--duration-minutes",
        dest="duration",
        type=int,
        required=True,
    )
    machine_add.add_argument("--language", required=True)
    machine_add.add_argument("--environment", required=True)
    machine_add.add_argument("--source", "--problem-source", dest="source", required=True)
    machine_add.add_argument(
        "--difficulty",
        choices=[difficulty.value for difficulty in MachineTestDifficulty],
        default=MachineTestDifficulty.UNKNOWN.value,
    )
    machine_add.add_argument(
        "--total",
        "--problem-count",
        dest="total",
        type=int,
        required=True,
    )
    machine_add.add_argument(
        "--solved",
        "--independently-solved-count",
        dest="solved",
        type=int,
        required=True,
    )
    machine_add.add_argument("--first-solve-minutes", type=int)
    machine_add.add_argument("--debugging-minutes", type=int)
    machine_add.add_argument(
        "--scoring-method",
        choices=[method.value for method in MachineScoringMethod],
        default=MachineScoringMethod.UNKNOWN.value,
    )
    machine_add.add_argument("--raw-score", type=float)
    machine_add.add_argument("--maximum-score", type=float)
    machine_add.add_argument("--first-exposure", action="store_true")
    machine_add.add_argument("--consulted-materials", action="store_true")
    machine_add.add_argument("--received-assistance", action="store_true")
    machine_add.add_argument("--paused-timer", action="store_true")
    machine_add.add_argument("--strict-timed", action="store_true")
    machine_add.add_argument("--attempt", type=int, default=1)
    machine_add.add_argument("--invalid-reason")
    machine_add.add_argument("--blocker", "--primary-blocker", dest="blocker")
    machine_add.add_argument("--note")

    machine_sessions = subparsers.add_parser(
        "machine-sessions",
        help="按原始时长查看机试记录，不做跨时长平均",
    )
    machine_sessions.add_argument(
        "--duration",
        "--duration-minutes",
        dest="duration",
        type=int,
    )
    machine_sessions.add_argument("--language")
    machine_sessions.add_argument("--problem-count", type=int)
    machine_sessions.add_argument("--valid-only", action="store_true")
    subparsers.add_parser(
        "machine-assessment",
        help="分别汇总90/120/180分钟机试基线，不生成综合机试分",
    )


def _add_candidate_commands(subparsers: argparse._SubParsersAction) -> None:
    report = subparsers.add_parser(
        "candidate-report",
        help="只读汇总候选身份、画像适配和历史可比性；不生成角色或概率",
    )
    report.add_argument(
        "--candidate-target-id",
        type=int,
        help="只查看一个候选目标版本；默认查看当前画像下的全部候选",
    )
    report.add_argument(
        "--history",
        action="store_true",
        help="同时显示候选、画像适配和历史可比性修订链；默认只显示当前链尾",
    )
    report.add_argument(
        "--details",
        action="store_true",
        help="在摘要外附带完整的规范化画像适配和可比性 JSON；默认不展开事件 ID/哈希",
    )


def _add_maintenance_commands(subparsers: argparse._SubParsersAction) -> None:
    export_parser = subparsers.add_parser("export", help="确定性导出项目 CSV")
    export_parser.add_argument("--output", required=True)
    export_parser.add_argument("--force", action="store_true")
    export_parser.add_argument("--excel-safe", action="store_true")
    export_parser.add_argument(
        "--raw-imported",
        action="store_true",
        help="导出未裁决的原始导入影子值；默认导出证据裁决后的安全视图",
    )
    subparsers.add_parser("doctor", help="检查数据库完整性和追溯链")
    backup_parser = subparsers.add_parser("backup", help="创建一致性 SQLite 备份")
    backup_parser.add_argument("--output", required=True)
    backup_parser.add_argument("--force", action="store_true")
