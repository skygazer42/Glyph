-- 政务智能问答数据库 Schema 设计
-- 参考 ChatDB 架构，适配济南市政策数据

-- ==================== 核心表结构 ====================

-- 1. 政策文档表
CREATE TABLE IF NOT EXISTS policy_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    category VARCHAR(50) NOT NULL,  -- 汽车补贴/家电以旧换新/消费券/数码补贴
    sub_category VARCHAR(50),  -- 子分类
    source_file VARCHAR(500),
    content TEXT NOT NULL,
    metadata JSON,  -- 存储额外元数据
    publish_date DATE,
    effective_date DATE,  -- 生效日期
    expiry_date DATE,  -- 失效日期
    status VARCHAR(20) DEFAULT 'active',  -- active/expired/draft
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 政策实体表（结构化提取的关键信息）
CREATE TABLE IF NOT EXISTS policy_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,  -- 补贴金额/申请条件/时间期限/办理流程
    entity_name VARCHAR(200) NOT NULL,
    entity_value TEXT,
    entity_unit VARCHAR(50),  -- 元/天/件
    confidence FLOAT DEFAULT 1.0,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doc_id) REFERENCES policy_documents(doc_id)
);

-- 3. QA 对表（问答对）
CREATE TABLE IF NOT EXISTS policy_qa_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    doc_id VARCHAR(100),
    category VARCHAR(50) NOT NULL,
    keywords TEXT,  -- 逗号分隔的关键词
    difficulty_level INTEGER DEFAULT 3,  -- 1-5，问题难度
    query_type VARCHAR(50) DEFAULT 'informational',  -- informational/procedural/eligibility
    verified BOOLEAN DEFAULT FALSE,
    use_count INTEGER DEFAULT 0,  -- 使用次数
    feedback_score FLOAT DEFAULT 0.0,  -- 用户反馈评分
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doc_id) REFERENCES policy_documents(doc_id)
);

-- 4. 政策标签表
CREATE TABLE IF NOT EXISTS policy_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id VARCHAR(100) NOT NULL,
    tag_name VARCHAR(100) NOT NULL,
    tag_type VARCHAR(50),  -- 领域/对象/场景
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doc_id) REFERENCES policy_documents(doc_id)
);

-- 5. 用户查询历史表
CREATE TABLE IF NOT EXISTS query_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(100),
    user_id VARCHAR(100),
    query TEXT NOT NULL,
    matched_doc_ids TEXT,  -- JSON 数组
    response TEXT,
    response_time_ms INTEGER,
    feedback VARCHAR(20),  -- positive/negative/neutral
    feedback_comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. 政策关系表（政策之间的关联）
CREATE TABLE IF NOT EXISTS policy_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_doc_id VARCHAR(100) NOT NULL,
    target_doc_id VARCHAR(100) NOT NULL,
    relationship_type VARCHAR(50) NOT NULL,  -- 补充/替代/依赖/相关
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_doc_id) REFERENCES policy_documents(doc_id),
    FOREIGN KEY (target_doc_id) REFERENCES policy_documents(doc_id)
);

-- 7. 政策变更历史表
CREATE TABLE IF NOT EXISTS policy_change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id VARCHAR(100) NOT NULL,
    change_type VARCHAR(50) NOT NULL,  -- created/updated/expired/superseded
    change_description TEXT,
    old_value TEXT,
    new_value TEXT,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doc_id) REFERENCES policy_documents(doc_id)
);

-- 8. Schema 提示表（帮助LLM理解表结构）
CREATE TABLE IF NOT EXISTS schema_hints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name VARCHAR(100) NOT NULL,
    column_name VARCHAR(100),
    hint_type VARCHAR(50),  -- description/example/constraint
    hint_text TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'zh',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== 索引优化 ====================

CREATE INDEX IF NOT EXISTS idx_doc_category ON policy_documents(category);
CREATE INDEX IF NOT EXISTS idx_doc_status ON policy_documents(status);
CREATE INDEX IF NOT EXISTS idx_doc_dates ON policy_documents(effective_date, expiry_date);
CREATE INDEX IF NOT EXISTS idx_qa_category ON policy_qa_pairs(category);
CREATE INDEX IF NOT EXISTS idx_qa_verified ON policy_qa_pairs(verified);
CREATE INDEX IF NOT EXISTS idx_entity_type ON policy_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_tags_doc ON policy_tags(doc_id);
CREATE INDEX IF NOT EXISTS idx_tags_name ON policy_tags(tag_name);
CREATE INDEX IF NOT EXISTS idx_query_session ON query_history(session_id);
CREATE INDEX IF NOT EXISTS idx_query_created ON query_history(created_at);

-- ==================== 视图定义 ====================

-- 活跃政策视图
CREATE VIEW IF NOT EXISTS v_active_policies AS
SELECT
    d.*,
    GROUP_CONCAT(DISTINCT t.tag_name) as tags,
    COUNT(DISTINCT e.id) as entity_count,
    COUNT(DISTINCT qa.id) as qa_count
FROM policy_documents d
LEFT JOIN policy_tags t ON d.doc_id = t.doc_id
LEFT JOIN policy_entities e ON d.doc_id = e.doc_id
LEFT JOIN policy_qa_pairs qa ON d.doc_id = qa.doc_id
WHERE d.status = 'active'
  AND (d.expiry_date IS NULL OR d.expiry_date >= date('now'))
GROUP BY d.id;

-- 高频问题视图
CREATE VIEW IF NOT EXISTS v_popular_questions AS
SELECT
    id,
    question,
    answer,
    category,
    use_count,
    feedback_score,
    ROUND(feedback_score * use_count, 2) as popularity_score
FROM policy_qa_pairs
WHERE verified = TRUE
ORDER BY popularity_score DESC;

-- 政策统计视图
CREATE VIEW IF NOT EXISTS v_policy_statistics AS
SELECT
    category,
    COUNT(*) as total_policies,
    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_policies,
    COUNT(DISTINCT doc_id) as unique_docs,
    MAX(updated_at) as last_updated
FROM policy_documents
GROUP BY category;
