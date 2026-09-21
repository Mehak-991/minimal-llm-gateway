# Minimal LLM Gateway

A minimal HTTP gateway that sits between clients and an LLM provider (Groq). It issues virtual API keys, enforces token budgets, and persists usage logs natively.

## Features
- **Virtual API Keys:** Issue gateway API keys that hash natively to the database.
- **Budget Enforcement:** Token budgets are atomically checked before routing to the provider.
- **Usage Logging:** Requests to the provider are parsed, cost-estimated, and logged.
- **Resilience:** Built-in retry mechanism for transient network timeouts or 5xx provider failures.
- **LLM Proxying:** 1-to-1 proxy of standard OpenAI `chat/completions` API structure to Groq.

## Requirements
- Python 3.9+
- PostgreSQL
- Groq API Key

## Local Setup
1. Clone the repository and navigate into it.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the environment variables configuration template and edit it:
   ```bash
   cp .env.example .env
   ```
   **Important:** Update the `.env` with your actual Postgres database connection string and Groq API credentials. Never commit your `.env` to version control.

## Running Locally
Start the local FastAPI development server:
```bash
uvicorn app.main:app --reload
```

## Running Tests
Run the mock resilience test suite via pytest:
```bash
pytest tests/test_fallback.py -v
```

## API Endpoints

### `GET /health`
Validates basic connectivity.

### `POST /keys`
Creates a gateway virtual API key with a default 10,000 token budget.

### `GET /usage`
**Header:** `Authorization: Bearer <GATEWAY_API_KEY>`
Retrieves token budget and actual spend.

### `POST /v1/chat/completions`
**Header:** `Authorization: Bearer <GATEWAY_API_KEY>`
Standard OpenAI chat completion request that routes through the gateway.

## Production Start Command
For deployment platforms (like Render, Railway, AWS AppRunner), run:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
*(Ensure all environment variables defined in `.env.example` are securely injected into your deployment environment.)*
