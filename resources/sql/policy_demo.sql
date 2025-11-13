PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS coupon_rules;
CREATE TABLE coupon_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    coupon_type TEXT NOT NULL,
    min_spend REAL NOT NULL,
    discount REAL NOT NULL,
    start_date TEXT,
    end_date TEXT,
    per_person_limit INTEGER,
    notes TEXT
);

INSERT INTO coupon_rules (city, coupon_type, min_spend, discount, start_date, end_date, per_person_limit, notes) VALUES
('济南', 'retail', 100, 20, '2025-02-01', '2025-04-30', 3, '泉城购零售券，单用户最多3张'),
('济南', 'retail', 200, 40, '2025-02-01', '2025-04-30', 3, '泉城购零售券，限指定商圈'),
('济南', 'retail', 300, 60, '2025-02-01', '2025-04-30', 3, '泉城购零售券，线下扫码核销'),
('济南', 'dining', 100, 25, '2025-02-01', '2025-04-30', 3, '泉城购餐饮券，可与商家折扣同享'),
('济南', 'dining', 200, 50, '2025-02-01', '2025-04-30', 3, '泉城购餐饮券，先到先得'),
('济南', 'dining', 300, 75, '2025-02-01', '2025-04-30', 3, '泉城购餐饮券，适用于线下核销'),
('青岛', 'retail', 0, 8224, '2025-11-09', '2026-03-07', 1, '青岛购新补贴：消费0-11万元档'),
('青岛', 'retail', 110000, 7850, '2025-11-09', '2026-03-07', 1, '青岛购新补贴：消费11-22万元档'),
('青岛', 'retail', 220000, 19701, '2025-11-09', '2026-03-07', 1, '青岛购新补贴：消费22-28万元档'),
('青岛', 'retail', 280000, 18304, '2025-11-09', '2026-03-07', 1, '青岛购新补贴：消费28万元以上档');

DROP TABLE IF EXISTS auto_subsidy_windows;
CREATE TABLE auto_subsidy_windows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    window_type TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    budget_million REAL,
    notes TEXT
);

INSERT INTO auto_subsidy_windows (city, window_type, start_time, end_time, budget_million, notes) VALUES
('济南', 'purchase', '2025-01-25 00:00', '2025-03-31 24:00', 3000, '机动车销售统一发票时间为准，先到先得'),
('济南', 'application', '2025-02-12 10:00', '2025-04-15 24:00', 3000, '在线申报窗口'),
('济南', 'modification', '2025-02-12 10:00', '2025-04-30 24:00', 3000, '资料修改截止时间');

DROP TABLE IF EXISTS auto_subsidy_tiers;
CREATE TABLE auto_subsidy_tiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    campaign_round TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    price_min REAL,
    price_max REAL,
    benefit_type TEXT NOT NULL,
    benefit_amount REAL NOT NULL,
    description TEXT
);

INSERT INTO auto_subsidy_tiers (city, campaign_round, vehicle_type, price_min, price_max, benefit_type, benefit_amount, description) VALUES
('济南', '2025春季首轮', '新能源', 100000, 300000, 'cash', 4000, '新能源乘用车，价格为不含税发票金额'),
('济南', '2025春季首轮', '新能源', 300000, NULL, 'cash', 5000, '新能源乘用车，30万元及以上档'),
('济南', '2025春季首轮', '燃油', 100000, 300000, 'cash', 3000, '燃油车 10-30 万档'),
('济南', '2025春季首轮', '燃油', 300000, NULL, 'cash', 4000, '燃油车 30 万及以上档'),
('济南', '2025下半年第一轮', '新能源', 0, 100000, 'gift_package', 1900, '礼包：1000元加油储值卡+800元保险补贴'),
('济南', '2025下半年第一轮', '新能源', 100000, 150000, 'gift_package', 3200, '礼包：2200元加油储值卡+1000元保险补贴'),
('济南', '2025下半年第一轮', '新能源', 150000, 250000, 'gift_package', 4800, '礼包：3300元加油储值卡+1500元保险补贴'),
('济南', '2025下半年第一轮', '新能源', 250000, 400000, 'gift_package', 6400, '礼包：4400元加油储值卡+2000元保险补贴'),
('济南', '2025下半年第一轮', '新能源', 400000, NULL, 'gift_package', 8500, '礼包：5500元加油储值卡+3000元保险补贴');

