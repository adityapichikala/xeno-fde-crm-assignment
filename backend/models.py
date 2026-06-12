"""
Xeno FDE Assignment — Database Models
======================================
SQLAlchemy models for the Mini CRM.
"""

from sqlalchemy import (
    Column, String, Float, Integer, DateTime, JSON,
    ForeignKey, Enum as SAEnum, Text, func
)
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime
import enum


class Base(DeclarativeBase):
    pass


# --- Enums ---

class CommunicationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"


class CampaignStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENDING = "SENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# --- Models ---

class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    city = Column(String, nullable=True)
    total_spent = Column(Float, default=0.0)
    order_count = Column(Integer, default=0)
    last_order_date = Column(String, nullable=True)
    created_at = Column(String, nullable=False)

    # Relationships
    orders = relationship("Order", back_populates="customer", lazy="dynamic")
    communications = relationship("Communication", back_populates="customer", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "city": self.city,
            "total_spent": self.total_spent,
            "order_count": self.order_count,
            "last_order_date": self.last_order_date,
            "created_at": self.created_at,
        }


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    amount = Column(Float, nullable=False)
    items = Column(JSON, nullable=True)
    status = Column(String, default="completed")
    created_at = Column(String, nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="orders")

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "amount": self.amount,
            "items": self.items,
            "status": self.status,
            "created_at": self.created_at,
        }


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    segment_query = Column(Text, nullable=True)  # The NL query that produced this segment
    segment_sql = Column(Text, nullable=True)     # The generated SQL
    message_template = Column(Text, nullable=True)
    channel = Column(String, default="whatsapp")
    audience_size = Column(Integer, default=0)
    status = Column(String, default=CampaignStatus.DRAFT.value)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    communications = relationship("Communication", back_populates="campaign", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "segment_query": self.segment_query,
            "segment_sql": self.segment_sql,
            "message_template": self.message_template,
            "channel": self.channel,
            "audience_size": self.audience_size,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Communication(Base):
    __tablename__ = "communications"

    id = Column(String, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    channel = Column(String, default="whatsapp")
    message_body = Column(Text, nullable=True)
    status = Column(String, default=CommunicationStatus.PENDING.value)
    sent_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    campaign = relationship("Campaign", back_populates="communications")
    customer = relationship("Customer", back_populates="communications")

    def to_dict(self):
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "customer_id": self.customer_id,
            "channel": self.channel,
            "message_body": self.message_body,
            "status": self.status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
