# 操作、备份与恢复

<!-- 政策事件账本文档 TraceId: 0524daa1-0276-4cbc-90b2-40da1cc3e845 -->
<!-- 政策来源快照文档 TraceId: a3b9be61-bfcf-4eac-aeeb-b3d78e03a7d3 -->

## 初始化与升级

权威主库当前已执行迁移 1—27。第 020—022 号迁移负责追加式四科核验、兼容列合同和证据裁决安全视图；第 023—025 号迁移增加推免三阶段、来源元数据影子纠正和结构化算术推导；第 026—027 号迁移增加匿名成绩统计合同、候选版本链和跨年可比性审查。023—027 的 SHA-256 依次固定为 `ee02516f5371db93e419e93d660a5d867fc1ae671e0f6813b3de2e2f5e3fd928`、`5631e752f1a88611f968dd2053fc19fc92cfaaf08acf2f9881a2590f32afde25`、`348be9893f87ed39dc0eee5683139cf1e5d1c95c9fab2602a2f721725815d5fd`、`aff06c157044bd16befb0fbf6264bdec18f0dc5d5ef97c33f9f8c0535c1448b1`、`3ec8a321f3042de89785694b130ef9fc97b517e2de795fc07040213544ced91b`。所有已执行迁移禁止回改；后续修复必须新增向前迁移。升级前应先做一致性备份，再运行：

```powershell
python manage.py init
```

迁移按文件名前三位版本号顺序执行。每个已执行迁移保存 SHA-256；迁移文件执行后如被修改，系统会拒绝启动，要求新增向前修复迁移。

`init` 是唯一会应用迁移的常规命令。除允许保留旧版本的 `backup` 外，其他命令先通过只读 SQLite 连接核对迁移版本、文件名与校验和；旧库返回 `DATABASE_MIGRATION_REQUIRED`，不会创建数据库、切换 journal mode、写入迁移表或执行后续业务查询。收到该错误后先备份，再显式运行 `python manage.py init`。

## 日常健康检查

```powershell
python manage.py doctor
```

通过条件：`integrity_check=ok`、没有外键违规、所有观测都有原始行和项目追溯、没有残留的 `running` 导入批次，且个人偏好事件、机试会话都存在同 TraceId 的匹配审计事件。`machine_test_missing_audit` 必须为 `0`；`resolved_catalog_subject_without_verification`、`resolved_catalog_location_without_unique_fact`、`resolved_catalog_numeric_without_unique_fact` 也必须全部为 `0`。

第 026 号迁移还要求统计主张的样本数、计算方法、匿名输入哈希、唯一人数映射和 Q25≤Q50≤Q75 顺序全部自洽；第 027 号迁移还要求候选规范身份哈希、审计唯一性、active/retired 版本链，以及跨年可比性维度和证据包哈希全部通过。任一错误计数非 0，`doctor.status` 都不能为 `ok`。

第 014 号迁移应用后，`doctor` 必须确认套卷写入与排除事件均有匹配审计，并检查四科数量／代码、会话与分科 TraceId、`ABSENT`／`PRESENT_BLANK` 分数契约、真实时段与 180 分钟时长、严格 22408 满分量尺、协议事实与无效原因、评分规则、两天日历重叠及同卷复用。关键错误计数包括 `mock_v2_missing_audit`、`mock_exclusion_missing_audit`、`legacy_mock_missing_audit`、`mock_v2_subject_count_mismatch`、`mock_v2_subject_code_mismatch`、`mock_subject_trace_mismatch`、`mock_v2_attendance_score_mismatch`、`mock_v2_validity_reason_mismatch` 和 `mock_v2_scoring_rule_missing`；本次主库与迁移后备份验收均为 0，`status=ok`。`legacy_mock_session_count` 只是信息计数，不是错误，也不能升级为评估样本。

机试会话是追加式原始测量：数据库触发器禁止 `UPDATE` 和 `DELETE`。发现一次记录无效时，应保留成绩并在录入时填写 `invalid_reason`；不得为了让基线更好看而删除低分或零通过记录。

第 015—016 号迁移后，政策事件及其来源快照必须通过健康检查。以下十二个错误计数全部应为 `0`：

