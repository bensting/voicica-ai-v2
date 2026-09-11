"""Periodic, backend-initiated work not triggered by an inbound request
(ADR 0007) — provider catalog sync today, a stuck-job sweep later. The
scheduling mechanism itself is still an open ADR 0007 item (deferred until
backend hosting is decided); these are plain callables in the meantime."""
