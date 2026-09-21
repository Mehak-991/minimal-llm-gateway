# Minimal LLM Gateway

A backend HTTP gateway designed to sit securely between client applications and an upstream LLM provider (Groq). It issues virtual API keys, enforcing strict token budgets to prevent overspending, and persists exact token usage and estimated cost logs natively. It also provides built-in resilience, automatically retrying transient provider failures before failing gracefully.

## Features

- HTTP LLM proxy endpoint
- Non-streaming chat completion flow
- Gateway-issued virtual API keys
- Server-side provider API key protection
- Per-key token budget enforcement
- Usage logging
- Input/output/total token tracking
- Estimated cost tracking
- Protected usage endpoint
- Provider retry/resilience behavior
- Clear failure response after retry exhaustion
- Health check

## Architecture

The request lifecycle is strictly enforced to protect upstream credentials and guarantee budget compliance:

```text
Client
  |
  | Authorization: Bearer <gateway-key>
  v
FastAPI Gateway
  |
  +--> Authenticate Gateway Key
  |
  +--> Check Token Budget
  |
  +--> Forward Request
  |
  v
Groq LLM Provider
  |
  +--> Retry once on eligible transient failure
  |
  v
Response
  |
  +--> Persist Usage / Token / Cost Data
  |
  v
Client
```

1. **Authenticate Gateway Key:** The client provides a virtual gateway key. The gateway securely hashes this key and looks it up in the PostgreSQL database.
2. **Check Token Budget:** An atomic database update reserves tokens to ensure the request is authorized within the user's budget ceiling, rejecting it immediately if funds are exhausted.
3. **Forward Request & Retry:** The request is passed to the Groq API using the protected server-side provider key. Transient network timeouts or 5xx server errors are caught and retried exactly once.
4. **Persist Usage:** The actual prompt and completion tokens are extracted from the provider's response. The database is updated to correct the token reservation and a persistent usage record is saved.

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

## Setup & Running Locally

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Configure Environment:**
   Copy `.env.example` to `.env` and fill in your real Groq API key and PostgreSQL URL.
   ```bash
   cp .env.example .env
   ```
3. **Run the Server:**
   ```bash
   uvicorn app.main:app --reload
   ```

## Testing
Run the mock resilience test suite via pytest:
```bash
pytest tests/test_fallback.py -v
```