DROP TABLE IF EXISTS insurance_subsidy_rules;
CREATE TABLE insurance_subsidy_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    min_premium REAL NOT NULL,
    max_premium REAL,
    subsidy_amount REAL NOT NULL,
    notes TEXT
);

INSERT INTO insurance_subsidy_rules (city, min_premium, max_premium, subsidy_amount, notes) VALUES
('济南', 2000, 3000, 800, '新车首保补充公告新增档'),
('济南', 3000, 4000, 1000, '首保消费券原始档位'),
('济南', 4000, 6000, 1500, '首保消费券原始档位'),
('济南', 6000, 8000, 2000, '首保消费券原始档位'),
('济南', 8000, NULL, 3000, '首保消费券最高档');

DROP TABLE IF EXISTS appliance_subsidy_rules;
CREATE TABLE appliance_subsidy_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    category TEXT NOT NULL,
    energy_level TEXT NOT NULL,
    subsidy_rate REAL NOT NULL,
    per_item_cap REAL NOT NULL,
    per_person_limit INTEGER,
    notes TEXT
);

INSERT INTO appliance_subsidy_rules (city, category, energy_level, subsidy_rate, per_item_cap, per_person_limit, notes) VALUES
('济南', '空调', '一级', 0.20, 2000, 3, '家电消费补贴实施方案'),
('济南', '空调', '二级', 0.15, 2000, 3, '家电消费补贴实施方案'),
('济南', '冰箱', '一级', 0.20, 2000, 2, '一级能效家电补贴20%'),
('济南', '冰箱', '二级', 0.15, 2000, 2, '二级能效家电补贴15%'),
('济南', '其他家电', '一级', 0.20, 2000, 1, '其他类别单品限购1件'),
('济南', '其他家电', '二级', 0.15, 2000, 1, '按方案限购');

DROP TABLE IF EXISTS appliance_category_limits;
CREATE TABLE appliance_category_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    per_person_limit INTEGER NOT NULL,
    notes TEXT
);

INSERT INTO appliance_category_limits (category, per_person_limit, notes) VALUES
('空调', 3, '方案明确每人限购3台'),
('冰箱', 2, '每人限购2台'),
('其他家电', 1, '同类别限购1台');

DROP TABLE IF EXISTS household_trade_in_notes;
CREATE TABLE household_trade_in_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    measure TEXT NOT NULL,
    detail TEXT NOT NULL
);

INSERT INTO household_trade_in_notes (city, measure, detail) VALUES
('济南', '购车补贴追加', '首批3000万元补贴额度用完后追加3000万元，规则不变'),
('济南', '新车首保补贴', '商业险金额2000-3000元档新增800元补贴'),
('济南', '多轮活动', '2025年下半年分三轮发放汽车消费礼包，每轮额度1200万元');

-- ==================== 政策流程与 Agent 参考数据 ====================
DROP TABLE IF EXISTS policy_documents;
CREATE TABLE policy_documents (
    doc_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    region TEXT NOT NULL,
    publish_date TEXT,
    issuing_agency TEXT,
    target_group TEXT,
    summary TEXT,
    source_path TEXT
);

