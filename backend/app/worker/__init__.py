"""Background job execution (ADR 0014, ADR 0026) — `dispatcher.py` is the
one process (`python -m app.worker.dispatcher`), claiming `jobs` rows
directly from Postgres, never imported by `api/`/`services/` themselves.
See `docs/architecture.md` §3f for the design this package implements.
"""
