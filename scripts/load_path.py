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
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
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

# any — 无需登录（菜单、静态资源）
PATHS_ANY = [
    f"/{MOD}/menu.ui",
    f"/{MOD}/imgs/kdb.svg",
]

# logined — 所有已登录用户
PATHS_LOGINED = [
    # 模块入口
    f"/{MOD}",
    f"/{MOD}/index.ui",

    # 顶层 .ui 页面
    f"/{MOD}/api_doc.ui",
    f"/{MOD}/api_doc.md",
    f"/{MOD}/llm_dialog.ui",
    f"/{MOD}/llm_launch_check.ui",
    f"/{MOD}/show_same_catelog_llm.ui",
    f"/{MOD}/show_llms.ui",
    f"/{MOD}/show_llms_by_providers.ui",
    f"/{MOD}/model_plaza.ui",
    f"/{MOD}/failed_accounting.ui",
    f"/{MOD}/llmcatelog_list.ui",

    # 顶层 .dspy（非 api/ 目录）
    f"/{MOD}/get_accounting_llmusages.dspy",
    f"/{MOD}/get_asynctask_status.dspy",
    f"/{MOD}/get_my_asynctasks.dspy",
    f"/{MOD}/get_type_llms.dspy",
    f"/{MOD}/grap_task_status.dspy",
    f"/{MOD}/list_catelog_models.dspy",
    f"/{MOD}/list_paging_catelog_llms.dspy",
    f"/{MOD}/llmaccounting.dspy",
    f"/{MOD}/llmcheck.dspy",
    f"/{MOD}/llmcost.dspy",
    f"/{MOD}/llminference.dspy",
    f"/{MOD}/model_estimate.dspy",
    f"/{MOD}/query_orders.dspy",
    f"/{MOD}/query_price.dspy",
    f"/{MOD}/test_llm_charging.dspy",
    f"/{MOD}/vidu_callback.dspy",
    f"/{MOD}/vidu_inference.dspy",

    # api/ 目录
    f"/{MOD}/api/failed_accounting_list.dspy",
    f"/{MOD}/api/get_apis.dspy",
    f"/{MOD}/api/get_catelogs.dspy",
    f"/{MOD}/api/get_organizations.dspy",
    f"/{MOD}/api/get_ppids.dspy",
    f"/{MOD}/api/get_search_providerid.dspy",
    f"/{MOD}/api/get_search_upappid.dspy",
    f"/{MOD}/api/get_upapps.dspy",
    f"/{MOD}/api/llm_launch_check_api.dspy",
    f"/{MOD}/api/llm_api_map_create.dspy",
    f"/{MOD}/api/llm_api_map_delete.dspy",
    f"/{MOD}/api/llm_api_map_list.dspy",
    f"/{MOD}/api/llm_api_map_options.dspy",
    f"/{MOD}/api/llm_catelog_options.dspy",
    f"/{MOD}/api/llm_create.dspy",
    f"/{MOD}/api/llm_delete.dspy",
    f"/{MOD}/api/llm_status_update.dspy",
    f"/{MOD}/api/llm_update.dspy",
    f"/{MOD}/api/llmcatelog_create.dspy",
    f"/{MOD}/api/llmcatelog_delete.dspy",
    f"/{MOD}/api/llmcatelog_list.dspy",
    f"/{MOD}/api/llmcatelog_update.dspy",
    f"/{MOD}/api/llmusage_accounting_failed_create.dspy",
    f"/{MOD}/api/llmusage_accounting_failed_delete.dspy",
    f"/{MOD}/api/llmusage_accounting_failed_update.dspy",
    f"/{MOD}/api/llmusage_create.dspy",
    f"/{MOD}/api/llmusage_delete.dspy",
    f"/{MOD}/api/llmusage_history_create.dspy",
    f"/{MOD}/api/llmusage_history_delete.dspy",
    f"/{MOD}/api/llmusage_history_update.dspy",
    f"/{MOD}/api/llmusage_update.dspy",
    f"/{MOD}/api/retry_accounting.dspy",
    f"/{MOD}/api/uapi_options.dspy",

    # CRUD 子目录 — llm/
    f"/{MOD}/llm/index.ui",
    f"/{MOD}/llm/add_llm.dspy",
    f"/{MOD}/llm/delete_llm.dspy",
    f"/{MOD}/llm/get_llm.dspy",
    f"/{MOD}/llm/update_llm.dspy",

    # CRUD 子目录 — llm_api_map/
    f"/{MOD}/llm_api_map/index.ui",
    f"/{MOD}/llm_api_map/add_llm_api_map.dspy",
    f"/{MOD}/llm_api_map/delete_llm_api_map.dspy",
    f"/{MOD}/llm_api_map/get_llm_api_map.dspy",
    f"/{MOD}/llm_api_map/update_llm_api_map.dspy",

    # CRUD 子目录 — llmcatelog_list/ (alias for llmcatelog)
    f"/{MOD}/llmcatelog_list/index.ui",
    f"/{MOD}/llmcatelog_list/add_llmcatelog.dspy",
    f"/{MOD}/llmcatelog_list/delete_llmcatelog.dspy",
    f"/{MOD}/llmcatelog_list/get_llmcatelog.dspy",
    f"/{MOD}/llmcatelog_list/update_llmcatelog.dspy",

    # CRUD 子目录 — llmusage/
    f"/{MOD}/llmusage/index.ui",
    f"/{MOD}/llmusage/add_llmusage.dspy",
    f"/{MOD}/llmusage/delete_llmusage.dspy",
    f"/{MOD}/llmusage/get_llmusage.dspy",
    f"/{MOD}/llmusage/update_llmusage.dspy",

    # CRUD 子目录 — llmusage_accounting_failed/
    f"/{MOD}/llmusage_accounting_failed/index.ui",
    f"/{MOD}/llmusage_accounting_failed/add_llmusage_accounting_failed.dspy",
    f"/{MOD}/llmusage_accounting_failed/delete_llmusage_accounting_failed.dspy",
    f"/{MOD}/llmusage_accounting_failed/get_llmusage_accounting_failed.dspy",
    f"/{MOD}/llmusage_accounting_failed/update_llmusage_accounting_failed.dspy",

    # CRUD 子目录 — llmusage_history/
    f"/{MOD}/llmusage_history/index.ui",
    f"/{MOD}/llmusage_history/add_llmusage_history.dspy",
    f"/{MOD}/llmusage_history/delete_llmusage_history.dspy",
    f"/{MOD}/llmusage_history/get_llmusage_history.dspy",
    f"/{MOD}/llmusage_history/update_llmusage_history.dspy",

    # v1 API 目录
    f"/{MOD}/v1/chat/completions/index.dspy",
    f"/{MOD}/v1/image/generations/index.dspy",
    f"/{MOD}/v1/models/catelog.dspy",
    f"/{MOD}/v1/models/index.dspy",
    f"/{MOD}/v1/tasks/index.dspy",
    f"/{MOD}/v1/video/generations/index.dspy",
    f"/{MOD}/v1/music/generations/index.dspy",
    f"/{MOD}/v1/audio/speech/index.dspy",
    f"/{MOD}/v1/audio/transcriptions/index.dspy",

    # 其他子目录
    f"/{MOD}/list_llmcatelogs/index.dspy",
    f"/{MOD}/list_llms/index.dspy",
    f"/{MOD}/openai/index.dspy",
    f"/{MOD}/t2t/index.dspy",
    f"/{MOD}/tasks/index.dspy",
    f"/{MOD}/upload_asset/index.dspy",
    f"/{MOD}/video/index.dspy",
]

# ============================================================
# 客户角色 — v1 API 调用权限
# ============================================================

PATHS_V1_CUSTOMER = [
    f"/{MOD}/v1/chat/completions/index.dspy",
    f"/{MOD}/v1/video/generations/index.dspy",
    f"/{MOD}/v1/image/generations/index.dspy",
    f"/{MOD}/v1/music/generations/index.dspy",
    f"/{MOD}/v1/audio/speech/index.dspy",
    f"/{MOD}/v1/audio/transcriptions/index.dspy",
    f"/{MOD}/v1/models/index.dspy",
    f"/{MOD}/v1/tasks/index.dspy",
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
    # 客户角色 — v1 API 调用权限
    for role in ["customer.admin", "customer.user"]:
        total += register_role_paths(role, PATHS_V1_CUSTOMER)
    print(f"\nDone. Total {total} permission entries registered.")
    print("NOTE: Restart Sage after permission changes to reload RBAC cache.")


if __name__ == "__main__":
    main()
