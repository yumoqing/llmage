-- ============================================================
-- Kimi K3 API 接入 (月之暗面 / Moonshot)
-- Base URL: https://api.moonshot.cn/v1
-- 兼容 OpenAI 格式, 文档: https://platform.kimi.com/docs/api/chat
-- 多模态: image_files/video_files 在 data 模板中用纯 Jinja2 构造 content 数组
-- ============================================================

-- ============================================================
-- 0. 前置: modelprovider / upapp (如不存在先创建)
-- ============================================================
-- INSERT IGNORE INTO modelprovider (id, name) VALUES ('moonshot', '月之暗面');
-- INSERT IGNORE INTO upapp (id, name, `key`, baseurl, enabled_date)
--   VALUES ('upapp_moonshot', '月之暗面', 'MOONSHOT_API_KEY', 'https://api.moonshot.cn', '2026-07-17');
SET @upapp_id = 'upapp_moonshot';   -- 替换为实际的月之暗面 upapp.id

-- ============================================================
-- Chat Completions — POST /v1/chat/completions
--   支持纯文本 + 多模态(图片/视频 base64)
--   ioid 复用 Is8l4TGkcZcqFSjbbeIK2 (文本会话)
-- ============================================================
REPLACE INTO `uapi` (`id`, `name`, `need_auth`, `stream`, `path`, `httpmethod`, `chunk_match`, `headers`, `params`, `data`, `response`, `ioid`, `callbackurl`, `upappid`)
VALUES (
  'kimi_t2t', 't2t', '0', 'stream',
  '/chat/completions', 'POST', 'data: ',
  '{"Authorization": "Bearer {{apikey}}", "Content-Type": "application/json"}',
  NULL,
  '{
{% if stream %}
    "stream_options":{"include_usage": true},
{% endif %}
{% if tools %}
    "tools": {{json.dumps(tools, ensure_ascii=False)}},
{% endif %}
{% if tool_choice %}
    "tool_choice": "{{tool_choice}}",
{% endif %}
{% if messages %}
    "messages": {{json.dumps(messages, ensure_ascii=False)}},
{% else %}
    "messages": [
{% if sys_prompt %}
        {"role": "system", "content": {{json.dumps(sys_prompt, ensure_ascii=False)}}},
{% endif %}
{% set _parts = [] %}
{% if prompt %}
{% set _ = _parts.append({"type": "text", "text": prompt}) %}
{% endif %}
{% if image_files %}
{% for _f in image_files %}
{% set _fp = FileStorage().realPath(_f) %}
{% if os.path.isfile(_fp) %}
{% set _mime = file_mime(_fp) %}
{% set _b64 = file_to_b64(_fp) %}
{% set _ = _parts.append({"type": "image_url", "image_url": "data:" + _mime + ";base64," + _b64}) %}
{% endif %}
{% endfor %}
{% endif %}
{% if video_files %}
{% for _f in video_files %}
{% set _fp = FileStorage().realPath(_f) %}
{% if os.path.isfile(_fp) %}
{% set _mime = file_mime(_fp) %}
{% set _b64 = file_to_b64(_fp) %}
{% set _ = _parts.append({"type": "video_url", "video_url": "data:" + _mime + ";base64," + _b64}) %}
{% endif %}
{% endfor %}
{% endif %}
        {"role": "user", "content": {{json.dumps(_parts, ensure_ascii=False)}}}
    ],
{% endif %}
{% if stream %}
    "stream":true,
{% endif %}
    "model": "{{model}}",
    "reasoning_effort": "max"
}',
  '{
    "id": "{{id}}", "object": "{{object}}", "created": {{created}},
    "choices": {{json.dumps(choices, ensure_ascii=False)}}, "model": "{{model}}",
{% if object == "chat.completion" %}
    "reasoning_content": {{json.dumps(choices[0].message.reasoning_content, ensure_ascii=False)}},
    "content":{{json.dumps(choices[0].message.content, ensure_ascii=False)}},
{% elif len(choices)>0 %}
    "reasoning_content": {{json.dumps(choices[0].delta.reasoning_content, ensure_ascii=False)}},
    "content":{{json.dumps(choices[0].delta.content, ensure_ascii=False)}},
{% endif %}
{% if usage %}{% set usage1 = usage.update({"model": model}) %}
    "finish": "1", "usage":{{json.dumps(usage)}}
{% else %}
    "finish":"0"
{% endif %}}',
  'Is8l4TGkcZcqFSjbbeIK2', NULL, @upapp_id
);
