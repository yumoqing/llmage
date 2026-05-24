-- ============================================================
-- llmage 模块数据库迁移脚本
-- 新增: llmusage_history (使用历史表) + llmusage_accounting_failed (记账失败表)
-- 日期: 2026-05-24
-- 执行前请备份数据库！
-- ============================================================

-- 1. 创建 llmusage_history 表 (已记账记录的历史归档)
CREATE TABLE IF NOT EXISTS llmusage_history
(
  `id` VARCHAR(32)   NOT NULL COMMENT 'id',
  `llmid` VARCHAR(32)   COMMENT '模型id',
  `use_date` date   COMMENT '使用日期',
  `use_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP   COMMENT '使用时间',
  `userid` VARCHAR(32)   COMMENT '用户id',
  `usages` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci   COMMENT '使用信息',
  `ioinfo` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci   COMMENT '交互内容',
  `transno` VARCHAR(32)   COMMENT '交易号',
  `responsed_seconds` double(18,3)   COMMENT '响应时间',
  `finish_seconds` double(18,3)   COMMENT '结束时间',
  `status` VARCHAR(32)   COMMENT '状态',
  `taskid` VARCHAR(256)   COMMENT '任务号',
  `amount` double(18,5)   COMMENT '交易金额',
  `cost` double(18,5)   COMMENT '交易成本',
  `userorgid` VARCHAR(32)   COMMENT '用户机构id',
  `ownerid` VARCHAR(32)   COMMENT '模型机构id',
  `accounting_status` VARCHAR(32)   COMMENT '记账状态',
  `backup_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP   COMMENT '备份时间',
  PRIMARY KEY(id)
)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
engine=innodb 
COMMENT '模型使用历史记录';

CREATE INDEX idx_lh_use_date ON llmusage_history(use_date);
CREATE INDEX idx_lh_userorgid ON llmusage_history(userorgid);
CREATE INDEX idx_lh_llmid ON llmusage_history(llmid);
CREATE INDEX idx_lh_backup_time ON llmusage_history(backup_time);

-- 2. 创建 llmusage_accounting_failed 表 (记账失败记录)
CREATE TABLE IF NOT EXISTS llmusage_accounting_failed
(
  `id` VARCHAR(32)   NOT NULL COMMENT 'id',
  `llmusageid` VARCHAR(32)   COMMENT '使用记录id',
  `llmid` VARCHAR(32)   COMMENT '模型id',
  `userid` VARCHAR(32)   COMMENT '用户id',
  `userorgid` VARCHAR(32)   COMMENT '用户机构id',
  `use_date` date   COMMENT '使用日期',
  `use_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP   COMMENT '使用时间',
  `amount` double(18,5)   COMMENT '交易金额',
  `cost` double(18,5)   COMMENT '交易成本',
  `failed_reason` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci   COMMENT '失败原因',
  `failed_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP   COMMENT '失败时间',
  `retry_count` int   COMMENT '重试次数',
  `handled` VARCHAR(1)   DEFAULT '0' COMMENT '是否已处理',
  `handled_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP   COMMENT '处理时间',
  `handled_note` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci   COMMENT '处理备注',
  PRIMARY KEY(id)
)
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
engine=innodb 
COMMENT '记账失败记录';

CREATE INDEX idx_laf_use_date ON llmusage_accounting_failed(use_date);
CREATE INDEX idx_laf_userorgid ON llmusage_accounting_failed(userorgid);
CREATE INDEX idx_laf_llmid ON llmusage_accounting_failed(llmid);
CREATE INDEX idx_laf_handled ON llmusage_accounting_failed(handled);
CREATE INDEX idx_laf_failed_time ON llmusage_accounting_failed(failed_time);

-- 3. 为 llmusage 表添加组合索引（优化备份查询: accounting_status + use_date）
CREATE INDEX idx_llmusage_accounting ON llmusage(accounting_status, use_date);

-- ============================================================
-- 验证步骤（执行后运行）:
-- 1. 确认表创建成功:
--    SHOW TABLES LIKE 'llmusage_%';
-- 2. 确认索引创建成功:
--    SHOW INDEX FROM llmusage_history;
--    SHOW INDEX FROM llmusage_accounting_failed;
-- 3. 确认表结构正确:
--    DESCRIBE llmusage_history;
--    DESCRIBE llmusage_accounting_failed;
-- ============================================================
-- 回滚步骤（如需撤销）:
-- DROP TABLE IF EXISTS llmusage_history;
-- DROP TABLE IF EXISTS llmusage_accounting_failed;
-- ============================================================
