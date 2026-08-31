# 数据字典

<!-- 四年历史窗口数据字典 TraceId: 34c4c1e3-1696-4084-bbff-9bb1e6e5fdf5 -->

## 普通统考语义护栏（迁移 029）

| 表或视图 | 语义 | 关键约束 |
|---|---|---|
| `v_current_accepted_fact_evidence` | 只返回当前裁决为 `accept` 且绑定主张的事实 | 机器消费入口，不包含 `unresolved` |
| `v_current_unresolved_fact_evidence` | 当前明确未解决或没有选中主张的事实 | 研究缺口与纠错入口，不得参与普通名额/分数排序 |
| `admission.suggested_list_total_count` | 官方建议录取名单总行数 | 不等于最终录取人数，也不等于普通统考人数 |
| `admission.suggested_list_blank_remark_count` | 建议名单中备注为空的行数 | 只能表示限定集合，不能自动升级为普通统考 |
| `admission.suggested_list_special_count` | 建议名单中有明确专项备注的行数 | 与空备注行并列展示，不能从总数相减推断普通名额 |

`admission.general_count`、`score.initial.min/median/mean/q25/q75` 是普通统考机器字段，
从迁移 029 起只能写入 `evidence_grade=official` 的同口径正式证据。官方来源但专项未拆、
规则推导、复试池或建议名单代理，必须使用受控代理事实键或保持 `unresolved`。

## 候选画像适配与近四年历史覆盖（迁移 028、030）

迁移 028 新增画像适配账本和只读历史覆盖投影，迁移 030 将完整窗口从三年扩为四年；两项迁移都不预置适配结论，也不把历史分数变成 2027 推荐。

| 表或视图 | 语义 | 关键约束 |
|---|---|---|
| `candidate_profile_fit_reviews` | 精确候选版本相对于当前人物画像的追加式审查 | 完整偏好/现状事件快照、三份 canonical JSON/SHA-256、线性修订链、TraceId、禁止改删 |
| `v_current_candidate_profile_fit_reviews` | 每个候选版本画像审查链的链尾 | 新候选版本不继承旧审查 |
| `v_active_candidate_profile_fit_reviews` | 当前 active 候选的画像审查 | 返回 `is_input_snapshot_current`；画像变化后旧审查仍保留但立即显示过期 |
| `v_candidate_history_year_coverage` | 每个 active 候选在目标年前 4、3、2、1 年的逐年证据覆盖 | 只接受迁移 027 显式绑定的 current 可比性审查，绝不按校名/专业名自动配对 |
| `v_candidate_history_window_coverage` | 四个逐年槽位的窗口汇总 | 分开报告审查覆盖、普通名额覆盖、可复算压力覆盖和严格边界，不产生报考角色 |

`strategy_bucket` 只允许 `985_priority_research`、`211_hedge_research`、`non_211_comparator_research`，且 `strategy_assignment_basis` 固定为 `user_strategy_assignment`。它表示本人安排官网取证的先后层，不是院校层级的客观事实，也不是“冲／稳／保”。`known_preference_fit` 只允许 `compatible/conditional/conflict/insufficient`；`output_scope` 永远为 `research_only`，`probability_status` 永远为 `not_estimated`。

`input_snapshot_json` 固定 `candidate-profile-input-v1`，冻结写入当时该画像的全部 current `applicant_preference_events` 与全部 current `applicant_context_events` ID。`dimension_results_json` 固定 `candidate-profile-fit-dimensions-v1`，必须逐项覆盖 `institution/program_code/region/training_location/tuition/joint_training/retest_format/school_tier_strategy/admission_fairness/preparation_timing`；维度状态为 `pass/conditional/hard_conflict/not_evaluable/not_applicable`。`evidence_gaps_json` 每项保存唯一 `code`、`missing/partial/resolved/not_applicable` 状态、`selection_gate/research_condition/advisory` 影响和说明。三份 JSON 都规范化、哈希并由 `doctor` 重算；画像事件后来追加时不覆盖旧审查，而由 active 视图将 `is_input_snapshot_current` 置为 0，随后用新审查版本替代。

历史覆盖窗口按 `target_year-4` 至 `target_year-1` 动态生成；当前 2027 画像对应 2023—2026。逐年可能是 `unreviewed/ambiguous/invalid_subject_contract/comparable/limited/insufficient/rejected`。同年存在多个潜在可用审查时固定为 `ambiguous`，投影不会自行挑选“看起来最好”的观测。窗口汇总新增 `four_year_reviewed` 与 `four_year_comparable`；三年、两年和单年状态只表示尚未补齐四年，不再满足完整历史门禁。

迁移 027 的 `comparable` 文字本身不够：028 要求目标和历史两侧的精确观测都在 `v_catalog` 中为同年度 `official_confirmed`，否则逐年状态为 `invalid_subject_contract`，`doctor.comparability_subject_contract_invalid` 非零。成绩压力只读取迁移 026 的 `v_current_structured_score_statistics`，且必须没有 `v_statistical_fact_quality_issues`；旧主张若 `sample_size/calculation_method_key/calculation_input_sha256` 为 NULL，只能算 `legacy_unreproducible`，不得进入压力覆盖。压力组还必须与审查冻结的 `population_scope + statistic_scope` 完全相同，且对应样本人数事实以及 Q25/Q50/Q75（或复试名单的 min/Q50/mean/max）每个事实键都在该审查的 `fact_keys` 中显式声明；实际统计存在但审查未完整声明时返回 `not_fully_declared_by_review`。`ordinary_general_admission_initial`、两个最终名单代理人群和 `retest_roster_initial` 永不混合。

`score_history_support` 仅在目标是正式观测、四年均有有效 `comparable`、普通名额事实与同一普通统考人群的可复算压力完整时为 1。由于复试合同跨年连续性尚无结构化合同，`history_stability_support` 固定为 0，并返回 `retest_contract_continuity_not_modeled`；`admission_role_is_established` 也固定为 0。迁移 030 只把历史覆盖门禁从三年扩为四年，不新增 `selection-readiness-v3` 必需门禁；历史最低分、中位数或完整四年分布仍不能单独推动 `is_selection_ready=true`，也不能自动生成“冲稳保”或录取概率。

## 候选目标与跨年可比性（迁移 027）

迁移 027 只新增结构、约束与只读视图，不预置候选或可比性结论。

| 表或视图 | 语义 | 关键约束 |
|---|---|---|
| `candidate_target_versions` | 精确候选身份的追加式版本账本 | 跨库 canonical JSON/SHA-256、稳定 `candidate_key`、`research_hypothesis/official_observation`、`active/retired`、线性修订链、TraceId |
| `v_current_candidate_target_versions` | 每条稳定候选链的链尾 | 以 `supersedes_version_id` 判定 current |
| `v_active_candidate_targets` | 当前研究池 | 只保留 current 且 `action=active`；不代表其他择校门禁通过 |
| `project_history_comparability_reviews` | 精确候选版本与较早年度观测的比较审查 | `comparable/limited/rejected/insufficient`、维度合同 hash、证据包 hash、线性修订链、TraceId |
| `v_current_project_history_comparability_reviews` | 每个候选版本与历史观测审查链的链尾 | 新候选版本不继承旧审查 |
| `v_current_resolved_fact_evidence` | 当前事实裁决及来源无损高表 | claim/resolution、类型值、群体/统计口径、推导、统计样本元数据、来源 ID/hash/doc type/URL |

