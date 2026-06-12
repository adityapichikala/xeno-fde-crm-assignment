# Xeno Mini CRM — AI-Powered Chat-to-Campaign Platform

> **Forward Deployed Engineer (FDE) Internship Assignment — Xeno 2026**

A conversational CRM where marketers use natural language to segment customers, draft personalized messages, and launch campaigns with real-time delivery tracking — powered by AI.

![Architecture](https://img.shields.io/badge/Architecture-Two_Service-6366f1?style=flat-square)
![AI](https://img.shields.io/badge/AI-OpenRouter_LLM-10b981?style=flat-square)
![Backend](https://img.shields.io/badge/Backend-FastAPI-059669?style=flat-square)
![Frontend](https://img.shields.io/badge/Frontend-Next.js_16-000?style=flat-square)

---

## 🎯 Product Decision: Why "Chat-to-Campaign"?

The assignment says: *"Figuring out exactly what to build — and what NOT to build — is part of what we are evaluating."*

Instead of building a complex filter-builder UI (which is slow to build, hard to use, and looks like every other CRM), I chose a **conversational interface** where:

1. A marketer types: *"Find customers who spent more than ₹5000 but haven't ordered in 60 days"*
2. The AI converts this to SQL, executes it, and returns the segment
3. The marketer reviews, drafts a personalized message, and launches the campaign
4. Real-time delivery tracking shows results as callbacks come in

**Why this wins for an FDE role:**
- **AI-native thinking** — AI is the engine, not a feature bolted on
- **Customer empathy** — Marketers want to *talk to their data*, not wrestle with filter dropdowns
- **Speed** — One chat replaces 10 clicks in a traditional CRM

---

## 🏗️ Architecture

```
┌──────────────┐     REST API      ┌──────────────────┐     POST /send     ┌─────────────────────┐
│              │ ◄──────────────► │                  │ ──────────────────► │                     │
│   Frontend   │                  │  CRM Backend     │                    │  Mock Channel       │
│   (Next.js)  │                  │  (FastAPI)       │ ◄────────────────── │  Service (FastAPI)  │
│   Port 3000  │                  │  Port 8000       │   POST /webhook    │  Port 8001          │
│              │                  │                  │   (async callback) │                     │
└──────────────┘                  └────────┬─────────┘                    └─────────────────────┘
                                          │
                                          │ OpenAI-compatible API
                                          ▼
                                  ┌──────────────────┐
                                  │   OpenRouter      │
                                  │   (Free LLM)      │
                                  └──────────────────┘
```

### Two-Service Architecture (Assignment Requirement)

The CRM and Mock Channel Service are **deliberately separate** processes:

1. **CRM Backend** (`backend/main.py` — Port 8000): Handles segmentation, campaign logic, and stores data
2. **Mock Channel Service** (`mock_channel_service/server.py` — Port 8001): Simulates WhatsApp/SMS delivery
   - Accepts messages via `POST /send` → returns `200 OK` immediately
   - After a random 2-10s delay, calls back `POST /api/webhook/callback` with delivery status
   - Status distribution: DELIVERED (60%), READ (20%), FAILED (10%), SENT (10%)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+ (tested on 3.14)
- Node.js 18+
- OpenRouter API key ([get free key here](https://openrouter.ai/keys))

### 1. Clone & Setup

```bash
git clone <repo-url>
cd xeno
```

### 2. Generate & Clean Data

```bash
cd backend/data
python generate_data.py   # Creates raw_data.json (with intentional quality issues)
python clean_data.py       # Cleans and outputs clean_data.json
cd ..
```

### 3. Configure Environment

```bash
# In backend/.env
cp .env.example .env
# Edit .env and add your OpenRouter API key:
# OPENROUTER_API_KEY=sk-or-v1-xxxxx
```

### 4. Start Backend (Terminal 1)

```bash
cd backend
pip install -r requirements.txt
python main.py
# → Running on http://localhost:8000
```

### 5. Start Mock Channel Service (Terminal 2)

```bash
cd mock_channel_service
pip install -r requirements.txt
python server.py
# → Running on http://localhost:8001
```

### 6. Start Frontend (Terminal 3)

```bash
cd frontend
npm install
npm run dev
# → Running on http://localhost:3000
```

### 7. Open & Use

Visit **http://localhost:3000** and try:
- "Find customers who spent more than ₹5000"
- "Show me top 10 customers from Mumbai"
- "Who are inactive users who haven't ordered in 60 days?"

---

## 🧠 AI Integration

### Text-to-SQL (Core Feature)

The chat endpoint uses OpenRouter's free LLM (Gemini 2.0 Flash) to:

1. **Parse intent** — Understand what the marketer wants
2. **Generate SQL** — Convert natural language to a safe `SELECT` query
3. **Safety checks** — Blocks `DROP`, `DELETE`, `UPDATE` and other dangerous operations
4. **Execute & return** — Runs the query and returns customer segment

### Message Drafting

The LLM also drafts personalized campaign messages based on:
- Segment characteristics (size, avg spend, cities)
- Channel type (WhatsApp, SMS, Email — with appropriate length limits)
- `{{name}}` placeholder for per-customer personalization

### Error Handling

If the LLM generates bad SQL, the system:
- Catches the execution error
- Returns a friendly message: *"I had trouble with that query. Could you rephrase?"*
- Shows the attempted SQL for transparency

---

## 📊 Data Pipeline (FDE Competency)

The data generation pipeline demonstrates enterprise data handling:

### `generate_data.py`
- Generates 50 customers + 200 orders
- **Intentionally injects ~20% quality issues:**
  - Malformed phone numbers (`12345`, missing `+91`)
  - Inconsistent name casing (`aarav sharma` vs `AARAV SHARMA`)
  - Missing emails
  - Duplicate customers with slight name variations
  - Inconsistent date formats (`DD/MM/YYYY`, `Month DD, YYYY`, etc.)

### `clean_data.py`
- **Phone normalization** → `+91XXXXXXXXXX` format
- **Name standardization** → Proper title case, whitespace cleanup
- **Email generation** → Placeholder for missing emails
- **Date normalization** → ISO `YYYY-MM-DD`
- **Deduplication** → Fuzzy name matching, keeps the record with more data
- **Prints a cleaning report** with issue counts

---

## 🛠️ Tech Stack & Decisions

| Layer | Choice | Why |
|-------|--------|-----|
| **Backend** | Python FastAPI | JD asks for Python; FastAPI is async-native, perfect for webhook callbacks |
| **Database** | SQLite + SQLAlchemy | Zero infrastructure, portable, great for demo. Production → PostgreSQL |
| **AI** | OpenRouter (free) | OpenAI-compatible API, free tier models, no vendor lock-in |
| **Frontend** | Next.js 16 + Tailwind | Fast to build, SSR-ready, great DX |
| **Mock Channel** | Separate FastAPI | Assignment explicitly requires separate stubbed service |
| **Deployment** | Docker Compose | All 3 services orchestrated together |

### Tradeoffs & What I'd Change at Scale

| Decision | Why (Demo) | What I'd Use (Production @ Xeno Scale) |
|----------|------------|----------------------------------------|
| SQLite | Zero setup, portable | **PostgreSQL** on RDS/Supabase |
| Synchronous HTTP to channel | Simple, works for 50 customers | **Kafka/RabbitMQ** for backpressure and reliability |
| Frontend polling for stats | Simple to implement | **WebSockets / Server-Sent Events** for real-time |
| Single-process backend | Easy to run | **Celery workers** for async campaign sending |
| `{{name}}` placeholders | Fast personalization | **Per-customer LLM calls** or template engine like Jinja2 |
| SQLite file storage | No setup | **Redis** for caching hot segments + session state |

---

## 📁 Project Structure

```
xeno/
├── backend/
│   ├── main.py              # FastAPI app — all API endpoints
│   ├── models.py            # SQLAlchemy models (Customer, Order, Campaign, Communication)
│   ├── database.py          # DB engine, session, data ingestion
│   ├── ai_engine.py         # OpenRouter LLM integration (text-to-SQL, drafting)
│   ├── data/
│   │   ├── generate_data.py # Mock data generator with quality issues
│   │   ├── clean_data.py    # Data cleaning pipeline
│   │   ├── raw_data.json    # Generated dirty data
│   │   └── clean_data.json  # Cleaned data ready for DB
│   ├── .env                 # API keys (gitignored)
│   ├── requirements.txt
│   └── Dockerfile
├── mock_channel_service/
│   ├── server.py            # Separate mock messaging gateway
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/app/
│   │   ├── page.tsx         # Main chat + dashboard UI
│   │   ├── layout.tsx       # Root layout with SEO
│   │   └── globals.css      # Premium dark theme
│   ├── next.config.ts       # API proxy config
│   └── package.json
├── docker-compose.yml       # Orchestrates all 3 services
├── .gitignore
└── README.md
```

---

## 🔄 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check with DB counts |
| `POST` | `/api/chat` | NL → SQL segmentation |
| `POST` | `/api/campaign/draft` | AI message drafting |
| `POST` | `/api/campaign/send` | Launch campaign to segment |
| `POST` | `/api/webhook/callback` | Receive delivery status from channel |
| `GET` | `/api/stats` | Campaign delivery stats |
| `GET` | `/api/campaigns` | List all campaigns |
| `GET` | `/api/customers` | Browse customers |

---

## 🐳 Docker

```bash
# Run all 3 services
docker-compose up --build

# Set API key
OPENROUTER_API_KEY=sk-or-v1-xxxx docker-compose up --build
```

---

## 📐 Evaluation Criteria Mapping

| Criteria | How This Project Demonstrates It |
|----------|----------------------------------|
| **Segmentation** | NL chat → SQL → customer segment with summary |
| **Campaign Sending** | Select segment → Draft message → Send via mock channel |
| **Two-Service Architecture** | CRM (8000) ↔ Mock Channel (8001) with async callbacks |
| **Performance Insights** | Real-time dashboard with delivery progress bar |
| **Data Handling** | Dirty data generation → cleaning pipeline → DB ingestion |
| **AI-Native** | LLM powers the core UX (not just a sidebar feature) |
| **System Design** | Documented tradeoffs and production alternatives |
| **Code Quality** | Clean separation of concerns, typed models, error handling |

---

## 👤 Built By

**Aditya** — FDE Internship Assignment, June 2026

Built with AI-native workflow using Cursor + Antigravity IDE.
