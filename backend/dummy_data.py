import asyncio
from sqlalchemy import text
from app.db import AsyncSessionLocal
from app.models.request_log import RequestLog
from datetime import datetime, timedelta, timezone
import random
import uuid

models = ["gpt-4o-mini", "gpt-4o", "claude-3-haiku-20240307", "gemini-1.5-flash"]
providers = ["openai", "openai", "anthropic", "google"]
users = ["alice123", "bob456", "charlie789"]
orgs = ["org_acme", "org_startup", None]

async def seed():
    async with AsyncSessionLocal() as db:
        print("Inserting 100 dummy records...")
        for i in range(100):
            days_ago = random.randint(0, 20)
            created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago, hours=random.randint(0,23))
            
            model_idx = random.randint(0, 3)
            model = models[model_idx]
            provider = providers[model_idx]
            task_type = "simple" if "mini" in model or "flash" in model else "complex"
            
            p_tokens = random.randint(50, 500)
            c_tokens = random.randint(10, 1000)
            
            cost = p_tokens * 0.00015 / 1000 + c_tokens * 0.00060 / 1000
            if "haiku" in model or "flash" in model:
                cost = p_tokens * 0.00025 / 1000 + c_tokens * 0.00125 / 1000
                
            log = RequestLog(
                id=uuid.uuid4(),
                user_id=random.choice(users),
                org_id=random.choice(orgs),
                task_type=task_type,
                provider=provider,
                model_requested="auto",
                model_used=model,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                total_tokens=p_tokens + c_tokens,
                cost_usd=cost,
                latency_ms=random.randint(300, 2500),
                was_sliced=random.choice([True, False, False, False]),
                messages_original_count=random.randint(2, 5),
                messages_sent_count=random.randint(2, 5),
                status_code=200,
                created_at=created_at
            )
            db.add(log)
        await db.commit()
        print("Done!")

asyncio.run(seed())