INSERT INTO policy_documents (doc_id, title, category, region, publish_date, issuing_agency, target_group, summary, source_path) VALUES
('JINAN_APPLIANCE_2025', '济南市2025年家电以旧换新补贴实施细则', '家电以旧换新', '济南', '2025-01-20', '济南市商务局等4部门', '个人消费者、参与销售企业', '12类家电参与，2级能效补贴15%，1级加成至20%，单件封顶2000元，空调按品类最多补贴3件。', 'resources/data/process/md2025年家电和数码以旧换新政策文件/关于印发济南市2025年家电以旧换新补贴实施细则的通知/关于印发济南市2025年家电以旧换新补贴实施细则的通知1_251103_104024.md'),
('JINAN_DIGITAL_2025', '济南市2025年手机、平板、智能手表购新补贴实施细则', '数码购新补贴', '济南', '2025-01-20', '济南市商务局等5部门', '个人消费者', '手机、平板、智能手表（手环）单价不超过6000元，补贴最终销售价的15%，单件封顶500元，每类限补1件。', 'resources/data/process/md2025年家电和数码以旧换新政策文件/关于印发《济南市2025年手机、平板、智能手表（手环）购新补贴实施细则》的通知(1)/关于印发济南市2025年手机平板智能手表手环购新补贴实施细则的通知1_251103_110749.md'),
('JINAN_AUTO_ROUND1_2025', '2025年政府汽车消费补贴活动公告', '汽车消费补贴', '济南', '2025-01-25', '济南市商务局', '在济购置非营运乘用车的个人', '预算3000万元，新能源车10-30万补4000元，30万及以上补5000元；燃油车10-30万补3000元，30万及以上补4000元。', 'resources/data/process/md市级消费活动政策/2025年政府汽车消费补贴活动公告/2025年政府汽车消费补贴活动公告_251103_131308.md'),
('JINAN_AUTO_GIFT_2025', '济南市2025年下半年第一轮汽车消费补贴活动公告', '汽车消费礼包', '济南', '2025-07-01', '济南市商务局', '购置非营运乘用车的个人及企业', '额度1200万元，按照10万元以下至40万元以上共5档发放“加油储值卡+商业保险补贴”礼包，个人限购1辆，企业限购3辆。', 'resources/data/process/md市级消费活动政策/济南市2025年下半年汽车消费补贴活动第一轮公告/济南市2025年下半年汽车消费补贴活动第一轮公告_251103_132615.md'),
('JINAN_COUPON_2025', '2025年济南市“泉城购”零售、餐饮消费券发放活动公告', '消费券发放', '济南', '2025-07-19', '济南市商务局', '定位在济南的实名用户', '活动从7月19日至11月15日，分5轮14批次在抖音APP发放零售/餐饮消费券，面额为满100减20等组合。', 'resources/data/process/md市级消费活动政策/2025年济南市“泉城购”零售、餐饮消费券发放活动公告/2025年济南市泉城购零售餐饮消费券发放活动公告_251103_131155.md'),
('JINAN_INSURANCE_2025', '济南市2025年新车首保消费券活动公告', '新车首保补贴', '济南', '2025-05-01', '济南市商务局', '首次购置并投保商业险的个人消费者', '总额度3000万元，按商业险金额分4档发放1000-3000元补贴，申报需上传发票、保单和登记证。', 'resources/data/process/md市级消费活动政策/济南市2025年新车首保消费券活动公告/济南市2025年新车首保消费券活动公告_251103_131722.md');

DROP TABLE IF EXISTS policy_benefit_rules;
CREATE TABLE policy_benefit_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL,
    benefit_item TEXT NOT NULL,
    criteria TEXT,
    price_floor REAL,
    price_ceiling REAL,
    subsidy_rate REAL,
    subsidy_cap REAL,
    flat_amount REAL,
    per_person_limit INTEGER,
    notes TEXT,
    FOREIGN KEY (doc_id) REFERENCES policy_documents(doc_id)
);

