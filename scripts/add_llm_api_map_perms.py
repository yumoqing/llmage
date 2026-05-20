#!/usr/bin/env python3
"""
Add permission records for new llm_api_map management files.
Run in Sage virtual environment:
    cd ~/repos/llmage && python scripts/add_llm_api_map_perms.py
"""
import os
import sys
import asyncio
from appPublic.uniqueID import getID
from sqlor.dbpools import DBPools

# Paths that need permissions
PERM_PATHS = [
    '/llm_api_map_manage.ui',
    '/api/llm_api_map_list.dspy',
    '/api/llm_api_map_create.dspy',
    '/api/llm_api_map_delete.dspy',
    '/api/llm_api_map_options.dspy',
    '/api/uapi_options.dspy',
]

async def add_permissions():
    """Insert permission records for llm_api_map files."""
    config_path = os.path.expanduser('~/repos/sage')
    from appPublic.jsonConfig import getConfig
    config = getConfig(config_path)
    
    db = DBPools(config.databases)
    dbname = list(config.databases.keys())[0]
    
    async with db.sqlorContext(dbname) as sor:
        for path in PERM_PATHS:
            # Check if permission already exists
            existing = await sor.sqlExe(
                "select id from permission where path = ${path}$",
                {'path': path}
            )
            if not existing:
                perm_id = getID()
                await sor.C('permission', {
                    'id': perm_id,
                    'path': path
                })
                print(f"Added permission: {path} (id={perm_id})")
            else:
                print(f"Permission already exists: {path}")
    
    print("\nDone. Now assign these permissions to roles using:")
    print("  python ~/repos/sage/script/set_role_perm.py <role_name> /llm_api_map_manage.ui")

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(add_permissions())
