-- ============================================================
-- MiniMax M3 接入 + M2.7-highspeed + 补充全模型定价
-- 生成时间: 2026-06-12
-- 数据来源: token.opencomputing.cn 实时查询 (bugfix/execute_sql)
-- 参考: qwen3.7-max (llm:u1EtkR9xRcmwMvdoCZRC8, ppid:5i1JIpqERgCWqKQ4DCegD)
-- ============================================================

-- ============================================================
-- 1. 新增 httpapi: MiniMax OpenAI兼容接口 (M3/M2.7-highspeed使用)
--    API地址由upapp.baseurl控制: https://api.minimaxi.com/v1/chat/completions
-- ============================================================
INSERT INTO `httpapi` (`id`, `apiname`, `label`, `providerid`, `apiinfo`, `apinote`, `use_session`, `response_mode`, `system_msg_format`, `user_msg_format`, `llm_msg_format`)
VALUES (
  'mm3_openai_t2t',
  'minimax_openai t2t',
  'MiniMax M3 OpenAI兼容',
  '0',
  '{"response_mode":"stream", "use_session":true, "method":"POST", "chunk_match":"data: ", "headers":[ { "name":"Content-Type", "value":"application/json" }, { "name":"Authorization", "value":"Bearer ${apikey}" } ], "data":[ { "name":"model", "value":"${model}" }, { "name":"messages", "value":"${messages}" }, { "name":"stream", "value":true } ], "resp":[ { "name":"content", "value":"choices[0].delta.content" }, { "name":"usage", "value":"usage" } ] }',
  'MiniMax M3/M2.7-highspeed OpenAI Chat Completions兼容API',
  '1',
  'stream',
  '',
  '',
  '{ "role":"user", "content":"${prompt}" }'
);

-- ============================================================
-- 2. 新增 llm: MiniMax-M3
-- ============================================================
INSERT INTO `llm` (`id`, `name`, `model`, `description`, `iconid`, `upappid`, `providerid`, `ownerid`, `enabled_date`, `expired_date`, `min_balance`, `status`)
VALUES (
  'mm3_MiniMax_M3',
  'MiniMax M3',
  'MiniMax-M3',
  'MiniMax M3: 编程及Agent SOTA, 1M超长上下文, 多模态, 交错思维链。≤512K永久五折。',
  'minimax',
  'minimax',
  'ww4e_kfX3Lh65Sdys0Vku',
  '0',
  '2026-06-12',
  '9999-12-31',
  10.00,
  'published'
);

-- ============================================================
-- 3. 新增 llm: MiniMax-M2.7-highspeed
-- ============================================================
INSERT INTO `llm` (`id`, `name`, `model`, `description`, `iconid`, `upappid`, `providerid`, `ownerid`, `enabled_date`, `expired_date`, `min_balance`, `status`)
VALUES (
  'mm_m27_highspeed',
  'MiniMax M2.7 Highspeed',
  'MiniMax-M2.7-highspeed',
  'MiniMax M2.7高速版, 更快速度, 适合低延迟场景。输入¥4.2/百万tokens, 输出¥16.8/百万tokens。',
  'minimax',
  'minimax',
  'ww4e_kfX3Lh65Sdys0Vku',
  '0',
  '2026-06-12',
  '9999-12-31',
  10.00,
  'published'
);

-- ============================================================
-- 4. 新增 llm_api_map: MiniMax-M3 → 5jmzup (minimax专用文本定价)
-- ============================================================
INSERT INTO `llm_api_map` (`id`, `llmid`, `llmcatelogid`, `apiname`, `query_apiname`, `query_period`, `ppid`, `isdefaultcatelog`)
VALUES (
  'mm3_map_t2t',
  'mm3_MiniMax_M3',
  't2t',
  'minimax_openai t2t',
  NULL,
  NULL,
  '5jmzupARABxkDFwUraFiQ',
  '1'
);

-- ============================================================
-- 5. 新增 llm_api_map: MiniMax-M2.7-highspeed → 5jmzup
-- ============================================================
INSERT INTO `llm_api_map` (`id`, `llmid`, `llmcatelogid`, `apiname`, `query_apiname`, `query_period`, `ppid`, `isdefaultcatelog`)
VALUES (
  'mm_m27hs_map_t2t',
  'mm_m27_highspeed',
  't2t',
  'minimax_openai t2t',
  NULL,
  NULL,
  '5jmzupARABxkDFwUraFiQ',
  '1'
);

-- ============================================================
-- 6. 补充现有模型 llm_api_map.ppid
-- ============================================================

-- 6a. MiniMax-Hailuo-2.3 (视频i2v) → 0V89 (已有Hailuo-2.3定价条目)
UPDATE `llm_api_map` SET `ppid` = '0V89eilc_UQ2KiZIRJO8M'
WHERE `llmid` = 'AU1f40HV3tqFjxcVWWpyR' AND (`ppid` IS NULL OR `ppid` = '');

-- 6b. Minimax海螺参考生视频 S2V-01 (视频i2v) → 0V89
UPDATE `llm_api_map` SET `ppid` = '0V89eilc_UQ2KiZIRJO8M'
WHERE `llmid` = 'oks-VG9D8p2b0Agvs-LeQ' AND (`ppid` IS NULL OR `ppid` = '');

-- 6c. music-2.0 (音乐) → fQzk (已有音乐定价 ¥1/首)
UPDATE `llm_api_map` SET `ppid` = 'fQzkUeS6t6NBz_Fu4Fi77'
WHERE `llmid` = 'ns7egG9aXi91wjI62yKfu' AND (`ppid` IS NULL OR `ppid` = '');

