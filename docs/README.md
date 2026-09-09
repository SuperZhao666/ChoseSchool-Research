# 项目维护说明

<!-- TraceId: 8c689b86-5d60-4f2f-96bc-868f6aa1aa83 -->

择校正文完整写在仓库根目录 README.md，本目录只保留维护资料。后续研究直接更新同校项目，不再按提问或日期新建读者报告。

- [架构与依赖方向](architecture.md)
- [数据字典](data-dictionary.md)
- [证据与状态规则](evidence-and-status.md)
- [本地操作](operations.md)
- [追加式证据账本决策](decisions/ADR-001-local-sqlite-and-append-only-evidence.md)

`research/archive/` 保存合并前的历史文档快照，仅供来源追溯和历史事实回归。文件内的“当前”“最新”和推荐顺序均属于原时间点，不是当前择校结论。历史来源不被新结论覆盖；根目录 README.md 是当前可读结论。

## 本地检查

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m unittest discover -s tests -p "test_*.py" -v
python manage.py doctor
```

公开代码用于核验证据，不是录取预测器。数据库、导出工作簿、原始聊天图片、个人成绩与成果、真实配置、个人草稿仍按 `.gitignore` 留在本地。首次使用请从 `config/settings.example.toml` 建立本地配置，勿将真实配置推送。

原始来源、事实主张、清洗、裁决和审计继续分开。计划、建议录取与正式普通录取不能混用；机器事实优先从 `v_current_accepted_fact_evidence` 读取。根目录文档的展示变化没有改变数据库字段、状态、迁移或来源等级。

本公开快照未另行授予代码或文档再许可；学校网页仅作研究引用，受控个人材料不随仓库公开。
