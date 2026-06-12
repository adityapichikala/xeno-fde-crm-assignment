"""
Xeno FDE Assignment — Data Cleaning Pipeline
=============================================
Reads raw_data.json (with intentional quality issues) and produces
clean_data.json ready for database ingestion.

Demonstrates:
- Phone number normalization
- Name standardization
- Email validation + placeholder generation
- Date format normalization
- Deduplication by fuzzy matching
- Cleaning report generation
"""

import json
import re
from datetime import datetime
from collections import Counter

# --- Cleaning Report Tracker ---
report = {
    "phones_fixed": 0,
    "phones_removed": 0,
    "names_fixed": 0,
    "emails_generated": 0,
    "dates_fixed": 0,
    "duplicates_removed": 0,
    "total_issues": 0,
}


def normalize_phone(phone: str) -> str:
    """
    Normalize phone number to +91XXXXXXXXXX format.
    Returns empty string if unrecoverable.
    """
    if not phone or phone in ("N/A", "null", "None", ""):
        report["phones_removed"] += 1
        report["total_issues"] += 1
        return ""

    # Strip all non-digit characters
    digits = re.sub(r'\D', '', phone)

    # Handle various formats
    if len(digits) == 10 and digits[0] in "6789":
        report["phones_fixed"] += 1
        report["total_issues"] += 1
        return f"+91{digits}"
    elif len(digits) == 12 and digits.startswith("91"):
        report["phones_fixed"] += 1
        report["total_issues"] += 1
        return f"+{digits}"
    elif len(digits) == 13 and digits.startswith("91"):
        # Already correct format without +
        return f"+91{digits[2:]}"
    elif phone.startswith("+91") and len(digits) == 12:
        return phone  # Already valid
    else:
        report["phones_removed"] += 1
        report["total_issues"] += 1
        return ""


def normalize_name(name: str) -> str:
    """
    Normalize name: strip whitespace, proper title case.
    """
    if not name or not name.strip():
        return "Unknown"

    original = name
    name = name.strip()
    name = " ".join(name.split())  # Remove extra whitespace
    name = name.title()  # Proper capitalization

    if name != original.strip():
        report["names_fixed"] += 1
        report["total_issues"] += 1

    return name


def normalize_email(email: str, name: str) -> str:
    """
    Validate email or generate a placeholder.
    """
    if email and "@" in email and "." in email.split("@")[1]:
        return email.lower().strip()

    # Generate placeholder from name
    clean_name = name.lower().replace(" ", ".").strip(".")
    if clean_name:
        report["emails_generated"] += 1
        report["total_issues"] += 1
        return f"{clean_name}@placeholder.com"

    return "unknown@placeholder.com"


def normalize_date(date_str: str) -> str:
    """
    Normalize date string to ISO format (YYYY-MM-DD).
    Handles multiple common formats.
    """
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")

    # Already in correct format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            pass

    # Try multiple date formats
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%d %B %Y",
        "%B %d, %Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%m/%d/%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            report["dates_fixed"] += 1
            report["total_issues"] += 1
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Fallback
    report["dates_fixed"] += 1
    report["total_issues"] += 1
    return datetime.now().strftime("%Y-%m-%d")


def deduplicate_customers(customers: list) -> list:
    """
    Remove duplicate customers by fuzzy name matching.
    Keeps the record with more complete data.
    """
    seen = {}
    unique = []

    for customer in customers:
        # Create a normalized key for deduplication
        name_key = customer["name"].lower().strip().replace(" ", "")

        if name_key in seen:
            report["duplicates_removed"] += 1
            report["total_issues"] += 1

            # Keep the one with more complete data
            existing = seen[name_key]
            existing_score = sum([
                bool(existing.get("phone")),
                bool(existing.get("email") and "@placeholder" not in existing.get("email", "")),
            ])
            new_score = sum([
                bool(customer.get("phone")),
                bool(customer.get("email") and "@placeholder" not in customer.get("email", "")),
            ])

            if new_score > existing_score:
                # Replace with the better record but keep the original ID
                customer["id"] = existing["id"]
                idx = unique.index(existing)
                unique[idx] = customer
                seen[name_key] = customer
        else:
            seen[name_key] = customer
            unique.append(customer)

    return unique


