-- ============================================================
-- Kimi K3 API 接入 (月之暗面 / Moonshot)
-- Base URL: https://api.moonshot.cn/v1
-- 兼容 OpenAI 格式, 文档: https://platform.kimi.com/docs/api/chat
-- ============================================================

-- ============================================================
-- 0. 前置: modelprovider / upapp (如不存在先创建)
-- ============================================================
-- INSERT IGNORE INTO modelprovider (id, name) VALUES ('moonshot', '月之暗面');
-- INSERT IGNORE INTO upapp (id, name, `key`, baseurl, enabled_date)
--   VALUES ('upapp_moonshot', '月之暗面', 'MOONSHOT_API_KEY', 'https://api.moonshot.cn', '2026-07-17');
SET @upapp_id = 'upapp_moonshot';   -- 替换为实际的月之暗面 upapp.id

-- ============================================================
-- 1. uapiio — 文件管理输入输出定义
-- ============================================================
REPLACE INTO `uapiio` (`id`, `name`, `description`, `input_fields`) VALUES
('kimi_file_upload_io', 'kimi文件上传', 'Kimi文件上传 multipart/form-data', '[]'),
('kimi_file_list_io', 'kimi文件列表', 'Kimi文件列表查询', '[]'),
('kimi_file_retrieve_io', 'kimi文件详情', 'Kimi文件元数据查询', '[]'),
('kimi_file_delete_io', 'kimi文件删除', 'Kimi文件删除', '[]'),
('kimi_file_content_io', 'kimi文件内容', 'Kimi文件内容提取', '[]');

-- ============================================================
-- 2. Chat Completions — POST /v1/chat/completions
--    t2t 复用已有 ioid Is8l4TGkcZcqFSjbbeIK2 (文本会话)
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
        {"role": "user", "content": {{json.dumps(prompt, ensure_ascii=False)}}}
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

-- ============================================================
-- 3. 上传文件 POST /v1/files
-- ============================================================
REPLACE INTO `uapi` (`id`, `name`, `need_auth`, `stream`, `path`, `httpmethod`, `chunk_match`, `headers`, `params`, `data`, `response`, `ioid`, `callbackurl`, `upappid`)
VALUES (
  'kimi_file_upload', 'file_upload', '0', 'none',
  '/files', 'POST', NULL,
  '{"Authorization": "Bearer {{apikey}}"}',
  NULL, NULL,
  '{"id": "{{id}}", "object": "{{object}}", "filename": "{{filename}}", "purpose": "{{purpose}}", "bytes": {{bytes}}, "created_at": {{created_at}}, "status": "{{status}}"}',
  'kimi_file_upload_io', NULL, @upapp_id
);

-- ============================================================
-- 4. 列出文件 GET /v1/files
-- ============================================================
REPLACE INTO `uapi` (`id`, `name`, `need_auth`, `stream`, `path`, `httpmethod`, `chunk_match`, `headers`, `params`, `data`, `response`, `ioid`, `callbackurl`, `upappid`)
VALUES (
  'kimi_file_list', 'file_list', '0', 'none',
  '/files', 'GET', NULL,
  '{"Authorization": "Bearer {{apikey}}"}',
  NULL, NULL,
  '{"object": "{{object}}", "data": {{json.dumps(data)}}}',
  'kimi_file_list_io', NULL, @upapp_id
);

-- ============================================================
-- 5. 文件详情 GET /v1/files/{file_id}
-- ============================================================
REPLACE INTO `uapi` (`id`, `name`, `need_auth`, `stream`, `path`, `httpmethod`, `chunk_match`, `headers`, `params`, `data`, `response`, `ioid`, `callbackurl`, `upappid`)
VALUES (
  'kimi_file_retrieve', 'file_retrieve', '0', 'none',
  '/files/{{file_id}}', 'GET', NULL,
  '{"Authorization": "Bearer {{apikey}}"}',
  NULL, NULL,
  '{"id": "{{id}}", "object": "{{object}}", "filename": "{{filename}}", "purpose": "{{purpose}}", "bytes": {{bytes}}, "created_at": {{created_at}}, "status": "{{status}}", "status_details": "{{status_details}}"}',
  'kimi_file_retrieve_io', NULL, @upapp_id
);

-- ============================================================
-- 6. 删除文件 DELETE /v1/files/{file_id}
-- ============================================================
REPLACE INTO `uapi` (`id`, `name`, `need_auth`, `stream`, `path`, `httpmethod`, `chunk_match`, `headers`, `params`, `data`, `response`, `ioid`, `callbackurl`, `upappid`)
VALUES (
  'kimi_file_delete', 'file_delete', '0', 'none',
  '/files/{{file_id}}', 'DELETE', NULL,
  '{"Authorization": "Bearer {{apikey}}"}',
  NULL, NULL,
  '{"id": "{{id}}", "object": "{{object}}", "deleted": {{deleted}}}',
  'kimi_file_delete_io', NULL, @upapp_id
);

-- ============================================================
-- 7. 文件内容 GET /v1/files/{file_id}/content
-- ============================================================
REPLACE INTO `uapi` (`id`, `name`, `need_auth`, `stream`, `path`, `httpmethod`, `chunk_match`, `headers`, `params`, `data`, `response`, `ioid`, `callbackurl`, `upappid`)
VALUES (
  'kimi_file_content', 'file_content', '0', 'none',
  '/files/{{file_id}}/content', 'GET', NULL,
  '{"Authorization": "Bearer {{apikey}}"}',
  NULL, NULL,
  '{"content": "{{content}}"}',
  'kimi_file_content_io', NULL, @upapp_id
);
