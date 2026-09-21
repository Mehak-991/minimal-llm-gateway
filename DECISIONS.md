# Engineering Decisions

## Build Summary
This project implements a Minimal LLM Gateway in Python using FastAPI and PostgreSQL, sitting between clients and the Groq LLM API. It provides a secure mechanism to issue virtual API keys, strictly enforce token budgets across concurrent requests via atomic database operations, and log exact token usage. It focuses on simplicity, leveraging standard SQLAlchemy ORM abstractions, avoiding heavy external dependencies like Redis or Celery, and protecting the upstream provider credentials. 

## Request Lifecycle
```text
Client Request  (Authorization: Bearer gw-...)
      │
      ▼
[ FastAPI Gateway ]
      │
      ├── 1. Authentication (SHA-256 Hash Lookup via PostgreSQL)
      │
      ├── 2. Budget Reservation (Atomic UPDATE: used_tokens + 2000)
      │      └─ If failed: Return 429 Token budget exceeded
      │
      ├── 3. Forward Request (httpx AsyncClient -> Groq API)
      │      └─ Includes 1 fallback retry for transient timeouts/5xx errors
      │
      ├── 4. Response Parsing (Extract Prompt/Completion Tokens)
      │
      └── 5. Usage Logging & Refund (Refund unused reserved tokens, persist UsageRecord)
      │
      ▼
Client Response (Standard OpenAI Chat Completion Format)
```

## Key Engineering Decisions & Tradeoffs

1. **Token Budgets via Atomic PostgreSQL Updates**
   - *Decision:* Used PostgreSQL atomic updates (`UPDATE ... WHERE budget_tokens >= used_tokens + reservation`) to prevent concurrency budget overruns.
   - *Tradeoff:* Removes the need for a separate distributed lock manager (like Redis) reducing system complexity. However, it relies heavily on the relational database for fast transactional locking under load.
2. **Conservative Reservation Pattern**
   - *Decision:* Because the LLM response token count is unknown ahead of time, the gateway reserves 2,000 tokens per request natively in the DB, refunding the difference afterward.
   - *Tradeoff:* Very simple to implement natively. However, users with just 10 tokens left might be blocked from requests that would only cost 5 tokens, since the flat reservation amount assumes a heavy completion. 
3. **Resilience & Fallback Strategy**
   - *Decision:* Kept it to exactly one retry solely for timeouts and 5xx errors. 
   - *Tradeoff:* Ensures users are shielded from micro-blips in provider availability, but doesn't overcomplicate the architecture with complex circuit breakers or multi-provider fallbacks.
4. **No JWTs for Gateway Auth**
   - *Decision:* Gateway API keys are generated as random strings and hashed into the DB rather than relying on stateless JWTs.
   - *Tradeoff:* Every request requires a database read to authenticate, increasing latency. However, it completely eliminates the complexity of token revocation and instantly enforces budget cutoffs.

## Least Confident Decision
The fixed 2,000 token reservation limit. While simple and atomic, different models and user prompts have wildly varying lengths. A heavily used gateway might experience constant "budget exceeded" bounce backs for users who technically have enough tokens for small prompts but fail the pessimistic ceiling test.

## What Would Break First at Higher Traffic
Database connection exhaustion. As traffic scales, hitting PostgreSQL for authentication, budget reservation, and usage logging (three separate transactional steps) per API request would quickly exhaust standard connection pools. A connection pooler (like PgBouncer) or a fast caching layer (Redis) would be strictly required.

## What Would Be Changed With One More Week
With one more week, I would introduce asynchronous database drivers (like `asyncpg`) to prevent the FastAPI event loop from being blocked by I/O. I would also introduce Redis for rate-limiting and offload the usage logging to a background queue or Kafka to decouple the user response time from the heavy database write.
