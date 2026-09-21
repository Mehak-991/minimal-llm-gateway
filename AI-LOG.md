# AI Log

## AI Tools Used
- Gemini / Antigravity IDE for architectural planning, code generation, testing configuration, and documentation drafting.

## Wrong or Misleading Suggestion
- **Suggestion:** During the budget checking phase, the AI originally suggested doing a standard `SELECT` to read the budget, validating it in Python, and then running an `UPDATE`. 
- **How it was caught:** I explicitly requested an atomic implementation to handle concurrency. The standard read-then-write pattern would have allowed race conditions where simultaneous requests bypassed the limit. It was caught during code review and corrected to a single atomic `UPDATE` clause with a strict `WHERE` constraint.

## AI Suggestion Overridden
- **Override:** The AI suggested adding a full `alembic` setup for database migrations. 
- **Reason:** For a minimal intern take-home project focused on simplicity and explainability, introducing Alembic felt like unnecessary overhead. I overrode the suggestion and relied on SQLAlchemy's native `Base.metadata.create_all()` which perfectly fits the local scope.

## Maintaining Control Over Secrets
The prompt explicitly required isolating secrets. Whenever generating implementation plans with the AI, I enforced constraints such as `Do NOT hardcode either value`, `Do not expose the Groq key in the response`, and strictly mocked the environment payload manually rather than asking the AI to populate actual secrets. I manually injected `LLM_PROVIDER_API_KEY` straight into my local environment configuration without logging it in any transcript or git-tracked configuration.

## Thing Learned from Scratch
- **Learning:** [FILL IN: Your personal experience here, e.g., using `httpx.AsyncClient` inside FastAPI or understanding atomic PostgreSQL updates over standard transactions.]
- **How:** [FILL IN: e.g., Reading the `httpx` documentation to ensure I properly caught timeouts without crashing the main thread.]
