INSERT INTO fact_definitions(fact_key, data_type, unit, description, preferred_source_type) VALUES
    ('retest.roster_count', 'integer', '人', '官方复试名单列示的普通统考人数；只证明进入公开名单，不证明通过资格审查或实际参加复试', '正式复试名单'),
    ('retest.result_published_count', 'integer', '人', '官方公开复试结果表中具有完整成绩行的普通统考人数；不自动等同全部实际参加复试人数', '正式复试结果表');
