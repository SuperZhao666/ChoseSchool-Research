INSERT INTO fact_definitions(
    fact_key,
    data_type,
    unit,
    description,
    preferred_source_type
) VALUES
    (
        'quota.recommendation_planned',
        'integer',
        '人',
        '目录静态发布阶段拟接收推免人数；与后续已接收推免人数分开，不参与最终统考名额推导',
        '正式招生目录静态版本'
    ),
    (
        'quota.recommendation_received',
        'integer',
        '人',
        '目录动态页或复试阶段文件明确列示的已接收推免人数；与拟接收计划及最终推免名单统计分开',
        '正式动态目录或复试细则'
    ),
    (
        'quota.plan_minus_received_recommendation',
        'integer',
        '人',
        '同一正式文件中的复试阶段总计划减去已接收推免人数得到的透明算术余量；可能包含专项，不等同普通统考有效名额',
        '正式复试细则及透明算术推导'
    ),
    (
        'admission.final_list_first_choice_fulltime_non_directed_count',
        'integer',
        '人',
        '一志愿最终名单中目标项目、全日制且拟录取类别为非定向的行数；名单无专项列时不得等同普通统考人数',
        '一志愿最终拟录取名单逐行筛选'
    ),
    (
        'score.final_list_first_choice_fulltime_non_directed_initial.min',
        'decimal',
        '分',
        '上述一志愿、全日制、非定向最终名单行的初试总分最低值；专项未拆时不得转存为普通统考最低分',
        '一志愿最终拟录取名单逐行复算'
    ),
    (
        'score.final_list_first_choice_fulltime_non_directed_initial.median',
        'decimal',
        '分',
        '上述一志愿、全日制、非定向最终名单行的初试总分中位数；专项未拆时不得转存为普通统考中位数',
        '一志愿最终拟录取名单逐行复算'
    ),
    (
        'score.final_list_first_choice_fulltime_non_directed_initial.mean',
        'decimal',
        '分',
        '上述一志愿、全日制、非定向最终名单行的初试总分算术均值；专项未拆时不得转存为普通统考均值',
        '一志愿最终拟录取名单逐行复算'
    );

UPDATE fact_definitions
SET description = '官方复试名单按主张限定群体列示的考生行数；不自动等于普通统考、资格审查通过或实际到场人数'
WHERE fact_key = 'retest.roster_count';

UPDATE fact_definitions
SET description = '官方复试结果表按主张限定群体列示的完整成绩行数；不自动等于普通统考或全部实际参加人数'
WHERE fact_key = 'retest.result_published_count';

UPDATE fact_definitions
SET description = '官方复试名单按主张限定群体计算的初试总分最低值；不自动等于普通统考或拟录取最低分'
WHERE fact_key = 'score.retest_roster_initial.min';

UPDATE fact_definitions
SET description = '官方复试名单按主张限定群体计算的初试总分中位数；不自动等于普通统考或拟录取中位数'
WHERE fact_key = 'score.retest_roster_initial.median';

UPDATE fact_definitions
SET description = '官方复试名单按主张限定群体计算的初试总分算术均值；不自动等于普通统考或拟录取均值'
WHERE fact_key = 'score.retest_roster_initial.mean';

UPDATE fact_definitions
SET description = '官方复试名单按主张限定群体计算的初试总分最高值；不自动等于普通统考或拟录取最高分'
WHERE fact_key = 'score.retest_roster_initial.max';