-- 6d. speech-2.6-hd (TTS) → mm_tts_pricing (新建)
UPDATE `llm_api_map` SET `ppid` = 'mm_tts_pricing'
WHERE `llmid` = 'q6rdMUsGD1z3S3NyZh_A_' AND (`ppid` IS NULL OR `ppid` = '');

-- 6e. speech-2.6-turbo (TTS) → mm_tts_pricing
UPDATE `llm_api_map` SET `ppid` = 'mm_tts_pricing'
WHERE `llmid` = 'CEYD4YWRxjCj4k_6bpzIM' AND (`ppid` IS NULL OR `ppid` = '');

-- 6f. speech-2.5-hd-preview (TTS) → mm_tts_pricing
UPDATE `llm_api_map` SET `ppid` = 'mm_tts_pricing'
WHERE `llmid` = 'Si2g0XJ9ym3P5jlrdmcfB' AND (`ppid` IS NULL OR `ppid` = '');

-- ============================================================
-- 7. 新增 pricing_program: MiniMax TTS定价 (元/万字符)
-- ============================================================
INSERT INTO `pricing_program` (`id`, `name`, `ownerid`, `providerid`, `pricing_belong`, `discount`, `description`, `pricing_spec`)
VALUES (
  'mm_tts_pricing',
  'MiniMax语音合成定价',
  '0',
  'ww4e_kfX3Lh65Sdys0Vku',
  'provider',
  1.000,
  'MiniMax speech系列TTS定价，按万字符计费',
  'fields:\n  model:\n    type: str\n    label: 模型\n  formula:\n    type: str\n    label: 公式\n'
);

-- ============================================================
-- 8. 新增 pricing_program_timing: MiniMax TTS
-- ============================================================
INSERT INTO `pricing_program_timing` (`id`, `ppid`, `name`, `enabled_date`, `expired_date`, `pricing_data`)
VALUES (
  'mm_tts_timing',
  'mm_tts_pricing',
  'MiniMax TTS全价',
  '2026-06-12',
  '9999-12-31',
  'unit_values:\n  万字符: 10000\nfields:\n  price_factors:\n    type: string\n    role: factor\n    label: 计价因子\n  unit_prices:\n    type: float\n    role: factor\n    label: 单位定价\n  unit:\n    type: string\n    role: factor\n    label: 计价单位\n  model:\n    type: string\n    role: filter\n    label: model\npricings:\n- price_factors: flat\n  unit_prices: 3.5\n  unit: 万字符\n  filters:\n  - model: speech-2.6-hd\n- price_factors: flat\n  unit_prices: 2.0\n  unit: 万字符\n  filters:\n  - model: speech-2.6-turbo\n- price_factors: flat\n  unit_prices: 3.5\n  unit: 万字符\n  filters:\n  - model: speech-2.5-hd-preview\n'
);

-- ============================================================
-- 9. 更新 5jmzup timing: 添加 MiniMax-M3 定价
--    M3 ≤512K永久五折: 输入2.1/输出8.4/缓存0.42
--    M3 512K~1M: 输入4.2/输出16.8/缓存0.84
-- ============================================================
UPDATE `pricing_program_timing`
SET `pricing_data` = CONCAT(`pricing_data`, '
- price_factors: prompt_tokens
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
')
WHERE `ppid` = '5jmzupARABxkDFwUraFiQ' AND `enabled_date` = '2026-04-12';

-- ============================================================
-- 10. 更新 pricing_program 5jmzup: 添加M3到模型选项
-- ============================================================
UPDATE `pricing_program`
SET `pricing_spec` = 'fields:\n  model:\n    type: str\n    label: 模型\n    options:\n      - MiniMax-M3\n      - MiniMax-M2.7\n      - MiniMax-M2.7-highspeed\n      - MiniMax-M2.5\n      - MiniMax-M2.5-highspeed\n      - M2-her\n  formula:\n    type: str\n    label: 公式\n'
WHERE `id` = '5jmzupARABxkDFwUraFiQ';


-- ============================================================
-- ROLLBACK 语句 (如需回滚)
-- ============================================================
-- DELETE FROM `httpapi` WHERE `id` = 'mm3_openai_t2t';
-- DELETE FROM `llm` WHERE `id` IN ('mm3_MiniMax_M3', 'mm_m27_highspeed');
-- DELETE FROM `llm_api_map` WHERE `id` IN ('mm3_map_t2t', 'mm_m27hs_map_t2t');
-- UPDATE `llm_api_map` SET `ppid` = NULL WHERE `llmid` = 'AU1f40HV3tqFjxcVWWpyR';
-- UPDATE `llm_api_map` SET `ppid` = NULL WHERE `llmid` = 'oks-VG9D8p2b0Agvs-LeQ';
-- UPDATE `llm_api_map` SET `ppid` = NULL WHERE `llmid` = 'ns7egG9aXi91wjI62yKfu';
-- UPDATE `llm_api_map` SET `ppid` = NULL WHERE `llmid` = 'q6rdMUsGD1z3S3NyZh_A_';
-- UPDATE `llm_api_map` SET `ppid` = NULL WHERE `llmid` = 'CEYD4YWRxjCj4k_6bpzIM';
-- UPDATE `llm_api_map` SET `ppid` = NULL WHERE `llmid` = 'Si2g0XJ9ym3P5jlrdmcfB';
-- DELETE FROM `pricing_program` WHERE `id` = 'mm_tts_pricing';
-- DELETE FROM `pricing_program_timing` WHERE `id` = 'mm_tts_timing';
-- -- 5jmzup的pricing_data CONCAT追加需手动编辑YAML移除M3条目
