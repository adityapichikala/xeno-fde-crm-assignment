"""
Xeno FDE Assignment — Mock Data Generator
==========================================
Generates realistic but intentionally messy customer + order data
to demonstrate data cleaning skills (a core FDE competency).

~20% of records have data quality issues:
- Missing/malformed phone numbers
- Inconsistent name casing
- Missing emails
- Duplicate customers with slight name variations
- Inconsistent date formats
"""

import json
import random
import uuid
from datetime import datetime, timedelta

# Seed for reproducibility
random.seed(42)

# --- Configuration ---
NUM_CUSTOMERS = 50
NUM_ORDERS = 200

CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow",
    "Chandigarh", "Goa", "Kochi", "Indore", "Nagpur"
]

ITEMS = [
    "T-Shirt", "Jeans", "Sneakers", "Watch", "Sunglasses",
    "Backpack", "Headphones", "Coffee Mug", "Notebook", "Perfume",
    "Wallet", "Belt", "Cap", "Socks", "Kurta",
    "Saree", "Hoodie", "Jacket", "Shorts", "Sandals"
]

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun",
    "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Ananya", "Diya", "Myra", "Sara", "Aanya",
    "Aadhya", "Ira", "Anika", "Riya", "Priya",
    "Rohan", "Kabir", "Shaurya", "Atharva", "Advait",
    "Meera", "Kavya", "Nisha", "Tanvi", "Pooja"
]

LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Singh", "Kumar",
    "Patel", "Reddy", "Nair", "Joshi", "Mehta",
    "Iyer", "Chopra", "Malhotra", "Bhat", "Das",
    "Rao", "Pillai", "Kapoor", "Agarwal", "Banerjee"
]

EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "protonmail.com"]


def generate_phone():
    """Generate a valid Indian phone number."""
    return f"+91{random.randint(7000000000, 9999999999)}"


def generate_dirty_phone():
    """Generate an intentionally malformed phone number."""
    choices = [
        lambda: str(random.randint(10000, 99999)),           # Too short
        lambda: f"91{random.randint(7000000000, 9999999999)}",  # Missing +
        lambda: f"+1{random.randint(2000000000, 9999999999)}",  # Wrong country code
        lambda: "",                                              # Empty
        lambda: "N/A",                                           # Placeholder text
    ]
    return random.choice(choices)()


def generate_date(start_year=2023, end_year=2025):
    """Generate a random date."""
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return start + timedelta(days=random_days)


def format_date_dirty(dt):
    """Format date in inconsistent ways (dirty data)."""
    formats = [
        dt.strftime("%Y-%m-%d"),
        dt.strftime("%d/%m/%Y"),
        dt.strftime("%m-%d-%Y"),
        dt.strftime("%d %B %Y"),
        dt.strftime("%B %d, %Y"),
    ]
    return random.choice(formats)


def generate_customers():
    """Generate customer records with intentional quality issues."""
    customers = []
    used_names = []

    for i in range(NUM_CUSTOMERS):
        customer_id = str(uuid.uuid4())
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        used_names.append((first, last))

        is_dirty = random.random() < 0.20  # 20% chance of dirty data

        if is_dirty:
            # Apply random data quality issues
            issue_type = random.choice(["name", "phone", "email", "date", "duplicate"])

            if issue_type == "name":
                # Inconsistent casing
                name = random.choice([
                    name.lower(),
                    name.upper(),
                    f"  {name}  ",  # Extra whitespace
                    first,          # Missing last name
                ])
            
            phone = generate_dirty_phone() if issue_type == "phone" else generate_phone()
            email = "" if issue_type == "email" else f"{first.lower()}.{last.lower()}@{random.choice(EMAIL_DOMAINS)}"
            created = format_date_dirty(generate_date(2022, 2024)) if issue_type == "date" else generate_date(2022, 2024).strftime("%Y-%m-%d")

            if issue_type == "duplicate" and len(used_names) > 5:
                # Create a duplicate with slight variation
                orig_first, orig_last = random.choice(used_names[:len(used_names)//2])
                name = f"{orig_first} {orig_last}" if random.random() > 0.5 else f"{orig_first.lower()} {orig_last}"
                phone = generate_phone()
                email = f"{orig_first.lower()}.{orig_last.lower()}@{random.choice(EMAIL_DOMAINS)}"
                created = generate_date(2022, 2024).strftime("%Y-%m-%d")
        else:
            phone = generate_phone()
            email = f"{first.lower()}.{last.lower()}@{random.choice(EMAIL_DOMAINS)}"
            created = generate_date(2022, 2024).strftime("%Y-%m-%d")

        customers.append({
            "id": customer_id,
            "name": name,
            "email": email,
            "phone": phone,
            "city": random.choice(CITIES),
            "created_at": created,
        })

    return customers


def generate_orders(customers):
    """Generate order records linked to customers."""
    orders = []

    for _ in range(NUM_ORDERS):
        customer = random.choice(customers)
        order_date = generate_date(2023, 2025)
        num_items = random.randint(1, 4)
        selected_items = random.sample(ITEMS, num_items)

        # Price varies by item count and some randomness
        base_amount = sum(random.randint(200, 3000) for _ in selected_items)
        amount = round(base_amount * random.uniform(0.8, 1.3), 2)

        orders.append({
            "id": str(uuid.uuid4()),
            "customer_id": customer["id"],
            "amount": amount,
            "items": selected_items,
            "status": random.choices(
                ["completed", "returned", "pending"],
                weights=[75, 15, 10],
                k=1
            )[0],
            "created_at": order_date.strftime("%Y-%m-%d"),
        })

    return orders


def main():
    print("=" * 60)
    print("  Xeno FDE — Mock Data Generator")
    print("=" * 60)

    print(f"\n📊 Generating {NUM_CUSTOMERS} customers and {NUM_ORDERS} orders...")
    print("⚠️  ~20% of records will have intentional data quality issues\n")

    customers = generate_customers()
    orders = generate_orders(customers)

    data = {
        "customers": customers,
        "orders": orders,
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "num_customers": len(customers),
            "num_orders": len(orders),
            "dirty_data_percentage": "~20%",
            "quality_issues": [
                "Missing/malformed phone numbers",
                "Inconsistent name casing",
                "Missing emails",
                "Duplicate customers with slight variations",
                "Inconsistent date formats",
            ]
        }
    }

    output_path = "raw_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Generated {len(customers)} customers")
    print(f"✅ Generated {len(orders)} orders")
    print(f"💾 Saved to: {output_path}")

    # Quick quality report
    dirty_phones = sum(1 for c in customers if not c["phone"].startswith("+91") or len(c["phone"]) != 13)
    missing_emails = sum(1 for c in customers if not c["email"])
    dirty_names = sum(1 for c in customers if c["name"] != c["name"].strip() or c["name"] == c["name"].lower() or c["name"] == c["name"].upper() or " " not in c["name"].strip())

    print(f"\n📋 Data Quality Report (raw):")
    print(f"   • Dirty phone numbers: {dirty_phones}")
    print(f"   • Missing emails: {missing_emails}")
    print(f"   • Name issues: {dirty_names}")
    print(f"\n🔧 Run clean_data.py to fix these issues.\n")


if __name__ == "__main__":
    main()
