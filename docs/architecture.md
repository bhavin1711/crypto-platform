# Architecture Documentation
## Crypto Market Intelligence Platform

---

## What this project is

**Not** a crypto prediction platform.

It is an **AI-assisted market intelligence and decision-support platform** that:
- Ingests live market data from the Binance public API
- Applies a simple, transparent SMA-based trend signal
- Generates analyst-style commentary via a rule-based AI layer (LLM-ready)
- Presents results in a clean, professional dashboard

The algorithm is intentionally simple. The story is the **architecture**.

---

## 1. Current MVP Architecture

```
┌─────────────────────────────────────────────────────┐
│                  User (Browser)                     │
│         Vanilla JS SPA — index.html + app.js        │
│                                                     │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │ Scanner  │  │   Chart   │  │    Backtest      │  │
│  │  Table   │  │   View    │  │    Results       │  │
│  └────┬─────┘  └─────┬─────┘  └────────┬─────────┘  │
│       └──────────────┴─────────────────┘            │
│                   apiFetch()                        │
└────────────────────────┬────────────────────────────┘
                         │ HTTP GET
                         ▼
┌─────────────────────────────────────────────────────┐
│             Python FastAPI Backend                  │
│                   main.py                           │
│                                                     │
│   GET /scan          GET /signal/{sym}              │
│   GET /backtest/{sym}  GET /insight/{sym}           │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  binance_service.py  — Data Ingestion         │   │
│  │  Primary: binance.com  Fallback: binance.us   │   │
│  └─────────────────┬────────────────────────────┘   │
│                    │                                 │
│  ┌─────────────────▼────────────────────────────┐   │
│  │  analytics.py  — Signal Engine (pure)         │   │
│  │  sma() · compute_signal() · run_backtest()    │   │
│  └─────────────────┬────────────────────────────┘   │
│                    │                                 │
│  ┌─────────────────▼────────────────────────────┐   │
│  │  insight.py  — AI Insight Layer               │   │
│  │  Rule-based NLG today · LLM-swappable         │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                         │ HTTPS
                         ▼
              ┌─────────────────────┐
              │  Binance Public API │
              │  (no key required)  │
              └─────────────────────┘
```

---

## 2. Data Pipeline

Every request follows the same linear flow. Easy to explain in one breath:

```
Binance API
    │
    │  Raw OHLCV candle data (JSON)
    ▼
binance_service.py  — Data Ingestion
    │  Normalises fields, filters stablecoins + leveraged tokens
    │  Primary/fallback failover
    ▼
analytics.py  — SMA Processing
    │  Computes SMA20, SMA50
    │  Pure functions — stateless, deterministic, no I/O
    ▼
Signal Generation
    │  BUY  = Price > SMA20 > SMA50
    │  SELL = Price < SMA20 < SMA50
    │  HOLD = anything else
    ▼
insight.py  — AI Insight Generation
    │  Rule-based NLG → analyst-style prose
    │  Same public interface as an LLM call
    ▼
Frontend Dashboard
    │  Renders API output — no business logic in the browser
    ▼
User Decision Support
```

**Interview one-liner:**
> "Data flows linearly through four stages — ingestion, analytics, insight generation, and visualisation. Each stage has one responsibility and a clean interface to the next."

---

## 3. Signal Logic

```
Signal   Condition                  Meaning
──────   ──────────────────────     ─────────────────────────────────────────
BUY      Price > SMA20 > SMA50      Uptrend: price leads, short MA above long
SELL     Price < SMA20 < SMA50      Downtrend: inverse of above
HOLD     Anything else              Consolidation or transition phase
```

**Why only SMA?**

| Criterion | Justification |
|---|---|
| Explainability | One sentence describes the entire algorithm |
| Testability | Pure function — zero mocking, deterministic output |
| Transparency | Any analyst can verify the signal by hand |
| Interview fit | Complexity is in the architecture, not the math |
| Extensibility | Adding RSI is additive — one function, no rewrites |

---

## 4. File Map — What Each File Does

