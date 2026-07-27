# Page Pulse — Failure Modes

This document catalogs the ways an audit request can fail — client-side and server-side —
and describes exactly how the current implementation detects and handles each one. Every
behavior described here is backed by code in `backend/app/` or `frontend/src/`, and by a
corresponding test in `backend/tests/` where one exists.

## Table of Contents

- [Invalid URL](#invalid-url)
- [DNS Failure](#dns-failure)
- [SSL Failure](#ssl-failure)
- [Timeout](#timeout)
- [Rate Limit](#rate-limit)
- [Cache Miss](#cache-miss)
- [Backend Crash](#backend-crash)
- [Frontend Network Failure](#frontend-network-failure)
- [Summary Table](#summary-table)

---

## Invalid URL

**Where it's caught:** Twice — once client-side, once server-side. This is deliberate
defense in depth, not redundancy for its own sake.

1. **Client-side (`frontend/src/schemas/urlSchema.ts`):** Zod validates that the input
   parses as a `URL` and that its protocol is `http:` or `https:`, via React Hook Form's
   `zodResolver`. An invalid URL never leaves the browser — the user sees an inline error
   under the input field and no network request is made.
2. **Server-side (`backend/app/utils/validators.py`):** `validate_and_normalize_url()`
   independently re-validates the URL using `urllib.parse.urlparse`, checking the scheme is
   in `{"http", "https"}` and that a host is present. This exists because the API must be
   safe to call directly (via `/docs`, curl, or any other client that bypasses the React
   form) — client-side validation is a UX convenience, not a security boundary.

**Handling:** `validate_and_normalize_url()` raises `InvalidURLError`, caught by the
`PagePulseError` handler in `middleware/error_handler.py`, which returns:

```json
{ "success": false, "error": { "code": "INVALID_URL", "message": "Invalid URL. Only http:// and https:// URLs are supported." } }
```

with HTTP status `400`. Covered by `tests/test_audit.py::test_invalid_url_returns_structured_error`.

A related case — a syntactically valid but semantically empty JSON body (e.g. missing the
`url` field entirely) — is caught one layer earlier by Pydantic's `AuditRequest` model and
surfaces as `VALIDATION_ERROR` / `422`, tested in
`test_missing_url_field_returns_validation_error`.

---

## DNS Failure

**Where it's caught:** `AuditService._perform_audit()`, inside the `try/except` around the
`httpx.AsyncClient.get()` call.

A hostname that doesn't resolve raises `httpx.ConnectError` (DNS resolution failures are
surfaced by httpx/httpcore as connection errors, not a distinct exception type). The
service catches `httpx.ConnectError` explicitly and raises `UnreachableHostError`.

**Handling:** Translated by the global `PagePulseError` handler into:

```json
{ "success": false, "error": { "code": "UNREACHABLE", "message": "Could not connect to host for <url>." } }
```

with HTTP status `502`. The distinction between this and a `TIMEOUT` matters operationally:
`UNREACHABLE` means the request never got a connection at all (bad hostname, refused
connection, network unreachable); `TIMEOUT` means a connection may have been attempted but
no response arrived in time.

---

## SSL Failure

**Where it's caught:** Also inside `AuditService._perform_audit()`'s exception handling,
one level up from `httpx.ConnectError`.

TLS handshake failures (expired certificate, self-signed cert, protocol mismatch) surface
from httpx as subclasses of `httpx.HTTPError` (specifically transport-level errors during
connection setup). Because `AuditService` catches `httpx.TimeoutException` and
`httpx.ConnectError` specifically and then falls through to a broader
`except httpx.HTTPError as exc`, SSL/TLS failures are caught by that final branch and
raised as `AuditFailedError`.

**Handling:** Returns:

```json
{ "success": false, "error": { "code": "AUDIT_FAILED", "message": "Failed to audit <url>: <underlying httpx error>" } }
```

with HTTP status `502`. The underlying httpx exception's message is included because it is
a description of a connection-level failure — not sensitive application internals — which
is consistent with the project's rule of never leaking a stack trace while still returning
an actionable error message.

---

## Timeout

**Where it's caught:** `AuditService._perform_audit()`, the first `except` clause,
matching `httpx.TimeoutException`.

The client is constructed with `httpx.Timeout(self._timeout_seconds)`, where
`timeout_seconds` comes directly from the `REQUEST_TIMEOUT_SECONDS` environment variable
(default `10`). If the audited server doesn't respond — or responds too slowly — within
that window, httpx raises `httpx.TimeoutException`.

**Handling:** Caught and re-raised as `AuditTimeoutError`, which the global handler
converts to:

```json
{ "success": false, "error": { "code": "TIMEOUT", "message": "The request to <url> timed out after <N>s." } }
```

with HTTP status `504`. Critically, this is a normal, expected control-flow path — the
service **never crashes** on a slow or unresponsive target; the exception is caught at the
service boundary and always converted to a structured JSON response. Covered by
`tests/test_audit.py::test_timeout_returns_structured_timeout_error`, which mocks the
timeout with `respx` rather than relying on a real slow endpoint.

---

## Rate Limit

**Where it's caught:** `slowapi`'s `Limiter`, applied via `@limiter.limit(...)` on the
`POST /api/audit` route in `routers/audit.py`, keyed by client IP
(`get_remote_address`, configured in `rate_limiter.py`).

When a single IP exceeds the configured budget (`RATE_LIMIT_DEFAULT`, default `100/hour`),
slowapi raises `RateLimitExceeded` before the route body — and therefore before the cache
lookup or any outbound fetch — ever executes.

**Handling:** A dedicated handler registered in `register_exception_handlers` converts this
into:

```json
{ "success": false, "error": { "code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests. Please try again later." } }
```

with HTTP status `429` — overriding slowapi's default plain-text response so the contract
stays consistent with every other endpoint. Because the check happens at the route
decorator level, it applies uniformly regardless of whether the request would have been a
cache hit or a fresh fetch: **rate limiting is enforced before caching is even
considered**, which is the correct order — a client abusing the endpoint with cached URLs
should still be throttled. Covered by `tests/test_rate_limit.py`, which configures a small
test-only limit (`3/minute`) via `conftest.py` to make the test deterministic and fast.

---

## Cache Miss

This isn't a failure in the error-response sense — it's the default, expected path — but
it's worth documenting explicitly because it's the branch where the most can go wrong
downstream.

**Where it happens:** `AuditService.audit()` calls `self._cache.get(normalized_url)`; a
`None` result (key absent, or present but expired per the TTL) means "cache miss," and
execution proceeds into `_perform_audit()` — the semaphore-guarded network fetch.

**Handling:** No special error handling is needed for the miss itself; it's a normal
`if cached is None:` branch. What matters is what happens *next*: a cache miss is the entry
point into every other failure mode above (timeout, DNS failure, SSL failure) because it's
the only path that actually reaches the network. A cache **hit**, by contrast, cannot fail
in any of those ways — it returns a `.model_copy(update={"cached": True})` of a previously
successful `AuditData`, with no network I/O at all. Covered indirectly by
`tests/test_audit.py::test_repeat_request_within_ttl_is_served_from_cache`, which asserts
the upstream mock is only called once across two identical requests.

---

## Backend Crash

Two distinct scenarios fall under this heading, handled differently:

**1. An unexpected exception during request handling (process stays alive).**
Any exception not already a `PagePulseError` — a bug, an unforeseen edge case in HTML
parsing, etc. — is caught by the catch-all `@app.exception_handler(Exception)` in
`middleware/error_handler.py`. It:

- Logs the full exception server-side via `logger.exception(...)`, tagged with the
  request's UUID (`request_id`), to the `page_pulse.errors` logger.
- Returns a generic, non-leaking response to the client:

```json
{ "success": false, "error": { "code": "INTERNAL_ERROR", "message": "An unexpected error occurred." } }
```

  with HTTP status `500` — never a stack trace, never internal exception details, matching
  the project's hard requirement that the API "never expose stack traces."

**2. The process itself dies (crashes, is killed, or fails to start).**
This is outside what in-process exception handling can address — there is no code that can
catch the process's own termination. This is the layer at which `GET /health` and external
process supervision matter:

- `uvicorn --reload` (local dev) or the platform's process manager (Render, in production —
  see `docs/scaling.md`) is responsible for restarting a crashed process.
- `/health` gives any supervisor or load balancer a cheap, dependency-free endpoint to
  detect "the process is up and answering," decoupled from whether any particular audit
  succeeds.
- Because the backend holds no persistent state outside its in-memory cache, a restart is
  safe and lossless from a correctness standpoint — the only cost of a crash-and-restart is
  a cold cache and reset rate-limit counters, not corrupted or lost data.

---

## Frontend Network Failure

**Where it's caught:** `frontend/src/lib/api.ts`, in `auditUrl()`'s `catch` block, which
normalizes every possible failure mode into a single typed `ApiError` so components never
handle raw Axios errors.

Three distinct network-failure shapes are handled explicitly:

1. **The backend responded with a structured error** (any of the `4xx`/`5xx` cases
   documented above). Axios surfaces this as an `AxiosError` with a `response` — `api.ts`
   reads `error.response?.data`, and if it matches the `{success: false, error: {...}}`
   shape, re-throws it as `ApiError` with the backend's own `code` and `message` preserved.
2. **The client-side request timed out** (`error.code === "ECONNABORTED"`, from Axios's own
   20-second `timeout` config in `client`). Mapped to a synthetic `ApiError("TIMEOUT", ...)`
   so the UI's error card looks identical whether the timeout happened server-side or
   client-side.
3. **The backend is unreachable at all** — connection refused, DNS failure on the client's
   own network, CORS rejection, or the backend simply not running. This is any `AxiosError`
   without a usable `response` payload, mapped to
   `ApiError("NETWORK_ERROR", "Could not reach the Page Pulse API. Is the backend
   running?")` — a message specific enough to be actionable during local development.

**Handling in the UI:** `App.tsx`'s `handleAudit()` catches any thrown `ApiError` and sets
`view = {status: "error", code, message}`, which `AuditErrorCard.tsx` renders with
`role="alert"` (for assistive technology) and the error's `code`/`message` displayed
directly — the same structured-error contract the backend guarantees is preserved all the
way to the pixel the user sees.

---

## Summary Table

| Failure | Detected in | Raised as | HTTP status | Error code |
|---|---|---|---|---|
| Invalid URL (client) | `urlSchema.ts` (Zod) | inline form error | — (no request sent) | — |
| Invalid URL (server) | `utils/validators.py` | `InvalidURLError` | 400 | `INVALID_URL` |
| Malformed request body | Pydantic (`AuditRequest`) | `RequestValidationError` | 422 | `VALIDATION_ERROR` |
| DNS failure | `services/audit_service.py` | `UnreachableHostError` | 502 | `UNREACHABLE` |
| SSL/TLS failure | `services/audit_service.py` | `AuditFailedError` | 502 | `AUDIT_FAILED` |
| Timeout | `services/audit_service.py` | `AuditTimeoutError` | 504 | `TIMEOUT` |
| Rate limit exceeded | `rate_limiter.py` (slowapi) | `RateLimitExceeded` | 429 | `RATE_LIMIT_EXCEEDED` |
| Cache miss | `services/cache_service.py` | *(not an error — triggers a fresh fetch)* | — | — |
| Unexpected server exception | `middleware/error_handler.py` | `Exception` (catch-all) | 500 | `INTERNAL_ERROR` |
| Process crash | outside app code | — | — (supervisor restarts process) | — |
| Frontend can't reach backend | `lib/api.ts` | `ApiError` | — (client-side) | `NETWORK_ERROR` |
| Frontend request timeout | `lib/api.ts` | `ApiError` | — (client-side) | `TIMEOUT` |

Every server-side row above resolves to the same JSON envelope shape
(`{"success": false, "error": {"code", "message"}}`), which is the single most important
invariant in this document: **no failure mode, expected or not, ever produces an HTML
error page, an unhandled exception response, or a leaked stack trace.**
