# Performance — measured

Measured with `tools/loadtest.py` on the container's own application server (one process, SQLite in WAL mode), 4 CPU cores,
**20,000 patients and 24,000 lab results**, virtual staff signed in as doctors repeating a realistic mix (day list, patient search,
open a chart, read results, read prescriptions, write a problem-list entry) with 0.2–1 s think time.

| Concurrent staff | Requests/s | Errors | Typical (p50) | Slowest 1 in 20 (p95) | Verdict |
|---|---|---|---|---|---|
| **15** | 22 | 0 | 9–21 ms | **24–69 ms** (every action) | Comfortable: a clinic of this size will not notice the system |
| 30 | 35 | 0 | 16–47 ms | 74–750 ms; saving a change up to ~3 s | Works, but writes queue — SQLite allows one writer at a time |

Reading the table honestly: it is **about 15 people working at the same time** (not 15 accounts: a 50-person clinic rarely has more than
15 active in the same second). Past about 30 simultaneous *writers*, plan for PostgreSQL (the schema is standard SQLAlchemy;
this is a deployment change, not a rewrite — it has not been done or tested yet). AI features are not included here: their speed
depends on the model server and is measured by `python -m app.cli eval`.

Tuning found by measuring: search used to return up to 200 enriched rows per keystroke (mean 291 ms at 30 users); it now returns 50 (mean 81 ms).
SQLite page cache and busy timeout were raised so a momentary write lock waits instead of failing.

Reproduce: start the app in development mode with `LOGIN_RATE_LIMIT_ATTEMPTS=100000`, create accounts `load0..N@test.local`, and run
`python tools/loadtest.py --url http://localhost:8011 --users 15 --seconds 40 --password <password>`.
