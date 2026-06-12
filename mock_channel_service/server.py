"""
Xeno FDE Assignment — Mock Channel Service
============================================
A SEPARATE FastAPI application that simulates a messaging gateway
(WhatsApp, SMS, Email).

This is the "stubbed channel service" required by the assignment.
It demonstrates the Two-Service Architecture:

1. CRM Backend sends POST /send with message details
2. This service accepts immediately (200 OK)
3. After a random delay (2-10s), it calls back the CRM's webhook
   with a delivery status (DELIVERED, READ, FAILED, SENT)

Architecture:
  CRM Backend → POST /send → Mock Channel → (async delay) → POST callback → CRM Webhook
"""

import os
import random
import asyncio
import httpx
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional


# --- Configuration ---
CALLBACK_URL = os.getenv("CALLBACK_URL", "http://localhost:8000/api/webhook/callback")
MIN_DELAY = int(os.getenv("MIN_DELAY", "2"))
MAX_DELAY = int(os.getenv("MAX_DELAY", "10"))


# --- Pydantic Models ---

class SendRequest(BaseModel):
    communication_id: str
    phone: str
    message_body: str
    channel_type: str = "whatsapp"


# --- App ---

app = FastAPI(
    title="Xeno Mock Channel Service",
    description="Simulates WhatsApp/SMS/Email delivery with async callbacks",
    version="1.0.0",
)

# Track active deliveries for logging
active_deliveries = 0


@app.get("/")
async def root():
    return {
        "service": "Mock Channel Service",
        "status": "running",
        "callback_url": CALLBACK_URL,
        "active_deliveries": active_deliveries,
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "active_deliveries": active_deliveries}


@app.post("/send")
async def send_message(request: SendRequest):
    """
    Accept a message for delivery.
    Returns 200 immediately, then simulates async delivery.
    """
    global active_deliveries
    active_deliveries += 1

    # Log receipt
    print(f"📨 Received: {request.communication_id[:8]}... → {request.phone} ({request.channel_type})")
    print(f"   Message: {request.message_body[:80]}...")

    # Spawn async delivery simulation
    asyncio.create_task(
        simulate_delivery(request.communication_id, request.channel_type)
    )

    return {
        "status": "accepted",
        "communication_id": request.communication_id,
        "message": "Message queued for delivery",
    }


async def simulate_delivery(communication_id: str, channel_type: str):
    """
    Simulate message delivery with random delay and status.
    After delay, calls back the CRM webhook with the result.
    """
    global active_deliveries

    # Random delay (simulating network latency + delivery time)
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    print(f"⏳ Delivering {communication_id[:8]}... (simulating {delay:.1f}s delay)")
    await asyncio.sleep(delay)

    # Determine delivery status with weighted probability
    status = random.choices(
        ["DELIVERED", "READ", "FAILED", "SENT"],
        weights=[60, 20, 10, 10],  # 60% delivered, 20% read, 10% failed, 10% sent
        k=1
    )[0]

    # Status emoji for logging
    status_emoji = {
        "DELIVERED": "✅",
        "READ": "👀",
        "FAILED": "❌",
        "SENT": "📤",
    }

    print(f"{status_emoji.get(status, '❓')} {communication_id[:8]}... → {status}")

    # Call back the CRM webhook
    callback_payload = {
        "communication_id": communication_id,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(CALLBACK_URL, json=callback_payload)
            if response.status_code == 200:
                print(f"📬 Callback sent for {communication_id[:8]}... → {status}")
            else:
                print(f"⚠️  Callback failed for {communication_id[:8]}...: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Callback error for {communication_id[:8]}...: {e}")
    finally:
        active_deliveries -= 1


# ==========================================
#  RUN
# ==========================================

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("  🔌 Xeno Mock Channel Service")
    print(f"  📡 Callback URL: {CALLBACK_URL}")
    print(f"  ⏱️  Delay range: {MIN_DELAY}-{MAX_DELAY} seconds")
    print("=" * 60 + "\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)
