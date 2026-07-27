# Page Pulse — Architecture Decisions

This document records the reasoning behind the technology and design choices made in the
Page Pulse implementation, along with the alternatives that were considered and why they
were not chosen. It is written after the fact, against the code that actually exists in
`backend/` and `frontend/`, rather than as a forward-looking proposal.

---

## Why FastAPI

The core job of this service is I/O-bound: accept a URL, make one outbound HTTP request,
wait on the network, and return JSON. FastAPI was chosen because:

- **Native `async def` support end-to-end.** Routes, dependencies, and middleware can all
  be `async`, which matters because the service spends nearly all of its time waiting on
  `httpx` rather than doing CPU work. A synchronous framework would need a thread pool to
  achieve the same concurrency.
- **Pydantic v2 is built in, not bolted on.** `AuditRequest`, `AuditData`, `AuditResponse`,
  and `ErrorResponse` (`app/schemas/audit.py`) double as both the validation layer and the
  OpenAPI schema source, so `/docs` is always accurate without separate documentation
  effort.
- **Dependency injection via `Depends`** maps cleanly onto the project's layered
  architecture: `app/dependencies.py` provides `AuditService` and `AuditCache` as
  singletons, and routers stay free of construction logic, which also makes them easy to
  test by overriding dependencies.
- **First-class middleware and exception-handler hooks**, used directly for
  `RequestLoggingMiddleware` and `register_exception_handlers` — no need for a separate
  WSGI-level shim.

**Alternatives considered:**

| Option | Why it was not chosen |
|---|---|
| **Flask** | Synchronous by default; async support exists but is bolted on via extensions rather than being a first-class part of the routing and dependency model. Would have complicated the concurrency story (semaphore + async httpx) for no real benefit. |
| **Django / Django REST Framework** | Far more machinery (ORM, admin, templating) than a stateless, database-free JSON API needs. Async support in Django is newer and less idiomatic than FastAPI's. |
| **aiohttp (bare)** | Fully async, but would require hand-rolling request validation, OpenAPI docs, and dependency injection that FastAPI provides out of the box. Not worth the extra code for this project's scope. |

---

## Why React

The frontend's job is a single, focused interaction: submit a URL, show a loading state,
render a result or an error. React (via Vite) was chosen because:

- **Team familiarity and ecosystem maturity** — React Hook Form and Zod integrate directly
  through `@hookform/resolvers`, giving typed, schema-driven client-side validation
  (`schemas/urlSchema.ts`) with minimal glue code.
- **Component boundaries map naturally onto UI states.** The app's view model is a small,
  explicit union (`idle | loading | success | error` in `App.tsx`), and React's
  conditional rendering handles that directly without a separate state-management library —
  there is no need for Redux or similar given the app has exactly one meaningful piece of
  server state at a time.
- **Vite's dev server and build pipeline** are fast and require near-zero configuration,
  which matters for a project meant to "run in VS Code without modification."
