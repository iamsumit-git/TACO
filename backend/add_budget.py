import asyncio
from app.db import AsyncSessionLocal
from app.models.budget import Budget
import uuid

async def add_zero_budget():
    async with AsyncSessionLocal() as db:
        print('Adding $0.00 budget for alice123...')
        budget = Budget(
            id=uuid.uuid4(),
            entity_type='user',
            entity_id='alice123',
            limit_usd=0.00,
            period='daily',
            action='block'
        )
        db.add(budget)
        await db.commit()
        print('Budget added!')

asyncio.run(add_zero_budget())
