# 常州政务官方资料目录

收录日期：2026-11-21。服务地区以江苏省常州市为主。

全库最新对齐已通过实际运行验证：220份公开来源（216政府域名、2官方机构、2保险产品第一方资料）、197条来源核验FAQ，以及15,151条用户原包记录；有效向量共16,176条。原包97文件的字节和哈希不变。业务仍有明确缺项，详见[本次对齐复核](changzhou_alignment_audit_20261121.md)与`changzhou_verification_20261121.json`；下表保留原官网核验轮次的范围统计。

| 项目 | 当前已核验数量（本轮官网核验范围） |
| --- | ---: |
| 常州/江苏适用资料 | 79 |
| 全国通用资料 | 120 |
| 官方资料合计 | 199 |
| 常州地方问答 | 176 |
| 全国适用问答 | 21 |
| 官方资料向量记录（本目录已回读部分） | 515 |
| 规则 | 25（23金额场景、2人工核验入口） |

资料包括正式政策、官方解读、办事指南、官方问答及明确标注的部门新闻和公开答复；“已核验”指来源、正文快照、哈希、引文和导入结果相符，不是对所有文件现行法律效力的统一认证。申请条件、区县范围和年度期限以具体原文及受理机关要求为准。


以上数量仅统计本轮及此前已回读的官方政策资料范围；`changzhou_alignment_*`等另行整理的资料按各自核验和导入报告记录，不混为本轮审查结论。用户原始语料、商业保险正式合同与政府政策的来源性质分别保留，不能统一称为政府正式文件。

## 当前入口

- `changzhou_alignment_audit_20261121.json/md`：原12项完整性缺口逐项对齐，4项已处理、7项部分补齐、1项仍缺，不将隔离旧资料冒充补齐。
- `import_changzhou_corpus_20261121.json`：36份原包解析件、15,151条记录和15,286条向量的原件哈希、实际下载路径及精确回读凭证。
- `changzhou_alignment_welfare_20261121.json`、`changzhou_alignment_insurance_20261121.json`、`changzhou_alignment_quality_20261121.json`：恢复的医保/养老PDF、正式保险条款和新版法规/服务资料，来源身份与年度限制随每段正文保留。

- `changzhou_housing_20261121.json`：10份住房/公积金/人才资料。
- `changzhou_services_20261121.json`：30份医保、就业、教育、救助、养老、企业、税务、户籍证照等资料。
- `national_faq_20261121.json`与`rules_2026_national.json`：3份2026全国计算/问答原文，重复规则来源按URL去重。
- `livelihood_20261121.json`、`employment_business_20261121.json`、`business_expansion_20261121.json`、`social_expansion_20261121.json`：保留112份全国资料。
- `import_changzhou_20261121.json`：108份增量导入资料及516条向量的ID、上传和解析版本，包含本次新增的真实来源。
- `changzhou_insurance_supplement_20261121.json`：8份新增医保、补充保险和退休来源，保障年度与适用说明随资料进入检索。
- `changzhou_financial_accuracy_20261121.json`：2份困难家庭公积金贷款贴息正式办法/解读，新增1条计算和6条FAQ；本轮逐规则校对记录见`docs/plans/changzhou-financial-accuracy-audit-report.md`。
- `changzhou_official_followup_20261121.json`：本轮8份常州政府/主管部门正文及18条问答，含地方自主智能品类、低保/失业金标准、创业就业说明及期限；当前接入和限制见[官网追加核验报告](../../../docs/plans/changzhou-official-followup-report.md)。
- `changzhou_verification_20261121.json`：真实鉴权接口与存储回读结果。
- `changzhou_graph_20261121.json`：新图谱的服务证据来源。
- `RULES_2026.md`：现有25条规则的范围和限制。

## 常州与江苏资料清单

