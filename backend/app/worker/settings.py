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

from app.core.queue import QUEUE_NAMES, redis_settings
from app.services.jobs import MAX_PROVIDER_TRIES
from app.worker.tasks import run_tts_job, run_voice_model_training_job

_tts_function = func(run_tts_job, name="run_tts_job", max_tries=MAX_PROVIDER_TRIES)
_training_function = func(
    run_voice_model_training_job, name="run_voice_model_training_job", max_tries=MAX_PROVIDER_TRIES
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


class AzureWorker:
    """No comparable hard limit has been observed for this account yet —
    this number is a provisional guess, not measured. Revisit if Azure ever
    starts rejecting/throttling concurrent requests."""

    functions: ClassVar[list] = [_tts_function]
    queue_name = QUEUE_NAMES["azure"]
    redis_settings = redis_settings()
    max_jobs = 20


class GoogleWorker:
    """Same caveat as `AzureWorker` — provisional, not measured."""

    functions: ClassVar[list] = [_tts_function]
    queue_name = QUEUE_NAMES["google"]
    redis_settings = redis_settings()
    max_jobs = 20
