"""
Xeno FDE Assignment — Main FastAPI Application
================================================
The core CRM backend with endpoints for:
- AI-powered chat (NL → SQL segmentation)
- Campaign creation and sending
- Webhook callbacks from mock channel service
- Campaign stats and customer management
"""

from dotenv import load_dotenv
load_dotenv()

import os
import uuid
import httpx
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import init_db, get_db, ingest_clean_data, SessionLocal
from models import Customer, Order, Campaign, Communication, CommunicationStatus, CampaignStatus
from ai_engine import text_to_sql, draft_campaign_message, analyze_segment, personalize_message


# --- Configuration ---
MOCK_CHANNEL_URL = os.getenv("MOCK_CHANNEL_URL", "http://localhost:8001")


# --- Pydantic Schemas ---

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    type: str  # "segment", "error", "info"
    message: str
    sql: Optional[str] = None
    explanation: Optional[str] = None
    customers: Optional[list] = None
    segment_size: Optional[int] = None
    segment_summary: Optional[str] = None

class DraftRequest(BaseModel):
    segment_description: str
    channel: str = "whatsapp"
    tone: str = "friendly and professional"
    custom_instructions: str = ""

class DraftResponse(BaseModel):
    message: str
    subject: Optional[str] = None
    error: Optional[str] = None

class CampaignSendRequest(BaseModel):
    name: str
    customer_ids: List[str]
    message_template: str
    channel: str = "whatsapp"
    segment_query: Optional[str] = None
    segment_sql: Optional[str] = None

class CallbackPayload(BaseModel):
    communication_id: str
    status: str
    timestamp: Optional[str] = None

class StatsResponse(BaseModel):
    total_sent: int = 0
    pending: int = 0
    sent: int = 0
    delivered: int = 0
    read: int = 0
    failed: int = 0
    campaign_id: Optional[int] = None
    campaign_name: Optional[str] = None


# --- App Lifecycle ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables and ingest data."""
    print("\n🚀 Starting Xeno CRM Backend...")
    init_db()
    db = SessionLocal()
    try:
        ingest_clean_data(db)
    finally:
        db.close()
    print("✅ Backend ready!\n")
    yield
    print("👋 Shutting down Xeno CRM Backend...")


# --- FastAPI App ---

