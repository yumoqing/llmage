#!/usr/bin/env python3
"""
llmcatelog ID 迁移脚本
将 llmcatelog.id 和 llm_api_map.llmcatelogid 从旧ID迁移为有意义的缩写ID。

执行顺序：
  1. 先更新 llm_api_map.llmcatelogid（外键表）
  2. 再更新 llmcatelog.id（主表）
  3. 验证迁移结果

用法：
  # 预览模式（不执行，只显示将要做的变更）
  python migrate_llmcatelog_ids.py --dry-run

  # 正式执行
  python migrate_llmcatelog_ids.py

  # 指定数据库名（默认 llmage）
  python migrate_llmcatelog_ids.py --dbname my_llmage
"""

import asyncio
import argparse
import sys
import os

# 从脚本位置推断 sage 根目录（脚本在 pkgs/llmage/scripts/ 下）
_script_dir = os.path.dirname(os.path.abspath(__file__))
sage_root = os.path.abspath(os.path.join(_script_dir, '..', '..', '..'))
sys.path.insert(0, sage_root)
sys.path.insert(0, os.path.join(sage_root, 'py3/lib/python3.10/site-packages'))

from appPublic.jsonConfig import getConfig

# 旧ID -> 新ID 映射表
ID_MAP = {
    'text2text':                 't2t',
    'text2image':                't2i',
    '-i2ET0YkhfVQdHONfk9pX':    't2v',
    'RdsO6pXgXcUTvUj819-7X':    'i2v',
    'fHrfsOnAFCz53DAILMO7G':    'r2v',
    'text2speech':               'tts',
    'audio2text':                'asr',
    'image2text':                'vision',
    '9_P5y-qiQzQASacTVk2Lq':    'ai_search',
    'czKvk-clQTRLS2KVddSWo':    'digital_human',
    'HaRXiNCaAACurZsmEqpsU':    'music_gen',
    'Rqj-QBj1v4560l-FPCrIU':    'text_cls',
    's6-nhQtEvDKxG_qDPWwT7':    '3d_gen',
    'sRmpG8draTM-tsbO5nMJO':    'video_tool',
    't7sUuj8BCnsD762PwMUKM':    'translate',
}


