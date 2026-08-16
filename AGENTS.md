# ChoseSchool 工程约束

本项目继承用户给出的高可维护性软件工程原则。后续修改还必须遵守以下项目级约束：

1. 依赖方向固定为：`access → business → domain ← ports ← data_access/infrastructure`。
2. `domain` 不得导入 SQLite、命令行、网络或文件系统实现。
3. 原始来源行不可覆盖；清洗、核验和裁决只能追加影子值、证据或审计事件。
4. 旧 CSV 的 `yes/是` 只是 `strict_22408_claim`，不得升级为官方确认。
5. 只有同一项目、同一招生年度的 `101+204+302+408` 正式目录证据，才可标记 `official_confirmed`。
6. 复合数字不得提取首个数字冒充精确事实；必须保留原文并生成质量问题。
7. 所有写操作必须具有 TraceId；用户可见错误不得泄露敏感数据，完整堆栈写入本地结构化日志。
8. 数据库变更必须新增向前迁移；已执行迁移不得修改。
9. 完成修改前运行：

   ```powershell
   $env:PYTHONIOENCODING='utf-8'
   python -m unittest discover -s tests -p "test_*.py" -v
   python manage.py doctor
   ```

10. 新增公共命令、字段或状态时，同步更新 README、数据字典和测试。
