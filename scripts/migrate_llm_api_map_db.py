#!/usr/bin/env python3
"""
llm_api_map 数据库迁移脚本
直接操作数据库，完成以下任务：
  1. 创建 llm_api_map 表（如不存在）
  2. 从 llm 表迁移 apiname/query_apiname/query_period/ppid 到 llm_api_map
  3. 关联 llm_catalog_rel 获取 llmcatelogid
  4. 可选：删除 llm 表中的旧字段（需用户确认）

运行位置：Sage 虚拟环境
用法：python scripts/migrate_llm_api_map_db.py [--dry-run] [--drop-old]
"""
import sys
import os
import asyncio
import argparse

# 确保 Sage 虚拟环境的包可用
sage_root = os.path.expanduser('~/repos/sage')
sys.path.insert(0, sage_root)
sys.path.insert(0, os.path.join(sage_root, 'py3/lib/python3.10/site-packages'))

from appPublic.jsonConfig import getConfig
from appPublic.uniqueID import getID
from sqlor.dbpools import DBPools


def print_sql(sql, label=""):
    if label:
        print(f"  [{label}] {sql}")
    else:
        print(f"  {sql}")


async def migrate(dry_run=False, drop_old=False):
    """Execute migration."""
    config = getConfig(sage_root)
    db = DBPools(config.databases)
    dbname = list(config.databases.keys())[0]
    
    print(f"Using database: {dbname}")
    print(f"Dry run: {dry_run}")
    print(f"Drop old columns: {drop_old}")
    print()
    
    async with db.sqlorContext(dbname) as sor:
        # =============================================
        # Step 1: Check if llm_api_map already has data
        # =============================================
        existing = await sor.sqlExe("SELECT COUNT(*) as cnt FROM llm_api_map", {})
        existing_count = existing[0]['cnt'] if existing else 0
        
        if existing_count > 0:
            print(f"[WARNING] llm_api_map already has {existing_count} records.")
            resp = input("Continue anyway? (y/N): ")
            if resp.lower() != 'y':
                print("Aborted.")
                return False
        
        # =============================================
        # Step 2: Create llm_api_map table
        # =============================================
        print("[Step 1] Creating llm_api_map table...")
        
        create_sql = """
CREATE TABLE IF NOT EXISTS llm_api_map (
    id VARCHAR(32) NOT NULL PRIMARY KEY,
    llmid VARCHAR(32) NOT NULL,
    llmcatelogid VARCHAR(32) NOT NULL,
    apiname VARCHAR(100) NOT NULL,
    query_apiname VARCHAR(100),
    query_period INT,
    ppid VARCHAR(32)
)
        """
        if dry_run:
            print_sql(create_sql.strip(), "SQL")
        else:
            try:
                await sor.sqlExe(create_sql, {})
                print("  Table created (or already exists)")
            except Exception as e:
                if 'already exists' in str(e).lower() or 'Duplicate' in str(e):
                    print("  Table already exists, continuing")
                else:
                    print(f"  ERROR: {e}")
                    return False
        
        # Create indexes
        indexes = [
            ("CREATE INDEX idx_api_map_llm ON llm_api_map (llmid)", "index llmid"),
            ("CREATE INDEX idx_api_map_catelog ON llm_api_map (llmcatelogid)", "index catelog"),
            ("CREATE INDEX idx_api_map_apiname ON llm_api_map (apiname)", "index apiname"),
            ("CREATE UNIQUE INDEX uk_llmid_apiname ON llm_api_map (llmid, apiname)", "unique (llmid, apiname)"),
        ]
        
        for sql, label in indexes:
            if dry_run:
                print_sql(sql, label)
            else:
                try:
                    await sor.sqlExe(sql, {})
                    print(f"  Index created: {label}")
                except Exception as e:
                    if 'already exists' in str(e).lower() or 'Duplicate' in str(e):
                        print(f"  Index already exists: {label}")
                    else:
                        print(f"  WARNING creating {label}: {e}")
        
        # =============================================
        # Step 3: Migrate data from llm -> llm_api_map
        # =============================================
        print("\n[Step 2] Migrating data...")
        
        # Get all llm records that have apiname
        llms = await sor.sqlExe("""
            SELECT id, name, apiname, query_apiname, query_period, ppid
            FROM llm
            WHERE apiname IS NOT NULL AND apiname != ''
        """, {})
        
        print(f"  Found {len(llms or [])} llm records with apiname")
        
        if not llms:
            print("  No data to migrate. Done.")
            return True
        
        # Build catalog_rel lookup
        rels = await sor.sqlExe("SELECT llmid, llmcatelogid FROM llm_catalog_rel", {})
        catelog_map = {}
        for r in (rels or []):
            catelog_map.setdefault(r['llmid'], []).append(r['llmcatelogid'])
        
        migrated = 0
        skipped = 0
        errors = []
        
        for llm in llms:
            llmid = llm['id']
            catelog_ids = catelog_map.get(llmid)
            
            if not catelog_ids:
                print(f"  [SKIP] llm '{llm.get('name', llmid)}' has no catalog_rel entry")
                skipped += 1
                continue
            
            for catelogid in catelog_ids:
                if dry_run:
                    print(f"  [DRY] Would insert: llm={llm.get('name', llmid)}, catelog={catelogid}, api={llm['apiname']}")
                    migrated += 1
                    continue
                
                # Check if already exists
                exists = await sor.sqlExe(
                    "SELECT id FROM llm_api_map WHERE llmid=${llmid}$ AND apiname=${apiname}$",
                    {'llmid': llmid, 'apiname': llm['apiname']}
                )
                if exists:
                    print(f"  [SKIP] Already exists: {llm.get('name', llmid)} / {llm['apiname']}")
                    skipped += 1
                    continue
                
                # Insert
                data = {
                    'id': getID(),
                    'llmid': llmid,
                    'llmcatelogid': catelogid,
                    'apiname': llm['apiname'],
                }
                if llm.get('query_apiname'):
                    data['query_apiname'] = llm['query_apiname']
                if llm.get('query_period') is not None:
                    data['query_period'] = int(llm['query_period']) if llm['query_period'] != '' else None
                if llm.get('ppid'):
                    data['ppid'] = llm['ppid']
                
                try:
                    await sor.C('llm_api_map', data)
                    migrated += 1
                except Exception as e:
                    errors.append(f"{llm.get('name', llmid)}: {e}")
        
        print(f"\n  Migrated: {migrated}, Skipped: {skipped}")
        if errors:
            print(f"  Errors: {len(errors)}")
            for e in errors[:5]:
                print(f"    - {e}")
        
        if dry_run:
            print("\n  (Dry run, no changes made)")
            return True
        
        # =============================================
        # Step 4: Verify migration
        # =============================================
        print("\n[Step 3] Verifying migration...")
        
        llm_api_count = await sor.sqlExe("SELECT COUNT(*) as cnt FROM llm_api_map", {})
        api_count = llm_api_count[0]['cnt'] if llm_api_count else 0
        print(f"  llm_api_map total records: {api_count}")
        
        # Check for llm records without corresponding llm_api_map
        orphan_check = await sor.sqlExe("""
            SELECT l.id, l.name
            FROM llm l
            WHERE l.apiname IS NOT NULL AND l.apiname != ''
            AND NOT EXISTS (
                SELECT 1 FROM llm_api_map m WHERE m.llmid = l.id
            )
        """, {})
        
        if orphan_check:
            print(f"  [WARNING] {len(orphan_check)} llm records have no llm_api_map entry:")
            for o in orphan_check[:5]:
                print(f"    - {o.get('name', o['id'])}")
            if len(orphan_check) > 5:
                print(f"    ... and {len(orphan_check) - 5} more")
        else:
            print("  All llm records with apiname have corresponding llm_api_map entries")
        
        # =============================================
        # Step 5: Optional - drop old columns from llm
        # =============================================
        if drop_old:
            print("\n[Step 4] Dropping old columns from llm table...")
            
            old_columns = ['apiname', 'query_apiname', 'query_period', 'ppid']
            for col in old_columns:
                try:
                    await sor.sqlExe(f"ALTER TABLE llm DROP COLUMN {col}", {})
                    print(f"  Dropped column: {col}")
                except Exception as e:
                    if 'column' in str(e).lower() and ('not exist' in str(e).lower() or 'doesn\'t exist' in str(e).lower()):
                        print(f"  Column already dropped: {col}")
                    else:
                        print(f"  WARNING dropping {col}: {e}")
            
            print("  Old columns removed from llm table")
            print("  NOTE: Update code to use llm_api_map instead of llm columns")
        
        print("\n[Done] Migration complete")
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate llm data to llm_api_map table')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without executing')
    parser.add_argument('--drop-old', action='store_true', help='Drop old columns from llm table after migration')
    args = parser.parse_args()
    
    if not args.dry_run:
        print("=" * 60)
        print("  llm_api_map Database Migration")
        print("=" * 60)
        resp = input("\nThis will modify the database. Continue? (y/N): ")
        if resp.lower() != 'y':
            print("Aborted.")
            sys.exit(0)
        print()
    
    success = asyncio.get_event_loop().run_until_complete(
        migrate(dry_run=args.dry_run, drop_old=args.drop_old)
    )
    sys.exit(0 if success else 1)
