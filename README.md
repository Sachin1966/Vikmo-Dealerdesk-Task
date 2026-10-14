# VIKMO DealerDesk

A robust, AI-native B2B parts distribution and ordering engine built with Django, PostgreSQL, and LLM tool calling. Conforms strictly to the VIKMO DealerDesk API and Run Contract.

🎥 **Video Walkthrough:** [Watch Project Demo on YouTube](https://youtu.be/B9uzxkPz43c)

---

## Tracks & Scope

This repository implements **both tracks**:
- **Django Track:** Core CRUD, atomic order concurrency, row-level locks, GST calculation (18% ROUND_HALF_UP), idempotent daily sequence numbering, robust supplier sync with retry backoff & rate-limit handling.
- **AI / ML Track:** Dealer Assistant with multi-turn conversation memory, prompt-injection defense, dynamic database stock/price retrieval, and 4-week demand forecasting with Diwali festive alignment and reorder suggestions.

**Implemented Parts:**
- **Part A1 & A2 (Backend Core & Order Engine):** Fully implemented (§4, §5, §6, §7).
- **Part B (Supplier Sync):** Fully implemented (§8).
- **Part C (Dealer Assistant - GenAI):** Fully implemented (§9). Provider: **Groq** (model: `llama-3.3-70b-versatile` / `llama-3.1-8b-instant`), with out-of-the-box support for **Google Gemini** (`gemini-1.5-flash`), **OpenAI** (`gpt-4o-mini`), and deterministic multi-turn tool engine fallback.
- **Part D (Forecasting & Reorder - ML):** Fully implemented (§10). Direct multi-horizon LightGBM Poisson models with `ml/forecast.csv` (160 rows).
- **Part E (Frontend Dealer Portal - Bonus):** Fully implemented (§8). Complete modern **React 18 + Vite** Single Page Application located in `frontend/` (launched via `cd frontend && npm run dev` at `http://localhost:5173/`), plus a zero-dependency Django-served portal directly at `http://localhost:8000/`. Features catalogue browsing with vehicle fitment filters, slide-over cart drawer with 18% GST line-by-line calculations, stock shortage warnings, order status lifecycles with inventory restoration, live AI assistant chat with tool inspection, and ML demand forecast reorder planning.

---

## Setup & Run Contract

### 1. Requirements
- Python 3.11+
- PostgreSQL database

### 2. Environment Configuration
Copy `.env.example` to `.env` (never commit `.env`):
```bash
cp .env.example .env
```
Configure your credentials in `.env`:
```ini
DATABASE_URL=postgres://postgres:postgres@localhost:5432/dealerdesk
SUPPLIER_API_URL=http://127.0.0.1:8099
SUPPLIER_API_KEY=dev-supplier-key
DJANGO_SECRET_KEY=your-secret-key
GROQ_API_KEY=your-groq-key
```

### 3. Run Grader Contract Commands
```bash
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py seed_data
python manage.py seed_data
python manage.py runserver 0.0.0.0:8000 --noreload
```

### 4. Optional: Run Modern React Frontend (Part E Bonus)
```bash
cd frontend
npm install
npm run dev
# Serves the modern React SPA at http://localhost:5173/ (proxies /api to Django on :8000)
```

---

## Running Smoke Tests & Unit Tests

### Automated Smoke Tests
To run against the local instance:
```bash
# Check Django track
python smoke_test.py --base-url http://localhost:8000 --track django

# Check AI/ML track
python smoke_test.py --base-url http://localhost:8000 --track aiml

# Check all parts combined
python smoke_test.py --base-url http://localhost:8000 --all
```

### Comprehensive Unit & Concurrency Test Suite
```bash
python manage.py test core.tests
```
Includes:
- Concurrent order confirmation testing (overselling prevention with `select_for_update`)
- GST rounding half-up paisa accuracy
- Idempotency key handling and conflict verification
- Order status lifecycle transitions and stock restoration
- Supplier sync retries, deduplication, and stock safety
- Forecasting CSV validations and reorder point formulas

---

## Architecture & Technical Highlights

1. **Concurrency & Overselling Prevention:**
   Order lines acquire row-level locks in deterministic SKU order (`select_for_update()`), preventing deadlocks. PostgreSQL check constraints enforce `stock >= 0` at the database level.

2. **Idempotency & Sequence Numbering:**
   Order numbers use `ORD-YYYYMMDD-NNNN` tied to atomic per-calendar-day sequence rows in Asia/Kolkata timezone. Idempotency keys verify SHA-256 canonical request hashes with race-condition handling.

3. **Supplier Catalogue Sync:**
   Paginates external supplier feeds, handles 429 `Retry-After` headers and 5xx backoffs up to 5 attempts, deduplicates multi-version SKUs by `updated_at`, skips malformed items gracefully, and commits changes atomically without touching local stock.

4. **Dealer Assistant (GenAI):**
   Full tool-calling loop using Groq / OpenAI. Supports:
   - `search_parts(query, vehicle)`
   - `check_stock(sku)`
   - `create_draft_order(dealer_id, items)`
   Catalogue descriptions are isolated to prevent prompt injection. All stock and price figures are queried live from the database.

5. **Machine Learning Demand Forecast:**
   Direct multi-horizon Poisson regression predicts 4 future weeks (`2026-09-28` to `2026-10-19`) for all 40 SKUs in `lead_times.csv`. Incorporates moving lunar Diwali dates (`weeks_to_diwali`) and planned promotional calendar signals without future data leakage.

---

## Assumptions & Design Choices

1. **GST Calculation:** 18% GST is computed strictly on a per-line basis and rounded to the nearest paisa (`0.01`) using `ROUND_HALF_UP` as specified in Contract §7.4. Order totals (`subtotal`, `tax_total`, `grand_total`) are exact sums of rounded line amounts.
2. **Catalog Price Dynamic Locking:** While an order is in `DRAFT` status, line item prices dynamically follow the live product catalogue price. Upon transition to `CONFIRMED`, prices are locked into the order items permanently and will never change.
3. **Supplier Warehouse Stock Isolation:** The supplier API's `supplier_stock` field represents external vendor inventory and is intentionally never written to DealerDesk local warehouse `stock`.
4. **Idempotency Lifetime:** Idempotency keys are cached in PostgreSQL and tied to the SHA-256 canonical hash of the request payload. Concurrent duplicate requests are serialized via transactional advisory locks.
5. **Demand Forecasting Horizon:** Models predict weekly demand directly for the 4 forecast weeks starting `2026-09-28`, `2026-10-05`, `2026-10-12`, and `2026-10-19`. The lunar festival peak is dynamically aligned using Diwali distance features without future data leakage.

---

## Submission Details

- **Tracks:** Both **Django Track** and **AI / ML Track** implemented (including optional Bonus parts: Supplier Sync, Assistant, Forecasting & Frontend).
- **LLM Provider:** Groq (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`) with automatic fallback to Gemini (`gemini-1.5-flash`), OpenAI (`gpt-4o-mini`), or deterministic tool engine.
- **Video Walkthrough:** [Watch Walkthrough Video on YouTube](https://youtu.be/B9uzxkPz43c)
- **Decisions & Rationale:** See [`DECISIONS.md`](./DECISIONS.md) for detailed line-by-line answers with exact code citations.
