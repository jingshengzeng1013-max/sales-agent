-- 结构化表：存储每条招标的结构化抽取结果
CREATE TABLE IF NOT EXISTS tender_structured (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id INTEGER NOT NULL,
    announce_type TEXT,                    -- 公告类型：招标公告/中标公告/废标公告/竞争性谈判/竞争性磋商/询价/单一来源
    buyer_name_std TEXT,                   -- 采购人标准化名称
    agency_name_std TEXT,                  -- 代理机构标准化名称
    province TEXT,                         -- 省份
    city TEXT,                             -- 城市
    budget_raw TEXT,                       -- 预算原文
    budget_amount REAL,                    -- 预算金额（数值）
    budget_unit TEXT,                      -- 预算单位：元/万元/亿元
    product_keywords TEXT,                 -- 产品关键词（JSON 数组字符串）
    application_scenario TEXT,             -- 应用场景
    content_summary TEXT,                  -- 公告内容摘要（用于检索）
    technical_requirements_summary TEXT,   -- 技术要求摘要
    -- 三方联系人信息（JSON 数组字符串）
    buyer_contacts TEXT,                   -- 采购人联系人列表：[{"name": "", "phone": ""}]
    agency_contacts TEXT,                  -- 代理机构联系人列表：[{"name": "", "phone": ""}]
    project_contacts TEXT,                 -- 项目联系人列表：[{"name": "", "phone": ""}]
    -- RAG 检索块
    contact_chunk TEXT,                    -- 联系方式块（用于向量检索）
    requirement_chunks TEXT,               -- 技术要求分块数组：[{"type": "", "text": ""}]
    -- 兼容旧字段
    contact_person TEXT,                   -- 联系人（兼容旧字段）
    contact_phone TEXT,                    -- 联系电话（兼容旧字段）
    attachment_summary TEXT,               -- 附件摘要
    opportunity_score INTEGER,             -- 机会评分 0-100
    opportunity_reason TEXT,               -- 机会原因
    next_action TEXT,                      -- 下一步建议动作
    extracted_json TEXT,                   -- 完整 JSON 输出（保留原始）
    llm_model TEXT,                        -- 使用的模型
    llm_version TEXT,                      -- 模型版本
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tender_id) REFERENCES tenders(id)
);

-- 索引：加速常用查询
CREATE INDEX IF NOT EXISTS idx_tender_structured_tender_id ON tender_structured(tender_id);
CREATE INDEX IF NOT EXISTS idx_tender_structured_announce_type ON tender_structured(announce_type);
CREATE INDEX IF NOT EXISTS idx_tender_structured_province ON tender_structured(province);
CREATE INDEX IF NOT EXISTS idx_tender_structured_buyer ON tender_structured(buyer_name_std);
CREATE INDEX IF NOT EXISTS idx_tender_structured_opportunity ON tender_structured(opportunity_score);

-- 分块表：用于 RAG 检索
CREATE TABLE IF NOT EXISTS tender_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id INTEGER NOT NULL,
    chunk_type TEXT,                       -- title/content_summary/requirement_chunk/contact_chunk/attachment_summary
    chunk_text TEXT NOT NULL,
    chunk_order INTEGER,
    metadata_json TEXT,                    -- 元数据（JSON 字符串）
    embedding_id TEXT,                     -- 向量 ID（可选）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tender_id) REFERENCES tenders(id)
);

CREATE INDEX IF NOT EXISTS idx_tender_chunks_tender_id ON tender_chunks(tender_id);
CREATE INDEX IF NOT EXISTS idx_tender_chunks_chunk_type ON tender_chunks(chunk_type);
