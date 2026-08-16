INSERT INTO fact_definitions(fact_key, data_type, unit, description, preferred_source_type) VALUES
    ('score.retest_roster_initial.min', 'decimal', '分', '普通统考复试名单中初试总分最低值；不是拟录取最低分', '正式复试名单'),
    ('score.retest_roster_initial.median', 'decimal', '分', '普通统考复试名单中初试总分中位数；不是拟录取中位数', '正式复试名单'),
    ('score.retest_roster_initial.mean', 'decimal', '分', '普通统考复试名单中初试总分算术均值；不是拟录取均值', '正式复试名单'),
    ('score.retest_roster_initial.max', 'decimal', '分', '普通统考复试名单中初试总分最高值；不是拟录取最高分', '正式复试名单');