| File | Layer | Responsibility |
|---|---|---|
| `backend/main.py` | API | Route definitions, middleware, error handling |
| `backend/binance_service.py` | Ingestion | All Binance HTTP calls, failover, filtering |
| `backend/analytics.py` | Analytics | SMA, signal, backtest — pure functions |
| `backend/insight.py` | AI | Rule-based NLG, LLM seam |
| `backend/requirements.txt` | Infra | Python dependencies |
| `frontend/index.html` | UI | Dashboard structure, tab layout |
| `frontend/app.js` | UI | API calls, chart rendering, DOM updates |
| `frontend/styles.css` | UI | Design tokens, component styles |
| `.github/workflows/deploy.yml` | CI/CD | Validate → Build → Deploy pipeline |
| `docs/architecture.md` | Docs | This file |
| `README.md` | Docs | Setup, API reference, interview guide |

**10 files. No more.**

---

## 5. API Endpoints

```
GET  /health              → {"status": "ok"}
GET  /scan?interval=4h    → ranked list of top pairs with signals
GET  /signal/{symbol}     → signal + SMA series for chart rendering
GET  /insight/{symbol}    → AI narrative string (HTML)
GET  /backtest/{symbol}   → simulation result + trade log
```

**Interview talking point:**
> "FastAPI auto-generates interactive docs at `/docs`. In an interview
> I can open that URL and live-demo the API without any Postman setup.
> It also shows the request/response schemas, which demonstrates I
> understand typed interfaces."

---

## 6. AI Insight Layer — The LLM Seam

`insight.py` exposes one public function:

```python
def generate(base, timeframe, price, change_24h, signal) -> str:
    # returns HTML prose string
```

**Today:** deterministic rules → instant, free, testable.

**Tomorrow (drop-in replacement):**

```python
async def generate(base, timeframe, price, change_24h, signal) -> str:
    response = await openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
            {"role": "user",   "content": json.dumps(signal)},
        ]
    )
    return response.choices[0].message.content
```

Route (`main.py`), API endpoint, and frontend: **zero changes**.

**Why rule-based first?**
- Demos work without an API key
- Deterministic → easy to write unit tests
- Zero latency, zero cost
- Graceful fallback if the LLM service is down

---

## 7. Future Cloud Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        AZURE                                 │
│                                                              │
│  ┌──────────────────────────────┐                           │
│  │  Azure Static Web Apps       │  ← Global CDN edge         │
│  │  frontend/ (HTML, JS, CSS)   │    Auto HTTPS, CI/CD       │
│  └──────────────┬───────────────┘                           │
│                 │ HTTPS API calls                            │
│                 ▼                                            │
│  ┌──────────────────────────────┐                           │
│  │  Azure App Service           │  ← Python runtime          │
│  │  FastAPI (main.py)           │    Auto-scaled, monitored  │
│  └──────┬───────────────────────┘                           │
│         │                                                    │
│         ├──────────────────────────────────┐                │
│         ▼                                  ▼                │
│  ┌──────────────────┐            ┌──────────────────────┐   │
│  │  Azure Cache      │            │  Azure Functions     │   │
│  │  (Redis) TTL/min  │            │  Timer: ingest       │   │
│  │  Reduces Binance  │            │  candles every 5min  │   │
│  │  API calls        │            │  → Table Storage     │   │
│  └──────────────────┘            └──────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
         ↑
    Binance API  /  OpenAI API (insight layer)
