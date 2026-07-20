-- ============================================================
--
-- Kimi K3 (月之暗面 / Moonshot) 完整注册
-- 生成时间: 2026-07-20
-- 模型: kimi-k3
-- 依赖: kimi_k3_uapi.sql (uapi 'kimi_t2t' 已创建)
-- ============================================================
-- 前置条件:
--   modelprovider 已有记录: id='0OkxCHYbZOdD_W_o5N9tN', name='moonshot'
--   uapi 已有记录: id='kimi_t2t' (由 kimi_k3_uapi.sql 创建)
--   uapi 已有记录: id='oL9cufrcRb7SPfH11Ra62' (tm2t, moonshot 通用多模态)
--   uapiio 已有记录: id='Is8l4TGkcZcqFSjbbeIK2' (文本会话)
--   uapiio 已有记录: id='t-ujII59ku45tIPcdXu4O' (文本媒体转文本)
-- ============================================================

-- ============================================================
-- 1. 新增 llm: kimi-k3 模型注册
-- ============================================================
INSERT IGNORE INTO `llm` (`id`, `name`, `model`, `description`, `iconid`, `upappid`, `providerid`, `ownerid`, `enabled_date`, `expired_date`, `min_balance`, `status`)
VALUES (
  'kimi-k3-llm',
  'kimi-k3',
  'kimi-k3',
  '月之暗面 Kimi K3，支持多模态(图片/视频)输入，兼容 OpenAI Chat Completions 格式，支持深度思考模式',
  'moonshot',
  'upapp_moonshot',
  '0OkxCHYbZOdD_W_o5N9tN',
  '0',
  '2026-07-20',
  '9999-12-31',
  10.00,
  'published'
);

-- ============================================================
-- 2. 新增 llm_api_map: t2t (纯文本对话)
-- ============================================================
INSERT IGNORE INTO `llm_api_map` (`id`, `llmid`, `llmcatelogid`, `apiname`, `query_apiname`, `query_period`, `ppid`, `isdefaultcatelog`)
VALUES (
  'kimi_k3_map_t2t',
  'kimi-k3-llm',
  't2t',
  't2t',
  NULL,
  30,
  NULL,
  '1'
);

-- ============================================================
-- 3. 新增 llm_api_map: tm2t (多模态对话, 文本+图片+视频)
-- ============================================================
INSERT IGNORE INTO `llm_api_map` (`id`, `llmid`, `llmcatelogid`, `apiname`, `query_apiname`, `query_period`, `ppid`, `isdefaultcatelog`)
VALUES (
  'kimi_k3_map_tm2t',
  'kimi-k3-llm',
  'vision',
  'tm2t',
  NULL,
  30,
  NULL,
  '1'
);

-- ============================================================
-- 验证 (执行后运行确认)
-- ============================================================
-- SELECT m.id, m.llmid, m.llmcatelogid, m.apiname, m.ppid,
--        l.name as model_name, l.model, l.status
-- FROM llm_api_map m
-- JOIN llm l ON m.llmid = l.id
-- WHERE m.llmid = 'kimi-k3-llm';
--
-- 预期: 2 行 (t2t + tm2t/vision)

-- SELECT id, name, model, status, providerid, upappid
-- FROM llm WHERE id = 'kimi-k3-llm';
--
-- 预期: 1 行, status='published'

-- ============================================================
-- 回滚
-- ============================================================
-- DELETE FROM llm_api_map WHERE id IN ('kimi_k3_map_t2t', 'kimi_k3_map_tm2t');
-- DELETE FROM llm WHERE id = 'kimi-k3-llm';
