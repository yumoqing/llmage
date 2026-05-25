from sqlor.dbpools import get_sor_context
from appPublic.timeUtils import curDateString, timestampstr
from datetime import datetime, timedelta
from appPublic.log import debug, exception

async def get_llmage_stats(request):
    """Get llmage module statistics"""
    env = request._run_ns
    userorgid = await env.get_userorgid()
    today = curDateString()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    stats = {
        'total_models': 0,
        'today_usage_count': 0,
        'today_amount': 0,
        'catelog_count': 0
    }
    
    async with get_sor_context(env, 'llmage') as sor:
        # Total enabled models
        sql_models = """
            SELECT COUNT(DISTINCT id) as cnt FROM llm
            WHERE enabled_date <= ${today}$
                AND expired_date > ${today}$
        """
        recs = await sor.sqlExe(sql_models, {'today': today})
        if recs:
            stats['total_models'] = int(recs[0].cnt or 0)
        
        # Today's usage count
        sql_usage = """
            SELECT COUNT(*) as cnt FROM llmusage
            WHERE userorgid = ${userorgid}$
                AND use_date >= ${today}$
                AND use_date < ${tomorrow}$
        """
        recs = await sor.sqlExe(sql_usage, {
            'userorgid': userorgid,
            'today': today,
            'tomorrow': tomorrow
        })
        if recs:
            stats['today_usage_count'] = int(recs[0].cnt or 0)
        
        # Today's total amount
        sql_amount = """
            SELECT COALESCE(SUM(amount), 0) as total FROM llmusage
            WHERE userorgid = ${userorgid}$
                AND use_date >= ${today}$
                AND use_date < ${tomorrow}$
        """
        recs = await sor.sqlExe(sql_amount, {
            'userorgid': userorgid,
            'today': today,
            'tomorrow': tomorrow
        })
        if recs:
            stats['today_amount'] = float(recs[0].total or 0)
        
        # Catalog count
        sql_catelog = """
            SELECT COUNT(*) as cnt FROM llmcatelog
        """
        recs = await sor.sqlExe(sql_catelog, {})
        if recs:
            stats['catelog_count'] = int(recs[0].cnt or 0)
    
    return stats
