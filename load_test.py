#!/usr/bin/env python3
"""并发压力测试 llmage /v1/chat/completions — 4分钟×3组(50/100/200)，TTFB/QPM/500/主机资源"""

import asyncio, aiohttp, time, json, sys, statistics, subprocess
from dataclasses import dataclass, field
from typing import List

URL = "https://token.opencomputing.cn/llmage/v1/chat/completions"
TOKEN = "V9J41PngWBUU6gdHWJWDJ"
MODEL = "qwen3.6-35b-a3b"
DURATION = 240  # 4 minutes
CONCURRENCIES = [50, 100, 200]

# Host monitoring via SSH
HOST_SSH = "token@token.opencomputing.cn"
HOST_CPU_CMD = "top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}'"
HOST_MEM_CMD = "free -m | awk '/Mem:/{printf \"%.1f\", $3/$2*100}'"
HOST_LOAD_CMD = "uptime | awk -F'[a-z]:' '{print $2}' | awk '{print $1,$2,$3}'"


@dataclass
class ReqStat:
    idx: int
    start_ts: float
    first_byte_ts: float | None = None
    end_ts: float | None = None
    http_status: int = 0


@dataclass
class HostSnap:
    ts: float
    cpu: float
    mem: float
    load: str


async def host_snapshot() -> HostSnap:
    loop = asyncio.get_running_loop()
    try:
        cpu = float((await loop.run_in_executor(
            None, lambda: subprocess.run(
                ["ssh", "-o", "ConnectTimeout=3", HOST_SSH, HOST_CPU_CMD],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
        )) or 0)
    except:
        cpu = 0
    try:
        mem = float((await loop.run_in_executor(
            None, lambda: subprocess.run(
                ["ssh", "-o", "ConnectTimeout=3", HOST_SSH, HOST_MEM_CMD],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
        )) or 0)
    except:
        mem = 0
    try:
        load = (await loop.run_in_executor(
            None, lambda: subprocess.run(
                ["ssh", "-o", "ConnectTimeout=3", HOST_SSH, HOST_LOAD_CMD],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
        )) or "N/A"
    except:
        load = "N/A"
    return HostSnap(ts=time.monotonic(), cpu=cpu, mem=mem, load=load)


async def worker(session: aiohttp.ClientSession, idx: int, stats_out: list):
    payload = {
        "model": MODEL,
        "stream": True,
        "messages": [{"role": "user", "content": f"你是谁? 请用一句话回答,编号{idx}"}],
    }
    stat = ReqStat(idx=idx, start_ts=time.monotonic())
    try:
        async with session.post(
            URL, json=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            stat.http_status = resp.status
            first = True
            async for line in resp.content:
                if first:
                    stat.first_byte_ts = time.monotonic()
                    first = False
        stat.end_ts = time.monotonic()
    except Exception:
        stat.end_ts = time.monotonic()
    stats_out.append(stat)


async def run_concurrency(concurrency: int):
    stats: List[ReqStat] = []
    host_snaps: List[HostSnap] = []
    idx = 0
    stop_at = time.monotonic() + DURATION

    connector = aiohttp.TCPConnector(limit=concurrency + 50, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks: list[asyncio.Task] = []
        last_snap = 0

        while time.monotonic() < stop_at:
            # Fill to concurrency
            while len(tasks) < concurrency and time.monotonic() < stop_at:
                idx += 1
                tasks.append(asyncio.create_task(worker(session, idx, stats)))

            if not tasks:
                break

            # Host snapshot every 15s
            now = time.monotonic()
            if now - last_snap > 15:
                host_snaps.append(await host_snapshot())
                last_snap = now
                sys.stdout.write(f"\r  [{concurrency}] {len(stats)} req | CPU:{host_snaps[-1].cpu:.0f}% MEM:{host_snaps[-1].mem:.0f}% LOAD:{host_snaps[-1].load}")
                sys.stdout.flush()

            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED, timeout=0.5)
            tasks = list(tasks)

        # Drain remaining
        if tasks:
            await asyncio.wait(tasks)

        # Final snapshot
        host_snaps.append(await host_snapshot())

    return stats, host_snaps


def analyze(concurrency: int, stats: List[ReqStat], host_snaps: List[HostSnap]):
    ttfb_list = [s.first_byte_ts - s.start_ts for s in stats if s.first_byte_ts]
    total_list = [s.end_ts - s.start_ts for s in stats if s.end_ts and s.first_byte_ts]
    failed = sum(1 for s in stats if s.first_byte_ts is None)
    status_500 = sum(1 for s in stats if s.http_status >= 500)
    status_errors = sum(1 for s in stats if s.http_status >= 400 and s.http_status != 200)

    total_req = len(stats)
    qpm = total_req / (DURATION / 60)

    print(f"\n{'='*65}")
    print(f"  并发={concurrency} | {DURATION}s | 请求={total_req} | 失败={failed} | 5xx={status_500}")
    print(f"{'='*65}")
    if ttfb_list:
        print(f"  TTFB(s):   min={min(ttfb_list):.3f}  avg={statistics.mean(ttfb_list):.3f}  "
              f"p50={statistics.median(ttfb_list):.3f}  p95={_pct(ttfb_list,95):.3f}  p99={_pct(ttfb_list,99):.3f}")
    if total_list:
        print(f"  完成(s):   min={min(total_list):.3f}  avg={statistics.mean(total_list):.3f}  "
              f"p50={statistics.median(total_list):.3f}  p95={_pct(total_list,95):.3f}  p99={_pct(total_list,99):.3f}")
    print(f"  QPM:       {qpm:.1f}  |  QPS: {total_req/DURATION:.1f}  |  HTTP错误: {status_errors}")

    # Per-minute breakdown
    for minute in range(int(DURATION / 60)):
        win_start = minute * 60
        win_end = (minute + 1) * 60
        pm = sum(1 for s in stats if s.end_ts and s.first_byte_ts
                 and win_start <= (s.start_ts - stats[0].start_ts) < win_end)
        print(f"  第{minute+1}分钟完成: {pm}")

    # Host stats
    if host_snaps:
        cpus = [s.cpu for s in host_snaps if s.cpu > 0]
        mems = [s.mem for s in host_snaps if s.mem > 0]
        print(f"  主机:      CPU avg={statistics.mean(cpus):.1f}% max={max(cpus):.1f}%  "
              f"MEM avg={statistics.mean(mems):.1f}% max={max(mems):.1f}%  "
              f"LOAD max={max((s.load for s in host_snaps if s.load!='N/A'), default='N/A')}")

    return {"concurrency": concurrency, "total": total_req, "failed": failed,
            "status_500": status_500, "status_errors": status_errors,
            "ttfb_avg": statistics.mean(ttfb_list) if ttfb_list else None,
            "ttfb_p50": statistics.median(ttfb_list) if ttfb_list else None,
            "ttfb_p95": _pct(ttfb_list, 95) if ttfb_list else None,
            "ttfb_p99": _pct(ttfb_list, 99) if ttfb_list else None,
            "total_avg": statistics.mean(total_list) if total_list else None,
            "total_p50": statistics.median(total_list) if total_list else None,
            "qpm": qpm,
            "host_cpu_avg": statistics.mean(cpus) if cpus else None,
            "host_cpu_max": max(cpus) if cpus else None,
            "host_mem_avg": statistics.mean(mems) if mems else None}


def _pct(data, p):
    return sorted(data)[int(len(data) * p / 100)]


async def main():
    results = []
    for c in CONCURRENCIES:
        print(f"\n>>> 开始 并发={c} [{DURATION}s] ...")
        stats, snaps = await run_concurrency(c)
        r = analyze(c, stats, snaps)
        results.append(r)

    print(f"\n{'='*65}")
    print("  汇总对比")
    print(f"{'='*65}")
    print(f"  {'并发':>5} {'请求':>7} {'失败':>5} {'5xx':>5} "
          f"{'TTFB_avg':>9} {'TTFB_p50':>9} {'TTFB_p95':>9} {'TTFB_p99':>9} "
          f"{'完成_avg':>9} {'QPM':>8} {'CPU_avg':>7} {'CPU_max':>7}")
    for r in results:
        t_avg = f'{r["ttfb_avg"]:.3f}' if r['ttfb_avg'] else 'N/A'
        t_p50 = f'{r["ttfb_p50"]:.3f}' if r['ttfb_p50'] else 'N/A'
        t_p95 = f'{r["ttfb_p95"]:.3f}' if r['ttfb_p95'] else 'N/A'
        t_p99 = f'{r["ttfb_p99"]:.3f}' if r['ttfb_p99'] else 'N/A'
        c_avg = f'{r["total_avg"]:.3f}' if r['total_avg'] else 'N/A'
        cpu = f'{r["host_cpu_avg"]:.0f}%' if r['host_cpu_avg'] else 'N/A'
        cmax = f'{r["host_cpu_max"]:.0f}%' if r['host_cpu_max'] else 'N/A'
        print(f"  {r['concurrency']:>5} {r['total']:>7} {r['failed']:>5} {r['status_500']:>5} "
              f"{t_avg:>9} {t_p50:>9} {t_p95:>9} {t_p99:>9} "
              f"{c_avg:>9} {r['qpm']:>8.0f} {cpu:>7} {cmax:>7}")


if __name__ == "__main__":
    asyncio.run(main())
