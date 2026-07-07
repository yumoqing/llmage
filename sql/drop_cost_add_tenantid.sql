-- DROP cost column, ADD tenantid column to llmusage
ALTER TABLE llmusage DROP COLUMN IF EXISTS cost;
ALTER TABLE llmusage ADD COLUMN IF NOT EXISTS tenantid VARCHAR(32) DEFAULT NULL COMMENT '租户orgid,标识客户在哪个分销商入口消费';
-- Also update llmusage_history if exists
ALTER TABLE llmusage_history DROP COLUMN IF EXISTS cost;
ALTER TABLE llmusage_history ADD COLUMN IF NOT EXISTS tenantid VARCHAR(32) DEFAULT NULL;
