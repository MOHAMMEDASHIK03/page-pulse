# Page Pulse — Monitoring & Observability

This document describes what Page Pulse currently emits for observability, and — clearly
separated from that — what a production deployment would layer on top. The "today" section
describes only what exists in the code; the "future" section is explicitly forward-looking
and does not describe anything currently implemented.

## Table of Contents

- [Structured Logging](#structured-logging)
- [Request IDs](#request-ids)
- [Response Time](#response-time)
- [Health Endpoint](#health-endpoint)
- [Future: Production Monitoring](#future-production-monitoring)
- [Future: Metrics](#future-metrics)
- [Future: Alerting](#future-alerting)

---

## Structured Logging

Every HTTP request handled by the FastAPI app produces exactly one structured JSON log
line, emitted by `RequestLoggingMiddleware` (`app/middleware/logging_middleware.py`) to the
`page_pulse.access` logger. Logging is configured once in `app/main.py` via
`logging.basicConfig(level=logging.INFO, format="%(message)s")` — the format string is
deliberately just `%(message)s` because the message itself is already a complete JSON
object; wrapping it in Python's default `LEVEL:name:message` format would break JSON
parsing downstream.

**Fields emitted on every request:**

```json
{
  "timestamp": "2026-07-27T05:30:24Z",
  "request_id": "0f7b5905-2c67-4b27-893e-ee3ccdad928f",
  "ip": "127.0.0.1",
  "method": "POST",
  "path": "/api/audit",
  "status": 200,
  "response_time_ms": 187.42,
  "cache_hit": false,
  "error": null
}
```

This single line answers the questions an operator most often needs during an incident —
*who* called, *what* they called, *how it went*, *how long it took*, and *whether it was
served from cache* — without needing to correlate multiple log statements.

A second logger, `page_pulse.errors`, is used exclusively by the catch-all exception
handler in `middleware/error_handler.py`. It logs the **full exception and traceback**
server-side via `logger.exception(...)` — the traceback never leaves the server; it exists
only in this log stream, while the client receives the sanitized `INTERNAL_ERROR` response
described in `docs/failure-modes.md`. This split is intentional: rich diagnostic detail for
operators, a minimal and safe payload for callers.

Because logs are structured JSON rather than free-text, they are immediately compatible
with log-aggregation tooling (see [Future: Production Monitoring](#future-production-monitoring))
without any reformatting step.

---

## Request IDs

Every request is assigned a UUID4 `request_id` at the very start of
`RequestLoggingMiddleware.dispatch()`, before the request reaches any router:

```python
request_id = str(uuid.uuid4())
request.state.request_id = request_id
```

This ID serves two purposes, both already implemented:

1. **It's attached to `request.state`**, making it available to any downstream code in the
   same request — notably the catch-all exception handler, which includes it in its log
   line (`logger.exception("Unhandled exception for request_id=%s", request_id)`), so a
   500 response and its corresponding stack trace can always be tied back together.
2. **It's returned to the caller** as the `X-Request-ID` response header, set
   unconditionally just before the response leaves the middleware — including on error
   responses. This means a user (or a frontend error report) can hand an operator a single
   ID that uniquely identifies their request in the access log, without needing to share
   timestamps or reconstruct which log line was theirs.

Because the ID is generated per-request rather than per-session or per-user, it composes
correctly with concurrent requests, cache hits, and rate-limited requests alike — every one
of them gets its own ID and its own log line, even two audits of the same URL a second
apart.

---

## Response Time

Response time is measured in two places, for two different purposes:

- **Per-request, end-to-end, in the logging middleware.** `RequestLoggingMiddleware` starts
  a `time.perf_counter()` timer as the very first thing it does and computes
  `elapsed_ms` in a `finally` block that runs regardless of success or failure — this is
  the `response_time_ms` field in the access log, and it measures the *entire* request,
  including FastAPI's own routing and validation overhead.
- **Per-audit, network-only, inside `AuditService`.** `_perform_audit()` independently
  times just the `httpx.AsyncClient.get()` call and returns that figure as
  `response_time_ms` inside the `AuditData` payload itself — this is the number shown to
  the end user in the "Response time" stat tile on the frontend, and it specifically
  measures the audited site's responsiveness, not Page Pulse's own overhead.

Keeping these two measurements separate matters: if a user's audit looks slow, this
distinction lets an operator immediately tell whether the delay was in the target site
(reflected in the `AuditData.response_time_ms`) or in Page Pulse itself (reflected in the
gap between the access log's `response_time_ms` and the audit's own figure) — for example,
time spent waiting on the concurrency semaphore.

---

## Health Endpoint

`GET /health` (`app/routers/health.py`) returns:

```json
{ "status": "ok", "version": "1.0.0", "uptime_seconds": 42.1 }
```

- **`status`** is currently a static `"ok"` — the endpoint only responds if the process is
  alive and able to handle a request, so a successful response *is* the signal.
- **`version`** is read from `Settings.APP_VERSION` (`app/config.py`), so a deployed
  instance's version is queryable without needing shell access to the host.
- **`uptime_seconds`** is computed from a module-level `_START_TIME = time.monotonic()`
  captured at import time, giving the number of seconds since the process (not the
  container or host) started — useful for spotting unexpected restarts.

This endpoint deliberately does **not** check the cache, the rate limiter, or make any
outbound network call — it answers "is this process able to serve requests at all," which
is the correct, minimal signal for a load balancer or process supervisor's liveness probe.
It is intentionally cheap: no I/O, no locks, no dependency on the audited internet being
reachable.

---

## Future: Production Monitoring

The structured JSON logs already produced by `RequestLoggingMiddleware` are the foundation
for this — the work described below is about *consuming* that existing log stream, not
changing how it's produced.

- **Centralized log aggregation.** Ship stdout (where `logging.basicConfig` currently
  writes) to a log platform — options appropriate for Render-hosted deployments include
  Render's own log stream export, or a hosted aggregator such as Datadog, Better Stack, or
  Axiom. Because logs are already JSON, this is a shipping/routing problem, not a
  reformatting one.
- **Distributed tracing.** The existing `request_id` is a natural trace ID. Adopting
  OpenTelemetry's FastAPI instrumentation would let a single request's lifecycle — router →
  `AuditService` → the outbound `httpx` call — be visualized as spans, rather than inferred
  from a single log line's timing.
- **Log-based dashboards.** Because `status`, `path`, `cache_hit`, and `response_time_ms`
  are already discrete structured fields, a dashboard (e.g. in Grafana or the aggregator's
  own UI) built directly from raw log queries is possible before any dedicated metrics
  pipeline exists — a reasonable first step before investing in the metrics work below.

## Future: Metrics

Today, the only quantitative signals are the log fields and the `uptime_seconds` on
`/health`. There is no metrics endpoint, no counters, and no histograms. A production
deployment would add:

- **A `/metrics` endpoint** (e.g. via `prometheus-fastapi-instrumentator` or a hand-rolled
  `prometheus_client` integration) exposing, at minimum:
  - `page_pulse_requests_total`, labeled by `path` and `status` — derivable directly from
    the same data already in every access-log line.
  - `page_pulse_audit_duration_seconds` (histogram) — a metrics-native counterpart to the
    `response_time_ms` field already computed in `AuditService`.
  - `page_pulse_cache_hit_ratio` — computed from the existing `cache_hit` boolean, ideally
    exposed as a running counter (`cache_hits_total` / `cache_lookups_total`) rather than a
    pre-divided ratio, so aggregation windows can be chosen at query time.
  - `page_pulse_rate_limited_total` — count of `429` responses, to distinguish "the service
    is slow" from "a client is being throttled" when investigating elevated error rates.
  - `page_pulse_semaphore_wait_seconds` — time spent waiting to acquire the
    `asyncio.Semaphore` in `AuditService`, which today is invisible; this would be the
    clearest signal that `MAX_CONCURRENT_AUDITS` needs to be raised (see
    `docs/scaling.md`).
- **Cache instrumentation.** `AuditCache` (`services/cache_service.py`) already exposes
  `__len__`, making a `page_pulse_cache_size` gauge a near-zero-effort addition once a
  metrics endpoint exists.

## Future: Alerting

No alerting exists today — this section is entirely prospective, describing what should be
built once the metrics above exist to alert on:

- **Availability:** page on repeated `/health` failures (via the hosting platform's own
  health-check-based restart/alert capability, e.g. Render's) — this requires no new
  application code, only platform configuration.
- **Error rate:** alert when the proportion of `5xx` responses (`INTERNAL_ERROR`,
  `AUDIT_FAILED`, `UNREACHABLE`, `TIMEOUT`) over a rolling window exceeds a threshold —
  computable directly from the `status` field already in every log line, or from
  `page_pulse_requests_total{status=~"5.."}` once the metrics endpoint above exists.
  `TIMEOUT` and `UNREACHABLE` in particular are worth watching separately from
  `INTERNAL_ERROR`, since a spike in the former usually points at the *audited sites*
  rather than at Page Pulse itself.
- **Latency:** alert on p95/p99 of `page_pulse_audit_duration_seconds` exceeding a
  threshold — signals either an overloaded `MAX_CONCURRENT_AUDITS` setting or widespread
  slowness among audited targets.
- **Rate-limit saturation:** alert if `page_pulse_rate_limited_total` spikes sharply,
  which may indicate abusive traffic rather than organic growth, and should be
  investigated before simply raising `RATE_LIMIT_DEFAULT`.
- **Delivery channel:** any standard integration (Slack webhook, PagerDuty, email) driven
  off the alerting rules in whatever metrics platform is adopted (Grafana Alerting,
  Datadog Monitors, or similar) — the specific tool is an operational choice independent of
  the application code described in this document.