`identity_canonical_json` 固定 15 个字段：`schema`、`profile_key`、`target_year`、`school`、`college`、`program_code`、`program_name`、`direction`、`campus`、`training_location`、`study_mode`、`training_type`、`admission_type`、`degree_type`、`training_arrangement`。可选身份字段缺失时显式写 `unspecified`，禁止从历史 `project_id` 暗中补值。`candidate_key = "candidate-v1:" + SHA256(UTF-8 canonical JSON)`。

命令 `candidate-report` 是候选模型的只读人类可读投影。默认展示当前链尾的候选身份、`985_priority_research`/`211_hedge_research`/`non_211_comparator_research` 用户策略分组、画像适配结论、维度状态计数、证据缺口、历史可比性计数，以及偏好问卷、严格套卷窗口和成果资产的摘要；`--history` 展开修订链摘要，`--details` 另外附带仓储已校验的完整规范化 JSON。该投影不创建 `decision_snapshot`，不排序学校，不输出冲稳保角色或录取概率，并固定携带 `selection_output.scope=research_only`、`selection_output.role=research_only` 和 `selection_output.probability_status=not_estimated`。成果资产只用于解释准备基础，不参与概率换算。它只消费业务服务的当前视图，不直接查询 SQLite，因此不会绕过领域规则；查询本身不写库。

`research_hypothesis` 的 `target_project_id` 与 `target_observation_id` 必须同时为 NULL；`official_observation` 的两个 ID 必须非 NULL，并绑定同目标年、同规范身份且具有官方目录证据的观测。

`dimension_contract_json` 冻结 `population_scope`、`statistic_scope`、`special_plan_handling`、`fact_keys`，以及十二项身份维度的 `target/historical/conclusion/rationale`。历史观测只要求早于目标年，不要求本地 `project_id` 相同。`evidence_bundle_json` 每项固定 `role/source_id/content_sha256/document_type/applicable_year/source_url`，且来源必须实际支持相应目标年或历史年观测。

<!-- 政策事件账本文档 TraceId: 0524daa1-0276-4cbc-90b2-40da1cc3e845 -->
<!-- 政策来源快照文档 TraceId: a3b9be61-bfcf-4eac-aeeb-b3d78e03a7d3 -->

## 导入与原始数据

| 表 | 作用 | 关键字段 |
|---|---|---|
| `schema_migrations` | 迁移版本与校验和 | `version`, `checksum`, `applied_at` |
| `import_batches` | 每次归档导入或显式官方观测追加事件 | `source_sha256`, `status`, `trace_id`, 各类计数 |
| `source_files` | ZIP 内 CSV 成员或官方目录单行来源封装 | `archive_member`, `content_sha256`, `header_json` |
| `raw_catalog_rows` | 不可变原始记录或显式提取字段快照 | `source_row_number`, `raw_json`, `raw_cells_json`, `row_sha256` |

## 项目目录与年度观测

| 表 | 作用 | 说明 |
|---|---|---|
| `schools` | 学校主数据 | 规范名唯一 |
| `colleges` | 学院主数据 | 在学校内唯一 |
| `projects` | 稳定项目分析单位 | 不包含年份 |
| `project_year_observations` | 一条来源行或显式官方目录提取形成的年度观测 | 数值解析失败或未显式提供时为 NULL，原文仍在原始层 |
| `v_catalog` | 原始／核验混合兼容视图 | 保留旧字段合同；四科可使用追加式核验，但其他标量仍是导入影子值，只供审计兼容 |
| `v_catalog_evidence_resolved` | 默认安全查询视图 | 四科只接受正式核验；数值和培养地点只接受同一事实键下唯一的当前裁决；未核字段为 NULL |

关键观测字段：

| 字段 | 类型/单位 | 规则 |
|---|---|---|
| `strict_22408_claim` | 枚举 | 只表示来源层声明，不能单独视作官方确认 |
| `strict_22408_evidence_status` | 枚举 | 观测创建时的证据成熟度 |
| `subject_*_code` | TEXT | 专业代码和科目代码一律按字符串保存 |
| `effective_general_exam_quota` | INTEGER/人 | 复合文本不强转 |
| `retest_cutoff` | REAL/分 | 不混用国家线、校线、院线、方向线 |
| `retest_count` | INTEGER/人 | 必须与录取人数口径一致后才能计算复录比 |
| `admit_initial_min/median/mean` | REAL/分 | 中位数当前仅1条有值 |
| `*_weight` | REAL/0—1 | 裸60或60%均规范为0.6；近似或复合值不强转 |
| `tuition_per_year` | REAL/元/年 | “全程费用”不擅自除以学制 |
| `study_length_years` | REAL/年 | 范围值不压成一个数 |

`project_year_observations.subject_*_code` 保存观测创建时的不可变导入或快照值。兼容视图 `v_catalog` 在存在追加式 `subject_verifications` 且四科组合唯一时显示核验四科；没有核验时仍会回退到原始观测字段，因此不能作为默认科学输出。

CLI 的 `projects` 与 `export` 默认读取 `v_catalog_evidence_resolved` 并返回／导出 `projection_mode=evidence_resolved`：

- 四科必须存在追加式正式核验；二级来源或旧 CSV 的四码不会回退显示；
- 每个兼容数值字段只在对应事实键恰有一个当前接受口径时展示；同一事实键同时存在多个接受人群／统计口径时保守留空，禁止任意挑一个；
- `campus` 与 `training_location` 分别只接受 `training.campus` 与 `training.city`，复试地点、迎新地点和旧导入文本都不能代填培养地点；
- 行级 `evidence_grade`、`official_source`、`retrieval_date` 和 `notes` 默认留空，因为单一标签不能代表整行每个字段的证据成熟度；来源应从具体事实主张或四科核验查询；
- `projects --raw-imported` 与 `export --raw-imported` 显式读取兼容视图并标记 `projection_mode=raw_imported`，仅用于追溯旧快照，不得进入当前排序。

两个视图变化都不会覆盖原始字段；四科冲突时状态为 `conflict` 且四科全部留空。`doctor` 检查安全视图不得泄漏无正式核验四科、无唯一当前事实的数值或无唯一培养地点事实。

## 证据与治理

| 表 | 作用 |
|---|---|
| `evidence_sources` | 来源标题、机构、URL、发布日期与获取日期；`source_note` 是首次建源时的非穷尽来源级说明，不得从某一条项目事实的 `note` 自动复制，具体页面／人群用途以引用它的事实主张或事件快照为准 |
| `observation_sources` | 观测与来源关系 |
| `field_evidence` | 关键字段的原值、影子值和核验状态 |
| `subject_verifications` | 四科官方核验的追加历史 |
| `policy_events` | 官方政策公告的追加历史；可绑定学校或精确项目，但不建立正式目录事实 |
| `policy_event_source_snapshots` | 每个政策事件写入时冻结一份完整来源元数据；一事件一快照，禁止改删 |
| `v_policy_event_history` | 联结学校、可选项目与不可变来源快照的只读历史；显式输出修订状态和两个严格性否定字段 |
| `fact_claims` | 原子事实主张；仅透明算术事实可以保存五个结构化推导列；成绩分布事实另保存 `sample_size`、`calculation_method_key`、`calculation_input_sha256`。旧主张的新列保持 NULL，不回填 |
| `data_quality_issues` | 规则代码、严重级别、原值、解决说明 |
| `audit_events` | TraceId、写操作类型、实体和脱敏载荷 |

