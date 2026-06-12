"""
Xeno FDE Assignment — Database Setup
=====================================
SQLAlchemy engine, session management, and data ingestion.
"""

import json
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Customer, Order


# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./xeno_crm.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created.")


def get_db():
    """Dependency: yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ingest_clean_data(db_session):
    """
    Ingest clean_data.json into the database.
    Only runs if the database is empty (first startup).
    """
    # Check if data already exists
    existing = db_session.query(Customer).first()
    if existing:
        print("📦 Database already has data. Skipping ingestion.")
        return

    # Try to find the clean data file
    data_paths = [
        os.path.join(os.path.dirname(__file__), "data", "clean_data.json"),
        os.path.join(os.path.dirname(__file__), "clean_data.json"),
        "data/clean_data.json",
        "clean_data.json",
    ]

    data_file = None
    for path in data_paths:
        if os.path.exists(path):
            data_file = path
            break

    if not data_file:
        print("⚠️  No clean_data.json found. Run generate_data.py and clean_data.py first.")
        return

    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Ingest customers
    customers_added = 0
    for c in data["customers"]:
        customer = Customer(
            id=c["id"],
            name=c["name"],
            email=c.get("email", ""),
            phone=c.get("phone", ""),
            city=c.get("city", "Unknown"),
            total_spent=c.get("total_spent", 0.0),
            order_count=c.get("order_count", 0),
            last_order_date=c.get("last_order_date", ""),
            created_at=c["created_at"],
        )
        db_session.add(customer)
        customers_added += 1

    # Ingest orders
    orders_added = 0
    for o in data["orders"]:
        order = Order(
            id=o["id"],
            customer_id=o["customer_id"],
            amount=o["amount"],
            items=o.get("items", []),
            status=o.get("status", "completed"),
            created_at=o["created_at"],
        )
        db_session.add(order)
        orders_added += 1

    db_session.commit()
    print(f"✅ Ingested {customers_added} customers and {orders_added} orders into database.")