```text
policy_event_missing_trace
policy_event_missing_fingerprint
policy_event_missing_audit
policy_event_duplicate_audit
policy_event_source_metadata_invalid
policy_event_missing_source_snapshot
policy_event_source_snapshot_invalid
policy_event_source_snapshot_drift
policy_event_year_mismatch
policy_event_binding_mismatch
policy_event_invalid_supersession
policy_event_status_source_mismatch
```

这些检查分别防止无 TraceId／指纹、缺失或重复审计、非官方公告来源、缺少来源快照、快照内部字段无效、共享来源相对快照漂移、证据年度错位、项目与学校错绑、非法修订链，以及把科目调整公告写成非 `pending_directory` 状态。任一计数非零都会令 `doctor.status=error`；不要手工 UPDATE/DELETE 绕过检查。来源漂移不会改写 `policy-events` 的历史输出，因为查询读取快照，但仍属于必须调查的完整性错误。

## 政策公告日常操作

灰灰考研等二级汇总不得传给 `official-observation-add` 或 `verify-exam`。需要先把它作为线索建档时，使用 `secondary-observation-add`，并显式提供原页面 URL、发布机构、标题、内容 SHA-256、适用年度、发布日期／获取日期、项目对应原文和项目身份依据。四科必须四项全给或全不填；即使是完整 `101+204+302+408`，结果也只能是 `secondary_only`，且两个官方确认返回字段均为 `false`。重放前后应核对 `created=false`、观测 ID 不变、`subject_verifications` 未增加；同源同项目年度解释不一致时应停止并核查来源，不得改哈希绕过冲突。

只有官网正式公告且已经取得原始页面或附件内容 SHA-256 时，才使用 `policy-event-add`。例如湖南大学网络空间安全学院公告只确认第四科由 866 调整为 408，未给同项目完整四码，因此以学校级政策事件保存，不绑定计算机学院的既有观测：

```powershell
python manage.py policy-event-add `
  --school "湖南大学" `
  --effective-year 2027 `
  --event-type subject_adjustment_notice `
  --scope-text "网络空间安全学院 085400 电子信息" `
  --title "关于调整我院电子信息专业2027年硕士研究生招生考试初试科目的通知" `
  --description "公告明确第四科由866数据结构调整为408计算机学科专业基础；完整四码及项目身份仍以2027年正式招生目录为准" `
  --announced-on 2026-05-19 `
  --source-title "关于调整我院电子信息专业2027年硕士研究生招生考试初试科目的通知" `
  --source-url "https://cst.hnu.edu.cn/info/1053/1255.htm" `
  --source-institution "湖南大学网络空间安全学院" `
  --source-document-type official_notice `
  --source-content-sha256 98aded9bc3cfe1a10ea4034af2f850b70191b9f374c96ac36bd8d34c82c309b6 `
  --applicable-year 2027 `
  --published-date 2026-05-19 `
  --retrieved-date 2026-08-02 `
  --note "学校级政策事件；只确认第四科调整，不绑定计算机学院观察57，不确认严格22408"
```

成功结果必须仍显示：

```text
event_status = pending_directory
establishes_official_catalog = false
can_confirm_strict_22408 = false
```

它只追加或复用 `evidence_sources`，并在同一事务追加 `policy_events`、`policy_event_source_snapshots` 和同 TraceId 的 `policy_event_added` 审计事件；不创建 `project_year_observations` 或 `subject_verifications`，也不改变任何 `v_catalog.strict_22408_status`。因此“公告出现 408”不能改写为“严格 22408 已确认”；反向调整公告也只是待正式目录核验的政策信号。

查询可按年度、学校、项目、类型和状态过滤：

```powershell
python manage.py policy-events --year 2027
python manage.py policy-events --year 2027 --status pending_directory
python manage.py policy-events --school "湖南大学" --current-only
python manage.py policy-events --observation-id 57
```

`--status` 只接受 `pending_directory`；`announced`、`confirmed`、`superseded` 等字符串会在 CLI 参数解析阶段被拒绝，不能被当成政策状态筛选器。`--observation-id` 只返回绑定到该观测所对应精确项目的政策事件，不混入同校学校级事件；观测不存在时返回 `OBSERVATION_NOT_FOUND`，而不是空列表。

