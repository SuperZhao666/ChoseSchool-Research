from __future__ import annotations

from chose_school.domain.enums import FactDataType


FACT_DATA_TYPES = {
    "quota.total_plan": FactDataType.INTEGER,
    "quota.exam_catalog_plan": FactDataType.INTEGER,
    "quota.recommendation_actual": FactDataType.INTEGER,
    "quota.recommendation_planned": FactDataType.INTEGER,
    "quota.recommendation_received": FactDataType.INTEGER,
    "quota.special": FactDataType.INTEGER,
    "quota.general_effective": FactDataType.INTEGER,
    "quota.plan_minus_received_recommendation": FactDataType.INTEGER,
    "applicant.above_national_line_count": FactDataType.INTEGER,
    "retest.cutoff_total": FactDataType.DECIMAL,
    "retest.entered_count": FactDataType.INTEGER,
    "retest.roster_count": FactDataType.INTEGER,
    "retest.result_published_count": FactDataType.INTEGER,
    "admission.exam_fulltime_total_count": FactDataType.INTEGER,
    "admission.general_count": FactDataType.INTEGER,
    "admission.final_list_fulltime_blank_remark_count": FactDataType.INTEGER,
    "admission.final_list_first_choice_fulltime_non_directed_count": FactDataType.INTEGER,
    "score.initial.min": FactDataType.DECIMAL,
    "score.initial.q25": FactDataType.DECIMAL,
    "score.initial.median": FactDataType.DECIMAL,
    "score.initial.mean": FactDataType.DECIMAL,
    "score.initial.q75": FactDataType.DECIMAL,
    "score.final_list_fulltime_blank_remark_initial.min": FactDataType.DECIMAL,
    "score.final_list_fulltime_blank_remark_initial.q25": FactDataType.DECIMAL,
    "score.final_list_fulltime_blank_remark_initial.median": FactDataType.DECIMAL,
    "score.final_list_fulltime_blank_remark_initial.mean": FactDataType.DECIMAL,
    "score.final_list_fulltime_blank_remark_initial.q75": FactDataType.DECIMAL,
    "score.final_list_first_choice_fulltime_non_directed_initial.min": FactDataType.DECIMAL,
    "score.final_list_first_choice_fulltime_non_directed_initial.q25": FactDataType.DECIMAL,
    "score.final_list_first_choice_fulltime_non_directed_initial.median": FactDataType.DECIMAL,
    "score.final_list_first_choice_fulltime_non_directed_initial.mean": FactDataType.DECIMAL,
    "score.final_list_first_choice_fulltime_non_directed_initial.q75": FactDataType.DECIMAL,
    "score.retest_roster_initial.min": FactDataType.DECIMAL,
    "score.retest_roster_initial.median": FactDataType.DECIMAL,
    "score.retest_roster_initial.mean": FactDataType.DECIMAL,
    "score.retest_roster_initial.max": FactDataType.DECIMAL,
    "weight.initial": FactDataType.DECIMAL,
    "weight.retest": FactDataType.DECIMAL,
    "weight.machine": FactDataType.DECIMAL,
    "machine.elimination_line": FactDataType.DECIMAL,
    "tuition.amount": FactDataType.DECIMAL,
    "tuition.basis": FactDataType.TEXT,
    "study.duration_months": FactDataType.INTEGER,
    "first_choice.protection": FactDataType.BOOLEAN,
    "training.city": FactDataType.TEXT,
    "training.campus": FactDataType.TEXT,
}

WEIGHT_FACT_KEYS = {"weight.initial", "weight.retest", "weight.machine"}


FACT_KEYS_FORBID_ORDINARY_GENERAL_EXAM_SCOPE = {
    "quota.recommendation_planned",
    "quota.recommendation_received",
    "quota.plan_minus_received_recommendation",
    "admission.final_list_first_choice_fulltime_non_directed_count",
    "score.final_list_first_choice_fulltime_non_directed_initial.min",
    "score.final_list_first_choice_fulltime_non_directed_initial.q25",
    "score.final_list_first_choice_fulltime_non_directed_initial.median",
    "score.final_list_first_choice_fulltime_non_directed_initial.mean",
    "score.final_list_first_choice_fulltime_non_directed_initial.q75",
}


PERCENTILE_INC_TYPE7_METHOD = "percentile_inc_type7_v1"


# New claims for score distributions must identify the exact calculation
# contract.  The median is q50, so q25/q50/q75 deliberately share one method.
STATISTICAL_FACT_METHODS = {
    "score.initial.min": "sample_min_v1",
    "score.initial.q25": PERCENTILE_INC_TYPE7_METHOD,
    "score.initial.median": PERCENTILE_INC_TYPE7_METHOD,
    "score.initial.mean": "arithmetic_mean_v1",
    "score.initial.q75": PERCENTILE_INC_TYPE7_METHOD,
    "score.final_list_fulltime_blank_remark_initial.min": "sample_min_v1",
    "score.final_list_fulltime_blank_remark_initial.q25": PERCENTILE_INC_TYPE7_METHOD,
    "score.final_list_fulltime_blank_remark_initial.median": PERCENTILE_INC_TYPE7_METHOD,
    "score.final_list_fulltime_blank_remark_initial.mean": "arithmetic_mean_v1",
    "score.final_list_fulltime_blank_remark_initial.q75": PERCENTILE_INC_TYPE7_METHOD,
    "score.final_list_first_choice_fulltime_non_directed_initial.min": "sample_min_v1",
    "score.final_list_first_choice_fulltime_non_directed_initial.q25": PERCENTILE_INC_TYPE7_METHOD,
    "score.final_list_first_choice_fulltime_non_directed_initial.median": PERCENTILE_INC_TYPE7_METHOD,
    "score.final_list_first_choice_fulltime_non_directed_initial.mean": "arithmetic_mean_v1",
    "score.final_list_first_choice_fulltime_non_directed_initial.q75": PERCENTILE_INC_TYPE7_METHOD,
    "score.retest_roster_initial.min": "sample_min_v1",
    "score.retest_roster_initial.median": PERCENTILE_INC_TYPE7_METHOD,
    "score.retest_roster_initial.mean": "arithmetic_mean_v1",
    "score.retest_roster_initial.max": "sample_max_v1",
}


DERIVED_FACT_RULES = {
    "quota.plan_minus_received_recommendation": (
        "subtract",
        "quota.total_plan",
        "quota.recommendation_received",
    ),
}


# A readable note remains part of the append-only claim identity, while the
# structured rule above is the machine-verifiable source of truth.
FACT_KEYS_REQUIRING_DERIVATION_NOTE = frozenset(DERIVED_FACT_RULES)