INSERT INTO policy_benefit_rules (doc_id, benefit_item, criteria, price_floor, price_ceiling, subsidy_rate, subsidy_cap, flat_amount, per_person_limit, notes) VALUES
('JINAN_APPLIANCE_2025', '空调', '一级能效或水效', NULL, NULL, 0.20, 2000, NULL, 3, '一级在15%基础上额外奖励5%，按最终销售价计算'),
('JINAN_APPLIANCE_2025', '空调', '二级能效或水效', NULL, NULL, 0.15, 2000, NULL, 3, '二级按15%补贴'),
('JINAN_APPLIANCE_2025', '冰箱/洗衣机/电视等', '一级能效或水效', NULL, NULL, 0.20, 2000, NULL, 1, '每类单品可补1件'),
('JINAN_APPLIANCE_2025', '冰箱/洗衣机/电视等', '二级能效或水效', NULL, NULL, 0.15, 2000, NULL, 1, '单件封顶2000元'),
('JINAN_DIGITAL_2025', '手机/平板/智能手表(手环)', '单件≤6000元且完成实名认证', NULL, 6000, 0.15, 500, NULL, 1, '每类产品每人限补1件，通过“泉城购”平台核销'),
('JINAN_AUTO_ROUND1_2025', '新能源乘用车', '开票价10万≤price<30万', 100000, 300000, NULL, NULL, 4000, 1, '发票金额以不含税价为准'),
('JINAN_AUTO_ROUND1_2025', '新能源乘用车', '开票价≥30万', 300000, NULL, NULL, NULL, 5000, 1, '新能源车辆含纯电/插混/燃料电池'),
('JINAN_AUTO_ROUND1_2025', '燃油乘用车', '开票价10万≤price<30万', 100000, 300000, NULL, NULL, 3000, 1, '仅限非营运乘用车'),
('JINAN_AUTO_ROUND1_2025', '燃油乘用车', '开票价≥30万', 300000, NULL, NULL, NULL, 4000, 1, '同一身份证限申领一次'),
('JINAN_AUTO_GIFT_2025', '汽车消费礼包', '开票价<10万', 0, 100000, NULL, NULL, 1900, 1, '礼包=1000元加油储值卡+800元保险补贴'),
('JINAN_AUTO_GIFT_2025', '汽车消费礼包', '10万≤price<15万', 100000, 150000, NULL, NULL, 3200, 1, '礼包=2000元加油卡+1000元保险补贴'),
('JINAN_AUTO_GIFT_2025', '汽车消费礼包', '15万≤price<25万', 150000, 250000, NULL, NULL, 4800, 1, '礼包=3000元加油卡+1500元保险补贴'),
('JINAN_AUTO_GIFT_2025', '汽车消费礼包', '25万≤price<40万', 250000, 400000, NULL, NULL, 6400, 1, '礼包=4000元加油卡+2000元保险补贴'),
('JINAN_AUTO_GIFT_2025', '汽车消费礼包', 'price≥40万', 400000, NULL, NULL, NULL, 8500, 1, '礼包=5000元加油卡+3000元保险补贴'),
('JINAN_INSURANCE_2025', '首保消费券', '商业险金额3000-4000元', 3000, 4000, NULL, NULL, 1000, 1, '申报时间2025-05-12至07-15'),
('JINAN_INSURANCE_2025', '首保消费券', '商业险金额4000-6000元', 4000, 6000, NULL, NULL, 1500, 1, '资料修改截止至2025-07-30'),
('JINAN_INSURANCE_2025', '首保消费券', '商业险金额6000-8000元', 6000, 8000, NULL, NULL, 2000, 1, '须上传行驶证及登记证'),
('JINAN_INSURANCE_2025', '首保消费券', '商业险金额≥8000元', 8000, NULL, NULL, NULL, 3000, 1, '同一申报人限一次'),
('JINAN_COUPON_2025', '零售消费券', '满100减20', 100, NULL, NULL, NULL, 20, 1, '抖音APP抢券，24小时内有效'),
('JINAN_COUPON_2025', '零售消费券', '满200减40', 200, NULL, NULL, NULL, 40, 1, '单笔订单限用1张'),
('JINAN_COUPON_2025', '零售消费券', '满300减60', 300, NULL, NULL, NULL, 60, 1, '适用线下零售/商超'),
('JINAN_COUPON_2025', '餐饮消费券', '满100减25', 100, NULL, NULL, NULL, 25, 1, '餐饮门店/酒店餐厅通用'),
('JINAN_COUPON_2025', '餐饮消费券', '满200减50', 200, NULL, NULL, NULL, 50, 1, '可与商家活动叠加'),
('JINAN_COUPON_2025', '餐饮消费券', '满300减75', 300, NULL, NULL, NULL, 75, 1, '超过有效期不补发');

DROP TABLE IF EXISTS policy_timelines;
CREATE TABLE policy_timelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    notes TEXT,
    FOREIGN KEY (doc_id) REFERENCES policy_documents(doc_id)
);

