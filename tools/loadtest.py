#!/usr/bin/env python3
"""Simulates a busy clinic against a running server and reports response times.

    python tools/loadtest.py --url http://localhost:8011 --users 20 --seconds 60 \
        --email-pattern "load{n}@test.local" --password "Blue-Heron-Walks-0914"

Needs a non-production server (production requires two-step verification, which a script cannot do) with N clinician
accounts, and LOGIN_RATE_LIMIT_ATTEMPTS raised so that signing in N users is not throttled. Each virtual user signs in,
then repeats a realistic mix: day list, patient search, open a chart, read results, write a problem-list entry.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time

import httpx


async def user(n: int, a, stop: float, stats: dict) -> None:
    async with httpx.AsyncClient(base_url=a.url, timeout=30, verify=False) as c:
        r = await c.post("/api/auth/login", json={"email": a.email_pattern.format(n=n), "password": a.password})
        if r.status_code != 200:
            stats.setdefault("login_failed", []).append(r.status_code)
            return
        pids = [p["id"] for p in (await c.get("/api/patients", params={"limit": 200})).json()]

        async def timed(name, coro):
            t = time.perf_counter()
            try:
                resp = await coro
                ok = resp.status_code < 400
            except Exception:
                ok = False
            stats.setdefault(name, []).append((time.perf_counter() - t, ok))

        while time.time() < stop:
            pid = random.choice(pids)
            roll = random.random()
            if roll < 0.15:
                await timed("today", c.get("/api/today"))
            elif roll < 0.30:
                await timed("search", c.get("/api/patients", params={"q": random.choice(["Pat", "Ient", "0", "Re"])}))
            elif roll < 0.60:
                await timed("chart", c.get(f"/api/patients/{pid}/overview"))
            elif roll < 0.80:
                await timed("results", c.get(f"/api/patients/{pid}/observations"))
            elif roll < 0.92:
                await timed("prescriptions", c.get(f"/api/patients/{pid}/prescriptions"))
            else:
                await timed("write", c.post(f"/api/patients/{pid}/conditions", json={"name": f"Load test {random.randint(1, 99999)}"}))
            await asyncio.sleep(random.uniform(0.2, 1.0))  # a person reads between clicks


def pct(v: list[float], q: float) -> float:
    return sorted(v)[min(len(v) - 1, int(len(v) * q))] * 1000


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--users", type=int, default=10)
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--email-pattern", default="load{n}@test.local")
    ap.add_argument("--password", required=True)
    a = ap.parse_args()
    stats: dict = {}
    stop = time.time() + a.seconds
    t0 = time.time()
    await asyncio.gather(*(user(n, a, stop, stats) for n in range(a.users)))
    wall = time.time() - t0
    total = errors = 0
    print(f"{a.users} users for {wall:.0f}s")
    print(f"{'action':14}{'count':>7}{'errors':>8}{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}")
    for name, rows in sorted(stats.items()):
        if name == "login_failed":
            print(f"login failures: {rows}")
            continue
        times = [t for t, _ in rows]
        bad = sum(1 for _, ok in rows if not ok)
        total, errors = total + len(rows), errors + bad
        print(f"{name:14}{len(rows):>7}{bad:>8}{pct(times, .5):>9.0f}{pct(times, .95):>9.0f}{pct(times, .99):>9.0f}")
    allt = [t for k, rows in stats.items() if k != "login_failed" for t, _ in rows]
    print(f"\n{total} requests, {errors} errors, {total / wall:.1f} req/s, mean {statistics.mean(allt) * 1000:.0f} ms")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