完全相同的写入重放应返回原 `event_id`、`created=false`，且来源、来源快照、事件和审计计数都不增加。若官网发布修订版，应追加新公告并传入 `--supersedes-event-id <旧事件ID>`；新旧事件的学校、可选项目、年度和类型必须相同。需要纠正同一官方页面的既有解析时，也允许复用同一来源，但必须显式指向被纠正事件；省略替代关系会返回 `POLICY_EVENT_SOURCE_CONFLICT`。同一旧事件已经有后继后再次尝试分叉会返回 `POLICY_EVENT_ALREADY_SUPERSEDED`。`--current-only` 只在查询时隐藏已经有后继的旧版本，历史行及其来源快照始终保留。

`policy-events` 的来源标题、机构、URL、文档类型、哈希和日期均来自 `policy_event_source_snapshots`。不得直接修改快照；迁移 016 的触发器会拒绝 UPDATE/DELETE。若其他流程意外改动共享 `evidence_sources`，历史查询仍显示冻结值，但 `policy_event_source_snapshot_drift` 会令 `doctor.status=error`，应追查漂移来源并通过新的向前修复方案处理，禁止覆盖快照以“消除”错误。

取得同一项目、同一招生年度正式招生目录完整四码后，才使用 `official-observation-add` 或 `verify-exam`。不要将公告改填为 `official_catalog`，也不要为了绑定事件而选择学院或专业不一致的观测。

## 四科套卷日常操作

推荐入口是 `mock-ledger-add`。每个协议布尔参数都必须显式给出肯定或否定形式，例如有效场次必须同时出现：

```text
--first-exposure
--complete-paper-set
--strict-schedule
--authentic-time-slots
--strict-timed
--no-consulted-materials
--no-received-assistance
--no-paused-timer
--no-reviewed-answers-early
```

不能只省略 `--consulted-materials` 来表示“没查资料”；CLI 的 `BooleanOptionalAction` 会要求显式的 `--no-consulted-materials`。任一执行条件为否时，仍应如实追加会话，但须同时填写 `--invalid-reason-code` 与 `--invalid-reason-note`。低分、正常疲劳或到场空白不是无效理由。

`mock-add` 是 legacy 兼容命令，写入的 `legacy_unverified` 行永不进入 v2 评估。查询与事后排除使用：

```powershell
python manage.py mock-sessions
python manage.py mock-sessions --include-legacy
python manage.py mock-sessions --eligible-only
python manage.py mock-exclude --session-id 12 --reason "计时器故障，事后核验无法证明连续计时"
python manage.py assessment
```

`mock-exclude` 追加事件，不更新或删除原会话。迁移 014 定义 `mock_exam_sessions`、`mock_exam_scores`、`mock_exam_subject_results`、`mock_exam_session_exclusions` 四表禁止 UPDATE/DELETE；纠错、重测与排除都只能追加并携带 TraceId。

解释 `assessment` 时，先看活动 `comparison_key` 和最近 5 次下界窗口。`ABSENT` 是 NULL 并排除整套，`PRESENT_BLANK` 是 0 且可作为有效低表现；主观区间禁止取中点。总分下界第二低是保守水平、第三低是常态水平，九档用半开边界并在跨档时取较低档护栏。`is_score_window_ready=true` 也不代表 `is_selection_ready=true`；当前迁移 014 后主库仍为 0 次套卷会话，二者均为 `false`。

## 八个择校门禁的日常判读

使用 JSON 输出查看完整门禁，不要只读取兼容字段 `is_decision_ready`：

```powershell
python manage.py --json assessment
```

首先检查：

```text
selection_gate_version
selection_gates[].code
selection_gates[].status
selection_gates[].blocking_reason
selection_gates[].details
selection_blocking_reasons
is_selection_ready
```

`selection-readiness-v3` 每次查询动态评估八项，查询使用只读连接且不写决策表，并采用 fail-closed 规则。状态解释为：

- `passed`：该项已有足够输入且满足当前合同；
- `blocked`：能够判断，但要求尚未满足或前置测量未完成；
- `not_evaluable`：缺权威结构、项目事实或审查合同，当前不能安全判断；它不是通过，也不等于项目已经被否决。

按下面顺序排查，不要手工改写输出：