INSERT INTO policy_timelines (doc_id, phase, start_time, end_time, notes) VALUES
('JINAN_APPLIANCE_2025', '实施期', '2025-01-20 00:00', '2025-12-31 23:59', '细则印发即执行，按库存动态调整目录'),
('JINAN_DIGITAL_2025', '补贴启动', '2025-01-20 00:00', NULL, '三类数码产品目录动态调整'),
('JINAN_AUTO_ROUND1_2025', '购车开票', '2025-01-25 00:00', '2025-03-31 24:00', '额度3000万元，先到先得'),
('JINAN_AUTO_ROUND1_2025', '补贴申报', '2025-02-12 10:00', '2025-04-15 24:00', '申报通过后统一公示发放'),
('JINAN_AUTO_ROUND1_2025', '资料修改', '2025-02-12 10:00', '2025-04-30 24:00', '逾期未修改视为自动放弃'),
('JINAN_AUTO_GIFT_2025', '购车开票', '2025-07-01 00:00', '2025-07-31 24:00', '第一轮额度1200万元'),
('JINAN_AUTO_GIFT_2025', '资料申报', '2025-07-10 10:00', '2025-08-05 24:00', '个人限1辆、企业限3辆'),
('JINAN_INSURANCE_2025', '活动期', '2025-05-01 00:00', '2025-06-30 24:00', '需同步购车与购买商业险'),
('JINAN_INSURANCE_2025', '补贴申报', '2025-05-12 10:00', '2025-07-15 24:00', '提交资料后可在线查看进度'),
('JINAN_INSURANCE_2025', '资料修改截止', NULL, '2025-07-30 24:00', '逾期未补正的不予受理'),
('JINAN_COUPON_2025', '总活动期', '2025-07-19 10:00', '2025-11-15 23:59', '5轮14批，抖音APP发放'),
('JINAN_COUPON_2025', '第一轮批次1', '2025-07-19 10:00', '2025-07-27 23:59', '零售+餐饮各可领1张'),
('JINAN_COUPON_2025', '第二轮批次3', '2025-08-18 10:00', '2025-08-31 23:59', '批次示例，超期不补发');

DROP TABLE IF EXISTS policy_execution_roles;
CREATE TABLE policy_execution_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL,
    role_name TEXT NOT NULL,
    responsibilities TEXT NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES policy_documents(doc_id)
);

INSERT INTO policy_execution_roles (doc_id, role_name, responsibilities) VALUES
('JINAN_APPLIANCE_2025', '泉城购服务平台', '负责补贴资格领取、核销、回收预约及客服保障'),
('JINAN_APPLIANCE_2025', '参与销售企业', '自愿报名、垫付补贴、上传销售信息接受全流程监管'),
('JINAN_APPLIANCE_2025', '第三方审核机构', '滚动审核交易链条并出具兑付报告'),
('JINAN_DIGITAL_2025', '泉城购服务平台', '负责三类数码产品目录、资格核验与风控'),
('JINAN_DIGITAL_2025', '销售企业', '单件下单结算，闭环管理激活、签收、退货流程'),
('JINAN_AUTO_ROUND1_2025', '齐鲁银行权益平台', '提供申报入口、短信通知及银行卡发放通道'),
('JINAN_AUTO_ROUND1_2025', '第三方复审机构', '对系统初审结果进行核验并集中公示'),
('JINAN_AUTO_ROUND1_2025', '个人消费者', '上传身份证、发票、行驶证、登记证等材料，确保真实有效'),
('JINAN_AUTO_GIFT_2025', '工银e生活平台', '负责扫码申领、资料收集与状态推送'),
('JINAN_AUTO_GIFT_2025', '中石油/中石化', '发放并管理加油储值卡，提醒90天有效期'),
('JINAN_COUPON_2025', '抖音APP', '承载领券、核销、风控与客服，支持直播/商家场景'),
('JINAN_COUPON_2025', '活动用户', '需实名、同批次限领1张，遵守不可拆单/套现规则'),
('JINAN_INSURANCE_2025', '保险公司', '按照活动期出具保单并配合核验真实性'),
('JINAN_INSURANCE_2025', '第三方审核机构', '审核补贴申报材料并在官网公示结果');

DROP TABLE IF EXISTS agent_capabilities;
CREATE TABLE agent_capabilities (
    agent_name TEXT PRIMARY KEY,
    route TEXT NOT NULL,
    description TEXT NOT NULL,
    requires_connection INTEGER DEFAULT 0,
    primary_tools TEXT,
    entry_point TEXT,
    default_chains TEXT,
    source_module TEXT
);