def clean_customers(customers: list) -> list:
    """Apply all cleaning transformations to customers."""
    cleaned = []
    for c in customers:
        cleaned.append({
            "id": c["id"],
            "name": normalize_name(c.get("name", "")),
            "email": normalize_email(c.get("email", ""), normalize_name(c.get("name", ""))),
            "phone": normalize_phone(c.get("phone", "")),
            "city": c.get("city", "Unknown"),
            "created_at": normalize_date(c.get("created_at", "")),
        })

    # Deduplicate after normalization
    cleaned = deduplicate_customers(cleaned)
    return cleaned


def clean_orders(orders: list, valid_customer_ids: set) -> list:
    """Clean orders and filter out orphans."""
    cleaned = []
    orphans_removed = 0

    for o in orders:
        if o["customer_id"] not in valid_customer_ids:
            orphans_removed += 1
            continue

        cleaned.append({
            "id": o["id"],
            "customer_id": o["customer_id"],
            "amount": round(float(o.get("amount", 0)), 2),
            "items": o.get("items", []),
            "status": o.get("status", "completed"),
            "created_at": normalize_date(o.get("created_at", "")),
        })

    if orphans_removed:
        print(f"   ⚠️  Removed {orphans_removed} orphan orders (missing customer)")

    return cleaned


def main():
    print("=" * 60)
    print("  Xeno FDE — Data Cleaning Pipeline")
    print("=" * 60)

    # Load raw data
    try:
        with open("raw_data.json", "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        print("❌ raw_data.json not found! Run generate_data.py first.")
        return

    raw_customers = raw["customers"]
    raw_orders = raw["orders"]
    print(f"\n📥 Loaded {len(raw_customers)} customers and {len(raw_orders)} orders\n")

    # Clean customers
    print("🔧 Cleaning customers...")
    clean_custs = clean_customers(raw_customers)
    valid_ids = {c["id"] for c in clean_custs}

    # Clean orders
    print("🔧 Cleaning orders...")
    clean_ords = clean_orders(raw_orders, valid_ids)

    # Compute per-customer aggregates
    customer_orders = {}
    for o in clean_ords:
        cid = o["customer_id"]
        if cid not in customer_orders:
            customer_orders[cid] = {"total_spent": 0, "order_count": 0, "last_order_date": ""}
        customer_orders[cid]["total_spent"] += o["amount"]
        customer_orders[cid]["order_count"] += 1
        if o["created_at"] > customer_orders[cid]["last_order_date"]:
            customer_orders[cid]["last_order_date"] = o["created_at"]

    # Enrich customers with aggregates
    for c in clean_custs:
        agg = customer_orders.get(c["id"], {"total_spent": 0, "order_count": 0, "last_order_date": ""})
        c["total_spent"] = round(agg["total_spent"], 2)
        c["order_count"] = agg["order_count"]
        c["last_order_date"] = agg["last_order_date"]

    # Save clean data
    output = {
        "customers": clean_custs,
        "orders": clean_ords,
        "metadata": {
            "cleaned_at": datetime.now().isoformat(),
            "original_customers": len(raw_customers),
            "clean_customers": len(clean_custs),
            "original_orders": len(raw_orders),
            "clean_orders": len(clean_ords),
            "issues_fixed": report["total_issues"],
        }
    }

    output_path = "clean_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Print cleaning report
    print(f"\n{'=' * 60}")
    print(f"  📋 DATA CLEANING REPORT")
    print(f"{'=' * 60}")
    print(f"  Customers: {len(raw_customers)} → {len(clean_custs)} ({report['duplicates_removed']} duplicates removed)")
    print(f"  Orders:    {len(raw_orders)} → {len(clean_ords)}")
    print(f"")
    print(f"  Issues Fixed:")
    print(f"    • Phone numbers fixed:    {report['phones_fixed']}")
    print(f"    • Phone numbers removed:  {report['phones_removed']}")
    print(f"    • Names standardized:     {report['names_fixed']}")
    print(f"    • Emails generated:       {report['emails_generated']}")
    print(f"    • Dates normalized:       {report['dates_fixed']}")
    print(f"    • Duplicates removed:     {report['duplicates_removed']}")
    print(f"  ─────────────────────────────────────")
    print(f"    Total issues resolved:    {report['total_issues']}")
    print(f"")
    print(f"  💾 Clean data saved to: {output_path}")

    # City distribution
    cities = Counter(c["city"] for c in clean_custs)
    print(f"\n  🏙️  City Distribution:")
    for city, count in cities.most_common(5):
        bar = "█" * count
        print(f"    {city:15s} {bar} ({count})")

    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    main()