`official-observation-add` 只接收项目身份、年度、四科代码和正式目录元数据。它把用户显式提供的项目字段保存为单行不可变来源封装，同时追加 `official_catalog` 来源和 `subject_verifications`；未提供的项目字段与全部数值事实保持 NULL。相同项目身份、招生年度和目录内容重复提交是幂等读取，若同一来源对同一身份给出不同四科契约则拒绝写入。

`secondary-observation-add` 使用现有表追加二级项目年度观测，不新增或修改迁移。`evidence_sources.evidence_grade` 固定为 `secondary`，`document_type` 固定为 `secondary_summary`；项目身份、完整来源元数据、逐字摘录和 `project_identity_basis` 保存在不可变 `raw_catalog_rows.raw_json`，并通过 `observation_sources` 关联。来源身份键与 `fact-add` 的内容 SHA-256、文档类型、适用年度和 URL 合同一致，因此同一篇文章后续拆出原子事实时复用原来源行，不复制第二个来源 ID。四科列只能全 NULL，或同时保存四个三位代码；前者状态为 `unverified`，后者状态最多为 `secondary_only`。该通路不写 `subject_verifications`，`official_source` 与全部数值影子列固定为 NULL。写入审计类型为 `secondary_project_observation_added`，其 TraceId 与来源封装批次一致。完全相同重放不新增任何行；同一内容来源、同一项目、同一招生年度的不同解释返回 `SECONDARY_OBSERVATION_SOURCE_CONFLICT`。

### 政策事件账本

`policy_events` 保存政策公告，不保存正式招生目录结论。当前公共写入命令只支持 `event_type=subject_adjustment_notice`，并且只允许使用 `evidence_grade=official`、`document_type=official_notice` 的来源。写入状态固定为 `pending_directory`，`policy-events --status` 也只接受 `pending_directory`；其他字符串不是公共 CLI 支持的政策状态。

关键字段如下：

| 字段 | 类型/单位 | 规则 |
|---|---|---|
| `school_id` | INTEGER | 必须引用数据库中已有学校 |
| `project_id` | INTEGER/NULL | 可选精确项目绑定；使用 `--observation-id` 时从该观测解析，且项目必须属于同一学校；学校／学院级公告应保持 NULL；写入或查询不存在的观测返回 `OBSERVATION_NOT_FOUND` |
| `effective_year` | INTEGER | 政策生效招生年度，必须等于来源的 `applicable_year` |
| `event_type` | 枚举 | 当前仅允许 `subject_adjustment_notice` |
| `event_status` | 枚举 | 当前新写入固定为 `pending_directory`，不能解释为目录确认 |
| `scope_text` | TEXT | 公告明确作用范围的原子描述；学院、专业代码、专业名称等不能省略或用猜测补齐 |
| `title` / `description` | TEXT | 公告标题与保守转录；不得把未公布的完整四码补入描述 |
| `source_id` | INTEGER | 引用 `evidence_sources` 中同内容、同文档类型、同适用年度的官方公告来源 |
| `source_content_sha256` | TEXT | 官方页面或附件原始内容的 64 位小写 SHA-256，必须与来源表一致 |
| `announced_on` | DATE 文本 | 公告发布时间语义；发布日期原文仍同时保存在来源元数据中 |
| `trace_id` | TEXT | 新增事件必填，并与唯一 `policy_event_added` 审计事件一致 |
| `event_fingerprint` | TEXT/SHA-256 | 由学校、可选项目、年度、类型、状态、作用域、正文、来源身份、公告日期和修订关系稳定派生；用于完全重放幂等 |
| `supersedes_event_id` | INTEGER/NULL | 修订版指向旧事件；新旧事件的学校、可选项目、年度和类型必须一致，同一旧事件最多有一个直接后继 |
| `created_at` / `updated_at` | 时间文本 | 插入时必须相同；事件插入后禁止 UPDATE/DELETE |

`policy_event_source_snapshots` 的主键是 `policy_event_id`，每个事件必须恰有一条来源快照。快照包含：

| 字段 | 规则 |
|---|---|
| `source_id` / `source_identity_key` | 保留写入时引用的共享来源及其稳定内容身份 |
| `source_title` / `source_institution` / `source_url` | 冻结写入时用于解释公告的来源标题、机构和 URL |
| `evidence_grade` / `source_document_type` | 必须分别为 `official`、`official_notice` |
| `source_content_sha256` / `applicable_year` | 必须与政策事件的内容哈希和生效年度一致 |
| `published_date` / `retrieved_date` | 冻结当时的发布与获取日期，不随后续共享来源元数据变化 |
| `captured_at` / `trace_id` | 保存快照创建时间；TraceId 必须与所属政策事件一致 |

快照在事件事务中同步插入，数据库触发器禁止 UPDATE/DELETE。迁移 016（冻结 SHA-256：`03d3a17d44af3f4992de7a26fb022284d0b0d727877b510ed767db947d69ffad`）将已有政策事件在迁移执行时可见的 `evidence_sources` 元数据一次性回填为快照；迁移后 `v_policy_event_history` 只从快照读取来源列。因此共享 `evidence_sources` 即使发生漂移，也不能悄悄改写历史事件的展示；漂移会由 `doctor` 报错。

`v_policy_event_history` 追加返回 `is_superseded`，并将 `establishes_official_catalog` 与 `can_confirm_strict_22408` 永久投影为 `0`。因此：

```text
subject_adjustment_notice
→ event_status = pending_directory
→ establishes_official_catalog = false
→ can_confirm_strict_22408 = false
```

政策事件不会创建 `project_year_observations` 或 `subject_verifications`，也不会改变 `v_catalog.strict_22408_status`。只有同一项目、同一招生年度正式目录的完整 `101+204+302+408` 证据，才允许经 `official-observation-add` 或 `verify-exam` 形成 `official_confirmed`。

完全相同的指纹重放只返回已有事件，不新增 `evidence_sources`、`policy_event_source_snapshots`、`policy_events` 或 `audit_events`。公告修订必须通过新事件和 `supersedes_event_id` 追加，不得改写旧公告。若同一来源需要纠正既有解析，必须显式指向被纠正事件；没有替代关系的不同解析仍返回 `POLICY_EVENT_SOURCE_CONFLICT`。同一旧事件已有直接后继后再次创建分叉，返回 `POLICY_EVENT_ALREADY_SUPERSEDED`。

`policy-events --current-only` 只隐藏已有后继的历史版本，不删除历史记录；按 `--observation-id` 查询只返回该观测对应项目的事件，不混入学校级事件，不存在的观测返回 `OBSERVATION_NOT_FOUND` 而不是空列表。

## 字段级事实与裁决

| 表/视图 | 作用 |
|---|---|
| `fact_definitions` | 注册允许维护的事实键、数据类型、单位和首选来源 |
| `fact_claims` | 一条来源对一个事实的类型化主张；成绩统计可携带样本数、算法键和匿名输入 SHA-256；追加后不可改删 |
| `fact_resolutions` | 选择可信主张或撤回当前选择的追加式裁决事件；`unresolved` 事件的 `selected_claim_id` 为 NULL |
| `v_fact_conflicts` | 同一事实身份存在多个不同值的冲突清单 |
| `v_current_fact_resolutions` | 每个事实身份当前最新的裁决 |

