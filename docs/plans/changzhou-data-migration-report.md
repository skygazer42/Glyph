# 常州政务数据迁移与扩充

日期：2026-11-21。目标地区：江苏省常州市。

## 已生效的资料

| 项目 | 数量 |
| --- | ---: |
| 常州/江苏适用官方资料 | 40 |
| 全国通用官方资料 | 115 |
| 官方资料合计 | 155 |
| 地方问答 / 全国2026问答 | 128 / 18 |
| 有效向量 | 464 |
| 活跃规则（常州 / 全国） | 4 / 4 |
| 知识库可见文件 | 156（另保留1份用户数学文档） |
| 新图谱实体 / 关系 | 911 / 679 |

服务资料覆盖医保、生育、异地就医、劳动工资、求职、救助、养老、婚姻、教育、企业信用、税费、公安证照及电动自行车登记等。住房资料另含公积金、住房保障、购房资助和人才原文。每份资料保留官方URL、地区、资料类型、日期、原始快照及正文哈希；每条FAQ有逐字引文和来源映射。

新图谱包含10份完整住房资料和30份服务资料的已核原文摘录，共11个已完成处理的图谱输入文档。服务摘录汇成一个保留来源边界的文档，不将其声称为30份全文图谱。模型提取的实体和关系仍需与正文交叉核对。

## 退休与简化

- 将28份错误地方目录资料、原始济南/山东资料及衍生上传/解析/嵌入状态归档，精准删除对应109条向量；374条保留全国向量连同每个浮点坐标均回读不变。
- 将16个历史或错误地区YAML迁出活跃规则目录，删除济南计算函数，按常州官方条件新增装修、物业、新房、存量房4条规则。未把其他城市的参数改名套用。
- 归档10条旧FAQ、无来源DSL演示材料和3个演示用户画像。用户聊天和无关上传保留。
- 清理采集过程中的过时问答和改题名前的上传副本，避免临时材料残留；中间版本和对应向量另有恢复快照。
- 删除随机政策/金额/资格生成逻辑，SQL种子、问答导出及向量导入共用核验目录。已存在来源的新增FAQ可补写，重复运行不再重复表提示。
- FAQ直答只接受文字条件一致的已核问题；不再用字符相似度判断资格，解决“有/没有贷款”“在/不在产权证上”的反义误答。
- 默认地区、推荐问题、实体提取和地区别名补齐常州/江苏及辖区。图谱页面、统计与子图接口统一使用当前工作目录。

## 主要改动文件

- 数据：`resources/data/{raw,process}/changzhou_20261121/`、`resources/data/policy_catalog/`、`resources/faq/`、`resources/data/graph_seed/`、`resources/data/lightrag_changzhou_20261121/`、`resources/data/guize/`、`uploads/`。
- 规则：`rules/Rule_Changzhou_*_2026.yaml`、`app/agents/dsl_generator/{housing_calculations,rule_engine}.py`。
- 问答与地区：`app/knowledge/{faq_responder,document_loader}.py`、`app/agents/{chatdb/domain_zh_gov,domain/policy_domain}.py`，以及相应默认提示/识别入口；前端仅调整`web/src/views/AgentChat.vue`的两处地区示例。
- 图谱：`app/api/endpoints/knowledge_graph.py`、`app/agents/packs/graph_retriever/node.py`、`app/agents/service/agent_service.py`、`app/config/app_config.py`、`scripts/seed_lightrag.py`。
- 导入与种子：`scripts/official_policy_data.py`、`scripts/import_changzhou_policies.py`、`scripts/import_data.py`、`scripts/seed_mysql_text2sql.py`、`resources/database/seed_data/`。快照、精确退休、图谱构建及验证脚本同在`scripts/`，不自动提交或执行数据库结构迁移。
- 回归：常州规则/迁移/种子/图谱测试，以及原有跨层、导入和图谱夹具。

## 已执行的验证

- 核心相关回归537项通过；FAQ/导入/MySQL种子既有回归另20项通过。日志：`docs/plans/changzhou-pytest.log`、`changzhou-seed-faq-regressions.log`。
- 相关Python Ruff检查通过；9个源码文件mypy检查通过，记录于`docs/plans/changzhou-mypy.log`。前端生产构建通过，保留既有大体积chunk提示。
- 真实鉴权接口：8条保存规则与草稿结果一致；155份官方上传状态核验；3组知识检索、4个FAQ聊天及新图谱统计通过。
- 向量全集ID与接受目录完全相符，退休ID不存在，原全国向量未改；146条FAQ全部能匹配原问题并返回可核证据。
- 图谱真实检索上下文包含常州及物业费3000元条款，不含旧济南/泉城内容。旧重排凭据返回401，本地配置已关闭可选图谱重排；未替换或泄露任何凭据。

结构化证据：`resources/data/policy_catalog/changzhou_verification_20261121.json`、`changzhou_graph_20261121.json`、`changzhou_graph_query_20261121.json`。服务来源自身校验位于`resources/data/process/changzhou_20261121/services/verification.json`。

## 边界与保留风险

当前运行MySQL库仅有聊天/连接表，没有政策表和政策库连接；本次完成SQL种子替换与离线事务/幂等验证，未宣称Text2SQL已入库，也未执行建表或清库。历史数据库的旧凭据不能通过认证，不能据此声称历史服务端内容已迁移。

部分官方网页直连403，保存的是正常网页工具读取的原始逐行JSON快照，清单明确格式，未伪称原始HTML。核验范围是来源、正文及导入一致性，不是对全部文件现行效力或个人申请资格的保证。区县、日期、家庭条件、历史次数等以具体官方原文为准；购房资助为抵扣购房款，不能描述成普遍现金补贴。

未将整仓历史前端夹具或无关Milvus空凭据测试声称为全绿；已有SVG检查器解析覆盖问题不属于本次数据迁移。此前其他代码改动及用户聊天历史保持。

## 恢复材料

`resources/archive/pre_changzhou_20261121/`包含原483条向量全字段和嵌入、文件SHA-256清单、精确退休计划、原文件、目录副本及中间导入恢复证据。归档位于所有默认索引源目录之外；不得把归档目录整体重新导入当前常州业务。
