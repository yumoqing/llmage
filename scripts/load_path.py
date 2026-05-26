#!/usr/bin/env python3
"""
llmage 模块 RBAC 权限管理脚本

使用方法:
    cd ~/repos/sage
    ./py3/bin/python ~/repos/llmage/scripts/load_path.py

每次代码变更如有新 path 出现，需同步更新此脚本。
"""

import subprocess
import os
import sys

def find_sage_root():
    candidates = [
        os.path.expanduser("~/repos/sage"),
        os.path.expanduser("~/sage"),
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    ]
    for c in candidates:
        if os.path.isdir(os.path.join(c, "py3")) and os.path.isdir(os.path.join(c, "wwwroot")):
            return c
    return None

SAGE_ROOT = find_sage_root()
if not SAGE_ROOT:
    print("ERROR: Cannot find Sage root directory")
    sys.exit(1)

PYTHON = os.path.join(SAGE_ROOT, "py3", "bin", "python")
SET_PERM_SCRIPT = os.path.join(SAGE_ROOT, "set_role_perm.py")

MOD = "llmage"

# ============================================================
# 权限路径定义 — 每次新增页面或API时同步更新
# ============================================================

# any — 无需登录（仅静态资源和菜单）
PATHS_ANY = [
    f"/{MOD}/menu.ui",
    f"/{MOD}/imgs",
    f"/{MOD}/imgs/kdb.svg",
    f"/{MOD}/list_catelog_models.dspy",
]

# logined — 需要认证的页面和 API
PATHS_LOGINED = [
    # Module entry
    f"/{MOD}",

    # Top-level pages and APIs
    f"/{MOD}/llmcost.dspy",
    f"/{MOD}/llminference.dspy",
    f"/{MOD}/llm_dialog.ui",
    f"/{MOD}/show_same_catelog_llm.ui",
    f"/{MOD}/model_estimate.dspy",
    f"/{MOD}/show_llms.ui",
    f"/{MOD}/llmcheck.dspy",
    f"/{MOD}/show_llms_by_providers.ui",
    f"/{MOD}/list_paging_catelog_llms.dspy",

    # llmusage CRUD directory
    f"/{MOD}/llmusage",
    f"/{MOD}/llmusage/update_llmusage.dspy",
    f"/{MOD}/llmusage/delete_llmusage.dspy",
    f"/{MOD}/llmusage/add_llmusage.dspy",
    f"/{MOD}/llmusage/index.ui",
    f"/{MOD}/llmusage/get_llmusage.dspy",

    # llmcatelog CRUD directory
    f"/{MOD}/llmcatelog",
    f"/{MOD}/llmcatelog/add_llmcatelog.dspy",
    f"/{MOD}/llmcatelog/get_llmcatelog.dspy",
    f"/{MOD}/llmcatelog/delete_llmcatelog.dspy",
    f"/{MOD}/llmcatelog/index.ui",
    f"/{MOD}/llmcatelog/update_llmcatelog.dspy",

    # llm CRUD directory
    f"/{MOD}/llm",
    f"/{MOD}/llm/update_llm.dspy",
    f"/{MOD}/llm/delete_llm.dspy",
    f"/{MOD}/llm/index.ui",
    f"/{MOD}/llm/get_llm.dspy",
    f"/{MOD}/llm/add_llm.dspy",

    # API endpoints
    f"/{MOD}/api/llm_list.dspy",
    f"/{MOD}/api/llm_create.dspy",
    f"/{MOD}/api/llm_update.dspy",
    f"/{MOD}/api/llm_delete.dspy",
    f"/{MOD}/api/get_organizations.dspy",
    f"/{MOD}/api/get_upapps.dspy",
    f"/{MOD}/api/llm_api_map_list.dspy",
    f"/{MOD}/api/llm_api_map_create.dspy",
    f"/{MOD}/api/llm_api_map_delete.dspy",
    f"/{MOD}/api/llm_api_map_options.dspy",
    f"/{MOD}/api/uapi_options.dspy",
    f"/{MOD}/api/failed_accounting_list.dspy",
    f"/{MOD}/api/llmusage_accounting_failed_create.dspy",
    f"/{MOD}/api/llmusage_accounting_failed_update.dspy",
    f"/{MOD}/api/llmusage_accounting_failed_delete.dspy",
    f"/{MOD}/api/llmusage_create.dspy",
    f"/{MOD}/api/llmusage_update.dspy",
    f"/{MOD}/api/llmusage_delete.dspy",

    # v1 API endpoints
    f"/{MOD}/v1/chat/completions",
    f"/{MOD}/v1/chat/completions/index.dspy",
    f"/{MOD}/v1/models",
    f"/{MOD}/v1/models/index.dspy",
    f"/{MOD}/v1/tasks",
    f"/{MOD}/v1/tasks/index.dspy",
    f"/{MOD}/v1/video/generations",
    f"/{MOD}/v1/video/generations/index.dspy",
    f"/{MOD}/v1/image/generations",
    f"/{MOD}/v1/image/generations/index.dspy",
]

# ============================================================
# 执行注册
# ============================================================

def run_set_perm(role, path):
    cmd = [PYTHON, SET_PERM_SCRIPT, role, path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def register_role_paths(role, paths):
    count = 0
    for p in paths:
        if run_set_perm(role, p):
            count += 1
    print(f"  {role}: {count}/{len(paths)} paths registered")
    return count

def main():
    print(f"Sage root: {SAGE_ROOT}")
    total = 0
    total += register_role_paths("any", PATHS_ANY)
    total += register_role_paths("logined", PATHS_LOGINED)
    print(f"\nDone. Total {total} permission entries registered.")
    print("NOTE: Restart Sage after permission changes to reload RBAC cache.")

if __name__ == "__main__":
    main()