INSERT INTO agent_capabilities (agent_name, route, description, requires_connection, primary_tools, entry_point, default_chains, source_module) VALUES
('AgentService', 'router', '统一入口，负责改写、意图识别与多路由调度。', 0, 'IntentDetectionTool, AgentService pipelines', 'app/agents/service/agent_service.py', 'rewrite_chain,router', 'app/agents/service'),
('RewriteAgent', 'rewrite', '对口语问题进行语义改写并补全主体信息。', 0, 'LLM', 'app/agents/pipeline/rewrite_agent.py', 'chat_chain', 'app/agents/pipeline'),
('DialogueAgent', 'dialogue', '处理问候、寒暄与结束语，输出模板化回复。', 0, 'ChatAgent pack', 'app/agents/pipeline/dialog_agent.py', 'chat_chain', 'app/agents/pipeline'),
('ClarifierAgent', 'clarification', '当意图不明时主动追问补充信息。', 0, 'Clarifier pack', 'app/agents/pipeline/dialog_agent.py', 'chat_chain', 'app/agents/pipeline'),
('KnowledgeAgent', 'knowledge', '调用Milvus/LightRAG及WebSearch生成政策摘要。', 0, 'KnowledgeTool, WebSearchTool', 'app/agents/pipeline/knowledge_agent.py', 'kb_chain', 'app/agents/pipeline'),
('GraphAgent', 'graph', '优先使用LightRAG进行关系推理，失败时回退知识检索。', 0, 'GraphRetriever, KnowledgeAgent', 'app/agents/pipeline/graph_agent.py', 'graph_chain', 'app/agents/pipeline'),
('RuleEngineAgent', 'rule_engine', '基于PolicyEngine执行DSL规则完成补贴计算。', 0, 'PolicyEngine, DSL规则', 'app/agents/pipeline/rule_agent.py', 'calculation_chain', 'app/agents/pipeline'),
('Text2SQLAgent', 'text2sql', '将自然语言转为SQL并执行，必须提供connection_id。', 1, 'ChatDB text2sql_service', 'app/agents/pipeline/text2sql_agent.py', 'text2sql_chain', 'app/agents/pipeline'),
('WorkflowAgent', 'workflow', 'GraphFlow + Vision/UserProfile，多模态任务的编排执行。', 0, 'VisionTool, UserProfileTool, KnowledgeAgent, RuleEngineAgent', 'app/agents/pipeline/workflow_agent.py', 'hybrid_chain', 'app/agents/pipeline');

DROP TABLE IF EXISTS agent_question_templates;
CREATE TABLE agent_question_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    scenario TEXT NOT NULL,
    question_template TEXT NOT NULL,
    expected_route TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (agent_name) REFERENCES agent_capabilities(agent_name)
);

INSERT INTO agent_question_templates (agent_name, scenario, question_template, expected_route, notes) VALUES
('DialogueAgent', '问候与身份确认', '早上好，请问你是政策服务的小助手吗？', 'dialogue', '测试寒暄模板'),
('ClarifierAgent', '信息不足', '想了解补贴，能告诉我需要准备什么吗？', 'clarification', '缺少地区/政策名称'),
('RewriteAgent', '口语纠错', '老旧空调能补多少钱？', 'rewrite', '期望补全为正式问题'),
('KnowledgeAgent', '政策摘要', '概括济南家电以旧换新细则的申请步骤。', 'knowledge', '需检索知识库'),
('GraphAgent', '关系对比', '比较济南与青岛汽车补贴涉及的执行主体。', 'graph', '若LightRAG不可用将回退知识库'),
('RuleEngineAgent', 'DSL计算', '套用 DSL 计算家电以旧换新的补贴金额。', 'rule_engine', '需匹配 rule_id'),
('Text2SQLAgent', 'SQL查询', '写一条 SQL 查 policy_benefit_rules 中补贴≥5000元的档位。', 'text2sql', '必须带 connection_id'),
('WorkflowAgent', '多模态', '我上传了消费券海报，请判断是否能与餐饮券叠加。', 'workflow', '触发 Vision + 知识'),
('AgentService', '全链路', '从问候到补贴计算的一次完整测试。', 'router', '验证统一入口逻辑');

