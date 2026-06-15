-- ============================================================
-- 修复 MiniMax-M3 定价重复条目
-- 问题：步骤11b的CONCAT重复执行导致M3条目重复
-- 解决：删除没有prompt_tokens filter的旧M3条目（前3条）
-- ============================================================

UPDATE `pricing_program_timing`
SET `pricing_data` = REPLACE(`pricing_data`, 
'- price_factors: prompt_tokens
  unit_prices: 2.1
  unit: 百万
  filters:
  - model: MiniMax-M3
- price_factors: completion_tokens
  unit_prices: 8.4
  unit: 百万
  filters:
  - model: MiniMax-M3
- price_factors: cached_tokens
  unit_prices: 0.42
  unit: 百万
  filters:
  - model: MiniMax-M3

', '')
WHERE `ppid` = '5jmzupARABxkDFwUraFiQ' AND `enabled_date` = '2026-04-12';