事实身份包含项目年度观测、事实键、考生群体和统计口径。这样不会把普通统考与专项计划、项目线与学校线混为同一值。

### 官方分专业汇总的计数口径

| 事实键 | 类型/单位 | 准确定义 | 首选来源 |
|---|---|---|---|
| `quota.exam_catalog_plan` | INTEGER/人 | 目录阶段公布的考试招生拟招人数；是计划口径，不是普通统考有效名额 | 正式招生目录或官方分专业汇总 |
| `quota.recommendation_actual` | INTEGER/人 | 最终推免拟录取公示名单按同一项目、同一招生年度逐行筛选得到的项目级行数；不是最终报到、入学或学籍注册人数 | 最终推免拟录取公示名单逐行统计 |
| `quota.recommendation_planned` | INTEGER/人 | 静态目录发布阶段“拟接收”推免人数；必须与后来实际接收人数分开保存 | 正式招生目录静态版本 |
| `quota.recommendation_received` | INTEGER/人 | 动态目录或复试阶段文件明确列示的“已接收”推免人数；必须与拟接收计划及最终推免名单统计分开 | 正式动态目录或复试细则 |
| `quota.plan_minus_received_recommendation` | INTEGER/人 | 同一正式文件中的复试阶段总计划减去已接收推免得到的透明算术余量；可能仍含专项，不等于普通统考有效名额 | 正式复试细则及算术推导 |
| `applicant.above_national_line_count` | INTEGER/人 | 初试达到国家线人数；不是实际进入复试人数 | 官方分专业报考录取汇总 |
| `retest.roster_count` | INTEGER/人 | 官方复试名单按主张限定群体列示的行数；不自动等于普通统考、资格审查通过或实际到场人数 | 正式复试名单 |
| `retest.result_published_count` | INTEGER/人 | 官方复试结果表按主张限定群体列示的完整成绩行数；不自动等于普通统考或全部实际参加人数 | 正式复试结果表 |
| `score.retest_roster_initial.min/median/mean/max` | DECIMAL/分 | 官方复试名单按主张限定群体计算的初试总分分布；不自动等于普通统考，且必须与拟录取 `score.initial.*` 分开 | 正式复试名单 |
| `admission.exam_fulltime_total_count` | INTEGER/人 | 全日制考试招生录取合计；可能包含专项，不是普通统考录取人数 | 官方分专业报考录取汇总 |
| `admission.final_list_fulltime_blank_remark_count` | INTEGER/人 | 最终名单中目标项目、全日制且备注空白的行数；不自动等于普通统考录取人数 | 最终拟录取名单逐行筛选 |
| `score.initial.min/q25/median/mean/q75` | DECIMAL/分 | 普通统考拟录取者初试总分分布；`q25/median/q75` 必须来自同一输入集 | 最终拟录取名单逐人复算 |
| `score.final_list_fulltime_blank_remark_initial.min/q25/median/mean/q75` | DECIMAL/分 | 上述名单筛选行的初试分布；不得转存到普通统考 `score.initial.*` | 最终拟录取名单逐行复算 |
| `admission.final_list_first_choice_fulltime_non_directed_count` | INTEGER/人 | 一志愿最终名单中目标项目、全日制、非定向的行数；名单无专项列时不得等同普通统考人数 | 一志愿最终名单逐行筛选 |
| `score.final_list_first_choice_fulltime_non_directed_initial.min/q25/median/mean/q75` | DECIMAL/分 | 上述限定名单行的初试分布；专项未拆时不得转存到普通统考 `score.initial.*` | 一志愿最终名单逐行复算 |
| `training.city` / `training.campus` | TEXT | 项目培养城市／精确校区；不得由复试地点或迎新地点推断 | 正式目录、培养安排或录取通知 |

这些口径不得互相转存。尤其不能把复试名单人数写成 `retest.entered_count`，不能把全日制考试招生合计写成 `admission.general_count`，也不能把“备注空白行”或“一志愿、全日制、非定向行”直接写成普通统考。`quota.plan_minus_received_recommendation` 只允许同一正式文件同时列出两个操作数时使用，主张说明必须写明公式与操作数；结构化元数据固定为 `subtract`、`quota.total_plan`、左操作数、`quota.recommendation_received`、右操作数，且事实值必须等于两数之差。其他事实键禁止携带这五个推导字段。该算术余量仍不是普通名额。只有官方字段完成普通统考、专项计划、推免和培养类型拆分后，才能为对应普通统考事实键追加独立主张。`fact-unresolve --claim-id ...` 通过任一现有主张定位完整事实身份，并追加当前未裁决事件；它不会删除主张或历史裁决。

### 成绩统计的可复算合同（迁移 026）

未来新增的成绩分布主张必须同时提供三个字段：`sample_size` 为正整数；`calculation_method_key` 为冻结算法版本；`calculation_input_sha256` 为 64 位小写十六进制。旧主张三列保持 `NULL`，只能通过追加新版主张获得可复算结构，不允许覆盖旧行。

`calculation_input_sha256` 的输入规范固定为 `score_values_sorted_json_v1`：只取主张声明人群中的有效初试总分，以十进制精确值升序排列并保留重复值；每个值转为不带指数、不带前导加号、去除小数末尾零的最短十进制字符串（负零归一为 `0`）；按无空格 UTF-8 JSON 字符串数组序列化，例如 `["309","316","350.5"]`，再计算 SHA-256。该哈希只冻结匿名分数序列，不保存姓名、考生号等个人信息。

`q25/median/q75` 的方法键统一为 `percentile_inc_type7_v1`：对升序序列 `x[1..n]` 取 `h=(n-1)p+1`，`j=floor(h)`，`g=h-j`，结果为 `(1-g)x[j]+g x[j+1]`，端点按首尾值处理；其中 `p` 分别为 `0.25/0.5/0.75`。这与 Excel `PERCENTILE.INC` 及 R type 7 口径一致。`min/mean/max` 分别使用 `sample_min_v1`、`arithmetic_mean_v1`、`sample_max_v1`。

机器不把自然语言 `statistic_scope` 的字面相等当作统计身份。质量组以“观测 + 统计族 + `population_scope`”为身份，再以 `sample_size + calculation_input_sha256` 锁定同一输入集。人数对应关系为：`score.initial.* → admission.general_count`，`blank_remark → admission.final_list_fulltime_blank_remark_count`，`first_choice_fulltime_non_directed → admission.final_list_first_choice_fulltime_non_directed_count`，`retest_roster → retest.roster_count`。对应受控人群的当前 accepted 人数必须恰好一条且等于 `sample_size`；同输入组必须满足 `q25 ≤ median ≤ q75`。`v_statistical_fact_quality_issues` 与 `doctor` 对缺失、多义、样本数不等、输入不一致、分位数组不完整及顺序错误均按错误处理。

### 最终录取者分科成绩研究层（2026-08-31）

<!-- 最终录取者分科成绩证据合同 TraceId: 306de97b-8fa5-4276-af08-2d438c190205 -->
<!-- 合工大 2024 旁证交叉状态续补 TraceId: 64922be8-f1a4-4f2e-a987-dcfa8c8fbae7 -->

