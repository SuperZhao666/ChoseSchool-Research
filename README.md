# ChoseSchool：证据驱动的 2027 计算机考研研究账本

这是一个本地优先、可追溯、追加式的考研择校研究项目。它把招生目录、科目调整公告、录取名单、个人偏好和研究假设分开保存，避免把图片里的推荐分数、宣传规模或历史最低分误包装成 2027 录取概率。

## 本轮图片调查

- [临沂大学信息科学与工程学院2026考研去向图：985/211实证审计](docs/linyi-2026-postgraduate-destination-985-211-audit-2026-08-20.md)：对用户提供的156条拟录取去向做隐私安全聚合，逐项目核对985/211中的学院、代码与初试科目，并区分同源可行性线索、严格22408事实、个人专业边界和不能估计的录取概率。
- [2027 图片线索新一轮官方核查](docs/2027-image-lead-investigation-2026-08-16.md)：逐张登记 `待调查信息/` 中的 34 张图片，并回到官方页面核对北航、北交、北理工、东北林业、西南大学、中科院大学、中石大华东等线索。
- [待调查信息图片索引](docs/待调查信息-图像索引-2026-08-16.md)：只保留文件名和线索摘要；原始图片不进入公开仓库。
- [11408 与 22408 的 985/211 分布实证](docs/11408-vs-22408-school-distribution-2026-08-16.md)：把 `11408`、`21408`、`22408` 分开，统计当前研究语料中的学校覆盖，并解释对 985 主研究和 211 风险对冲的实际影响。

本轮报告使用一个专门的 `official_notice_confirmed` 标签表示“官方公告确认了科目或调整事项”。它不等同于数据库严格的 `official_confirmed`：后者必须同时满足同一项目、同一年度、同一学习方式以及正式目录的 `101+204+302+408` 四码。

## 当前研究原则

1. 图片是检索线索，不是录取证据。
2. `planned`、`received`、`actual` 三个推免阶段不互相替代；“总计划减推免”不自动等于普通统考名额。
3. 推荐分数、平均分、宣传规模和单年最低分不直接生成冲稳保或概率。
4. 目标年正式目录、普通名额、复试合同、公平性审查和个人测量窗口任一缺失，都保持 `research_only`。
5. 原始来源、事实主张、裁决、复核和审计均采用追加式记录；历史结论被纠正时追加影子值，不覆盖原行。

当前画像下的候选研究池可以用只读命令查看：

```powershell
$env:PYTHONIOENCODING='utf-8'
python manage.py candidate-report
python manage.py --json candidate-report --candidate-target-id 10
python manage.py candidate-report --history --details
```

`candidate-report` 只组合候选身份、用户策略分组、画像适配缺口、历史可比性审查和个人测量/成果资产摘要，不写数据库。每条候选都明确带有 `selection_output.scope=research_only` 与 `probability_status=not_estimated`；`985_priority_research`、`211_hedge_research` 和 `non_211_comparator_research` 是用户指定的取证顺序，不是学校客观层级、冲稳保角色或录取概率。默认输出摘要；只有显式 `--details` 才展开规范化 JSON、事件 ID和证据哈希。

## 代码结构

- `src/chose_school/domain/`：领域模型、枚举和证据规则，不依赖 SQLite 或命令行。
- `src/chose_school/business/`：目录、事实、偏好、候选画像适配和择校门禁服务。
- `src/chose_school/data_access/`：SQLite 仓储和只读投影。
- `src/chose_school/infrastructure/migrations/`：001—029 向前迁移；已执行迁移禁止回改。
- `tests/`：单元、集成和 CLI 验收测试。
- `docs/`：公开研究方法、证据边界和官方来源链接。
- `config/settings.example.toml`：不含个人值的配置模板；真实 `config/settings.toml` 只保留在本地。

## 本地数据边界

公开版故意不包含：

- `data/*.sqlite3`、`data/*.db`：本地申请人数据库，可能包含个人偏好、成果和审计记录；
- `outputs/*.(xlsx|xls|csv)`：从本地库导出的工作簿；
- `待调查信息/`：原始聊天图片；
- 个人成果证书、云盘链接、个人测量日历和个人择校草稿。

这些文件仍可在本地工作区使用，并已加入 `.gitignore`；它们不会因为本次公开推送而上传。

首次使用时，请复制 `config/settings.example.toml` 为本地 `config/settings.toml`，再填写自己的画像字段。

## 本地验证

在拥有本地数据库副本的环境中运行：

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m unittest discover -s tests -p "test_*.py" -v
python manage.py doctor
```

当前公开代码的目标是可复核研究基础设施，不是自动录取预测器，也不替代招生单位发布的最终目录、复试办法和拟录取名单。

迁移 029 进一步把“官方建议录取名单行数”与“普通统考最终拟录取人数”分开，
并让普通统考机器事实拒绝 `official_mixed`、规则推导或专项未拆的数据。查询机器事实时优先使用
`v_current_accepted_fact_evidence`，不要直接消费包含 `unresolved` 行的高表。

## 许可证与来源

本公开快照未单独授予代码或文档的再许可；学校官方页面仅作为研究引用入口。原始图片和受控个人材料不随公开仓库再分发。
