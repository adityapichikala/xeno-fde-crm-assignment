"""
Xeno FDE Assignment — AI Engine
================================
Handles all LLM interactions:
- Natural language → SQL query generation
- Personalized message drafting
- Segment analysis/summarization

Uses OpenRouter API (free tier models) — OpenAI-compatible format.
Free models: google/gemini-2.0-flash-exp:free, meta-llama/llama-3.1-8b-instruct:free
"""

import os
import json
import re
from openai import AsyncOpenAI

# --- Configuration ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

# OpenRouter uses OpenAI-compatible API format
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY or "dummy_key_to_prevent_startup_crash",
)

# Database schema context for the LLM
DB_SCHEMA = """
You have access to a SQLite database with the following tables:

TABLE: customers
- id (TEXT, PRIMARY KEY) — UUID
- name (TEXT) — Customer's full name
- email (TEXT) — Email address
- phone (TEXT) — Phone number in +91XXXXXXXXXX format
- city (TEXT) — City name (e.g., Mumbai, Delhi, Bangalore)
- total_spent (REAL) — Total amount spent across all orders (in INR ₹)
- order_count (INTEGER) — Number of orders placed
- last_order_date (TEXT) — Date of most recent order (YYYY-MM-DD format)
- created_at (TEXT) — When the customer was created (YYYY-MM-DD)

TABLE: orders
- id (TEXT, PRIMARY KEY) — UUID
- customer_id (TEXT, FOREIGN KEY → customers.id)
- amount (REAL) — Order amount in INR ₹
- items (JSON) — List of item names (e.g., ["T-Shirt", "Jeans"])
- status (TEXT) — "completed", "returned", or "pending"
- created_at (TEXT) — Order date (YYYY-MM-DD)

TODAY'S DATE: Use date('now') for current date calculations.
"""


async def _chat(system_prompt: str, user_prompt: str) -> str:
    """Send a chat completion request to OpenRouter."""
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY not set. Get a free key at https://openrouter.ai/keys"
        )

    response = await client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,  # Low temperature for precise SQL generation
        max_tokens=1024,
    )

    return response.choices[0].message.content.strip()


def _parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences."""
    # Remove markdown code fences if present
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    text = text.strip()
    return json.loads(text)


async def text_to_sql(user_prompt: str) -> dict:
    """
    Convert a natural language query to a SQL SELECT statement.
    
    Returns:
        {
            "sql": "SELECT ...",
            "explanation": "This query finds...",
            "error": null
        }
    """
    try:
        system_prompt = f"""You are a SQL expert assistant for a CRM system. Convert the user's natural language query into a safe SQLite SELECT query.

{DB_SCHEMA}

RULES:
1. ONLY generate SELECT queries. Never INSERT, UPDATE, DELETE, DROP, or ALTER.
2. Always return results from the customers table (you can JOIN with orders).
3. Return DISTINCT customer records when joining with orders.
4. Use appropriate WHERE clauses based on the user's intent.
5. For "inactive" customers, compare last_order_date with date('now').
6. For "high value" customers, use total_spent.
7. For date-based queries, use SQLite date functions like date('now', '-60 days').
8. LIMIT results to 100 max.
9. Order results meaningfully (e.g., by total_spent DESC for "top customers").

