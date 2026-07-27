# Page Pulse

A production-grade, asynchronous URL audit service. Point it at any `http(s)` URL and it
reports back the page's vital signs — status, redirect chain, response time, HTTPS status,
title, meta description, headers, and content length — in real time.

Built for the **Digital Heroes Software Development** qualification task.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Architecture](#architecture)
- [Folder Structure](#folder-structure)
- [API Contract](#api-contract)
- [Environment Variables](#environment-variables)
- [Installation](#installation)
- [Running the Backend](#running-the-backend)
- [Running the Frontend](#running-the-frontend)
- [Running Tests](#running-tests)
- [Deployment](#deployment)

---

## Project Overview

Page Pulse is a two-part application:

- **Backend** — a FastAPI service that validates, fetches, and audits a URL, returning
  structured JSON. It enforces timeouts, a global concurrency ceiling, per-URL TTL caching,
  and per-IP rate limiting, and never leaks a stack trace or an HTML error page.
- **Frontend** — a React + TypeScript single-page app with a dark, glassmorphic UI. Users
  submit a URL and watch an animated "pulse" waveform while the audit runs, then see the
  result rendered as a set of readable stat tiles.

## Features

- ✅ Strict `http(s)` URL validation with structured error responses
- ✅ Async page fetch via `httpx`, following redirects, with full metadata extraction
  (title, meta description, server header, content type, content length)
- ✅ Configurable request timeout — never crashes, always returns a structured `TIMEOUT` error
- ✅ Configurable global concurrency limit via `asyncio.Semaphore`
- ✅ TTL response cache (`cachetools`) with an explicit `cached: true/false` flag
- ✅ Per-IP rate limiting via `slowapi`, JSON error responses on `429`
- ✅ Structured JSON request logging with a per-request UUID (`X-Request-ID`)
- ✅ Global exception handling — every error, expected or not, returns
  `{"success": false, "error": {"code", "message"}}`, never HTML, never a trace
- ✅ `GET /health` liveness endpoint with uptime and version
- ✅ Auto-generated OpenAPI docs at `/docs`
- ✅ Dark-mode, glassmorphic, responsive React UI with an animated signature waveform
- ✅ Client-side validation with React Hook Form + Zod before any request is sent
- ✅ Pytest suite covering valid/invalid URLs, timeouts, caching, rate limiting, and health
- ✅ GitHub Actions CI: installs dependencies and runs the backend test suite (and a
  frontend type-check/build) on every push

## Architecture

The backend follows a layered, dependency-injected architecture with no business logic in
routes:

```
Router (HTTP layer, no logic)
   │
   ▼
Service (business logic: AuditService, AuditCache)
   │
   ▼
Utils (pure functions: validators, exceptions)
```

- **Routers** (`app/routers/`) parse the request, call a service, and shape the response.
  They contain no fetching, parsing, or caching logic themselves.
- **Services** (`app/services/`) own the actual work: `AuditService` performs the async
  fetch + HTML metadata extraction under a semaphore and timeout; `AuditCache` wraps a
  `cachetools.TTLCache`.
- **Schemas** (`app/schemas/`) are Pydantic v2 models defining the exact request/response
  contract, shared between the OpenAPI docs, validation, and serialization.
- **Middleware** (`app/middleware/`) handles two cross-cutting concerns: structured
  request logging (`RequestLoggingMiddleware`) and global exception translation
  (`register_exception_handlers`), so no individual route needs its own try/except for
  the happy path.
- **Dependency injection** (`app/dependencies.py`) constructs `AuditService` and
  `AuditCache` as cached singletons and hands them to routes via FastAPI's `Depends`,
  keeping construction logic out of the routers and making the service trivially
  mockable in tests.

The frontend mirrors this separation: `lib/api.ts` is the only module that knows about
Axios or the API's error envelope; components only ever see typed `AuditData` or a typed
`ApiError`.

## Folder Structure

```
page-pulse/
├── backend/
│   ├── app/
│   │   ├── main.py                 # App factory: wires middleware, routers, CORS
│   │   ├── config.py                # Env-driven Settings (pydantic-settings)
│   │   ├── dependencies.py          # DI providers (cache, service singletons)
│   │   ├── rate_limiter.py          # Shared slowapi Limiter instance
│   │   ├── routers/
│   │   │   ├── audit.py             # POST /api/audit
│   │   │   └── health.py            # GET /health
│   │   ├── services/
│   │   │   ├── audit_service.py     # Fetch, parse, timeout, concurrency
│   │   │   └── cache_service.py     # TTL cache wrapper
│   │   ├── schemas/
│   │   │   └── audit.py             # Pydantic request/response models
│   │   ├── middleware/
│   │   │   ├── logging_middleware.py
│   │   │   └── error_handler.py
│   │   └── utils/
│   │       ├── validators.py
│   │       └── exceptions.py
│   ├── tests/                       # pytest suite (respx-mocked HTTP)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/              # Hero, UrlForm, AuditResultCard, etc.
│   │   ├── lib/api.ts                # Axios client + typed ApiError
│   │   ├── schemas/urlSchema.ts      # Zod validation schema
│   │   ├── types/index.ts            # Shared TS types (mirrors backend schema)
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── .env.example
├── .github/workflows/ci.yml
└── README.md
```

## API Contract

### `POST /api/audit`

**Request**

```json
{ "url": "https://example.com" }
```

**Success — `200 OK`**

```json
{
  "success": true,
  "data": {
    "url": "https://example.com",
    "final_url": "https://example.com/",
    "status_code": 200,
    "response_time_ms": 187.42,
    "https": true,
    "title": "Example Domain",
    "meta_description": "This domain is for use in examples.",
    "content_type": "text/html; charset=UTF-8",
    "server": "ECS",
    "content_length": 1256,
    "timestamp": "2026-07-27T05:30:00Z",
    "cached": false
  }
}
```

**Error — e.g. `400 Bad Request`**

```json
{
  "success": false,
  "error": {
    "code": "INVALID_URL",
    "message": "Invalid URL. Only http:// and https:// URLs are supported."
  }
}
```

| Code                  | HTTP Status | Meaning                                   |
| --------------------- | ----------- | ------------------------------------------ |
| `INVALID_URL`         | 400         | URL failed validation                      |
| `VALIDATION_ERROR`    | 422         | Request body malformed                     |
| `TIMEOUT`              | 504         | Upstream did not respond in time           |
| `UNREACHABLE`          | 502         | Could not connect to host                  |
| `AUDIT_FAILED`         | 502         | Upstream request failed for another reason |
| `RATE_LIMIT_EXCEEDED`  | 429         | Too many requests from this IP             |
| `INTERNAL_ERROR`       | 500         | Unexpected server error (never a trace)    |

### `GET /health`

```json
{ "status": "ok", "version": "1.0.0", "uptime_seconds": 42.1 }
```

### `GET /docs`

Interactive OpenAPI (Swagger) documentation, auto-generated by FastAPI.

## Environment Variables

### Backend (`backend/.env`, see `backend/.env.example`)

| Variable                   | Default                                | Description                                  |
| --------------------------- | --------------------------------------- | --------------------------------------------- |
| `APP_NAME`                  | `Page Pulse`                            | Service name                                 |
| `APP_VERSION`                | `1.0.0`                                 | Reported by `/health`                        |
| `ENVIRONMENT`                | `development`                           | Free-text environment label                  |
| `CORS_ORIGINS`               | `http://localhost:5173,...`             | Comma-separated allowed origins              |
| `REQUEST_TIMEOUT_SECONDS`    | `10`                                    | Per-audit fetch timeout                      |
| `MAX_CONCURRENT_AUDITS`      | `5`                                     | Global `asyncio.Semaphore` size              |
| `USER_AGENT`                 | `PagePulse-Auditor/1.0 (...)`           | User-Agent sent to audited hosts             |
| `CACHE_TTL_SECONDS`          | `300`                                   | How long a result is cached per URL          |
| `CACHE_MAX_SIZE`             | `1000`                                  | Max distinct cached URLs                     |
| `RATE_LIMIT_DEFAULT`         | `100/hour`                              | slowapi rate limit string, per IP            |

### Frontend (`frontend/.env`, see `frontend/.env.example`)

| Variable              | Default                 | Description                     |
| ---------------------- | ------------------------ | -------------------------------- |
| `VITE_API_BASE_URL`     | `http://localhost:8000`  | Base URL of the backend API      |

## Installation

Requires **Python 3.12+**, **Node.js 20+**, and **VS Code** (or any editor/terminal).

```bash
git clone <this-repo>
cd page-pulse
```

## Running the Backend

```bash
cd backend
python -m venv venv

# macOS / Linux
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env      # optional — defaults work out of the box

uvicorn app.main:app --reload
```

The API is now running at `http://localhost:8000` (docs at `/docs`, health at `/health`).

## Running the Frontend

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env      # optional — defaults point at localhost:8000

npm run dev
```

Open `http://localhost:5173`.

## Running Tests

```bash
cd backend
source venv/bin/activate  # if not already active
pytest -v
```

The suite covers: a valid URL audit, an invalid URL, a request timeout, cache hit vs.
miss, rate-limit enforcement, and the health endpoint. All outbound HTTP calls are
mocked with `respx`, so tests run offline and deterministically.

## Deployment

### Backend → Render

1. Push this repo to GitHub.
2. Create a new **Web Service** on Render, pointing at the `backend/` directory.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add the environment variables listed above (set `CORS_ORIGINS` to your Netlify URL).

### Frontend → Netlify

1. Create a new site from the same repo, base directory `frontend/`.
2. Build command: `npm run build`
3. Publish directory: `dist`
4. Add environment variable `VITE_API_BASE_URL` pointing at your Render backend URL.

---

Built for the [Digital Heroes](https://digitalheroesco.com) Software Development
training task.