[当前 16 项四年分科审计](current-16-four-year-admitted-subject-score-distribution-audit-2026-08-31.md)新增了政治、外语、业务课一、业务课二的匿名聚合研究层。该层当前是人类可读证据库，**不是迁移 030 以前已有的 `fact_definitions` 机器字段，也不进入 `v_current_structured_score_statistics`、`score_history_support` 或录取概率**。这样可避免把需要“两份原件交叉”的统计硬塞进只能表达单一事实来源的旧主张合同。

研究状态固定为：

| 状态 | 合同 |
|---|---|
| `official_final_subject_rows` | 正式最终名单本身同时给出最终身份和四科 |
| `official_final_crossmatch` | 同项目同年度的正式含四科名单与正式最终名单按稳定编号 100% 无歧义匹配，且四科和与最终初试总分一致 |
| `secondary_mirror_final_crossmatch` | 正式最终名单与完整第三方镜像四科表按稳定编号 100% 无歧义匹配、四科和与正式总分一致，但镜像尚未与正式附件完成字节或哈希同一性核验；只允许作为人类可读旁证，不算官方精确格 |
| `official_final_total_only` | 最终人口可确认，但正式原件只有初试总分，禁止反推四科 |
| `official_retest_subject_rows_only` | 四科只支持复试人口，缺完整最终集合或稳定匹配，禁止冒充录取人口 |
| `missing` | 正式附件撤下、验证码/空文件、公示结束或项目方向身份不闭环；不等于 0 |
| `not_applicable` | 当年尚无独立项目；不等于录取 0 人 |

决策模型只允许把前两种状态用作分科历史上下文；`secondary_mirror_final_crossmatch` 只能在报告中显式标为旁证，不得进入择校排序、目标分、录取概率或“冲稳保”判断。正式状态还必须同时保留 `population_scope`、专项/联培/委托排除规则、学习方式、方向边界和当年四科合同。相同总分不意味着相同科目结构；`917/961/902/861/840/839` 与 `408` 均为比较断点。读取时优先看中位数与 Q25—Q75，最低值、最高值和单年小样本不得建立“安全线”。

如果未来把该研究层升级为机器事实，至少要新增可绑定“含四科原件 + 最终名单原件”的多来源证据包，并对总分和四个科目分别冻结 `n/min/Q25/median/mean/Q75/max`、Type 7 方法版本和匿名输入哈希；每科样本数必须等于对应最终人口。迁移、领域注册表、CLI、质量视图、`doctor`、README 与测试须同步向前新增。在此之前，不为本轮 18 个可算年度制造看似结构化但证据链不完整的数据库行。

## 个人测评

<!-- 个人测评口径修复 TraceId: 2f82ffa4-df9d-42ff-be5c-9f6961cd2603 -->
<!-- 追加式个人偏好能力 TraceId: db529e6a-5f02-4b81-a13b-6de6bc0744c1 -->

| 表 | 作用 |
|---|---|
| `applicant_profiles` | 本科、目标年份、考试科目和目标层级；`preferences_json`仅作旧版兼容 |
| `applicant_preference_events` | 地域、培养地点、专业代码、费用、复试形式等接受边界的追加历史；禁止改删 |
| `v_current_applicant_preferences` | 每个画像、维度和具体对象下最新一条偏好事件 |
| `applicant_context_events` | 备考进度、作息、测量状态、准备时序与个人约束的追加式画像事件；禁止改删 |
| `v_current_applicant_context` | 每个画像、维度和具体对象下最新一条画像事件 |
| `candidate_fairness_reviews` | 精确项目年度的普通本科背景友好度审查；保存结论、摘要、不可变证据 JSON、证据哈希和 TraceId；禁止改删 |
| `v_current_candidate_fairness_reviews` | 每个项目年度最新一条公平性审查；不得跨项目或跨年度继承结论 |
| `applicant_achievement_events` | 竞赛、奖学金和能力证书的追加式事实版本；保存范围、阶段、个人/团队口径、结构化详情、核验状态、指纹版本和 TraceId；禁止改删 |
| `applicant_evidence_documents` | 个人成果原始证据文件的不可变来源快照；文件身份由画像和内容 SHA-256 唯一确定，018 的复核列仅作 legacy 快照，禁止改删 |
| `applicant_evidence_review_events` | 对同一原始证据文件追加的复核/纠正版本；保存复核日期、方法、等级、状态、主张、说明、复核指纹和 TraceId；禁止改删 |
| `applicant_achievement_evidence_links` | 成果版本与证据文件之间的 `supports/contradicts/context` 关系；禁止改删 |
| `applicant_achievement_evidence_review_links` | 将每条成果—证据关系固定绑定到当时采用的具体复核版本，避免后续复核改写历史成果含义；禁止改删 |
| `v_current_applicant_achievements` | 每个 `profile_id × achievement_key` 下 ID 最大的当前成果版本；旧版本继续留在事件表 |
| `mock_exam_sessions` | 套卷会话主记录；legacy v1 与两天协议 v2 共表，以 `ledger_version` 隔离；迁移 014 后禁止改删 |
| `mock_exam_scores` | legacy v1 四科精确分；仅兼容留痕，不是 v2 权威成绩源；迁移 014 后禁止改删 |
| `mock_exam_subject_results` | v2 分科权威结果；保存出勤状态、分数下／上界、满分、实际起止时间、时长和 TraceId；禁止改删 |
| `mock_exam_session_exclusions` | 事后发现客观协议问题时追加的排除事件；一场至多一条，禁止改删，不能覆盖原会话 |
| `v_mock_exam_ledger_sessions` | 从会话、四科结果和排除事件派生执行有效性、评估资格、分数精度及 `comparison_key` |
| `machine_test_sessions` | 追加式机试原始会话；保存时长、语言/环境、题组、独立通过情况、有效性前提、TraceId；禁止改删 |
| `v_machine_test_sessions` | 在原始会话上派生 `is_valid`，不改写会话，也不生成跨时长平均值 |
| `decision_snapshots` | 001 迁移遗留占位表；缺 TraceId、年度观测绑定、追加保护和完整门禁，当前禁止作为权威择校快照 |
| `decision_candidates` | 001 迁移遗留占位表；只引用 `project_id` 且角色含义不足，当前禁止作为权威候选结构 |

`applicant_profiles.preferences_json` 是旧版预留字段，不作为当前偏好的权威来源。个人边界由 `applicant_preference_events` 保存，事实身份为：

```text
profile_id × dimension × subject_key
```

每次改变答案都追加新事件；当前值由该身份下 `id` 最大的事件决定。支持的 `dimension` 为 `region`、`training_location`、`program_code`、`tuition_ceiling`、`retest_format`、`joint_training`、`school_tier_requirement`、`admission_fairness`、`institution`。`acceptance_level` 只允许 `accept`、`reluctant`、`reject`、`unknown`；其中 `unknown` 不得默认为通过筛选。`value_json` 必须是合法 JSON 对象。学费策略既可使用 `amount+basis+currency` 的金额上限，也可使用 `{"mode":"no_hard_cap"}`；个人院校排除必须说明是个人选择，不能写成院校事实。每次写入和对应 `audit_events` 共用一个 TraceId。

