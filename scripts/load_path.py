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
    f"/{MOD}/imgs/%",
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
    f"/{MOD}/show_same_catelog_llm.ui",
    f"/{MOD}/show_llms.ui",
    f"/{MOD}/show_llms_by_providers.ui",
    f"/{MOD}/model_plaza.ui",
    f"/{MOD}/failed_accounting.ui",
    f"/{MOD}/llmcatelog_list.ui",

    # 顶层 .dspy（非 api/ 目录）
    f"/{MOD}/%.dspy",

    # api/ 目录 — 所有 .dspy 通配
    f"/{MOD}/api/%",

    # CRUD 子目录 — 通配（每个子目录下的所有文件）
    f"/{MOD}/llm/%",
    f"/{MOD}/llmcatelog/%",
    f"/{MOD}/llmcatelog_list/%",
    f"/{MOD}/llmusage/%",
    f"/{MOD}/llmusage_accounting_failed/%",
    f"/{MOD}/llmusage_history/%",
    f"/{MOD}/llm_api_map/%",

    # v1 API 目录（管理员通过 logined 访问）
    f"/{MOD}/v1/%",

    # 其他子目录
    f"/{MOD}/list_llmcatelogs/%",
    f"/{MOD}/list_llms/%",
    f"/{MOD}/openai/%",
    f"/{MOD}/t2t/%",
    f"/{MOD}/tasks/%",
    f"/{MOD}/upload_asset/%",
    f"/{MOD}/video/%",
]

# ============================================================
# 客户角色 — v1 API 调用权限
# ============================================================

PATHS_V1_CUSTOMER = [
    f"/{MOD}/v1/chat/completions/index.dspy",
    f"/{MOD}/v1/video/generations/index.dspy",
    f"/{MOD}/v1/image/generations/index.dspy",
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