- **TypeScript-first.** React's typing story (via `@types/react`) combined with the shared
  `types/index.ts` (mirroring the backend's Pydantic schema) gives compile-time protection
  against the frontend and backend contracts drifting apart.

**Alternatives considered:**

| Option | Why it was not chosen |
|---|---|
| **Vue 3** | Equally capable, but React was chosen for consistency with the broader ecosystem of tooling requested (React Hook Form, Zod) and for team familiarity. |
| **Next.js** | Adds server-side rendering, file-based routing, and a Node server — none of which this single-page, single-form app needs. The project explicitly targets a static build deployed to Netlify. |
| **Plain HTML/JS** | Would have made the form-validation and typed-state requirements (RHF + Zod, typed `AuditData`) significantly more manual and error-prone. |

---

## Why Async (async/await throughout the backend)

Every I/O boundary in the backend is `async`: the route handler, `AuditService.audit()`,
and the `httpx.AsyncClient` call itself. This was a deliberate choice, not a default:

- **The bottleneck is network latency, not CPU.** A single audit request spends the
  overwhelming majority of its time waiting for a TCP handshake, TLS negotiation, and the
  remote server's response. Async I/O lets one process handle many such waits
  concurrently on a single thread, rather than blocking a worker thread per request.
- **It composes directly with the concurrency limit.** `asyncio.Semaphore` (see below)
  only makes sense in an async context — it's a cooperative primitive, not an OS-level
  lock — so async was a prerequisite for the chosen concurrency-control mechanism.
- **It avoids a second concurrency model.** FastAPI can run sync `def` routes in a thread
  pool, but mixing sync and async code paths for the same operation (fetching a URL) would
  have meant reasoning about two different concurrency models in one service. Committing
  fully to `async def` keeps the mental model — and the code — simpler.

**Alternatives considered:**

| Option | Why it was not chosen |
|---|---|
| **Synchronous `requests` + FastAPI's thread-pool sync routes** | Works, but each in-flight audit ties up a worker thread for the full duration of the request, so the concurrency ceiling becomes "however many threads the pool has" rather than a value the service controls explicitly. |
| **Multiprocessing / worker-per-request** | Massive overhead for a lightweight I/O-bound task; would need process-level coordination for the cache and rate limiter, adding complexity with no throughput benefit for an I/O-bound workload. |

---

## Why `asyncio.Semaphore`

`AuditService` holds a single `asyncio.Semaphore(max_concurrent)`, constructed once per
service instance and shared across all requests it handles. Its job is to cap the number
of **simultaneous outbound fetches** to audited websites, independent of how many HTTP
requests FastAPI is currently accepting.

- **Protects both the server and the audited target.** Without a cap, a burst of audit
  requests could open an unbounded number of outbound connections at once — bad for the
  Page Pulse process's own resource usage, and impolite to whatever site is being audited.
- **It's the simplest correct primitive for the job.** A semaphore directly expresses "at
  most N of this operation in flight," with no polling, no external coordination, and
  automatic release via `async with self._semaphore:` even if the fetch raises.
- **Configurable, not hardcoded**, via `MAX_CONCURRENT_AUDITS` — the correct limit depends
  on deployment resources and is an operational, not a code-level, decision.

**Alternatives considered:**

| Option | Why it was not chosen |
|---|---|
| **`httpx.Limits` (connection-pool limits)** | Controls connections *within* a single client, but the service creates a fresh `AsyncClient` per audit; a semaphore controlling audit-level concurrency is the more direct match for "how many audits can run at once." |
| **External queue (e.g. Celery, RQ)** | Would decouple request-handling from audit execution, but introduces a broker and worker processes that this stage of the project (see `docs/scaling.md`) doesn't yet need — a semaphore is the right-sized solution for a single-process deployment. |
| **No limit at all** | Rejected outright — an unbounded fan-out of outbound requests is both a self-inflicted resource risk and a way to inadvertently DoS whatever site is being audited. |

---

## Why TTL Cache (`cachetools.TTLCache`)

Repeated audits of the same URL within a short window are common — a user re-checking a
result, or a monitoring script polling on an interval shorter than meaningful change.
`AuditCache` wraps a `cachetools.TTLCache`, keyed by normalized URL:

- **Avoids redundant outbound requests.** A cache hit skips the semaphore, the network
  call, and the HTML parsing entirely, which reduces both latency for the caller and load
  on the audited site.
- **In-process and dependency-free.** `cachetools` is a small, pure-Python library — no
  extra service to run, configure, or monitor, which matches the project's constraint of
  no Docker/Redis/Postgres for this stage.
- **Both TTL and max size are bounded and configurable** (`CACHE_TTL_SECONDS`,
  `CACHE_MAX_SIZE`), so the cache can't grow unbounded and staleness is explicitly
  time-boxed rather than indefinite.
- **Explicit `cached` flag in the response** means the cache is never a "hidden" behavior —
  callers always know whether they're looking at a fresh fetch or a cached one.

**Alternatives considered:**

| Option | Why it was not chosen |
|---|---|
| **Redis** | The correct choice once the service runs as multiple instances (see `docs/scaling.md`) — but for a single-process deployment it's an extra network hop and an extra piece of infrastructure to operate, with no benefit over an in-process cache. |
| **No cache** | Would mean every repeated audit of the same URL re-does the full fetch and parse, wasting latency and load for no reason when the underlying page is unlikely to have changed within seconds. |
| **`functools.lru_cache`** | LRU without TTL — would serve stale audit results indefinitely for any URL that stays "hot," which is wrong for a service whose entire value proposition is *current* status. |

---

## Why SlowAPI (rate limiting)

`slowapi` provides per-IP rate limiting on `POST /api/audit`, configured via
`RATE_LIMIT_DEFAULT` (default `100/hour`) and enforced with `@limiter.limit(...)` on the
route.

- **Purpose-built for FastAPI/Starlette**, with `get_remote_address` as the key function —
  no manual header parsing or middleware written from scratch.
- **Protects the concurrency and cache layers from abuse.** Rate limiting is the outermost
  guard: it rejects excess traffic *before* it reaches the semaphore or the cache, so a
  single misbehaving client can't starve the concurrency budget for everyone else.
- **Fits the "no external services" constraint.** SlowAPI's default in-memory storage
  requires no Redis or other backing store, consistent with the project's current
  single-process scope (with a documented upgrade path to a shared store — see
  `docs/scaling.md`).
- **Structured JSON errors, not slowapi's default response**, by registering a custom
  handler for `RateLimitExceeded` in `register_exception_handlers`, so a `429` still
  conforms to the project's `{"success": false, "error": {...}}` contract.

**Alternatives considered:**

| Option | Why it was not chosen |
|---|---|
| **Nginx / API-gateway-level rate limiting** | Effective in production, but this project has no reverse proxy or gateway layer in front of the FastAPI process at this stage — application-level rate limiting keeps the guarantee true even when running the service directly. |
| **Hand-rolled middleware with a dict + timestamps** | Reinventing what slowapi already provides, with more surface area for subtle bugs (race conditions, window-boundary edge cases) than a maintained library. |
| **Redis-backed rate limiting from day one** | Correct for a multi-instance deployment, but premature for a single process — slowapi's in-memory storage is a drop-in replacement for a Redis-backed storage class later, so nothing about this choice is a dead end. |

---

## Why GitHub Actions

`.github/workflows/ci.yml` runs on every push and pull request, with two jobs: install and
test the backend, install and build/type-check the frontend.

- **Zero additional infrastructure.** GitHub Actions runs directly against the repository
  with no CI server to provision or maintain — appropriate for a project explicitly scoped
  to avoid unnecessary operational complexity.
- **Matches the deployment targets.** Render and Netlify (the project's chosen deployment
  platforms) both integrate directly with GitHub; a GitHub-native CI pipeline keeps the
  whole train-of-custody (push → test → deploy) inside one platform.
- **Fast feedback on the exact thing that matters.** The backend job runs `pytest -v`
  against the same `requirements.txt` a developer would install locally; the frontend job
  runs `tsc -b && vite build`, catching type errors and build breakages before they reach
  a deploy step.

**Alternatives considered:**

| Option | Why it was not chosen |
|---|---|
| **CircleCI / Travis CI / GitLab CI** | Any of these would work equally well technically, but they require a separate account, billing relationship, and configuration surface disconnected from where the code already lives (GitHub). No functional advantage for this project's needs. |
| **Jenkins (self-hosted)** | Requires provisioning and maintaining a CI server — directly contradicts the project's "no unnecessary infrastructure" constraint for what is currently a small, two-job pipeline. |
| **No CI** | Rejected — automated testing on every push is a baseline expectation for a "production-grade" service, and the task explicitly requires it. |