async def migrate(dry_run=False, dbname='llmage'):
    from sqlor.dbpools import DBPools
    from appPublic.log import debug

    config = getConfig(sage_root)
    db = DBPools(config.databases)
    
    # 如果传入的 dbname 不在配置中，尝试使用第一个数据库
    if dbname not in config.databases:
        available = list(config.databases.keys())
        print(f"Warning: '{dbname}' not in config.databases, available: {available}")
        if available:
            dbname = available[0]
            print(f"Using '{dbname}' instead")
    
    async with db.sqlorContext(dbname) as sor:
        print(f"{'='*60}")
        print(f"llmcatelog ID 迁移脚本")
        print(f"数据库: {dbname}")
        print(f"模式: {'预览(DRY-RUN)' if dry_run else '正式执行'}")
        print(f"{'='*60}\n")

        # ===== 阶段0: 检查当前数据 =====
        print("[阶段0] 检查当前 llmcatelog 数据...")
        current = await sor.sqlExe("SELECT id, name FROM llmcatelog ORDER BY name", {})
        if not current:
            print("  llmcatelog 表为空，无需迁移。")
            return

        print(f"  当前共 {len(current)} 条记录:\n")
        print(f"  {'旧ID':<30} {'name':<15} {'新ID':<15} {'状态'}")
        print(f"  {'-'*30} {'-'*15} {'-'*15} {'-'*10}")

        valid_records = []
        unmapped = []
        for row in current:
            old_id = row['id']
            name = row['name']
            new_id = ID_MAP.get(old_id)
            if new_id:
                # 检查是否已经迁移过（old_id == new_id 的情况不会发生，
                # 但如果 id 已经是新值则跳过）
                if old_id == new_id:
                    status = '已迁移'
                else:
                    status = '待迁移'
                    valid_records.append((old_id, new_id, name))
                print(f"  {old_id:<30} {name:<15} {new_id:<15} {status}")
            else:
                status = '无映射!'
                unmapped.append((old_id, name))
                print(f"  {old_id:<30} {name:<15} {'---':<15} {status}")

        if unmapped:
            print(f"\n  ⚠ 警告: {len(unmapped)} 条记录无映射关系，将跳过:")
            for uid, uname in unmapped:
                print(f"    - {uid} ({uname})")

        if not valid_records:
            print("\n  没有需要迁移的记录。")
            return

        print(f"\n  共 {len(valid_records)} 条记录需要迁移。\n")

        # ===== 阶段1: 检查 llm_api_map 关联 =====
        print("[阶段1] 检查 llm_api_map 关联...")
        for old_id, new_id, name in valid_records:
            maps = await sor.sqlExe(
                "SELECT COUNT(*) as cnt FROM llm_api_map WHERE llmcatelogid = ${old_id}$",
                {'old_id': old_id}
            )
            cnt = maps[0]['cnt'] if maps else 0
            print(f"  {name}({old_id}): {cnt} 条映射")

        # ===== 阶段2: 检查新ID是否已被占用 =====
        print(f"\n[阶段2] 检查新ID是否已被占用...")
        conflict = False
        for old_id, new_id, name in valid_records:
            check = await sor.sqlExe(
                "SELECT id, name FROM llmcatelog WHERE id = ${new_id}$",
                {'new_id': new_id}
            )
            if check:
                # 如果新ID已存在且就是当前记录（已经迁移过），跳过
                if check[0]['id'] == old_id:
                    print(f"  {new_id}: 已是当前记录，跳过")
                else:
                    print(f"  ✗ 冲突! 新ID '{new_id}' 已被 {check[0]['name']} 使用")
                    conflict = True
            else:
                print(f"  ✓ {new_id}: 可用")

        if conflict:
            print("\n  ✗ 存在ID冲突，终止迁移！")
            return

        if dry_run:
            print(f"\n{'='*60}")
            print("预览模式结束。以上是将会执行的变更。")
            print("去掉 --dry-run 参数以正式执行。")
            print(f"{'='*60}")
            return

        # ===== 阶段3: 执行迁移 =====
        print(f"\n[阶段3] 开始执行迁移...")

        # 3a: 先更新 llm_api_map（外键表）
        print(f"\n  --- 3a: 更新 llm_api_map.llmcatelogid ---")
        for old_id, new_id, name in valid_records:
            try:
                await sor.sqlExe(
                    "UPDATE llm_api_map SET llmcatelogid = ${new_id}$ WHERE llmcatelogid = ${old_id}$",
                    {'new_id': new_id, 'old_id': old_id}
                )
                maps = await sor.sqlExe(
                    "SELECT COUNT(*) as cnt FROM llm_api_map WHERE llmcatelogid = ${new_id}$",
                    {'new_id': new_id}
                )
                cnt = maps[0]['cnt'] if maps else 0
                print(f"  ✓ {name}: {old_id} -> {new_id} (关联 {cnt} 条)")
            except Exception as e:
                print(f"  ✗ {name}: 更新 llm_api_map 失败: {e}")
                print(f"    回滚中...")
                raise

        # 3b: 再更新 llmcatelog（主表）
        print(f"\n  --- 3b: 更新 llmcatelog.id ---")
        for old_id, new_id, name in valid_records:
            try:
                await sor.sqlExe(
                    "UPDATE llmcatelog SET id = ${new_id}$ WHERE id = ${old_id}$",
                    {'new_id': new_id, 'old_id': old_id}
                )
                print(f"  ✓ {name}: {old_id} -> {new_id}")
            except Exception as e:
                print(f"  ✗ {name}: 更新 llmcatelog 失败: {e}")
                raise

        # ===== 阶段4: 验证 =====
        print(f"\n[阶段4] 验证迁移结果...")

        # 验证 llmcatelog
        catelogs = await sor.sqlExe("SELECT id, name FROM llmcatelog ORDER BY id", {})
        print(f"\n  llmcatelog ({len(catelogs)} 条):")
        for row in catelogs:
            print(f"    {row['id']:<20} {row['name']}")

        # 验证关联完整性
        orphans = await sor.sqlExe("""
            SELECT m.llmcatelogid, COUNT(*) as cnt
            FROM llm_api_map m
            LEFT JOIN llmcatelog c ON m.llmcatelogid = c.id
            WHERE c.id IS NULL
            GROUP BY m.llmcatelogid
        """, {})
        if orphans:
            print(f"\n  ✗ 发现孤立关联:")
            for o in orphans:
                print(f"    llmcatelogid={o['llmcatelogid']}: {o['cnt']} 条无对应主记录")
        else:
            print(f"\n  ✓ 所有 llm_api_map 关联完整，无孤立记录")

        # 验证映射表
        map_stats = await sor.sqlExe("""
            SELECT m.llmcatelogid, c.name, COUNT(*) as cnt
            FROM llm_api_map m
            JOIN llmcatelog c ON m.llmcatelogid = c.id
            GROUP BY m.llmcatelogid, c.name
            ORDER BY m.llmcatelogid
        """, {})
        if map_stats:
            print(f"\n  llm_api_map 关联统计:")
            for row in map_stats:
                print(f"    {row['llmcatelogid']:<20} {row['name']:<15} {row['cnt']} 条映射")

        print(f"\n{'='*60}")
        print("迁移完成！")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description='llmcatelog ID 迁移脚本')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不执行实际变更')
    parser.add_argument('--dbname', default='llmage', help='数据库名 (默认: llmage)')
    args = parser.parse_args()

    asyncio.run(migrate(dry_run=args.dry_run, dbname=args.dbname))


if __name__ == '__main__':
    main()