`preference-readiness` 使用只读合同 `personal-selection-preference-v2`。必需身份共 23 个：

- `region:actual_training_scope` 1 个，值的 `mode` 只允许 `near_region/mainland/custom`；`custom` 必须提供非空 `locations`；
- `joint_training` 的 `offsite/enterprise/international/unknown_assignment` 4 个；
- `tuition_ceiling:default` 1 个；金额上限和 `no_hard_cap` 均受支持；
- `program_code` 的 `085404/085405/085410/085411/085412/085400/145200/any_other_eligible_code` 8 个；
- `school_tier_requirement` 的 `211_floor/non_211_acceptable` 2 个，必须互补；
- `retest_format` 的 `machine_test/written_test/theory_closed_book/pure_interview/high_weight_interview` 5 个；
- `admission_fairness` 的 `ordinary_undergraduate_friendly/no_background_discrimination` 2 个。

当前 `985_priority_211_hedge=accept` 仅是排序偏好，不计入上述 23 项。权威主库当前为 23/23；输出 `answered_subject_count` 只统计已有且非 `unknown` 的原子答案。完整度完成只表示本人边界已回答，不代表具体候选项目事实足够筛选，更不代表 `is_selection_ready=true`。

### 个人现状与公平性审查账本

`applicant_context_events` 的事实身份为 `profile_id × dimension × subject_key`。`dimension` 只允许 `study_progress/study_routine/measurement_status/preparation_strategy/personal_constraint`；`value_json` 保存本人原话可支持的结构化影子值，`note` 保留人类可读说明。当前值由视图取最新事件，但旧事件和对应审计均保留。

`candidate_fairness_reviews` 的事实身份为 `profile_id × observation_id`；目标招生年度来自该 observation。`conclusion` 只允许 `favorable/mixed/adverse/insufficient`。`evidence_json` 必须是数组，每个证据对象保存来源、日期、可复核摘要和信号方向，规范化 JSON 的 SHA-256 写入 `evidence_sha256`；没有足够证据时只能写 `insufficient`。个人院校排除属于偏好账本，不得写入此表，也不得把未经证实的“歧视”说法当作事实。

### 个人成果证据账本

迁移 018 新增成果、文件和关系三表；迁移 019 只向前新增复核事件/复核关联，并为成果增加 `fingerprint_version`。成果事实身份为：

```text
profile_id × achievement_key
```

同一身份可以追加更正版本；当前视图按事件 ID 选择最新一条，但旧版本、证据链接、具体复核版本和审计事件不删除。迁移前事件保留 `v1` 指纹，新事件使用包含成果 `note` 与证据复核内容的 `v2` 指纹；完全相同的规范化请求重放不产生新行，而 note-only 修订会追加新成果版本。同一 `profile_id × source_content_sha256` 只能对应一份不可变原始文件身份；复核状态、方法、主张或说明变化时追加 `applicant_evidence_review_events`，成果关系固定引用采用的那一版复核。

`ApplicantAchievementInput` 的关键枚举为：

| 字段 | 允许值与边界 |
|---|---|
| `category` | `competition_award/scholarship/ability_certificate`；奖学金不计入算法竞赛数量 |
| `scope_level` | `national/provincial/school/unspecified/not_applicable`；证书没写级别时必须用 `unspecified` |
| `stage` | `national_final/provincial_round/preliminary_round/popularization/academic_year/assessment` |
| `participation_type` | `individual/team/not_applicable/unknown`；团队成果必须有团队名，奖学金用 `not_applicable` |
| `verification_status` | `document_confirmed/metadata_only/self_reported/conflict`；这里不存在招生目录专属的 `official_confirmed` |
| `details_json` | 合法 JSON 对象；复合成绩用 `score.obtained+maximum`，排名用 `rank.position+population`；禁止证书号、学号、身份证号和报名标识 |

证据等级 `primary_document_user_copy` 表示用户提供的原件副本已经逐页核验；它不等于发证方在线确认。在发证方身份、官方域名和核验快照模型建立前，服务完全拒绝 `official_online_verification`。`document_confirmed` 至少需要一条视觉确认的 `supports`，并且不得存在 `contradicts` 关系或 `evidence_status=conflict` 的复核。敏感键先经 NFKC、大小写和分隔符规范化，成果标题/结果/说明及证据标题/主张/说明也检查带标签的敏感编号。查询不返回原始文件标题、证据摘录和备注；私人 Drive 与本地文件 URL 返回 `null`，只有 `public_web` 可返回 URL，同时保留访问范围和内容哈希用于非秘密溯源。

现有两张 `decision_*` 表均为空且只作 legacy 占位。未来若实现权威选择快照，必须通过新的向前迁移绑定精确 `observation_id × target_year`、当前五次窗口、偏好事件水位、复试审查、TraceId 和证据哈希，并禁止更新删除；不得回改 001，也不得将 legacy 行用于通过择校门禁。

### 动态择校就绪度投影

择校就绪度不是数据库表，也不写入 `decision_snapshots`。`assessment` 在每次查询时组合套卷统计与只读 `SelectionReadinessFacts`，按 `selection-readiness-v3` 动态返回：

| 输出字段 | 语义 |
|---|---|
| `selection_gate_version` | 当前八门禁合同版本，现为 `selection-readiness-v3` |
| `selection_gates` | 固定顺序的八条 `SelectionGateResult`；每条包含 `code`、`status`、`blocking_reason` 和只读 `details` |
| `selection_blocking_reasons` | 按门禁顺序去重后的所有非通过原因；同时包含 `blocked` 与 `not_evaluable` |
| `is_selection_ready` | 仅在八个预期代码完整、顺序正确且状态全部为 `passed` 时为真 |

`SelectionGateStatus` 的取值和 fail-closed 语义为：

| 状态 | 语义 | 能否通过总门禁 |
|---|---|---|
| `passed` | 当前合同要求已经满足且有足够输入证明 | 是 |
| `blocked` | 可以判断，但当前尚未满足要求或缺少前置输入 | 否 |
| `not_evaluable` | 缺少权威结构、项目事实或审查合同，不能安全判断 | 否；也不得解释为项目已经失败 |

八个门禁固定为：

| `SelectionGateCode` | 判定依据与当前 v2 边界 |
|---|---|
| `score_window` | `is_score_window_ready`；不足 5 次时 `blocked` |
| `subject_risk` | 无窗口时 `blocked`；已有窗口但没有单科审查合同时 `not_evaluable`，当前不会自动 `passed` |
| `preference_input_coverage` | 23 项 V2 偏好完整度；缺失、`unknown`、矛盾或不支持值均 `blocked` |
| `candidate_structure` | `active_candidate_count > 0` 且 basis 分组计数一致时通过；0 条时以 `ACTIVE_CANDIDATE_SET_EMPTY` 返回 `not_evaluable`；retired/legacy 均不计 |
| `candidate_2027_catalog` | 所有 active 均为 `official_observation` 且逐条绑定同目标年度 effective `official_confirmed` 时通过；任一研究假设或未确认正式候选均为 `not_evaluable` |
| `candidate_ordinary_quota` | 要求项目级 `quota.general_effective`、`ordinary_general_exam`、`project` 同口径事实；没有权威候选集合时返回 `not_evaluable` |
| `candidate_retest_contract` | 要求记录项目特定机试／笔试／面试形式、权重、硬线和准备时序；不再要求当前阶段先完成机试基线 |
| `candidate_fairness_review` | 要求每个候选具有同项目、同招生年度的当前公平性审查；缺审查或只有印象时返回 `not_evaluable` |

