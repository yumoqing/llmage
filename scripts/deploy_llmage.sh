#!/bin/bash
# deploy_llmage.sh
# 一键部署 llmage 模块的 llm_api_map 变更
#
# 包含：代码拉取 -> 构建 -> 数据库迁移 -> 权限设置 -> 重启
#
# 用法：
#   bash deploy_llmage.sh              # 完整部署
#   bash deploy_llmage.sh --dry-run    # 预览，不执行变更
#   bash deploy_llmage.sh --skip-db    # 跳过数据库迁移
#   bash deploy_llmage.sh --skip-perm  # 跳过权限设置

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LLMAGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SAGE_DIR="$(cd "$LLMAGE_DIR/../sage" && pwd 2>/dev/null || echo "")"

# 参数解析
DRY_RUN=false
SKIP_DB=false
SKIP_PERM=false

for arg in "$@"; do
    case $arg in
        --dry-run)  DRY_RUN=true ;;
        --skip-db)  SKIP_DB=true ;;
        --skip-perm) SKIP_PERM=true ;;
        -h|--help)
            echo "用法: bash deploy_llmage.sh [options]"
            echo "  --dry-run    预览模式，不执行变更"
            echo "  --skip-db    跳过数据库迁移"
            echo "  --skip-perm  跳过权限设置"
            echo "  -h, --help   显示帮助"
            exit 0
            ;;
    esac
done

echo "============================================"
echo "  llmage 模块部署: llm_api_map"
echo "============================================"
echo "LLMAGE_DIR: $LLMAGE_DIR"
echo "SAGE_DIR:   $SAGE_DIR"
echo "Dry run:    $DRY_RUN"
echo "Skip DB:    $SKIP_DB"
echo "Skip Perm:  $SKIP_PERM"
echo ""

# =============================================
# Step 1: 拉取最新代码
# =============================================
echo ">>> [1/5] 拉取最新代码..."
cd "$LLMAGE_DIR"

if $DRY_RUN; then
    echo "  [DRY] git pull origin main"
else
    git pull origin main
    echo "  Done"
fi

# =============================================
# Step 2: 构建模块（生成 UI/DDL）
# =============================================
echo ""
echo ">>> [2/5] 构建模块..."
cd "$LLMAGE_DIR/json"

if $DRY_RUN; then
    echo "  [DRY] bash build.sh"
else
    bash build.sh
    echo "  Done"
fi

# =============================================
# Step 3: 数据库迁移
# =============================================
if ! $SKIP_DB; then
    echo ""
    echo ">>> [3/5] 数据库迁移..."
    
    # 先在 Sage 虚拟环境中 dry-run 验证
    cd "$SAGE_DIR"
    if $DRY_RUN; then
        echo "  [DRY] python $LLMAGE_DIR/scripts/migrate_llm_api_map_db.py --dry-run"
        python "$LLMAGE_DIR/scripts/migrate_llm_api_map_db.py" --dry-run
    else
        echo "  执行 dry-run 预览..."
        python "$LLMAGE_DIR/scripts/migrate_llm_api_map_db.py" --dry-run
        echo ""
        echo "  确认以上预览无误后，执行实际迁移..."
        python "$LLMAGE_DIR/scripts/migrate_llm_api_map_db.py"
    fi
    echo "  Done"
else
    echo ""
    echo ">>> [3/5] 跳过数据库迁移"
fi

# =============================================
# Step 4: 权限设置
# =============================================
if ! $SKIP_PERM; then
    echo ""
    echo ">>> [4/5] 设置 RBAC 权限..."
    
    cd "$SAGE_DIR"
    if $DRY_RUN; then
        echo "  [DRY] bash $LLMAGE_DIR/scripts/setup_llmage_perms.sh"
    else
        bash "$LLMAGE_DIR/scripts/setup_llmage_perms.sh"
    fi
    echo "  Done"
else
    echo ""
    echo ">>> [4/5] 跳过权限设置"
fi

# =============================================
# Step 5: 重启服务
# =============================================
echo ""
echo ">>> [5/5] 重启服务..."

if $DRY_RUN; then
    echo "  [DRY] 请手动重启 Sage 服务以生效新代码"
    echo "  示例: systemctl restart sage  或  supervisorctl restart sage"
else
    echo "  请手动重启 Sage 服务以使变更生效："
    echo "    systemctl restart sage"
    echo "  或："
    echo "    supervisorctl restart sage"
fi

# =============================================
# 完成
# =============================================
echo ""
echo "============================================"
echo "  部署完成"
echo "============================================"
echo ""
echo "验证清单："
echo "  1. 检查 llm_api_map 表是否创建成功"
echo "  2. 访问 /llmage/llm_api_map_manage.ui 确认页面可访问"
echo "  3. 确认有权限的用户可以正常操作"
echo "  4. 确认无权限的用户返回 401"
echo ""
echo "如需回滚旧 llm 表字段（已删除的话）："
echo "  请从 git 历史恢复或手动添加 apiname/query_apiname/query_period/ppid 字段"
echo ""
