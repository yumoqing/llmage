-- ============================================================
-- Kimi K3 API 接入 (月之暗面 / Moonshot)
-- Base URL: https://api.moonshot.cn/v1
-- 兼容 OpenAI 格式
-- 文档: https://platform.kimi.com/docs/api/chat
-- ============================================================

-- ============================================================
-- 1. 确认 modelprovider 和 upapp 存在
-- ============================================================
-- INSERT IGNORE INTO modelprovider (id, name) VALUES ('<provider_id>', '月之暗面');
-- INSERT IGNORE INTO upapp (id, name, key, baseurl, enabled_date) VALUES ('<upapp_id>', '月之暗面', 'MOONSHOT_API_KEY', 'https://api.moonshot.cn', '2026-07-17');

-- ============================================================
-- 2. Chat Completions (对话补全) — OpenAI 兼容，支持流式
--    POST /v1/chat/completions
-- ============================================================
REPLACE INTO `uapi` (`id`, `name`, `need_auth`, `stream`, `path`, `httpmethod`, `chunk_match`, `headers`, `params`, `data`, `response`, `ioid`, `callbackurl`, `upappid`)
VALUES (
  'kimi_t2t',
  't2t',
  '0',
  'stream',
  '/chat/completions',
  'POST',
  'data: ',
  '{
    "Authorization": "Bearer {{apikey}}",
    "Content-Type": "application/json"
}',
  NULL,
  '{
{% if stream %}
    "stream_options":{
        "include_usage": true
    },
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
        {
            "role": "system",
            "content": {{json.dumps(sys_prompt, ensure_ascii=False)}}
        },
{% endif %}
        {
            "role": "user",
            "content": {{json.dumps(prompt, ensure_ascii=False)}}
        }
    ],
{% endif %}
{% if stream %}
    "stream":true,
{% endif %}
    "model": "{{model}}",
    "reasoning_effort": "max"
}
',
  '{
    "id": "{{id}}",
    "object": "{{object}}",
    "created": {{created}},
    "choices": {{json.dumps(choices, ensure_ascii=False)}},
    "model": "{{model}}",
{% if object == "chat.completion" %}
    "reasoning_content": {{json.dumps(choices[0].message.reasoning_content, ensure_ascii=False)}},
    "content":{{json.dumps(choices[0].message.content, ensure_ascii=False)}},
{% elif len(choices)>0 %}
    "reasoning_content": {{json.dumps(choices[0].delta.reasoning_content, ensure_ascii=False)}},
    "content":{{json.dumps(choices[0].delta.content, ensure_ascii=False)}},
{% endif %}
{% if usage %}
{% set usage1 = usage.update({"model": model}) %}
    "finish": "1",
    "usage":{{json.dumps(usage)}}
{% else %}
    "finish":"0"
{% endif %}
}
',
  'Is8l4TGkcZcqFSjbbeIK2',  -- 复用文本会话 ioid
  NULL,
  '<upapp_id>'              -- 替换为月之暗面的 upapp.id
);

-- ============================================================
-- 3. 上传文件 POST /v1/files (multipart/form-data)
-- ============================================================
REPLACE INTO `uapi` (`id`, `name`, `need_auth`, `stream`, `path`, `httpmethod`, `chunk_match`, `headers`, `params`, `data`, `response`, `ioid`, `callbackurl`, `upappid`)
VALUES (
  'kimi_file_upload',
  'file_upload',
  '0',
  'none',
  '/files',
  'POST',
  NULL,
  '{
    "Authorization": "Bearer {{apikey}}"
}',
  NULL,
  NULL,   -- multipart 由 Sage 框架自动处理
  '{
    "id": "{{id}}",
    "object": "{{object}}",
    "filename": "{{filename}}",
    "purpose": "{{purpose}}",
    "bytes": {{bytes}},
    "created_at": {{created_at}},
    "status": "{{status}}"
}',
  '<ioid_file>',   -- 需新建 file_upload ioid
  NULL,
  '<upapp_id>'
);

-- ============================================================
-- 4. 列出文件 GET /v1/files
-- ============================================================
REPLACE INTO `uapi` (`id`, `name`, `need_auth`, `stream`, `path`, `httpmethod`, `chunk_match`, `headers`, `params`, `data`, `response`, `ioid`, `callbackurl`, `upappid`)
VALUES (
  'kimi_file_list',
  'file_list',
  '0',
  'none',
  '/files',
  'GET',
  NULL,
  '{
    "Authorization": "Bearer {{apikey}}"
}',
  NULL,
  NULL,
  '{
    "object": "{{object}}",
    "data": {{json.dumps(data)}}
}',
  '<ioid_file_list>',   -- 需新建 ioid
  NULL,
  '<upapp_id>'
);

-- ============================================================
-- 5. 文件详情 GET /v1/files/{file_id}
-- ============================================================
REPLACE INTO `uapi` (`id`, `name`, `need_auth`, `stream`, `path`, `httpmethod`, `chunk_match`, `headers`, `params`, `data`, `response`, `ioid`, `callbackurl`, `upappid`)
VALUES (
  'kimi_file_retrieve',
  'file_retrieve',
  '0',
  'none',
  '/files/{{file_id}}',
  'GET',
  NULL,
  '{
    "Authorization": "Bearer {{apikey}}"
}',
  NULL,
  NULL,
  '{
    "id": "{{id}}",
    "object": "{{object}}",
    "filename": "{{filename}}",
    "purpose": "{{purpose}}",
    "bytes": {{bytes}},
    "created_at": {{created_at}},
    "status": "{{status}}",
    "status_details": "{{status_details}}"
}',
  '<ioid_file_info>',   -- 需新建 ioid
  NULL,
  '<upapp_id>'
);

-- ============================================================
-- 6. 删除文件 DELETE /v1/files/{file_id}
-- ============================================================
REPLACE INTO `uapi` (`id`, `name`, `need_auth`, `stream`, `path`, `httpmethod`, `chunk_match`, `headers`, `params`, `data`, `response`, `ioid`, `callbackurl`, `upappid`)
VALUES (
  'kimi_file_delete',
  'file_delete',
  '0',
  'none',
  '/files/{{file_id}}',
  'DELETE',
  NULL,
  '{
    "Authorization": "Bearer {{apikey}}"
}',
  NULL,
  NULL,
  '{
    "id": "{{id}}",
    "object": "{{object}}",
    "deleted": {{deleted}}
}',
  '<ioid_file_delete>',   -- 需新建 ioid
  NULL,
  '<upapp_id>'
);

-- ============================================================
-- 7. 文件内容 GET /v1/files/{file_id}/content
-- ============================================================
REPLACE INTO `uapi` (`id`, `name`, `need_auth`, `stream`, `path`, `httpmethod`, `chunk_match`, `headers`, `params`, `data`, `response`, `ioid`, `callbackurl`, `upappid`)
VALUES (
  'kimi_file_content',
  'file_content',
  '0',
  'none',
  '/files/{{file_id}}/content',
  'GET',
  NULL,
  '{
    "Authorization": "Bearer {{apikey}}"
}',
  NULL,
  NULL,
  '{
    "content": "{{content}}"
}',
  '<ioid_file_content>',   -- 需新建 ioid
  NULL,
  '<upapp_id>'
);
