-- ============================================================
-- Kimi K3 API 接入 (月之暗面 / Moonshot)
-- Base URL: https://api.moonshot.cn/v1
-- 兼容 OpenAI 格式, 文档: https://platform.kimi.com/docs/api/chat
-- 多模态: 图片/视频通过 webpath_to_base64() 转 data URI
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
  -- === data 模板 ===
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
{% if images or videos %}{# === 多模态: 构造 content 数组 === #}
{% set content_parts = [] %}
{% if prompt %}
{% do content_parts.append({"type": "text", "text": prompt}) %}
{% endif %}
{% for img in images %}
{% set img_b64 = rfexe("webpath_to_base64", img) %}
{% if img_b64 %}
{% do content_parts.append({"type": "image_url", "image_url": img_b64}) %}
{% endif %}
{% endfor %}
{% for vid in videos %}
{% set vid_b64 = rfexe("webpath_to_base64", vid) %}
{% if vid_b64 %}
{% do content_parts.append({"type": "video_url", "video_url": vid_b64}) %}
{% endif %}
{% endfor %}
    "messages": [
{% if sys_prompt %}
        {"role": "system", "content": {{json.dumps(sys_prompt, ensure_ascii=False)}}},
{% endif %}
        {"role": "user", "content": {{json.dumps(content_parts, ensure_ascii=False)}}}
    ],
{% else %}{# === 纯文本 === #}
    "messages": [
{% if sys_prompt %}
        {"role": "system", "content": {{json.dumps(sys_prompt, ensure_ascii=False)}}},
{% endif %}
        {"role": "user", "content": {{json.dumps(prompt, ensure_ascii=False)}}}
    ],
{% endif %}
{% endif %}
{% if stream %}
    "stream":true,
{% endif %}
    "model": "{{model}}",
    "reasoning_effort": "max"
}',
  -- === response 模板 ===
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
