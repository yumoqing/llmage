-- Add permissions for llm_api_map management files
-- Run this SQL in the Sage database to grant access to new llm_api_map endpoints
-- After inserting, assign these permissions to roles via:
--   python ~/repos/sage/script/set_role_perm.py <role_name> /llm_api_map_manage.ui

INSERT INTO permission (id, path) 
SELECT REPLACE(UUID(), '-', ''), '/llm_api_map_manage.ui' 
WHERE NOT EXISTS (SELECT 1 FROM permission WHERE path = '/llm_api_map_manage.ui');

INSERT INTO permission (id, path) 
SELECT REPLACE(UUID(), '-', ''), '/api/llm_api_map_list.dspy' 
WHERE NOT EXISTS (SELECT 1 FROM permission WHERE path = '/api/llm_api_map_list.dspy');

INSERT INTO permission (id, path) 
SELECT REPLACE(UUID(), '-', ''), '/api/llm_api_map_create.dspy' 
WHERE NOT EXISTS (SELECT 1 FROM permission WHERE path = '/api/llm_api_map_create.dspy');

INSERT INTO permission (id, path) 
SELECT REPLACE(UUID(), '-', ''), '/api/llm_api_map_delete.dspy' 
WHERE NOT EXISTS (SELECT 1 FROM permission WHERE path = '/api/llm_api_map_delete.dspy');

INSERT INTO permission (id, path) 
SELECT REPLACE(UUID(), '-', ''), '/api/llm_api_map_options.dspy' 
WHERE NOT EXISTS (SELECT 1 FROM permission WHERE path = '/api/llm_api_map_options.dspy');

INSERT INTO permission (id, path) 
SELECT REPLACE(UUID(), '-', ''), '/api/uapi_options.dspy' 
WHERE NOT EXISTS (SELECT 1 FROM permission WHERE path = '/api/uapi_options.dspy');