```

**What changes and what stays the same:**

| | MVP | Production |
|---|---|---|
| Ingest | Fetch on every request | Azure Function timer → Time-Series DB |
| Analytics | Run per API call | Same code, reads from DB |
| Insight | Rule-based NLG | OpenAI/Anthropic call, same interface |
| Frontend | File:// or local server | Azure Static Web Apps (CDN) |
| Backend | localhost:8000 | Azure App Service (auto-scaled) |
| Cache | None | Redis TTL per endpoint |

---

## 8. CI/CD Pipeline

```
Push to main branch
        │
        ▼
  GitHub Actions (deploy.yml)
  ┌──────────────────────┐   ┌──────────────────────┐
  │  validate-backend     │   │  build-frontend       │  ← parallel
  │  pip install          │   │  validate static files│
  │  syntax check         │   │  upload artifact      │
  │  health-check start   │   └──────────┬────────────┘
  └──────────┬────────────┘              │
             │   Both pass               │
             └───────────────┬───────────┘
                             │
              ┌──────────────▼──────────────┐
              │  deploy-backend             │  ← Azure App Service
              │  deploy-frontend            │  ← Azure Static Web Apps
              └─────────────────────────────┘
```

---

## 9. Design Decisions & Tradeoffs

### Vanilla JS frontend (not React)
| Decision | Vanilla JS — no framework, no build step |
|---|---|
| Why | Frontend just renders API output — no complex state or component logic to justify React overhead |
| Tradeoff | Harder to scale with a team; no component reuse patterns |
| When to change | When there are multiple developers or complex client-side state |

### Python + FastAPI backend (not Node.js)
| Decision | FastAPI — async Python with auto-generated OpenAPI docs |
|---|---|
| Why | Readable, typed, industry-standard for data/analytics APIs; auto Swagger UI for live demo |
| Tradeoff | Slightly more infra setup than a JS monorepo |
| When to change | Never — Python is the right home for analytics |

### Rule-based NLG (not LLM)
| Decision | Deterministic rules generate insight text |
|---|---|
| Why | Zero cost, zero latency, 100% testable, works without API keys |
| Tradeoff | Fixed vocabulary, no contextual reasoning |
| When to change | When product value justifies LLM cost and latency |

### SMA-only signal
| Decision | BUY/SELL/HOLD from two moving averages |
|---|---|
| Why | One-sentence explainability; pure function; easy to test; interview-appropriate |
| Tradeoff | Lower signal fidelity in ranging markets |
| When to change | Adding RSI is additive — one function in analytics.py |

---

## 10. Interview Answer Templates

**"Walk me through the architecture."**
> "It's a three-tier web application. The frontend is static HTML and JavaScript — its only job is to call the API and render results, no business logic. The backend is FastAPI — it owns the pipeline: fetch market data from Binance, run the SMA analytics engine, and generate insight text. The AI layer sits inside the backend as a module — today it's rule-based NLG, but the interface is identical to what an LLM call would look like, so swapping it in is a one-function change with zero impact on the frontend."

**"Why is the algorithm so simple?"**
> "Intentionally. The interview focus is architecture — clean data flow, separation of concerns, cloud-readiness — not quant finance. A simple algorithm means every design choice is explainable and the logic is verifiable by hand. Adding RSI would take ten minutes and it's additive — I can show exactly where it would slot in."

**"How would you scale this?"**
> "Two changes cover 90% of the scaling story. First, decouple ingestion from queries — replace the inline Binance fetch with an Azure Function on a timer that writes candles to a time-series store. The API reads from the store instead of calling Binance on every request. That fixes latency, cost, and rate-limit exposure in one move. Second, add Redis caching in front of the signal and insight endpoints — same symbol and timeframe within a 60-second window gets served from cache."

**"Where would the LLM fit in?"**
> "It already has a reserved seat. The insight module has one public function — `generate()` — that takes a signal snapshot and returns a string. Today the body uses rules. I replace it with an async OpenAI call, passing the snapshot as structured JSON in the user message. The route, the API endpoint URL, and the frontend are completely unchanged. The API key stays server-side so it never touches the browser. I'd add Redis caching keyed on the signal hash to avoid paying for duplicate narratives."

**"Why FastAPI over Flask?"**
> "FastAPI gives me two things Flask doesn't out of the box: async support, which matters when I'm making parallel Binance calls across 30 pairs in the scanner, and auto-generated OpenAPI docs at /docs. In this demo I can open /docs and live-demo every endpoint without Postman. Flask would have required manually writing the Swagger spec."
