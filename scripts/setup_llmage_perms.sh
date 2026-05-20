#!/bin/bash
# setup_llmage_perms.sh
# 为 llmage 模块的 llm_api_map 管理功能配置 RBAC 角色权限
#
# 授权角色：
#   owner.superuser   — 系统超管：全局所有模型配置
#   *.admin           — 机构管理员：管理本机构模型（通过ownerid隔离数据）
#   reseller.operator — 运营：产品管理、模型配置
#
# 运行位置: sage 项目根目录 (包含 set_role_perm.py 的目录)
# 用法: bash setup_llmage_perms.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SAGE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd 2>/dev/null || echo "")"
if [ ! -f "$SAGE_DIR/set_role_perm.py" ]; then
    SAGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd 2>/dev/null || echo "")"
fi
if [ ! -f "$SAGE_DIR/set_role_perm.py" ]; then
    echo "Error: Cannot find set_role_perm.py"
    exit 1
fi
cd "$SAGE_DIR"

COUNT=0
set_perm() {
    local role="$1"
    local path="$2"
    python set_role_perm.py "${role}" "${path}"
    COUNT=$((COUNT + 1))
}

# 授权角色（超管 + 各机构管理员 + 运营）
PERM_ROLES=(
    "owner.superuser"
    "owner.admin"
    "reseller.admin"
    "provider.admin"
    "customer.admin"
    "reseller.operator"
)

echo "============================================"
echo "  llmage: llm_api_map 权限初始化"
echo "============================================"

LLM_API_MAP_PATHS=(
    "/llmage/llm_api_map_manage.ui"
    "/llmage/api/llm_api_map_list.dspy"
    "/llmage/api/llm_api_map_create.dspy"
    "/llmage/api/llm_api_map_delete.dspy"
    "/llmage/api/llm_api_map_options.dspy"
    "/llmage/api/uapi_options.dspy"
)

for p in "${LLM_API_MAP_PATHS[@]}"; do
    for role in "${PERM_ROLES[@]}"; do
        set_perm "${role}" "${p}"
    done
done

echo ""
echo "============================================"
echo "  权限配置完成，共设置 ${COUNT} 条权限"
echo "============================================"