`SelectionReadinessFacts` 的候选字段来自 `v_active_candidate_targets`，并按当前 `profile_id × target_exam_year` 过滤：

| 字段 | 含义 |
|---|---|
| `active_candidate_count` | current 且 active 的候选总数 |
| `active_research_hypothesis_count` | 其中尚不绑定本地观测的研究假设数 |
| `active_official_observation_count` | 其中绑定正式目标年度观测的候选数 |
| `active_official_confirmed_count` | 正式候选中，精确观测同目标年度且 `v_catalog.strict_22408_status=official_confirmed` 的数量 |

`target_year_observation_count`、`official_confirmed_target_year_count` 与 `official_pending_target_year_count` 仍是全库诊断字段，`global_catalog_counts_are_authoritative=false`，不得参与目录门禁通过判定。第 001 号迁移遗留的 `decision_snapshots` 和 `decision_candidates` 也不属于这套动态投影；其计数只出现在 `candidate_structure.details`，且 `legacy_rows_are_authoritative=false`、`legacy_rows_affect_gate=false`。`CandidateTier` 同样只是旧占位枚举，不能当作当前个人候选角色的权威来源。

兼容字段 `is_decision_ready` 只镜像分数窗口就绪，不能替代 `is_selection_ready`。当前 13 个 active 候选全部为研究假设，因此偏好与候选结构两项通过，但目录门禁仍为 `not_evaluable`，其他门禁也没有全部通过；不能锁校、不能生成保底结论，也不能输出个人录取概率。机试测量仍可在初试通过后追加，但不再属于 V3 八门禁之一。

### 四科完整套卷账本 v2

第 014 号迁移已应用到权威主库，SHA-256 为 `d57a5b1b383eee63a66d9d599044412c5f2c148707c5a11ed940597b0c146914`，执行后禁止回改。迁移后 legacy/v2 套卷、分科结果和排除事件仍均为 0；`is_score_window_ready=false`、`is_selection_ready=false`。

`mock-add` 只保留兼容能力：它追加 `ledger_version=1` 的会话及 `mock_exam_scores`，派生为 `legacy_unverified`。无论旧行是否有四个精确分、是否传入 `--strict-timed`，都不能升级为 v2 评估样本。v2 只能由 `mock-ledger-add` 追加，且所有协议布尔字段必须由 CLI 的 `BooleanOptionalAction` 显式给出 `--foo` 或 `--no-foo`，不能由缺省值猜测。

`mock_exam_sessions` 的 v2 关键字段为：

| 字段 | 类型/单位 | 规则 |
|---|---|---|
| `ledger_version` | INTEGER | `1` 为 legacy，`2` 为两天四科协议 |
| `taken_on` / `completed_on` | DATE 文本 | v2 的第一天／第二天；合格执行必须恰好相差 1 天 |
| `paper_name` / `paper_key` | TEXT | 显示名与稳定身份；同一画像、同一试卷重复作答不能冒充首次见卷 |
| `paper_source` / `paper_content_sha256` | TEXT | 试卷来源及可选内容哈希；哈希存在时用于识别改名后的同卷 |
| `exam_contract` | TEXT | 当前固定为严格 `101+204+302+408` 契约 |
| `first_exposure` | BOOLEAN | 是否首次见卷；重复尝试不能标记为真 |
| `complete_paper_set` | BOOLEAN | 是否使用完整四科卷面，未学部分不能删去后按比例放大 |
| `strict_schedule` | BOOLEAN | 是否连续两天完成 |
| `authentic_time_slots` | BOOLEAN | 是否使用 08:30—11:30／14:00—17:00 的真实时段 |
| `strict_timed` | BOOLEAN | 是否每科到点停笔，未补时 |
| `consulted_materials` | BOOLEAN | 是否查资料；为真则执行无效 |
| `received_assistance` | BOOLEAN | 是否接受人、AI 或其他提示；为真则执行无效 |
| `paused_timer` | BOOLEAN | 是否暂停计时；为真则执行无效 |
| `reviewed_answers_early` | BOOLEAN | 第二天结束前是否看答案；为真则执行无效 |
| `paper_family` | 枚举 | `official_past`、`calibrated_mock`、`training`、`unknown`；后两者不能进入比较窗口 |
| `difficulty_label` | 枚举 | `standard`、`easier`、`harder`、`unknown`；`unknown` 不能进入比较窗口 |
| `scoring_rule_key` | TEXT | 评分协议身份；不同口径不能混算 |
| `invalid_reason_code` / `invalid_reason_note` | 枚举/TEXT | 任一执行条件失败时必须同时填写受控代码和说明；全部合格时必须为空 |
| `trace_id` | TEXT | v2 必填，并与四科结果及 `mock_exam_added` 审计事件一致 |

`mock_exam_subject_results.attendance_status` 有三种互斥语义：

- `present_scored`：到场并评分，`score_lower`、`score_upper` 与起止时间必填；
- `present_blank`（用户语义 `PRESENT_BLANK`）：到场并严格坐满但空白，分数固定为 `0..0`，属于有效低表现；
- `absent`（用户语义 `ABSENT`）：缺考，分数、起止时间和时长都必须为 NULL，整套不得进入最近 5 次。

政治、英语满分固定 100，数学、408 满分固定 150；四个非缺考科目各须实际完成 180 分钟。主观题只能得到区间时原样保存下界与上界，禁止计算中点作为精确事实。分数精度派生为 `exact` 或 `interval`，并参与比较组身份。

可进入评估的会话必须同时满足：v2、TraceId 完整、首次见卷、完整卷面、连续两天、真实时段、严格限时、未查资料、未接受提示、未暂停、未提前看答案、四科结果齐全且无 `ABSENT`、每科 180 分钟、没有追加排除事件，且试卷家族和难度允许比较。其 `comparison_key` 为：

```text
exam_contract
× paper_family
× difficulty_label
× scoring_rule_key
× score_precision_mode
```

当前个人分数规则使用 `[assessment] minimum_sessions = 5` 和 `rolling_window_size = 5`。系统选取最新合格会话所属的活动 `comparison_key`，只在该组内按第二天日期、会话 ID 取最近 5 次；不同试卷家族、难度、评分协议或精度模式绝不凑数。第 6 次以后只滚动窗口，不覆盖旧行。

窗口的分档一律使用总分下界：排序后第二低下界为保守水平，第三低下界为常态水平。含区间的窗口不会取中点，也不返回伪精确均值、标准差或旧式精确 `conservative_total`。九档是半开区间 `<290`、`[290,305)`、`[305,315)`、`[315,325)`、`[325,335)`、`[335,345)`、`[345,360)`、`[360,380)`、`>=380`；最近五次占据多个档位时，角色档位取所占较低档作为下护栏。

`is_score_window_ready` 只回答“活动比较组是否已有 5 次有效样本”。`is_selection_ready` 使用上述八个动态 fail-closed 门禁；分数窗口只是其中一项，不能让其他七项自动通过。兼容输出 `is_decision_ready` 只镜像分数窗口就绪，不得解释为已经锁校。

