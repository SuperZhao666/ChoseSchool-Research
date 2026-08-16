INSERT INTO fact_definitions(fact_key, data_type, unit, description, preferred_source_type) VALUES
    ('quota.exam_catalog_plan', 'integer', '人', '目录阶段公布的考试招生拟招人数；属于计划口径，不等同普通统考有效名额', '正式招生目录或官方分专业汇总'),
    ('applicant.above_national_line_count', 'integer', '人', '初试达到国家线人数；不等同实际进入复试人数', '官方分专业报考录取汇总'),
    ('admission.exam_fulltime_total_count', 'integer', '人', '全日制考试招生录取合计人数；可能包含专项计划，不等同普通统考录取人数', '官方分专业报考录取汇总');
