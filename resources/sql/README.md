# 常州官方政策 SQL 种子

旧地区及随机金额的演示 SQL 已归档到 `resources/archive/pre_changzhou_20261121/`。

现有导出位于 `resources/database/seed_data/policy_qa_初始数据.json`，每条问答均保留官方 URL、原文引文、地区、正文哈希和路径。重新导出使用 `python -X utf8 -m resources.database.seed_data.generate_qa_data`。

显式向已配置的政策数据库导入时，使用 `python -X utf8 -m scripts.seed_mysql_text2sql --skip-schema`。此命令只读取已核验官方目录，不再生成随机政策、补贴数字或资格；按来源稳定ID、问答和表提示去重，失败时回滚。当前运行库仅供聊天持久化，未配置政策库连接，本次未执行建表或 SQL 种子写入。
