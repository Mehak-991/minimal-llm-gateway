import secrets
import hashlib
import httpx
from fastapi import FastAPI, Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import text, update
from app.config import settings
from app.db.postgres import engine, Base, get_db
from app.models import VirtualKey, UsageRecord

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Connecting to PostgreSQL and creating tables if necessary...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        Base.metadata.create_all(bind=engine)
        print("Successfully connected to PostgreSQL.")
    except Exception as e:
        print(f"Failed to connect to PostgreSQL: {e}")
        raise e
    yield
    print("Shutting down application...")

app = FastAPI(title="Minimal LLM Gateway", lifespan=lifespan)

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

def get_current_api_key(header_key: str = Security(api_key_header), db: Session = Depends(get_db)):
    if not header_key:
        raise HTTPException(status_code=401, detail="Missing API Key")
    if header_key.startswith("Bearer "):
        header_key = header_key.split(" ")[1]
        
    key_hash = hashlib.sha256(header_key.encode()).hexdigest()
    
    key_doc = db.query(VirtualKey).filter(VirtualKey.key_hash == key_hash).first()
    if not key_doc:
        raise HTTPException(status_code=401, detail="Invalid API Key")
        
    return key_doc

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "ok", 
        "environment": settings.gateway_env,
        "database": db_status
    }

@app.post("/keys")
def create_key(db: Session = Depends(get_db)):
    raw_key = f"gw-{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    
    virtual_key = VirtualKey(key_hash=key_hash, budget_tokens=10000, used_tokens=0)
    db.add(virtual_key)
    db.commit()
    db.refresh(virtual_key)
    
    return {"key": raw_key}

@app.get("/usage")
def get_usage(key_doc: VirtualKey = Depends(get_current_api_key), db: Session = Depends(get_db)):
    usages = db.query(UsageRecord).filter(UsageRecord.gateway_key_hash == key_doc.key_hash).all()
    total_cost = sum(u.estimated_cost for u in usages)
    
    db.refresh(key_doc)
    
    return {
        "budget_tokens": key_doc.budget_tokens,
        "used_tokens": key_doc.used_tokens,
        "remaining_tokens": key_doc.budget_tokens - key_doc.used_tokens,
        "total_estimated_cost": total_cost,
        "requests_logged": len(usages)
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request, key_doc: VirtualKey = Depends(get_current_api_key), db: Session = Depends(get_db)):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    if "model" not in body or "messages" not in body:
        raise HTTPException(status_code=400, detail="Missing required request fields: 'model' and 'messages'")
        
    if body.get("stream"):
        raise HTTPException(status_code=400, detail="Streaming is not supported")
        
    if settings.llm_provider != "groq":
        raise HTTPException(status_code=500, detail="Unsupported provider configured")
        
    if not settings.llm_provider_api_key:
        raise HTTPException(status_code=500, detail="Provider API key not configured")
        
    reservation_amount = 2000
    result = db.execute(
        update(VirtualKey)
        .where(VirtualKey.id == key_doc.id)
        .where(VirtualKey.budget_tokens >= VirtualKey.used_tokens + reservation_amount)
        .values(used_tokens=VirtualKey.used_tokens + reservation_amount)
    )
    db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=429, detail="Token budget exceeded")

    headers = {
        "Authorization": f"Bearer {settings.llm_provider_api_key}",
        "Content-Type": "application/json"
    }
    
    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=body,
                    headers=headers,
                    timeout=settings.llm_provider_timeout
                )
                response.raise_for_status()
                provider_resp = response.json()
                
                usage = provider_resp.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
                
                cost = (prompt_tokens / 1000.0 * settings.llm_provider_cost_per_1k_prompt) + \
                       (completion_tokens / 1000.0 * settings.llm_provider_cost_per_1k_completion)
                       
                db.execute(
                    update(VirtualKey)
                    .where(VirtualKey.id == key_doc.id)
                    .values(used_tokens=VirtualKey.used_tokens - reservation_amount + total_tokens)
                )
                
                record = UsageRecord(
                    gateway_key_hash=key_doc.key_hash,
                    model=body["model"],
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    estimated_cost=cost
                )
                db.add(record)
                db.commit()
                
                return provider_resp
                
        except httpx.HTTPStatusError as e:
            # Do NOT retry 4xx errors (client faults, invalid model, authentication failures)
            if 400 <= e.response.status_code < 500:
                db.execute(update(VirtualKey).where(VirtualKey.id == key_doc.id).values(used_tokens=VirtualKey.used_tokens - reservation_amount))
                db.commit()
                error_detail = "Provider request failed"
                try:
                    error_detail = e.response.json()
                except Exception:
                    pass
                raise HTTPException(status_code=e.response.status_code, detail=error_detail)
            
            # 5xx errors (server faults) trigger retry, if attempts exhausted fail cleanly
            if attempt == max_attempts:
                db.execute(update(VirtualKey).where(VirtualKey.id == key_doc.id).values(used_tokens=VirtualKey.used_tokens - reservation_amount))
                db.commit()
                raise HTTPException(status_code=502, detail="Provider encountered an error and retries failed")
                
        except httpx.RequestError:
            # Network errors, timeouts trigger retry
            if attempt == max_attempts:
                db.execute(update(VirtualKey).where(VirtualKey.id == key_doc.id).values(used_tokens=VirtualKey.used_tokens - reservation_amount))
                db.commit()
                raise HTTPException(status_code=504, detail="Provider timeout or network error after retries")
