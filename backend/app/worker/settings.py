"""arq `WorkerSettings` classes — one per provider queue (ADR 0014), each
meant to be run as its own process:

    arq app.worker.settings.FishAudioWorker
    arq app.worker.settings.AzureWorker
    arq app.worker.settings.GoogleWorker

`max_jobs` (per-process concurrency) is where each provider's real limit is
actually enforced — see each class's own comment for where its number comes
from. Splitting into separate classes/processes (rather than one Worker
juggling several `queue_name`s) is what makes one provider's slowness or
rate limit structurally unable to delay another's jobs — see
`docs/architecture.md` §3f.
"""

from typing import ClassVar

from arq.worker import func

from app.core.queue import QUEUE_NAMES, WORKER_POLL_DELAY_SECONDS, redis_settings
from app.services.jobs import MAX_PROVIDER_TRIES
from app.worker.tasks import run_kie_submit_job, run_tts_job, run_voice_model_training_job

# arq's own per-attempt ceiling (asyncio.wait_for around the whole task) —
# a real question surfaced this was silently using arq's unstated default
# (also 300, as it happens) rather than a value anyone had actually chosen.
# Sized against this codebase's own now-explicit numbers, not guessed: the
# provider HTTP call itself is capped at 60s (providers/*.py), R2 upload at
# up to ~180s worst case (2 attempts × (30s connect + 60s read),
# services/assets.py) — 300s covers that with real margin rather than
# cutting off a slow-but-succeeding upload. If this ever actually fires,
# arq auto-retries the task (up to MAX_PROVIDER_TRIES) same as a caught
# TransientProviderError — but unlike that path, arq's retry doesn't touch
# this app's own Job row/credit hold, so a run that exhausts all retries
# this way leaves the job `processing` with its hold still active until
# the stuck-job sweep (worker/cron.py, ADR 0007) resolves it — the real
# backstop for exactly this edge case, not something arq's timeout itself
# guarantees.
_JOB_TIMEOUT_SECONDS = 300

_tts_function = func(run_tts_job, name="run_tts_job", max_tries=MAX_PROVIDER_TRIES)
_training_function = func(
    run_voice_model_training_job, name="run_voice_model_training_job", max_tries=MAX_PROVIDER_TRIES
)
_kie_submit_function = func(
    run_kie_submit_job, name="run_kie_submit_job", max_tries=MAX_PROVIDER_TRIES
)


class FishAudioWorker:
    """Both Fish TTS and clone training call the same Fish Audio account,
    so they share this queue and its concurrency cap. `max_jobs=4` against
    a *verified, real* `ratelimit-limit-concurrency: 5` response header
    (see `providers/fish_audio.py`'s module docstring) — one seat of
    headroom rather than running right up against the observed ceiling."""

    functions: ClassVar[list] = [_tts_function, _training_function]
    queue_name = QUEUE_NAMES["fish_audio"]
    redis_settings = redis_settings()
    max_jobs = 4
    job_timeout = _JOB_TIMEOUT_SECONDS
    poll_delay = WORKER_POLL_DELAY_SECONDS


class AzureWorker:
    """No comparable hard limit has been observed for this account yet —
    this number is a provisional guess, not measured. Revisit if Azure ever
    starts rejecting/throttling concurrent requests."""

    functions: ClassVar[list] = [_tts_function]
    queue_name = QUEUE_NAMES["azure"]
    redis_settings = redis_settings()
    max_jobs = 20
    job_timeout = _JOB_TIMEOUT_SECONDS
    poll_delay = WORKER_POLL_DELAY_SECONDS


class GoogleWorker:
    """Same caveat as `AzureWorker` — provisional, not measured."""

    functions: ClassVar[list] = [_tts_function]
    queue_name = QUEUE_NAMES["google"]
    redis_settings = redis_settings()
    max_jobs = 20
    job_timeout = _JOB_TIMEOUT_SECONDS
    poll_delay = WORKER_POLL_DELAY_SECONDS


class KieSubmitWorker:
    """Deliberately its own queue/process (ADR 0014/0015): this task only
    ever calls Kie's createTask and returns — it never waits for Kie to
    finish generating, so its `max_jobs` isn't about Kie's generation
    capacity, only about how many createTask calls can be in flight at
    once. No real limit observed yet (Kie doesn't document one for this
    endpoint) — provisional, same caveat as Azure/Google's numbers."""

    functions: ClassVar[list] = [_kie_submit_function]
    queue_name = QUEUE_NAMES["kie"]
    redis_settings = redis_settings()
    max_jobs = 10
    job_timeout = _JOB_TIMEOUT_SECONDS
    poll_delay = WORKER_POLL_DELAY_SECONDS
