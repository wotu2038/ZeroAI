-- ============================================================
-- 为模板表添加 LLM 生成相关字段
-- ============================================================
-- 
-- 【推荐】使用 Python 迁移脚本（自动从 .env 读取数据库配置）：
-- docker-compose -f docker-compose.backend.yml exec zero-ai-backend python /app/migrations/add_llm_template_fields.py
-- 
-- 【备选】手动执行 SQL（需要指定数据库名）：
-- docker-compose exec mysql mysql -u root -p${MYSQL_PASSWORD} ${MYSQL_DATABASE} < migrations/add_llm_template_fields.sql
-- 
-- 注意：不要直接执行此 SQL 文件，需要通过上述命令指定目标数据库
-- ============================================================

-- 添加LLM生成相关字段
ALTER TABLE entity_edge_templates
ADD COLUMN IF NOT EXISTS is_llm_generated BOOLEAN DEFAULT FALSE NOT NULL COMMENT '是否LLM生成' AFTER is_system,
ADD COLUMN IF NOT EXISTS source_document_id INT NULL COMMENT '来源文档ID（LLM生成时关联）' AFTER is_llm_generated,
ADD COLUMN IF NOT EXISTS analysis_mode VARCHAR(50) NULL COMMENT '分析模式：smart_segment/full_chunk' AFTER source_document_id,
ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(50) NULL COMMENT 'LLM提供商（生成时使用）' AFTER analysis_mode,
ADD COLUMN IF NOT EXISTS generated_at DATETIME NULL COMMENT '生成时间' AFTER llm_provider;

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_is_llm_generated ON entity_edge_templates(is_llm_generated);
CREATE INDEX IF NOT EXISTS idx_source_document_id ON entity_edge_templates(source_document_id);

