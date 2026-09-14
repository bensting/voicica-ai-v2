"""Convenience entrypoint: runs every worker (ADR 0014/0015's provider
queues + the cron sweep, `worker/settings.py`/`worker/cron.py`) in one OS
process — one thing to start for local dev instead of five.

**This doesn't change the design** — it's still 4 independent `arq.Worker`
instances under the hood, each enforcing its own `max_jobs` against its own
queue exactly as if it were a separate process (Fish Audio's real
concurrency limit is still respected on its own; a burst of Kie-shaped
slowness, once that exists, still can't touch Azure/Google's capacity).
All that's shared is the process — a crash here takes all four down
together, which is a real trade-off against running them separately, and
exactly why this is a *local-dev* convenience, not the deployment shape:
splitting back into separate processes/containers (one per
`worker/settings.py` class) for independent scaling/restarts in production
is a config change (which command each container runs), not a code change.

Run with: `python -m app.worker.run_all`
"""

import asyncio
import logging
import logging.config

from arq.logs import default_log_config
from arq.worker import Worker, create_worker

from app.worker.cron import CronWorker
from app.worker.settings import AzureWorker, FishAudioWorker, GoogleWorker, KieSubmitWorker

logger = logging.getLogger(__name__)

_ALL_WORKER_SETTINGS = [FishAudioWorker, AzureWorker, GoogleWorker, KieSubmitWorker, CronWorker]


async def _run() -> None:
    # The `arq` CLI sets this up itself before calling run_worker() — since
    # this script drives Worker instances directly instead, without it every
    # job-picked-up/finished log line arq normally prints is silently lost.
    logging.config.dictConfig(default_log_config(verbose=False))

    # handle_signals=False on every instance: a single Ctrl+C should stop
    # all four together via this process's own asyncio.run() cancellation,
    # not have four competing SIGINT handlers installed in one process.
    workers: list[Worker] = [
        create_worker(settings_cls, handle_signals=False) for settings_cls in _ALL_WORKER_SETTINGS
    ]
    try:
        await asyncio.gather(*(worker.async_run() for worker in workers))
    finally:
        # async_run() deliberately leaves connections open (arq's own
        # docstring: "useful when testing") — closing them here is this
        # script's job, not each Worker's.
        await asyncio.gather(*(worker.close() for worker in workers), return_exceptions=True)


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Stopped.")


if __name__ == "__main__":
    main()
