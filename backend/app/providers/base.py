"""Abstract provider interface (ADR 0001, refined by ADR 0002).

Every vendor adapter (azure.py, google.py, fish_audio.py, kie.py) implements
this same interface, so `services/` never imports a concrete provider directly
— only this module and `registry.py`. That is what makes swapping or adding a
vendor a one-file change.

`submit()` does the work inline for a synchronous vendor and returns an
already-terminal `JobRef`; for an asynchronous vendor it returns a `pending`
`JobRef` immediately and `poll()` advances it later. See architecture.md §3.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

JobCanonicalStatus = Literal["pending", "processing", "succeeded", "failed"]


@dataclass
class JobRef:
    """What `submit()` returns."""

    status: JobCanonicalStatus
    provider_job_id: str | None = None  # the vendor's own task id, if it has one
    provider_state: str | None = None  # raw vendor state, e.g. Kie's "queuing" (UI only, never logic)
    output: dict[str, Any] | None = None  # present once status is a terminal success; provider-shaped, not yet DB-safe JSON
    error: str | None = None  # present once status is "failed"


@dataclass
class JobStatus:
    """What `poll()` returns."""

    status: JobCanonicalStatus
    provider_state: str | None = None
    output: dict[str, Any] | None = None
    error: str | None = None


class Provider(ABC):
    """One instance per vendor. `services/jobs.py` depends only on this interface."""

    @abstractmethod
    async def submit(self, capability: str, inputs: dict[str, Any]) -> JobRef:
        """Start (and, for a synchronous vendor, finish) a generation request."""
        ...

    async def poll(self, provider_job_id: str) -> JobStatus:
        """Advance an in-flight job. Synchronous vendors never need this —
        their `submit()` already returned a terminal `JobRef` — so the default
        raises rather than silently no-op-ing a call that should never happen.
        """
        raise NotImplementedError(
            f"{type(self).__name__} is synchronous; poll() should never be called for it"
        )
