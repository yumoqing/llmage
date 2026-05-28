-- llmage: 添加模型上架/下架功能
-- 执行此 SQL 后，所有现有模型默认已上架，不影响线上使用

-- 1. 添加 status 字段
ALTER TABLE llm ADD COLUMN `status` VARCHAR(16) NOT NULL DEFAULT 'unpublished' COMMENT '上架状态: published/unpublished' AFTER `min_balance`;

-- 2. 现有模型全部设为已上架
UPDATE llm SET status = 'published';

-- 3. 添加索引（按状态筛选是高频操作）
ALTER TABLE llm ADD INDEX `idx_status` (`status`);
