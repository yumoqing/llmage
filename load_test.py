#!/usr/bin/env python3
"""并发压力测试 llmage /v1/chat/completions，统计 TTFB / 完成时间 / QPM"""

import asyncio
import aiohttp
import time
import json
import sys
import statistics
from dataclasses import dataclass, field
from typing import List

URL = "https://token.opencomputing.cn/llmage/v1/chat/completions"
TOKEN = "V9J41PngWBUU6gdHWJWDJ"
MODEL = "qwen3.6-35b-a3b"
DURATION = 180  # 3 分钟
CONCURRENCIES = [10, 50, 100, 200]


@dataclass
class ReqStat:
    prompt_idx: int
    start_ts: float
    first_byte_ts: float | None = None
    end_ts: float | None = None


async def worker(session: aiohttp.ClientSession, idx: int, stats_out: list):
    """单个请求：发送 stream 请求，记录首字时间和完成时间"""
    prompt = f"请用一句话介绍你自己，编号{idx}"
    payload = {
        "model": MODEL,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
    }
    stat = ReqStat(prompt_idx=idx, start_ts=time.monotonic())
    try:
        async with session.post(
            URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {TOKEN}",
            },
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            first = True
            async for line in resp.content:
                if first:
                    stat.first_byte_ts = time.monotonic()
                    first = False
                # 读完所有 chunk 才算完成
        stat.end_ts = time.monotonic()
    except Exception as e:
        # 异常请求也记录（TTFB=None 表示失败）
        stat.end_ts = time.monotonic()
    stats_out.append(stat)


async def run_concurrency(concurrency: int):
    """以固定并发运行 DURATION 秒，持续发起新请求"""
    stats: List[ReqStat] = []
    idx = 0
    stop_at = time.monotonic() + DURATION

    connector = aiohttp.TCPConnector(limit=concurrency + 20, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks: list[asyncio.Task] = []

        while time.monotonic() < stop_at:
            # 保持并发数：补满到 concurrency
            while len(tasks) < concurrency and time.monotonic() < stop_at:
                idx += 1
                tasks.append(
                    asyncio.create_task(worker(session, idx, stats))
                )

            if not tasks:
                break

            # 等待任意一个完成，腾出槽位
            done, tasks = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED, timeout=0.5
            )
            # 清理已完成的
            tasks = list(tasks)

        # 时间到，等待所有进行中的请求完成
        if tasks:
            await asyncio.wait(tasks)

    return stats


def analyze(name: str, stats: List[ReqStat]):
    """分析并打印统计"""
    ttfb_list = [s.first_byte_ts - s.start_ts for s in stats if s.first_byte_ts]
    total_list = [s.end_ts - s.start_ts for s in stats if s.end_ts and s.first_byte_ts]
    failed = sum(1 for s in stats if s.first_byte_ts is None)
    total_req = len(stats)
    elapsed = DURATION
    qpm = total_req / (elapsed / 60)

    print(f"\n{'='*60}")
    print(f"  并发={name} | 运行{DURATION}s | 总请求={total_req} | 失败={failed}")
    print(f"{'='*60}")
    if ttfb_list:
        print(f"  TTFB (s):  min={min(ttfb_list):.3f}  avg={statistics.mean(ttfb_list):.3f}  "
              f"p50={statistics.median(ttfb_list):.3f}  p95={_pct(ttfb_list, 95):.3f}  p99={_pct(ttfb_list, 99):.3f}")
    if total_list:
        print(f"  完成 (s):  min={min(total_list):.3f}  avg={statistics.mean(total_list):.3f}  "
              f"p50={statistics.median(total_list):.3f}  p95={_pct(total_list, 95):.3f}  p99={_pct(total_list, 99):.3f}")
    print(f"  QPM:       {qpm:.1f}")
    print(f"  QPS:       {total_req / elapsed:.1f}")

    # 按分钟分段统计
    for minute in range(int(elapsed / 60)):
        win_start = minute * 60
        win_end = (minute + 1) * 60
        cnt = sum(1 for s in stats if s.end_ts and (s.end_ts - s.start_ts) >= 0
                  and win_start <= (s.start_ts - stats[0].start_ts) < win_end)
        print(f"  第{minute+1}分钟完成请求数: {cnt}")

    return {
        "concurrency": name,
        "total": total_req,
        "failed": failed,
        "ttfb_avg": statistics.mean(ttfb_list) if ttfb_list else None,
        "ttfb_p50": statistics.median(ttfb_list) if ttfb_list else None,
        "ttfb_p95": _pct(ttfb_list, 95) if ttfb_list else None,
        "total_avg": statistics.mean(total_list) if total_list else None,
        "total_p50": statistics.median(total_list) if total_list else None,
        "qpm": qpm,
    }


def _pct(data, p):
    return sorted(data)[int(len(data) * p / 100)]


async def main():
    results = []
    for c in CONCURRENCIES:
        print(f"\n>>> 开始测试 并发={c} ...")
        stats = await run_concurrency(c)
        r = analyze(str(c), stats)
        results.append(r)

    # 汇总表格
    print(f"\n{'='*60}")
    print("  汇总对比")
    print(f"{'='*60}")
    print(f"  {'并发':>6} {'总请求':>8} {'失败':>5} {'TTFB_avg':>9} {'TTFB_p50':>9} {'TTFB_p95':>9} {'完成_avg':>9} {'QPM':>8}")
    for r in results:
        print(f"  {r['concurrency']:>6} {r['total']:>8} {r['failed']:>5} "
              f"{r['ttfb_avg']:.3f}s" if r['ttfb_avg'] else "N/A".rjust(9) + " "
              f"{(r['ttfb_p50'] or 0):.3f}s".rjust(9) + " "
              f"{(r['ttfb_p95'] or 0):.3f}s".rjust(9) + " "
              f"{r['total_avg']:.3f}s".rjust(9) if r['total_avg'] else "N/A".rjust(9))


if __name__ == "__main__":
    asyncio.run(main())
