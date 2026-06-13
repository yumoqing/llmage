-- ============================================================
-- 修复数字人模型显示错误 — pricing timing缺失
-- 问题: get_ppid_pricing 找不到有效timing记录导致"data not found"
-- 影响: 
--   1. orNSwYIFP0HFv2UnY-9EW (wan2.6-i2v-flash) — 有program无timing
--   2. 0B6aldoAej1PpZ4ydtrEZ (wan2.2-s2v数字人) — program和timing都缺
-- 生成时间: 2026-06-13
-- 执行用户: sword (bugfix模块) 或 root (mysql直接执行)
-- ============================================================

-- ============================================================
-- 1. 修复 wan2.6-i2v-flash: 设置discount + 创建timing记录
-- ============================================================

-- 1a. 修复 discount (当前为null)
UPDATE pricing_program 
SET discount = 1.0 
WHERE id = 'orNSwYIFP0HFv2UnY-9EW';

-- 1b. 创建 pricing_program_timing 记录
-- 官方定价: 有声720P=0.3元/秒, 1080P=0.5元/秒; 无声720P=0.15元/秒, 1080P=0.25元/秒
INSERT INTO pricing_program_timing (id, ppid, name, enabled_date, expired_date, pricing_data)
VALUES (
  'orNSwYIFP0HFv2UnY-t1',
  'orNSwYIFP0HFv2UnY-9EW',
  NULL,
  '2026-06-13',
  '9999-12-31',
  'unit_values:\n  秒: 1\nfields:\n  price_factors:\n    type: string\n    role: factor\n    label: 计价因子\n  unit_prices:\n    type: float\n    role: factor\n    label: 单位定价\n  unit:\n    type: string\n    role: factor\n    label: 计价单位\n  size:\n    type: string\n    role: filter\n    label: 分辨率\n  audio:\n    type: string\n    role: filter\n    label: 音频\npricings:\n- price_factors: duration\n  unit_prices: 0.3\n  unit: 秒\n  filters:\n  - size: 720P\n  - audio: true\n- price_factors: duration\n  unit_prices: 0.5\n  unit: 秒\n  filters:\n  - size: 1080P\n  - audio: true\n- price_factors: duration\n  unit_prices: 0.15\n  unit: 秒\n  filters:\n  - size: 720P\n  - audio: false\n- price_factors: duration\n  unit_prices: 0.25\n  unit: 秒\n  filters:\n  - size: 1080P\n  - audio: false'
);

-- ============================================================
-- 2. 创建 wan2.2-s2v 数字人定价 (program + timing)
-- ============================================================

-- 2a. 创建 pricing_program
INSERT INTO pricing_program (id, name, ownerid, providerid, pricing_belong, discount, description, pricing_spec)
VALUES (
  '0B6aldoAej1PpZ4ydtrEZ',
  '通义万象-数字人 wan2.2-s2v',
  '0',
  '6fadgewjraOyvxC_EkHou',
  'provider',
  1.0,
  '万相数字人视频生成定价，按输出视频秒数计费',
  'fields:\n  model:\n    type: str\n    label: 模型\n    options:\n      - wan2.2-s2v\n  size:\n    type: str\n    label: 分辨率\n    options:\n      - 480P\n      - 720P\n  duration:\n    type: factor\n    label: 时长（秒）'
);

-- 2b. 创建 pricing_program_timing
-- 官方定价: 480P=0.5元/秒, 720P=0.9元/秒
INSERT INTO pricing_program_timing (id, ppid, name, enabled_date, expired_date, pricing_data)
VALUES (
  '0B6aldoAej1PpZ4ydtrE-t1',
  '0B6aldoAej1PpZ4ydtrEZ',
  NULL,
  '2026-06-13',
  '9999-12-31',
  'unit_values:\n  秒: 1\nfields:\n  price_factors:\n    type: string\n    role: factor\n    label: 计价因子\n  unit_prices:\n    type: float\n    role: factor\n    label: 单位定价\n  unit:\n    type: string\n    role: factor\n    label: 计价单位\n  size:\n    type: string\n    role: filter\n    label: 分辨率\npricings:\n- price_factors: duration\n  unit_prices: 0.5\n  unit: 秒\n  filters:\n  - size: 480P\n- price_factors: duration\n  unit_prices: 0.9\n  unit: 秒\n  filters:\n  - size: 720P'
);


-- ============================================================
-- 验证 (执行后运行以下查询确认)
-- ============================================================
-- SELECT pp.id, pp.name, pp.discount, COUNT(ppt.id) as timing_count
-- FROM pricing_program pp
-- LEFT JOIN pricing_program_timing ppt ON pp.id = ppt.ppid
-- WHERE pp.id IN ('orNSwYIFP0HFv2UnY-9EW', '0B6aldoAej1PpZ4ydtrEZ')
-- GROUP BY pp.id, pp.name, pp.discount;
--
-- 预期结果:
-- | id                      | name                       | discount | timing_count |
-- |-------------------------|----------------------------|----------|--------------|
-- | orNSwYIFP0HFv2UnY-9EW   | wan2.6-i2v-flash           | 1.0      | 1            |
-- | 0B6aldoAej1PpZ4ydtrEZ   | 通义万象-数字人 wan2.2-s2v  | 1.0      | 1            |


-- ============================================================
-- 回滚 (如需回滚)
-- ============================================================
-- DELETE FROM pricing_program_timing WHERE id IN ('orNSwYIFP0HFv2UnY-t1', '0B6aldoAej1PpZ4ydtrE-t1');
-- DELETE FROM pricing_program WHERE id = '0B6aldoAej1PpZ4ydtrEZ';
-- UPDATE pricing_program SET discount = NULL WHERE id = 'orNSwYIFP0HFv2UnY-9EW';
