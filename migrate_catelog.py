#!/usr/bin/env python3
"""
Migration script: Move llm.llmcatelogid to llm_catalog_rel.
Run this AFTER creating the llm_catalog_rel table via build.sh.
"""
import asyncio
from sqlor.dbpools import DBPools
from appPublic.jsonConfig import getConfig
from appPublic.log import info, error
from ahserver.serverenv import ServerEnv

async def migrate():
    env = ServerEnv()
    try:
        dbname = env.get_module_dbname('llmage')
    except:
        dbname = 'default'

    config = getConfig()
    db = DBPools()
    db.databases = config.databases

    async with db.sqlorContext(dbname) as sor:
        # 1. Migrate data
        print("Migrating data...")
        # Get all llms with a llmcatelogid
        # Note: llmcatelogid still exists in DB until we drop it, or we assume it's there.
        # Assuming it's there.
        sql = "select id, llmcatelogid from llm where llmcatelogid is not null and llmcatelogid != ''"
        rows = await sor.sqlExe(sql, {})
        
        if not rows:
            print("No data to migrate.")
            return

        print(f"Found {len(rows)} records to migrate.")
        
        for r in rows:
            # Insert into llm_catalog_rel
            # Use getID() logic or simple uuid, here assuming we can use a function or simple generation
            # but sqlor insert C() is better
            data = {
                'llmid': r['id'],
                'llmcatelogid': r['llmcatelogid']
            }
            await sor.C('llm_catalog_rel', data)

        print("Migration complete.")
        
        # 2. Drop column (Optional but recommended)
        # print("Dropping column...")
        # await sor.sqlExe("alter table llm drop column llmcatelogid", {})
        # print("Column dropped.")

if __name__ == '__main__':
    asyncio.run(migrate())
