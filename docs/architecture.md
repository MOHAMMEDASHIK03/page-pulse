# Page Pulse — System Architecture

This document describes the architecture of Page Pulse as implemented: a FastAPI backend
performing asynchronous URL audits, and a React/Vite/TypeScript frontend consuming it. It
reflects the actual code in `backend/app/` and `frontend/src/` — no proposed or aspirational
components are included here.

## Table of Contents

- [High-Level Architecture](#high-level-architecture)
- [Component Diagram](#component-diagram)
- [Data Flow](#data-flow)
- [Request Lifecycle](#request-lifecycle)
- [API Flow](#api-flow)
- [Cache Flow](#cache-flow)
- [Logging Flow](#logging-flow)

---

## High-Level Architecture

Page Pulse is a two-tier system: a stateless SPA and a stateless (aside from its in-memory
cache) API service. There is no database and no external message broker — state that needs
to persist across requests lives only in two in-process structures owned by the backend: the
`AuditCache` (a `cachetools.TTLCache`) and the `slowapi` rate-limiter's counter store.

```mermaid
graph TB
    subgraph Client["Client — Browser"]
        UI["React 19 + Vite SPA<br/>Tailwind CSS UI"]
    end

    subgraph Backend["Page Pulse API — FastAPI (single process)"]
        MW["Middleware chain<br/>CORS → SlowAPI → Request Logging → Error Handlers"]
        RT["Routers<br/>/api/audit · /health"]
        SVC["Services<br/>AuditService · AuditCache"]
        CACHE[("In-memory TTL Cache")]
    end

    subgraph External["Audited Target"]
        SITE["Any http(s) website"]
    end

    UI -- "Axios: POST /api/audit" --> MW
    MW --> RT
    RT --> SVC
    SVC <--> CACHE
    SVC -- "httpx.AsyncClient GET" --> SITE
    RT -- "JSON response" --> UI
```

**Key architectural properties:**

- **Stateless horizontally, stateful locally.** Each backend process holds its own cache and
  rate-limit counters in memory. Running multiple instances behind a load balancer (see
  `docs/scaling.md`) means cache hits and rate limits are currently per-instance, not
  shared — an explicit, documented trade-off of the current single-process design.
- **No business logic in the HTTP layer.** Routers (`app/routers/audit.py`,
  `app/routers/health.py`) only parse input, call a service, and shape the response.
- **Single external dependency at runtime.** The only outbound network call the backend
  makes is the `httpx.AsyncClient` GET request to the audited URL.

---

## Component Diagram

```mermaid
graph LR
    subgraph frontend["frontend/src"]
        App["App.tsx<br/>(view-state orchestration)"]
        Form["UrlForm.tsx<br/>React Hook Form + Zod"]
        Result["AuditResultCard.tsx"]
        Api["lib/api.ts<br/>Axios client, ApiError"]
        App --> Form
        App --> Result
        App --> Api
    end

    subgraph backend["backend/app"]
        Main["main.py<br/>App factory"]

        subgraph Middleware["middleware/"]
            Logging["logging_middleware.py<br/>RequestLoggingMiddleware"]
            ErrHandler["error_handler.py<br/>register_exception_handlers"]
        end

        RateLimiter["rate_limiter.py<br/>slowapi Limiter"]

        subgraph Routers["routers/"]
            AuditRouter["audit.py<br/>POST /api/audit"]
            HealthRouter["health.py<br/>GET /health"]
        end

        subgraph Services["services/"]
            AuditSvc["audit_service.py<br/>AuditService"]
            CacheSvc["cache_service.py<br/>AuditCache"]
        end

        subgraph Utils["utils/"]
            Validators["validators.py"]
            Exceptions["exceptions.py"]
        end

        Deps["dependencies.py<br/>DI providers"]
        Config["config.py<br/>Settings (env-driven)"]

        Main --> Middleware
        Main --> RateLimiter
        Main --> Routers
        AuditRouter --> Deps
        Deps --> AuditSvc
        Deps --> CacheSvc
        AuditSvc --> CacheSvc
        AuditSvc --> Validators
        AuditSvc --> Exceptions
        AuditRouter --> RateLimiter
        Config -.-> Deps
        Config -.-> RateLimiter
    end

    Api -- "HTTP/JSON" --> AuditRouter
```

Each subdirectory has exactly one responsibility, matching the folder structure declared in
`README.md`:

| Layer | Directory | Responsibility |
|---|---|---|
| Transport | `routers/` | Parse HTTP requests, call one service, return a schema |
| Business logic | `services/` | Fetching, parsing, caching, concurrency control |
| Contract | `schemas/` | Pydantic v2 request/response models |
| Cross-cutting | `middleware/` | Logging and global error translation |
| Pure functions | `utils/` | URL validation, typed exceptions |
| Wiring | `dependencies.py`, `main.py` | Dependency injection, app assembly |

---

## Data Flow

Data flows in one direction per request — there is no bidirectional streaming or
server-push. The diagram below traces a single audit from user input to rendered result.

```mermaid
flowchart LR
    A["User types URL"] --> B["Zod validation<br/>(urlSchema.ts)"]
    B -- "invalid" --> B1["Inline form error<br/>(no request sent)"]
    B -- "valid" --> C["Axios POST /api/audit<br/>(lib/api.ts)"]
    C --> D["FastAPI receives request"]
    D --> E["Pydantic validates body<br/>(AuditRequest)"]
    E -- "invalid" --> E1["422 VALIDATION_ERROR"]
    E -- "valid" --> F["AuditService.audit(url)"]
    F --> G["validate_and_normalize_url()"]
    G -- "invalid" --> G1["400 INVALID_URL"]
    G -- "valid" --> H{"In AuditCache?"}
    H -- "hit" --> I["Return cached AuditData<br/>cached=true"]
    H -- "miss" --> J["Acquire semaphore slot"]
    J --> K["httpx.AsyncClient GET<br/>(follow redirects)"]
    K --> L["Parse title / meta description<br/>Build AuditData, cached=false"]
    L --> M["Store in AuditCache"]
    I --> N["JSON response to client"]
    M --> N
    N --> O["React renders AuditResultCard"]
```

---

## Request Lifecycle

Every request to the FastAPI app — not just `/api/audit` — passes through the same
middleware chain, registered in `app/main.py` in this order:

```mermaid
sequenceDiagram
    participant C as Client
    participant CORS as CORSMiddleware
    participant SA as SlowAPIMiddleware
    participant Log as RequestLoggingMiddleware
    participant R as Router
    participant EH as Exception Handlers

    C->>CORS: HTTP request
    CORS->>SA: allowed origin check
    SA->>Log: rate-limit state attached
    Log->>Log: generate request_id (uuid4)<br/>start timer
    Log->>R: call_next(request)
    alt Success
        R-->>Log: Response
        Log->>Log: compute response_time_ms<br/>emit structured JSON log
        Log-->>C: Response + X-Request-ID header
    else Raised exception
        R--xEH: PagePulseError / ValidationError / RateLimitExceeded / Exception
        EH-->>Log: structured JSON error response
        Log->>Log: log error field, still emits log line
        Log-->>C: Response + X-Request-ID header
    end
```

This guarantees two invariants regardless of outcome:

1. **Every response carries `X-Request-ID`**, set by `RequestLoggingMiddleware` in a
   `finally`-adjacent path so it applies to both success and error responses.
2. **Every response body conforms to the `{success, data}` / `{success, error}` envelope** —
   enforced by `register_exception_handlers`, which registers handlers for
   `PagePulseError`, `RequestValidationError`, `RateLimitExceeded`, and the bare `Exception`
   class as a catch-all.

---

## API Flow

Detailed sequence for `POST /api/audit`, covering the dependency-injected service layer:

```mermaid
sequenceDiagram
    participant FE as Frontend (Axios)
    participant Route as audit.py (router)
    participant Dep as dependencies.py
    participant Svc as AuditService
    participant Val as validators.py
    participant Cache as AuditCache
    participant HTTP as httpx.AsyncClient
    participant Target as Audited Website

    FE->>Route: POST /api/audit {url}
    Route->>Dep: Depends(get_audit_service)
    Dep-->>Route: AuditService singleton
    Route->>Svc: audit(payload.url)
    Svc->>Val: validate_and_normalize_url(url)
    alt Invalid URL
        Val--xSvc: raise InvalidURLError
        Svc--xRoute: propagate
        Route--xFE: 400 {success:false, error:{code:"INVALID_URL"}}
    else Valid URL
        Val-->>Svc: normalized_url
        Svc->>Cache: get(normalized_url)
        alt Cache hit
            Cache-->>Svc: cached AuditData
            Svc-->>Route: copy with cached=true
        else Cache miss
            Svc->>Svc: acquire asyncio.Semaphore
            Svc->>HTTP: GET normalized_url (timeout, follow_redirects)
            HTTP->>Target: HTTP GET
            Target-->>HTTP: response (or timeout/connect error)
            HTTP-->>Svc: httpx.Response
            Svc->>Svc: extract title/meta, build AuditData
            Svc->>Cache: set(normalized_url, AuditData)
            Svc-->>Route: AuditData (cached=false)
        end
        Route-->>FE: 200 {success:true, data:{...}}
    end
```

---

## Cache Flow

The cache is a single `cachetools.TTLCache` wrapped by `AuditCache`
(`services/cache_service.py`), keyed by the **normalized URL string**, constructed once as a
process-lifetime singleton via `dependencies.get_audit_cache()` (`@lru_cache`).

```mermaid
flowchart TD
    A["AuditService.audit(url)"] --> B["normalize URL"]
    B --> C{"cache.get(url)"}
    C -- "found & not expired" --> D["Return AuditData.copy(cached=True)"]
    C -- "not found or expired" --> E["Run full audit<br/>(semaphore + httpx fetch)"]
    E --> F["cache.set(url, AuditData)<br/>entry stamped with TTL"]
    F --> G["Return AuditData (cached=False)"]
    D --> H["Response to client"]
    G --> H

    subgraph TTLCache["cachetools.TTLCache internals"]
        F -.-> T1["Entry expires after<br/>CACHE_TTL_SECONDS (default 300s)"]
        T1 -.-> T2["Evicted lazily on next access,<br/>or when CACHE_MAX_SIZE is exceeded (LRU eviction)"]
    end
```

Notes that match the implementation directly:

- **Cache key = normalized URL, not the raw input string.** `validate_and_normalize_url()`
  runs before the cache lookup, so `https://example.com` and a URL with surrounding
  whitespace resolve to the same cache entry.
- **The rate limiter check happens independently of the cache.** Because `@limiter.limit`
  decorates the route function itself, a cached response still consumes one unit of the
  caller's rate-limit quota — only the expensive upstream fetch is skipped.
- **TTL and max size are both configurable** via `CACHE_TTL_SECONDS` and `CACHE_MAX_SIZE`
  (see `docs/decisions.md` and the root `README.md` for the full environment variable
  table).

---

## Logging Flow

`RequestLoggingMiddleware` (`middleware/logging_middleware.py`) is the single source of
structured logs for HTTP traffic. It emits one JSON line per request to the
`page_pulse.access` logger; `middleware/error_handler.py` additionally logs unexpected
exceptions (with full traceback, server-side only) to `page_pulse.errors`.

```mermaid
flowchart LR
    A["Request enters middleware"] --> B["request_id = uuid4()<br/>start = perf_counter()"]
    B --> C["request.state.request_id = request_id"]
    C --> D["await call_next(request)"]
    D --> E{"Exception raised?"}
    E -- "yes" --> F["error_message = str(exc)<br/>re-raise after logging"]
    E -- "no" --> G["status_code = response.status_code"]
    F --> H
    G --> H["Build structured log payload:<br/>timestamp, request_id, ip, method,<br/>path, status, response_time_ms,<br/>cache_hit, error"]
    H --> I["logger.info(json.dumps(payload))"]
    I --> J["response.headers['X-Request-ID'] = request_id"]
    J --> K["Response returned to client"]
```

Example log line as actually emitted:

```json
{"timestamp": "2026-07-27T05:30:24Z", "request_id": "0f7b5905-2c67-4b27-893e-ee3ccdad928f", "ip": "127.0.0.1", "method": "POST", "path": "/api/audit", "status": 200, "response_time_ms": 187.42, "cache_hit": false, "error": null}
```

The `cache_hit` field is populated by the router (`request.state.cache_hit =
result.cached`) after the service call returns, then read by the logging middleware once
`call_next` completes — this is why cache-hit visibility lives in the log line without the
logging middleware needing any knowledge of the audit domain itself.

See `docs/monitoring.md` for how this logging foundation extends into request-tracing,
metrics, and alerting as the service scales.
