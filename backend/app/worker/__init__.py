"""Background job execution (ADR 0014) — arq tasks + WorkerSettings, run as
separate processes from the FastAPI app (`arq app.worker.settings.FishAudioWorker`,
etc.), never imported by `api/`/`services/` themselves. See `docs/architecture.md`
§3f for the queue-per-provider design this package implements.
"""
