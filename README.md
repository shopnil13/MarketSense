# MarketSense AI

**Intelligent competitive pricing for Pakistani e-commerce — powered by a 3-agent Band collaboration**

> LabLab.ai Band of Agents Hackathon · Track 1: Internal Enterprise Workflows · June 2026

---

## What it does

MarketSense AI monitors competitor prices in real time, analyses strategic options, and queues recommended price changes for human approval — all without a human in the loop until a decision is actually needed.

A price drop triggers a chain across three specialised agents coordinated via [Band](https://app.band.ai):

```
Scout ──alerts──► Analyst ◄──sentiment──► Scout
                    │
                 save report
                    │
                    ▼
               Executive
                    │
             queue for review
                    │
                    ▼
          Human (HiTL Dashboard)
                    │
              ✓ Approve / ✗ Reject
```

---

## Agents

| Agent | Role | LLM |
|---|---|---|
| **Scout** | Scans competitor prices; detects drops ≥5%; retrieves social sentiment | AI/ML API (`gpt-4o-mini`) |
| **Analyst** | Calculates match/undercut/hold options against margin floor; generates strategic narrative | AI/ML API (`gpt-4o-mini`) |
| **Executive** | Drafts action brief; queues for human approval via HiTL dashboard | AI/ML API (`gpt-4o-mini`) |

Agents communicate via Band chatrooms. All structured data (reports, actions) live in a shared Postgres database — Band messages carry only IDs and human-readable summaries.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Band Platform                      │
│  ┌──────────┐   chatroom   ┌──────────┐   chatroom      │
│  │  Scout   │◄────────────►│ Analyst  │                 │
│  │  Agent   │              │  Agent   │◄────────────┐   │
│  └────┬─────┘              └────┬─────┘             │   │
│       │ price data              │ report_id         │   │
│       ▼                         ▼                   │   │
│  ┌──────────────────────────────────────────────┐   │   │
│  │              PostgreSQL                      │   │   │
│  │  products · competitors · price_snapshots   │   │   │
│  │  sentiment_records · analysis_reports        │   │   │
│  │  pending_actions                             │   │   │
│  └──────────────────────────────────────────────┘   │   │
│                         │                            │   │
│                    ┌────┴──────┐                     │   │
│                    │ Executive │─────────────────────┘   │
│                    │   Agent   │                         │
│                    └────┬──────┘                         │
└─────────────────────────┼───────────────────────────────┘
                          │ queue action
                          ▼
              ┌───────────────────────┐
              │   HiTL Dashboard      │  ← Application URL
              │   (FastAPI + HTML)    │
              │                       │
              │  [ ✓ Approve ]        │
              │  [ ✗ Reject  ]        │
              └───────────────────────┘
```

---

## Tech stack

- **Band SDK** (`band-sdk 1.0.0`) — multi-agent coordination via Band chatrooms
- **LangGraph** + **LangChain OpenAI** — agent reasoning loops with tool-calling
- **AI/ML API** — powers all 3 agent brains (reliable tool-calling, OpenAI-compatible) and the Analyst's bounded narrative call
- **FastAPI** — HiTL approval dashboard (the submission Application URL)
- **PostgreSQL** + **SQLAlchemy (async)** + **Alembic** — shared market state & migrations
- **Docker Compose** — local orchestration (postgres + 3 agents + HiTL API)
- **pydantic-settings** — typed config via `.env`

---

## Quickstart (local)

### Prerequisites
- Python 3.11
- Docker Desktop
- Band account with 3 Remote Agents registered at [app.band.ai](https://app.band.ai)

### Setup

```bash
# 1. Clone and create virtual environment
git clone <repo-url>
cd MarketSense
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — fill in AIML_API_KEY, DATABASE_URL
# Edit agent_config.yaml — fill in Band agent UUIDs and API keys

# 3. Start database
docker compose up postgres -d

# 4. Run migrations and seed data
python -m alembic upgrade head
python scripts/seed_data.py

# 5. Start all agents
python agents/scout/agent.py &
python agents/analyst/agent.py &
python agents/executive/agent.py &

# 6. Start HiTL dashboard
uvicorn agents.executive.hitl_api:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** to see the HiTL approval dashboard.

### Trigger the demo

In Band, @mention the Scout Agent:

```
@Scout Agent please scan competitor prices for PUMA-SNK-001
```

Scout will detect the Daraz price drop (23.9% below list), create an alert room, recruit the Analyst, the Analyst will request sentiment from Scout, generate a strategic narrative, save the report, and recruit the Executive — which will queue a `price_match` action for human approval on the dashboard.

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `AIML_API_KEY` | ✅ | AI/ML API key (all 3 agent brains + Analyst narrative) |
| `AIML_MODEL` | | Model ID (default: `openai/gpt-4o-mini`) |
| `DATABASE_URL` | ✅ | AsyncPG connection string |
| `SLACK_WEBHOOK_URL` | | Slack webhook for action notifications |
| `HITL_API_URL` | | HiTL dashboard base URL (default: `http://localhost:8000`) |
| `MARGIN_FLOOR_PCT` | | Minimum acceptable margin % (default: `6.0`) |
| `MAX_PRICE_CHANGE_PCT` | | Max allowed single price change % (default: `15.0`) |
| `PRICE_DROP_THRESHOLD_PCT` | | Competitor drop threshold to trigger alert (default: `5.0`) |

---

## Project structure

```
MarketSense/
├── agents/
│   ├── scout/
│   │   ├── agent.py          # Scout agent — Band connection + LangGraph adapter
│   │   ├── tools.py          # scan_competitor_prices, get_social_sentiment
│   │   └── scraper.py        # Mock-first price data (httpx+BS4 live fallback)
│   ├── analyst/
│   │   ├── agent.py          # Analyst agent
│   │   └── tools.py          # Pricing strategy, strategic narrative, report persistence
│   └── executive/
│       ├── agent.py          # Executive agent
│       ├── tools.py          # load_analysis_report, draft_action_content, queue_for_human_approval
│       └── hitl_api.py       # FastAPI HiTL dashboard
├── core/
│   ├── config.py             # pydantic-settings (reads .env)
│   ├── database.py           # Async SQLAlchemy engine
│   ├── models.py             # 6 ORM tables
│   ├── schemas.py            # Inter-agent Pydantic contracts
│   └── llm.py                # AI/ML API client helpers (agent brain + narrative)
├── scripts/
│   ├── seed_data.py          # Seeds 3 products with competitor data
│   └── trigger_demo.py       # Automated demo trigger (backup)
├── alembic/                  # Database migrations
├── Dockerfile.agents         # Image for Scout/Analyst/Executive workers
├── Dockerfile.api            # Image for HiTL FastAPI service
├── docker-compose.yml        # Local orchestration
├── pyproject.toml
└── requirements.txt
```

---

## Demo products (seeded)

| SKU | Product | Our Price | Key Competitor Drop |
|---|---|---|---|
| PUMA-SNK-001 | PUMA Sneaker Classic White | PKR 9,500 | Daraz: PKR 7,225 (−23.9%) |
| NIKE-AIR-002 | Nike Air Max 270 | PKR 18,500 | Daraz: PKR 17,020 (−8.0%) |
| ADIDAS-RUN-003 | Adidas Ultraboost 22 | PKR 22,000 | Goto: PKR 19,800 (−10.0%) |

---

## Key design decisions

**Why pass `report_id` through Band, not JSON?** LLM-formatted JSON in chat is unreliable for structured data. The Analyst saves the full analysis to Postgres and passes only the UUID via Band; the Executive loads from the database. This guarantees data integrity regardless of how the LLM formats its message.

**Why split agent reasoning from the narrative call?** The three agents run as full LangGraph reasoning loops with tool-calling. The `generate_strategic_narrative` step is deliberately *not* an agentic loop — it's a single bounded, text-only completion. Keeping it separate makes the narrative deterministic and cheap, and isolates it from the tool-calling control flow. Both run on AI/ML API (GPT-4o-mini).

**Why mock-first scraping?** Competitor sites rate-limit aggressively and the demo environment is unpredictable. Mock data ensures deterministic demo behaviour; the live scraper (httpx + BeautifulSoup + tenacity retry) is a labeled best-effort upgrade path.

---

## License

MIT — see [pyproject.toml](pyproject.toml).
