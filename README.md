# Minimal LLM Gateway

A backend HTTP gateway that sits securely between client applications and the Groq LLM API. The service proxies standard chat completion requests while issuing virtual API keys, enforcing per-key token budgets, and persisting usage and cost metrics. Built for resilience, it includes a retry policy to shield clients from transient upstream timeouts and provider failures.

## Features
- **HTTP Proxy:** 1-to-1 proxy of standard OpenAI `chat/completions` payload to Groq.
- **Virtual API Keys:** Gateway-issued keys, hashed before database storage.
- **Token Budgets:** Token budget enforcement per key using database constraints.
- **Usage & Cost Tracking:** Extracts and logs prompt, completion, and total tokens, estimating costs per request.
- **Resilience:** Explicit 1-retry fallback policy for 5xx and timeout errors.
- **Security:** Hides the upstream provider API credentials from the client.

## Architecture / Request Lifecycle
```text
Client
  │
  │  POST /v1/chat/completions
  │  Authorization: Bearer <gateway-key>
  ▼
FastAPI Gateway
  │
  ├── 1. Authenticate Gateway Key (SHA-256 hash lookup in PostgreSQL)
  │
  ├── 2. Budget Reservation (Database reservation of maximum tokens)
  │      └─ Rejects if budget is exhausted (HTTP 429).
  │
  ├── 3. Forward Request (httpx AsyncClient -> Groq API)
  │      └─ Retries exactly once on transient timeouts or 5xx provider faults.
  │
  ├── 4. Parse Response (Extract prompt and completion tokens natively)
  │
  └── 5. Usage Logging (Refund unused reserved tokens, persist UsageRecord)
  │
  ▼
Client Response (Standard OpenAI Chat Completion Format)
```

## Project Structure
```text
minimal-llm-gateway/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── models.py
│   └── db/
│       ├── __init__.py
│       └── postgres.py
├── tests/
│   └── test_fallback.py
├── .env.example
├── .gitignore
├── AI-LOG.md
├── DECISIONS.md
├── README.md
└── requirements.txt
```

## Tech Stack
- **Framework:** FastAPI / Uvicorn (Python 3.9+)
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy
- **HTTP Client:** HTTPX (Asynchronous proxying)
- **Testing:** Pytest, Respx, Pytest-Asyncio

## API Endpoints

### `GET /health`
Validates basic connectivity.
```bash
curl -X GET http://localhost:8000/health
```

### `POST /keys`
Creates a gateway virtual API key with a default 10,000 token budget.
```bash
curl -X POST http://localhost:8000/keys
```

### `GET /usage`
Retrieves token budget and actual spend.
- **Auth:** `Authorization: Bearer <gateway-key>`
```bash
curl -X GET http://localhost:8000/usage \
     -H "Authorization: Bearer <gateway-key>"
```

### `POST /v1/chat/completions`
Standard OpenAI chat completion request proxy (non-streaming).
- **Auth:** `Authorization: Bearer <gateway-key>`
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
     -H "Authorization: Bearer <gateway-key>" \
     -H "Content-Type: application/json" \
     -d '{"model": "openai/gpt-oss-20b", "messages": [{"role": "user", "content": "Hello!"}]}'
```

## Authentication & Security
- **Virtual Gateway API Keys:** Clients authenticate via standard `Bearer` tokens provided by the gateway. The gateway only stores the `SHA-256` hash of this token.
- **Provider API Key Protection:** The upstream Groq API key remains entirely server-side. It is never passed back to the client or logged.
- **Environment Isolation:** Secrets are excluded from version control via `.gitignore`. 

## Per-Key Token Budget
Budgets are tracked in PostgreSQL. A fixed reserve limit is applied to every request before network execution. If the user's `budget_tokens` falls below the reserve requirement, the request is bounced at the database level.

## Usage & Cost Logging
The API intercepts the JSON provider response, extracts the `"usage"` payload natively, computes pricing based on environment configurations, and inserts an audit log into the `usage_records` table mapping the cost to the virtual key hash.

## Retry / Resilience Policy
- The gateway utilizes `httpx` within a bounded retry loop targeting a maximum of 2 total attempts (1 initial + 1 retry).
- It explicitly retries ONLY on network timeouts or HTTP 5xx faults.
- HTTP 400-499 errors fail without retrying.

## Environment Configuration
Configuration is provided through environment variables. Configure using `.env`:
```ini
GATEWAY_PORT=8000
GATEWAY_ENV=development

LLM_PROVIDER=groq
LLM_PROVIDER_API_KEY=<provider-key>
LLM_PROVIDER_DEFAULT_MODEL=openai/gpt-oss-20b
LLM_PROVIDER_TIMEOUT=15.0

LLM_PROVIDER_COST_PER_1K_PROMPT=0.00
LLM_PROVIDER_COST_PER_1K_COMPLETION=0.00

DATABASE_URL=postgresql://<user>:<pass>@localhost:5432/<db>
```

## Local Setup
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the configuration template:
   ```bash
   cp .env.example .env
   ```
4. Edit `.env` with your active PostgreSQL credentials and Groq API key.

## Running the Application
```bash
uvicorn app.main:app --reload
```

## Running Tests
Tests use `pytest` and `respx` to mock external HTTP traffic and validate the gateway's fallback logic.
```bash
pytest tests/test_fallback.py -v
```

## Database
Uses standard PostgreSQL. No database migrations (`alembic`) are required for the base assignment—SQLAlchemy's `create_all()` orchestrates the schema identically on boot.

## Deployment
The application can be deployed to a platform that supports a Python/FastAPI service and PostgreSQL.
- Requires an active PostgreSQL service bound to the `DATABASE_URL` environment variable.
- Inject the `LLM_PROVIDER_API_KEY` into your host's environment settings.
- Utilize the standard production start command, leaning on `$PORT` assignment:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```
- The `/health` endpoint is available to bind to platform liveness checks.

## Design Scope
This gateway is purposefully built as a minimalistic intern take-home project. In alignment with the assignment guidelines, complex stretch features such as frontends/dashboards, multi-tenancy models, internal caching layers, and deployment orchestration (Docker/K8s) were deliberately omitted.

## Assignment Alignment
The repository implements the core requirements of the Minimal LLM Gateway assignment, including proxying, virtual API keys, token budget enforcement, usage logging, and provider resilience.

## Documentation
Additional architectural reasoning and execution summaries can be found in:
- [DECISIONS.md](./DECISIONS.md)
- [AI-LOG.md](./AI-LOG.md)