app = FastAPI(
    title="Xeno Mini CRM",
    description="AI-native CRM with Chat-to-Campaign interface",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
#  HEALTH CHECK
# ==========================================

@app.get("/")
async def root():
    return {
        "service": "Xeno Mini CRM",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health(db: Session = Depends(get_db)):
    customer_count = db.query(Customer).count()
    order_count = db.query(Order).count()
    return {
        "status": "healthy",
        "customers": customer_count,
        "orders": order_count,
    }


# ==========================================
#  CHAT — AI-Powered Segmentation
# ==========================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    The core Chat-to-Campaign endpoint.
    Takes natural language → generates SQL → executes → returns segment.
    """
    user_message = request.message.strip()
    if not user_message:
        return ChatResponse(
            type="error",
            message="Please enter a query to search for customers."
        )

    # Step 1: Convert NL to SQL using AI
    result = await text_to_sql(user_message)

    if result["error"]:
        return ChatResponse(
            type="error",
            message=result["error"]
        )

    sql = result["sql"]
    explanation = result["explanation"]

    # Step 2: Execute the SQL safely
    try:
        result_proxy = db.execute(text(sql))
        columns = list(result_proxy.keys())
        rows = result_proxy.fetchall()
        customers = [dict(zip(columns, row)) for row in rows]

    except Exception as e:
        return ChatResponse(
            type="error",
            message=f"I generated a query but it had an issue: {str(e)}. Let me try again — could you rephrase your request?",
            sql=sql,
        )

    if not customers:
        return ChatResponse(
            type="info",
            message="No customers found matching your criteria. Try broadening your search.",
            sql=sql,
            explanation=explanation,
            customers=[],
            segment_size=0,
        )

    # Step 3: Generate segment summary
    segment_summary = await analyze_segment(customers)

    return ChatResponse(
        type="segment",
        message=f"Found {len(customers)} customers matching your criteria.",
        sql=sql,
        explanation=explanation,
        customers=customers,
        segment_size=len(customers),
        segment_summary=segment_summary,
    )


# ==========================================
#  CAMPAIGN — Draft & Send
# ==========================================

@app.post("/api/campaign/draft", response_model=DraftResponse)
async def draft_message(request: DraftRequest):
    """Draft a campaign message using AI."""
    result = await draft_campaign_message(
        segment_description=request.segment_description,
        channel=request.channel,
        tone=request.tone,
        custom_instructions=request.custom_instructions,
    )

    if result["error"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return DraftResponse(
        message=result["message"],
        subject=result.get("subject"),
    )


@app.post("/api/campaign/send")
async def send_campaign(request: CampaignSendRequest, db: Session = Depends(get_db)):
    """
    Launch a campaign:
    1. Create campaign record
    2. Create communication records for each customer
    3. Send each to the mock channel service
    """
    # Validate customers exist
    customers = db.query(Customer).filter(Customer.id.in_(request.customer_ids)).all()
    if not customers:
        raise HTTPException(status_code=400, detail="No valid customers found")

    # Create campaign
    campaign = Campaign(
        name=request.name,
        segment_query=request.segment_query,
        segment_sql=request.segment_sql,
        message_template=request.message_template,
        channel=request.channel,
        audience_size=len(customers),
        status=CampaignStatus.SENDING.value,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    # Create communications and send to mock channel
    sent_count = 0
    failed_count = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        for customer in customers:
            comm_id = str(uuid.uuid4())

            # Personalize the message
            personalized = await personalize_message(
                request.message_template, customer.to_dict()
            )

            # Create communication record
            comm = Communication(
                id=comm_id,
                campaign_id=campaign.id,
                customer_id=customer.id,
                channel=request.channel,
                message_body=personalized,
                status=CommunicationStatus.PENDING.value,
                sent_at=datetime.utcnow(),
            )
            db.add(comm)

            # Send to mock channel service
            try:
                response = await client.post(
                    f"{MOCK_CHANNEL_URL}/send",
                    json={
                        "communication_id": comm_id,
                        "phone": customer.phone or "",
                        "message_body": personalized,
                        "channel_type": request.channel,
                    }
                )
                if response.status_code == 200:
                    comm.status = CommunicationStatus.SENT.value
                    sent_count += 1
                else:
                    comm.status = CommunicationStatus.FAILED.value
                    failed_count += 1
            except Exception as e:
                print(f"⚠️  Failed to send to channel for {customer.name}: {e}")
                comm.status = CommunicationStatus.FAILED.value
                failed_count += 1

    db.commit()

    # Update campaign status
    if failed_count == len(customers):
        campaign.status = CampaignStatus.FAILED.value
    else:
        campaign.status = CampaignStatus.COMPLETED.value
    db.commit()

    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "total_audience": len(customers),
        "sent": sent_count,
        "failed": failed_count,
        "status": campaign.status,
    }


# ==========================================
#  WEBHOOK — Callback from Mock Channel
# ==========================================

@app.post("/api/webhook/callback")
async def webhook_callback(payload: CallbackPayload, db: Session = Depends(get_db)):
    """
    Receive delivery status callbacks from the mock channel service.
    Updates communication status in the database.
    """
    comm = db.query(Communication).filter(Communication.id == payload.communication_id).first()
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")

    # Update status
    valid_statuses = [s.value for s in CommunicationStatus]
    new_status = payload.status.upper()

    if new_status in valid_statuses:
        comm.status = new_status
        comm.updated_at = datetime.utcnow()
        db.commit()
        print(f"📬 Callback: {payload.communication_id[:8]}... → {new_status}")
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {payload.status}. Must be one of {valid_statuses}"
        )

    return {"status": "received", "communication_id": payload.communication_id, "new_status": new_status}


# ==========================================
#  STATS — Campaign Performance
# ==========================================

@app.get("/api/stats")
async def get_stats(campaign_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Get campaign delivery stats.
    If campaign_id is provided, returns stats for that campaign.
    Otherwise returns stats for the most recent campaign.
    """
    if campaign_id:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    else:
        campaign = db.query(Campaign).order_by(Campaign.created_at.desc()).first()

    if not campaign:
        return StatsResponse()

    comms = db.query(Communication).filter(Communication.campaign_id == campaign.id).all()

    stats = {
        "total_sent": len(comms),
        "pending": sum(1 for c in comms if c.status == CommunicationStatus.PENDING.value),
        "sent": sum(1 for c in comms if c.status == CommunicationStatus.SENT.value),
        "delivered": sum(1 for c in comms if c.status == CommunicationStatus.DELIVERED.value),
        "read": sum(1 for c in comms if c.status == CommunicationStatus.READ.value),
        "failed": sum(1 for c in comms if c.status == CommunicationStatus.FAILED.value),
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
    }

    return stats


# ==========================================
#  CAMPAIGNS — List & Details
# ==========================================

@app.get("/api/campaigns")
async def list_campaigns(db: Session = Depends(get_db)):
    """List all campaigns."""
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
    return [c.to_dict() for c in campaigns]


@app.get("/api/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """Get campaign details with communication breakdown."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    comms = db.query(Communication).filter(Communication.campaign_id == campaign_id).all()

    return {
        **campaign.to_dict(),
        "communications": [c.to_dict() for c in comms],
    }


# ==========================================
#  CUSTOMERS — Browse & Search
# ==========================================

@app.get("/api/customers")
async def list_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=100),
    city: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List customers with optional filtering."""
    query = db.query(Customer)

    if city:
        query = query.filter(Customer.city == city)

    customers = query.order_by(Customer.total_spent.desc()).offset(skip).limit(limit).all()
    total = query.count()

    return {
        "customers": [c.to_dict() for c in customers],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@app.get("/api/customers/{customer_id}")
async def get_customer(customer_id: str, db: Session = Depends(get_db)):
    """Get customer details with order history."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    orders = db.query(Order).filter(Order.customer_id == customer_id).order_by(Order.created_at.desc()).all()

    return {
        **customer.to_dict(),
        "orders": [o.to_dict() for o in orders],
    }


# ==========================================
#  RUN
# ==========================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