| 门禁 | 常见非通过原因 | 正确处理 |
|---|---|---|
| `score_window` | `SCORE_WINDOW_INCOMPLETE` | 按 v2 协议完成同一比较组的 5 次有效套卷 |
| `subject_risk` | `SUBJECT_RISK_NOT_REVIEWABLE` / `SUBJECT_RISK_REVIEW_NOT_RECORDED` | 先完成窗口，再建立可复核的单科失守审查；不能凭总分自动通过 |
| `preference_input_coverage` | `PERSONAL_PREFERENCES_INCOMPLETE` | 用 `preference-readiness` 查看 23 项 V2 边界；当前主库已为 23/23 |
| `candidate_structure` | `ACTIVE_CANDIDATE_SET_EMPTY` / `CANDIDATE_STRUCTURE_INCONSISTENT` | 通过候选版本服务追加 current active 目标并检查 basis 分组；不能向 legacy 表手工插行绕过，retired 不计 |
| `candidate_2027_catalog` | `CANDIDATE_CATALOG_NOT_EVALUABLE` | 将研究假设逐条升级为同年度 `official_observation`，并确保 effective 状态为 `official_confirmed`；不能用全库计数或预告替代 |
| `candidate_ordinary_quota` | `CANDIDATE_QUOTA_NOT_EVALUABLE` | 补 `quota.general_effective × ordinary_general_exam × project` 的项目级当前事实 |
| `candidate_retest_contract` | `CANDIDATE_RETEST_CONTRACT_NOT_RECORDED` | 记录具体项目的机试／笔试／面试形式、权重、硬线和准备时序；机试按本人策略在初试通过后准备 |
| `candidate_fairness_review` | `CANDIDATE_FAIRNESS_REVIEW_NOT_RECORDED` | 对精确项目年度追加有来源、有日期、有摘要的普通本科背景公平性审查；口碑传闻不能代填 |

八项必须全部为 `passed` 才允许 `is_selection_ready=true`。`selection_blocking_reasons` 会按门禁顺序收集所有 `blocked` 和 `not_evaluable` 原因；不得因为某一项通过、分数较高或 legacy 表存在记录而忽略其余原因。

第 001 号迁移中的 `decision_snapshots` 和 `decision_candidates` 只作 legacy 诊断占位。它们缺少精确年度观测、当前窗口、偏好水位、复试审查、TraceId 和证据哈希；`assessment` 明确报告 `legacy_rows_are_authoritative=false`、`legacy_rows_affect_gate=false`。不要直接向这两张表写入“冲刺／匹配／稳健”角色，不要把其中旧行导出为当前推荐。

当前已存在 13 个 active `research_hypothesis`，所以 `candidate_structure` 通过；但正式候选计数为 0，目录门禁仍不通过。当前操作结论只能是：逐条取得 2027 正式目录后，使用新的候选版本升级为 `official_observation`，并继续补套卷测量、普通名额、复试合同与公平性证据；不能锁定主报或保底学校，也不能生成个人录取概率。机试训练已经后移，不应再作为当前删校理由。

## 备份

```powershell
python manage.py backup --output "data\backups\chose_school-YYYY-MM-DD.sqlite3"
```

备份使用 SQLite Backup API 和只读源连接生成一致性快照。默认不覆盖已有文件。`backup` 允许源库停留在旧 schema：它先确认数据库已经存在，再原样保存当前版本，因此可以真实用于“升级前备份”。升级必须在备份成功后显式运行 `python manage.py init`。若数据库不存在，备份命令失败且不会创建一个空库。

## 恢复

恢复属于可能覆盖当前数据的操作，因此没有提供自动命令。安全步骤：

1. 关闭所有使用数据库的进程；
2. 先为当前 `data/chose_school.sqlite3` 再创建一个外部副本；
3. 将确认过的备份复制为新的数据库文件；
4. 运行 `python manage.py init` 应用后续迁移；
5. 运行 `python manage.py doctor` 验证完整性。

不要直接删除 WAL/SHM 文件来“修复”数据库。

## 日志

结构化日志位于 `logs/chose_school.jsonl`，包含时间、级别、TraceId、操作、结果、耗时和异常堆栈。日志不写套卷详细备注或原始来源全文。

## 解决质量问题

先查询问题：

```powershell
python manage.py issues --severity warning --limit 20
```

取得可验证证据后再关闭：

```powershell
python manage.py issue-resolve --issue-id 123 --note "已按2027正式目录核对，见核验记录456"
```

关闭不会删除问题；状态、说明、时间和 TraceId 都会保留。