套卷四张表由迁移 014 定义为追加式：禁止 UPDATE/DELETE。客观协议问题只能通过 `mock-exclude` 追加 `mock_exam_session_exclusions`，原始会话与分科结果继续可查。`mock-sessions` 默认只显示 v2，只有显式 `--include-legacy` 才显示旧记录；`--eligible-only` 只筛评估合格项。所有写操作携带 TraceId，`doctor` 检查套卷／排除审计、四科数量和科目代码、分科 TraceId、出勤分数契约、时间表、满分量尺、评分规则、协议原因、日历重叠以及同卷复用异常。

### 机试原始会话

<!-- 追加式机试记录文档 TraceId: 7acdcafb-dde0-4a88-b789-c0a16d43b54b -->
<!-- 迁移013机试补强文档 TraceId: ba4c71bc-dd36-467b-9d18-8553b2968fb1 -->

第 012 号迁移首次建立该表且已经执行，禁止回改。第 013 号迁移通过 `ALTER TABLE` 向前新增测量协议字段、增加插入校验触发器，并重建 `v_machine_test_sessions` 的有效性派生规则；它不会覆盖任何第 012 号迁移后已经追加的会话。

`machine_test_sessions` 的核心字段为：

| 字段 | 类型/单位 | 规则 |
|---|---|---|
| `profile_id` | INTEGER | 关联个人画像；删除画像不得级联删除机试历史 |
| `taken_on` | DATE 文本 | 实际测量日期 |
| `duration_minutes` | INTEGER/分钟 | 保存真实协议时长；允许记录项目特定时长，不压缩到最近的标准桶 |
| `language` | TEXT | 本次实际使用语言，例如 C 或 C++；不同语言不能因时长相同而视作同一协议 |
| `environment` | TEXT | 编译器、IDE、判题或离线环境的自包含描述 |
| `problem_source` | TEXT | 可区分题组的来源；与日期、尝试次数共同防止同一记录重复写入 |
| `difficulty_label` | 枚举 | `basic`、`mixed`、`candidate_specific`、`unknown` |
| `problem_count` | INTEGER/题 | 必须为 1—100 |
| `independently_solved_count` | INTEGER/题 | 允许为 0，但不得超过总题数；只记在限时内独立通过的题 |
| `first_solve_minutes` | INTEGER/分钟或 NULL | 通过 0 题时必须为 NULL；至少通过 1 题时必须为 1 至本场时长 |
| `first_exposure` | BOOLEAN | 是否首次见到该题组 |
| `consulted_materials` | BOOLEAN | 是否查资料；查资料样本不得进入有效基线 |
| `received_assistance` | BOOLEAN | 是否接受人、AI 或其他外部提示/帮助；接受帮助的样本不得进入有效基线 |
| `paused_timer` | BOOLEAN | 是否暂停计时；暂停过的样本不得进入有效基线 |
| `strict_timed` | BOOLEAN | 是否连续严格限时并到点停止 |
| `scoring_method` | 枚举 | `solved_count`、`points`、`mixed`、`unknown`；表示本场原始计分口径 |
| `raw_score` | REAL/分或 NULL | 必须与 `maximum_score` 同时填写或同时留空；不得小于 0 或超过满分 |
| `maximum_score` | REAL/分或 NULL | 必须大于 0；`points`、`mixed` 计分时与 `raw_score` 都必填 |
| `debugging_minutes` | INTEGER/分钟或 NULL | 允许为 0；不得超过本场 `duration_minutes` |
| `attempt_number` | INTEGER | 同题组尝试序号，至少为 1；重复尝试不冒充首次见题 |
| `invalid_reason` | TEXT 或 NULL | 非首次见题、查资料、接受帮助、暂停计时或非严格限时时必填；有效样本必须为空 |
| `primary_blocker` | TEXT 或 NULL | 本场主要卡点，例如读题、建模、编码或调试 |
| `notes` | TEXT 或 NULL | 只保存补充上下文，不用于绕过结构化有效性规则 |
| `trace_id` | TEXT | 每次写入必填，并与 `machine_test_added` 审计事件一致 |
| `created_at` | UTC 时间 | 追加时生成；不替代实际测量日期 |

有效性是严格的派生事实：

```text
is_valid = first_exposure
           AND NOT consulted_materials
           AND NOT received_assistance
           AND NOT paused_timer
           AND strict_timed
           AND invalid_reason IS EMPTY
```

因此，独立通过 0 题只要满足上述全部条件，仍是有效低表现；不能因成绩难看而考后删除或宣布无效。非首次见题、查资料、接受帮助、暂停计时或非严格限时的训练同样允许保存，但必须写明 `invalid_reason`，且 `is_valid=0`。有效条件全部成立时又填写 `invalid_reason` 也会被拒绝，不能用自由文本把结构化事实反向改写。所有会话由触发器禁止 UPDATE/DELETE；纠错应追加新会话并在说明中引用旧记录，不能覆盖历史。

计分字段契约如下：

- `raw_score` 与 `maximum_score` 必须成对出现；
- `maximum_score > 0` 且 `0 <= raw_score <= maximum_score`；
- `points` 和 `mixed` 必须提供成对分数；
- `solved_count` 与 `unknown` 可以不提供成对分数；
- 原始分/满分用于保留同一量尺和拆分比较组，不允许跨量尺标准化成一个综合机试分。

`machine-sessions` 用于逐条查询，可按时长、语言、题量筛选，并可只显示有效记录。`machine-assessment` 的职责只有：

- 报告总会话数与有效会话数；
- 对配置要求的 90、120、180 分钟分别返回 `not_measured`、`invalid_only` 或 `valid_measured`；
- 在每个时长内按 `language × problem_count × difficulty_label × scoring_method × maximum_score` 返回 `comparison_groups`；
- 每个比较组只返回本组有效会话数和最近一条有效记录；
- 只有三类核心时长都至少有一条有效记录时，才把顶层 `is_duration_coverage_complete` 标为真。

`is_duration_coverage_complete` 只表示时长覆盖完整，不能缩写回含义模糊的 `is_complete`，更不表示机试稳定、已通过院校硬线或已经完成个人择校。同一时长中只要语言、题量、难度、计分方式或满分量尺不同，就进入不同比较组，组间不得求平均。

90、100、120、180 分钟结果不得平均、相加或插值。100 分钟用于郑州大学计算机与人工智能学院 084-085404/085410 等项目的精确匹配，但不是全局核心完成门槛；若保留这些项目，就必须另做 100 分钟题组，不能用 90 与 120 分钟结果代替。即使时长相同，纯 C/C++、ACM/OJ、理论与编程复合卷、纸笔程序设计以及不同题量/难度也不得自动合并。

一条有效记录只证明该时长已经测过，不证明能力稳定，也不证明通过院校正式硬线。厦门大学 180 分钟首次基线不得升级为“机试稳定”；最终保留其 085404/085405 前至少需要 3 次同协议有效记录，并按正式计分规则另行核对。`decision_snapshots.machine_test_level` 是旧版预留字段，不是当前机试权威来源，不得填入跨时长平均或用来制造录取概率。

## NULL 语义

NULL 表示“没有足够可靠的结构化事实”，不表示 0。特别是推免人数、有效统考名额、中位数、学费和机试淘汰线，缺失时禁止参与精确概率计算。