DROP TABLE IF EXISTS text2sql_reference_questions;
CREATE TABLE text2sql_reference_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    recommended_table TEXT NOT NULL,
    filter_hint TEXT,
    doc_id TEXT,
    difficulty INTEGER DEFAULT 1,
    expected_insight TEXT,
    FOREIGN KEY (doc_id) REFERENCES policy_documents(doc_id)
);

INSERT INTO text2sql_reference_questions (question, recommended_table, filter_hint, doc_id, difficulty, expected_insight) VALUES
('写一条SQL列出济南家电以旧换新细则中所有空调补贴档位及补贴比例。', 'policy_benefit_rules', 'doc_id=''JINAN_APPLIANCE_2025'' AND benefit_item=''空调''', 'JINAN_APPLIANCE_2025', 1, '对比一级/二级能效补贴率和封顶值'),
('统计policy_benefit_rules按doc_id的记录数，看看哪份政策拆分的档位最多。', 'policy_benefit_rules', NULL, NULL, 2, '识别哪类政策结构最复杂'),
('查询policy_timelines里2025年7月之后开始的阶段及所属政策。', 'policy_timelines', 'start_time>=''2025-07-01''', NULL, 1, '锁定暑期活动的重要节点'),
('找出policy_execution_roles中职责包含“平台”的角色名称和对应政策。', 'policy_execution_roles', 'responsibilities LIKE ''%平台%''', NULL, 1, '梳理平台方责任'),
('列出agent_capabilities里requires_connection=1的代理及入口文件。', 'agent_capabilities', 'requires_connection=1', NULL, 1, '强调Text2SQL依赖connection_id'),
('按expected_route统计agent_question_templates的数量，并按降序展示。', 'agent_question_templates', NULL, NULL, 2, '验证每类路由的测试覆盖'),
('查询policy_documents里summary包含“泉城购”的政策标题及分类。', 'policy_documents', 'summary LIKE ''%泉城购%''', 'JINAN_COUPON_2025', 1, '定位依赖泉城购平台的政策'),
('写SQL找出policy_benefit_rules中flat_amount介于3000和5000之间的档位信息。', 'policy_benefit_rules', 'flat_amount BETWEEN 3000 AND 5000', NULL, 2, '用于比较不同补贴轮次'),
('查询policy_timelines中doc_id="JINAN_INSURANCE_2025"的所有阶段并按start_time排序。', 'policy_timelines', 'doc_id=''JINAN_INSURANCE_2025''', 'JINAN_INSURANCE_2025', 1, '确认首保活动的时间链路'),
('列出policy_execution_roles中涉及“抖音APP”的责任主体及说明。', 'policy_execution_roles', 'responsibilities LIKE ''%抖音%''', 'JINAN_COUPON_2025', 1, '验证消费券执行渠道'),
('统计agent_capabilities按照route分组的数量，了解主流程覆盖度。', 'agent_capabilities', NULL, NULL, 1, '辅助排查缺失路由'),
('查询coupon_rules表中青岛档位的折扣金额及适用区间。', 'coupon_rules', 'city=''青岛''', NULL, 1, '复用旧表测试SQL'),
('找出auto_subsidy_tiers里benefit_type=''gift_package''的最高benefit_amount。', 'auto_subsidy_tiers', 'benefit_type=''gift_package''', NULL, 2, '检验礼包档位'),
('列出appliance_subsidy_rules里per_person_limit>1的品类。', 'appliance_subsidy_rules', 'per_person_limit>1', NULL, 1, '验证旧家电表仍可查询'),
('查询policy_benefit_rules中subsidy_cap>=2000或flat_amount>=2000的条目，按金额降序。', 'policy_benefit_rules', '(subsidy_cap>=2000 OR flat_amount>=2000)', NULL, 2, '用于演示混合条件'),
('写SQL返回agent_capabilities里route在("knowledge","graph")的代理及primary_tools。', 'agent_capabilities', 'route IN (''knowledge'',''graph'')', NULL, 1, '凸显检索链路依赖');