Respond ONLY in this exact JSON format, no markdown code fences:
{{"sql": "YOUR_SQL_QUERY", "explanation": "Brief explanation of what this query does"}}"""

        response_text = await _chat(system_prompt, user_prompt)
        result = _parse_json_response(response_text)

        # Safety check: ensure it's a SELECT query
        sql = result.get("sql", "").strip()
        if not sql.upper().startswith("SELECT"):
            return {
                "sql": None,
                "explanation": None,
                "error": "I can only run SELECT queries for your safety. Please rephrase your request."
            }

        # Block dangerous keywords
        dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "EXEC"]
        sql_upper = sql.upper()
        for keyword in dangerous:
            # Check as whole words to avoid false positives (e.g., "updated_at")
            if re.search(r'\b' + keyword + r'\b', sql_upper):
                return {
                    "sql": None,
                    "explanation": None,
                    "error": f"Query contains potentially dangerous keyword: {keyword}"
                }

        return {
            "sql": sql,
            "explanation": result.get("explanation", ""),
            "error": None
        }

    except json.JSONDecodeError:
        return {
            "sql": None,
            "explanation": None,
            "error": "I had trouble understanding that request. Could you rephrase it?"
        }
    except Exception as e:
        error_msg = str(e)
        if "API key" in error_msg or "auth" in error_msg.lower():
            return {
                "sql": None,
                "explanation": None,
                "error": "AI service not configured. Please set OPENROUTER_API_KEY in your .env file."
            }
        return {
            "sql": None,
            "explanation": None,
            "error": f"AI service error: {error_msg}"
        }


async def draft_campaign_message(
    segment_description: str,
    channel: str = "whatsapp",
    tone: str = "friendly and professional",
    custom_instructions: str = ""
) -> dict:
    """
    Draft a personalized campaign message template.
    Uses {{name}} as a placeholder for personalization.
    """
    try:
        system_prompt = """You are a marketing copywriter for a retail brand in India.
Write a short, engaging message for the given customer segment and channel.

RULES:
1. Use {{name}} as a placeholder for the customer's name.
2. Keep it under 160 characters for SMS, 300 for WhatsApp, 500 for email.
3. Include a clear call-to-action.
4. Make it feel personal, not spammy.
5. Use emojis sparingly (1-2 max for WhatsApp/SMS).
6. For Indian audience — be warm and respectful.

Respond ONLY in this exact JSON format, no markdown code fences:
{"message": "Your message here", "subject": "Email subject line (only for email channel, otherwise empty string)"}"""

        user_prompt = f"""Segment: {segment_description}
Channel: {channel}
Tone: {tone}
{f"Additional instructions: {custom_instructions}" if custom_instructions else ""}"""

        response_text = await _chat(system_prompt, user_prompt)
        result = _parse_json_response(response_text)

        return {
            "message": result.get("message", ""),
            "subject": result.get("subject", ""),
            "error": None
        }

    except Exception as e:
        return {
            "message": None,
            "subject": None,
            "error": f"Message drafting failed: {str(e)}"
        }


async def analyze_segment(customers: list) -> str:
    """
    Generate a natural language summary of a customer segment.
    """
    if not customers:
        return "No customers found matching your criteria."

    try:
        total = len(customers)
        avg_spent = sum(c.get("total_spent", 0) for c in customers) / total if total else 0
        cities = {}
        for c in customers:
            city = c.get("city", "Unknown")
            cities[city] = cities.get(city, 0) + 1
        top_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)[:3]

        system_prompt = "You are a concise marketing analytics assistant. Summarize customer segments in 2-3 short, insightful sentences. Be data-driven and actionable. No fluff."

        user_prompt = f"""Summarize this customer segment for a marketing manager:

- Segment size: {total} customers
- Average spend: ₹{avg_spent:,.0f}
- Top cities: {', '.join(f'{c} ({n})' for c, n in top_cities)}
- Spend range: ₹{min(c.get('total_spent', 0) for c in customers):,.0f} to ₹{max(c.get('total_spent', 0) for c in customers):,.0f}"""

        return await _chat(system_prompt, user_prompt)

    except Exception as e:
        # Fallback to a simple summary (no AI needed)
        total = len(customers)
        avg_spent = sum(c.get("total_spent", 0) for c in customers) / total if total else 0
        return f"Found {total} customers with an average spend of ₹{avg_spent:,.0f}."


async def personalize_message(template: str, customer: dict) -> str:
    """
    Replace placeholders in message template with customer data.
    Simple string replacement — no LLM needed.
    """
    message = template
    message = message.replace("{{name}}", customer.get("name", "there"))
    message = message.replace("{{city}}", customer.get("city", ""))
    message = message.replace("{{total_spent}}", f"₹{customer.get('total_spent', 0):,.0f}")
    message = message.replace("{{email}}", customer.get("email", ""))
    return message
