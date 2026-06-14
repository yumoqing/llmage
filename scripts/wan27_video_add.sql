-- ============================================================
-- 
-- Wan2.7 文生视频 API接口接入
-- 生成时间: 2026-06-12 (重写: 2026-06-13)
-- 模型: wan2.7-t2v-2026-04-25 (文生视频)
-- 支持: 720P/1080P, 2-15秒, 音频, 多镜头叙事
-- ============================================================
-- 前置条件:
--   llm表已有记录: id='IE8Ws20ZSoyAkOryWqhG_', model='wan2.7-t2v-2026-04-25'
--   pricing_program已有记录: id='GFJm2LIQoq2C70fFoY1H3', name='通义万相 wan2.7-t2v'
--   uapi 't2v' (id='It-ShFhCGIhS0ds3C2JJ0') 已有，复用万象通用文生视频接口
-- ============================================================

-- ============================================================
-- 1. 新增 llm_api_map: wan2.7-t2v → t2v接口 + 定价
-- ============================================================
INSERT IGNORE INTO `llm_api_map` (`id`, `llmid`, `llmcatelogid`, `apiname`, `query_apiname`, `query_period`, `ppid`, `isdefaultcatelog`)
VALUES (
  'wan27t2v_map_001',
  'IE8Ws20ZSoyAkOryWqhG_',
  't2v',
  't2v',
  't2vstatus',
  10,
  'GFJm2LIQoq2C70fFoY1H3',
  '1'
);

-- ============================================================
-- 2. 新增 pricing_program_timing: wan2.7-t2v 定价
--    官方定价: 720P=0.6元/秒, 1080P=1.0元/秒
-- ============================================================
INSERT INTO `pricing_program_timing` (`id`, `ppid`, `name`, `enabled_date`, `expired_date`, `pricing_data`)
VALUES (
  'wan27t2v_timing_001',
  'GFJm2LIQoq2C70fFoY1H3',
  NULL,
  '2026-05-20',
  '9999-12-31',
  'unit_values:\n  秒: 1\nfields:\n  price_factors:\n    type: string\n    role: factor\n    label: 计价因子\n  unit_prices:\n    type: float\n    role: factor\n    label: 单位定价\n  unit:\n    type: string\n    role: factor\n    label: 计价单位\n  SR:\n    type: string\n    role: filter\n    label: SR\npricings:\n- price_factors: duration\n  unit_prices: 0.6\n  unit: 秒\n  filters:\n  - SR: 720\n- price_factors: duration\n  unit_prices: 1.0\n  unit: 秒\n  filters:\n  - SR: 1080'
);


-- ============================================================
-- 验证 (执行后运行确认)
-- ============================================================
-- SELECT m.id, m.llmid, m.llmcatelogid, m.apiname, m.query_apiname, m.ppid,
--        l.name as model_name, l.model,
--        pp.name as pricing_name,
--        (SELECT COUNT(*) FROM pricing_program_timing WHERE ppid = m.ppid) as timing_count
-- FROM llm_api_map m
-- JOIN llm l ON m.llmid = l.id
-- JOIN pricing_program pp ON m.ppid = pp.id
-- WHERE m.llmid = 'IE8Ws20ZSoyAkOryWqhG_';
--
-- 预期: timing_count = 1


-- ============================================================
-- 回滚
-- ============================================================
-- DELETE FROM llm_api_map WHERE id = 'wan27t2v_map_001';
-- DELETE FROM pricing_program_timing WHERE id = 'wan27t2v_timing_001';