| 主题 | 范围 | 官方资料 |
| --- | --- | --- |
| 公积金装修与物业提取 | 江苏省常州市 | [关于提取住房公积金支付物业费和装修自住住房的通知](https://www.changzhou.gov.cn/gi_news/312178969370166) |
| 公积金提取解读 | 江苏省常州市 | [《关于提取住房公积金支付物业费和装修自住住房的通知》政策解读](https://www.changzhou.gov.cn/ns_news/783178969498604) |
| 装修提取问答 | 江苏省常州市 | [我可以提取住房公积金用于支付装修费吗？有什么条件？可以提取多少钱？](https://gjj.changzhou.gov.cn/html/gjj/2026/MHLFKOQA_1016/14434.html) |
| 公积金贷款 | 江苏省常州市 | [关于调整住房公积金贷款相关规定的通知](https://www.changzhou.gov.cn/gi_news/726176697730432) |
| 公积金贷款解读 | 江苏省常州市 | [《关于调整住房公积金贷款相关规定的通知》政策解读](https://www.changzhou.gov.cn/ns_news/284176697860699) |
| 住房保障准入 | 江苏省常州市市区（市区户籍城镇中低收入家庭） | [关于明确我市市区2026年度城镇中低收入住房困难家庭住房保障申请条件的通知](https://www.changzhou.gov.cn/gi_news/596178123411574) |
| 青年人才与科创支持 | 江苏省常州市 | [中共常州市委科技委员会关于印发《关于推进高能级创新型城市建设的若干措施》的通知](https://www.changzhou.gov.cn/gi_news/575178824994368) |
| 住房困难工薪群体购房资助 | 江苏省常州市 | [进一步资助住房困难工薪群体购买商品住房公告](https://www.zhonglou.gov.cn/html/czzl/2025/NLLKPQAP_1208/385650.html) |
| 公积金缴存提取贷款 | 江苏省常州市 | [关于印发《常州市住房公积金缴存管理实施细则》《常州市住房公积金提取管理实施细则》《常州市住房公积金个人住房贷款管理实施细则》的通知](https://www.changzhou.gov.cn/gi_news/472177500750450) |
| 2026人才政策解读 | 江苏省常州市 | [全力建设新时代人才强市 助力打造长三角创新高地暨“龙城英才计划”2026升级版政策解读新闻发布会实录](https://www.changzhou.gov.cn/ns_news/973177967360695) |
| 异地就医 | 江苏省常州市 | [关于进一步明确异地就医备案有关事项的通知](https://www.changzhou.gov.cn/gi_news/593173684258383) |
| 婚姻登记与结婚落户 | 江苏省常州市 | [常州市婚姻政策宣传在线访谈实录（2026-06-18）](https://www.changzhou.gov.cn/talk/message_detail.php?sort=asc&theme_id=1926) |
| 户籍证照与出入境 | 江苏省常州市 | [答“移”解问｜未成年人与成年人出入境证件办理有区别吗？](https://wsb.changzhou.gov.cn/html/wsb/2026/MDIAJFOO_0202/8652.html) |
| 居民医保参保 | 江苏省常州市 | [居民医疗保险 守护全民健康——2026年度居民医保政策在线访谈实录](https://www.changzhou.gov.cn/talk/message_detail.php?sort=asc&theme_id=1894) |
| 企业信用与年报 | 江苏省常州市 | [深化信用监管赋能，优化一流营商环境——在线访谈实录](https://www.changzhou.gov.cn/talk/message_detail.php?sort=asc&theme_id=784178892131645) |
| 企业开办与税务 | 江苏省常州市武进区 | [2026年度部分税费优惠政策答疑——武进区在线访谈实录](https://www.changzhou.gov.cn/talk/message_detail.php?sort=asc&theme_id=216178885717150) |
| 教育与校外托管 | 江苏省常州市 | [《常州市加强校外托管机构管理工作指导意见》解读——在线访谈实录](https://www.changzhou.gov.cn/talk/message_detail.php?sort=asc&theme_id=551175099936145) |
| 劳动权益与工资支付 | 江苏省常州市 | [《常州市建筑工人实名制管理和工资支付保障实施办法》解读——在线访谈实录](https://www.changzhou.gov.cn/talk/message_detail.php?sort=asc&theme_id=555177016970028) |
| 养老服务 | 江苏省常州市常州经济开发区 | [常州经开区养老服务消费券补贴政策——在线访谈实录](https://www.changzhou.gov.cn/talk/message_detail.php?sort=asc&theme_id=165178217522533) |
| 生育保险 | 江苏省常州市 | [生育津贴怎么申领？流程复杂吗？需要跑腿吗？](https://ybj.changzhou.gov.cn/html/ybj/2026/MQMMQQAF_0701/5956.html) |
| 生育保险 | 江苏省常州市 | [产前检查费用怎么报销？需要自己跑腿去办吗？](https://ybj.changzhou.gov.cn/html/ybj/2026/MQMMQQAF_0701/5954.html) |
| 门诊慢性病 | 江苏省常州市 | [恶性肿瘤可以申请门诊慢性病吗？请问如何申请？](https://ybj.changzhou.gov.cn/html/ybj/2026/MQMMQQAF_0622/5946.html) |
| 法律援助 | 江苏省常州市 | [市司法局关于印发《常州市法律援助市域通办工作实施方案（试行）》的通知](https://www.changzhou.gov.cn/gi_news/871175315395926) |
| 就业创业 | 江苏省 | [关于做好一次性求职补贴发放工作的通知](https://jshrss.jiangsu.gov.cn/art/2026/8/26/art_77276_11820813.html) |
| 社会救助 | 江苏省常州市 | [关于2026年常州市非本地户籍人员“临时救助+慈善救助”联动救助项目常见问题的热点回应](https://www.changzhou.gov.cn/ns_news/484176820188105) |
| 社会救助 | 江苏省常州市 | [关于进一步完善临时救助工作的实施意见](https://www.changzhou.gov.cn/gi_news/680165335487487) |
| 长期护理保险 | 江苏省常州市 | [申请常州长期护理保险流程是怎样的？](https://ybj.changzhou.gov.cn/html/ybj/2026/MQMMQQAF_0615/5936.html) |
| 医保家庭共济 | 江苏省常州市 | [如何办理家庭共济？和哪些亲属家人可以办理绑定？](https://ybj.changzhou.gov.cn/html/ybj/2026/MQMMQQAF_0609/5930.html) |
| 长期护理保险 | 江苏省常州市 | [长期护理保险评估通过后，申请待遇需要准备哪些材料？](https://ybj.changzhou.gov.cn/html/ybj/2026/MQMMQQAF_0302/5808.html) |
| 育儿生育与健康服务 | 江苏省常州市天宁区 | [从婚孕保健到老年照护，推动健康服务覆盖全生命周期——天宁区在线访谈实录](https://www.changzhou.gov.cn/talk/message_detail.php?sort=asc&theme_id=578179203137313) |
| 社会保障卡 | 江苏省 | [江苏省社会保障卡服务指南](https://jshrss.jiangsu.gov.cn/col/col74430/index.html) |
| 户籍证照与公共服务 | 江苏省 | [省内户籍居民首次申领身份证需要哪些材料？](https://gat.jiangsu.gov.cn/art/2025/6/11/art_90830_6907.html) |
| 户籍证照与公共服务 | 江苏省 | [外省户籍的居民，在本市首次申领身份证需要哪些材料？](https://gat.jiangsu.gov.cn/art/2025/6/11/art_90830_6911.html) |
| 户籍证照与公共服务 | 江苏省 | [哪些情形下公民申请变更姓名时，公安机关不予受理？](https://gat.jiangsu.gov.cn/art/2025/2/18/art_90830_6721.html) |
| 户籍证照与公共服务 | 江苏省 | [单位怎么申请开具“无犯罪记录证明”？](https://gat.jiangsu.gov.cn/art/2025/1/21/art_90830_6672.html) |
| 户籍证照与公共服务 | 江苏省 | [需要上报到县级以上公安机关审批（审核）的户口登记多长时间完成？](https://gat.jiangsu.gov.cn/art/2025/2/18/art_90830_6722.html) |
| 户籍证照与公共服务 | 江苏省 | [哪类情形可以由公安派出所出具证明？](https://gat.jiangsu.gov.cn/art/2025/2/18/art_90830_6715.html) |
| 户籍证照与公共服务 | 江苏省 | [线下申请查询无犯罪记录需要哪些材料？](https://gat.jiangsu.gov.cn/art/2025/1/9/art_90830_6659.html) |
| 户籍证照与公共服务 | 江苏省 | [申请人有哪些情形之一的，护照签发机关不予签发护照？](https://gat.jiangsu.gov.cn/art/2025/4/17/art_90830_6844.html) |
| 户籍证照与公共服务 | 江苏省 | [新规定实施后，新车上牌流程有何变化？](https://gat.jiangsu.gov.cn/art/2026/8/31/art_90830_7271.html) |

## 常州事项补充资料

MimirQ 公开仓库中的常州事项资料已保存到 `resources/data/raw/mimirq_changzhou_20261121/`。其中[事项字段片段](../raw/mimirq_changzhou_20261121/常州市事项_59条字段片段.json)包含 59 个事项、246 个字段，覆盖常州市本级与 7 个区市；[源文件](../raw/mimirq_changzhou_20261121/human_mixed_eval_cases.original.json)保留 100 条评测用例及原始证据。来源提交、文件哈希与检索范围见同目录的 `manifest.json` 和 `README.md`。

这批资料属于公开语料证据摘录，部分字段被上游截取到 120 字符；“高效办成一件事”的另 9 条记录仅保留名称与标签。数量单独列示，不计入上文 199 份已核官方资料或 197 条 FAQ；下载归档不代表已导入运行中的检索库。

用户随后提供的六类原始资料已另行保存到 `resources/data/raw/changzhou_user_corpus_20261121/`，共 97 个原文件、27,552,904 字节，与桌面来源逐文件 SHA-256 一致。包含公积金七份 Excel（贷款、缴存、提取、线上业务、其他业务、服务网点、工作站），以及医保、不动产、12345、专题问答等资料；公积金表格已逐表读取并确认有正文。文件清单、核验结果和来源见[原始资料归档说明](../raw/changzhou_user_corpus_20261121/README.md)。

这份资料包已完成97文件哈希核对、逐条解析和检索接入：15,151条准许检索记录生成15,286段，36份解析件均经Strong回读与真实下载校验。已知经开区事项文件与常州市事项文件内容重复，“汽车置换补贴常见问题.txt”为空；重复、空答案、过期金额和原包法规按独立清单隔离，原件保持不变。具体凭证见`import_changzhou_corpus_20261121.json`，不能据接入数量宣称全市业务完整。

## 购房、医保社保和补充保险核查

既有住房、公积金和医保社保相关资料按 URL 合并后，58 项均有原始快照与正文文件。用户原包提供的七份公积金 Excel 也已归档核对；原包部分医保和退休问答含旧年度文字，需要保留日期后使用。

本轮针对“补充医保、60岁”等提问，新增[8 个官方网页来源](changzhou_insurance_supplement_20261121.json)，包括 2026/2027 年度江苏医惠保、常州职工医保最低缴费年限、灵活就业医保年龄范围、断缴等待期和延迟退休公开答复。不同险种与保障年度分别保存，详细范围及未取得正文的 PDF 见[核查说明](../raw/changzhou_insurance_supplement_20261121/README.md)。该批资料已导入并通过存储回读和4组[实际接口检索](changzhou_insurance_verification_20261121.json)，已计入上方数量。

## 数据迁移与使用限制

错误地区资料已迁出活跃检索和规则目录；恢复快照位于`resources/archive/pre_changzhou_20261121/`，不能将该目录作为导入源。全国原文即使由外地官网转载，也按正文权限和适用范围保留，不按网站地名误删。

最新实际界面共257份文件：220份公开来源、36份用户原包解析件及1份既有用户数学文档；全库16,176条有效向量。197条FAQ均有完整来源映射，直答只忽略两端空白、大小写和结尾问号/句号；条件改写交给正式检索。

常州官网部分页面正常直连返回403，按清单保留经网页工具正常读取的原始逐行JSON快照，明确标注格式；未伪称原始HTML。

图谱使用新的`resources/data/lightrag_changzhou_20261121`目录，包含10份完整住房资料及30份服务资料的已核原文摘录。图谱中的实体和关系由模型提取，应结合正文复核。

SQL问答种子已切换为官方资料。当前运行MySQL库仅有聊天/连接表，未配置政策库连接，未新建政策表或宣称Text2SQL已完成导入。

本地原重排服务凭据不可用，已设置`LIGHTRAG_RERANK_ENABLED=false`，图谱使用正常召回顺序；配置有效重排服务后可重新开启。

## 金额规则扩充

新增15条规则及26份不同URL的官方资料，金额目录见`FINANCIAL_RULES_20261121.md`。当前FAQ共173条；原地方/全国问答128/18条是上次迁移计数，新增问答27条。
