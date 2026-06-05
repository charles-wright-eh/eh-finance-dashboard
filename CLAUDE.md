# EH Finance Dashboard — Project Brief for Claude

## What this project is

A two-part finance dashboard system for Element Human. It pulls live data from Xero and renders an interactive dashboard using Streamlit.

**Part 1 — Data pipeline** (`scripts/fetch_data.py` + `.github/workflows/refresh_data.yml`)
A GitHub Actions workflow that runs nightly (and on manual trigger). Pulls invoice detail and account transactions from Xero for EHL and EHRL, writes clean JSON files to `data/`, commits them to the repo, and posts a Slack summary.

**Part 2 — Dashboard app** (`app.py`)
A Streamlit web app that reads the JSON files from `data/` and renders an interactive finance dashboard. Does not connect to any external services at runtime — all data comes from the pre-fetched files.

---

## File structure

```
eh-finance-dashboard/
├── app.py                          # Streamlit dashboard — main entry point
├── requirements.txt                # Python dependencies for the app
├── CLAUDE.md                       # This file
├── .gitignore
├── .github/
│   └── workflows/
│       └── refresh_data.yml        # GitHub Actions — nightly data refresh
├── scripts/
│   └── fetch_data.py               # Xero data pull script (run by GitHub Actions)
└── data/
    ├── README.md
    ├── ehl_invoices.json           # EHL invoice line items (auto-generated)
    ├── ehrl_invoices.json          # EHRL invoice line items (auto-generated)
    ├── ehl_transactions.json       # EHL account transactions (auto-generated)
    ├── ehrl_transactions.json      # EHRL account transactions (auto-generated)
    └── metadata.json               # Refresh timestamp and counts (auto-generated)
```

---

## Business context

**Company:** Element Human — a UK-based behavioural-AI platform. Measures audience attention, emotion and memory for brands and agencies.

**Three legal entities:**
- `EHL` — Element Human Limited (UK, GBP). Tenant ID: `4f611f9d-0f19-4b1d-9847-15cbfb058820`
- `EHGL` — Element Human Group Limited (UK, GBP). Tenant ID: `586d2a29-b3b9-4a2d-9389-2288ca24cafb`
- `EHRL` — Element Human Research Limited (Canada, CAD → converted to GBP). Tenant ID: `948b2ba0-6f1b-4e1f-8579-e9ff60a5c509`

This dashboard currently covers **EHL and EHRL only**. EHGL is inter-company and excluded from revenue reporting.

**The user:** Charlie Wright, Head of Finance. Non-developer. Uses GitHub browser UI, VS Code with Claude Code. Works on Windows.

---

## Revenue account codes

These are the only account codes that represent external client revenue:

| Code | Name |
|------|------|
| 401  | Recurring Revenue |
| 402  | License Revenue |
| 403  | Retained Revenue |
| 409  | Overages |
| 410  | Ad hoc Revenue |
| 411  | Services Revenue |
| 430  | Audience Recharges |

**Exclude from revenue totals:**
- `490` — Inter-co Sales (EHL → EHGL)
- `491` — Inter-co Sales (EHRL → EHGL)
- `250` — Income in Advance (balance sheet, not P&L)
- `111` — Provision for Doubtful Debts

---

## Client codes and categories

The `function` field on EHL invoices contains a client code (e.g. `NET001`, `BBC001`). The mapping lives in `app.py` as `CLIENT_CODES` and `CATEGORIES`. Categories are: CTV, Media, Agency, Brand.

Key clients to be aware of:
- **Whalar** — was paying a £100k/month licence (ended mid-2024). Must be **excluded from TTM growth charts** until July 2026 as it distorts the growth rate. A `WHALAR_TTM_EXCLUDE_UNTIL` constant should control this.
- **Netflix** — multiple entities (NET001–NET008). Usually grouped as "Netflix" for summary views.
- **Amazon** — AMA001 (Amazon UK, ended 2024) and AMA002 (Amazon Advertising LLC, EHRL).

---

## Xero API notes

**OAuth token rotation:** Tokens rotate on every use. After each API call the new access token and refresh token must be saved back to the `XERO_CONFIG` GitHub Secret using PyNaCl encryption and the GitHub API. This is handled in `scripts/fetch_data.py`.

**Scopes in use:** `accounting.invoices.read` — note: `accounting.transactions` is blocked for apps created after 2 March 2026. Use the Journals endpoint for account transactions.

**Pagination:** Xero returns max 100 records per page. All Xero fetches must paginate.

**Rate limits:** 429 responses must be handled with a retry after the `Retry-After` header value.

**Two-step contact lookup:** The list endpoint ignores `summaryOnly=false`. To get purchase defaults, fetch ContactID first then call `/Contacts/{id}?summaryOnly=false`. Not needed for this dashboard but worth knowing.

**EHRL currency:** EHRL invoices are in CAD. The pipeline converts to GBP using the exchange rate at time of fetch (stored in metadata). All dashboard values display in GBP.

---

## GitHub Actions

**Workflow file:** `.github/workflows/refresh_data.yml`
**Schedule:** `0 2 * * *` = 02:00 UTC daily (02:00 GMT winter / 03:00 BST summer)
**Manual trigger:** `workflow_dispatch` — available in GitHub Actions UI

**Secrets required:**
| Secret | Description |
|--------|-------------|
| `XERO_CONFIG` | JSON: `{"client_id":"...","client_secret":"...","access_token":"...","refresh_token":"..."}` |
| `SLACK_BOT_TOKEN` | Slack bot token (same as other EH automations) |
| `SLACK_CHANNEL_ID` | `#xero_billing` channel ID |
| `GH_PAT` | Fine-grained PAT with Secrets + Actions read/write on this repo |

**After each run:** The workflow commits updated `data/*.json` files back to the repo. The Streamlit app reads these on next page load.

---

## Streamlit app architecture

**Entry point:** `streamlit run app.py`

**Pages (sidebar navigation):**
1. Summary — KPI cards, revenue by entity/type/client, category breakdown
2. Monthly Revenue — monthly chart, client heatmap table, rolling TTM/T6M/T3M metrics, revenue by type stacked bar
3. Invoice Detail — full filterable transaction table with CSV download
4. Account Transactions — journal-level data with filters and CSV download

**Data flow:**
1. App loads JSON files from `data/` using `@st.cache_data(ttl=300)`
2. DataFrames are built in `load_data()` and returned to each page
3. Sidebar filters (date range, entity) are applied before rendering each page
4. All monetary values display in GBP, formatted with `fmt_gbp()`

**Key functions in app.py:**
- `load_data()` — loads and processes all JSON files into DataFrames
- `fmt_gbp(value)` — formats a number as £ (e.g. `£1.2m`, `£45k`, `£1,234`)
- `fmt_pct(value)` — formats a decimal as percentage with sign (e.g. `+12.3%`)

---

## Planned next phases

These are not yet built. Build them in order when instructed:

### Phase 2 — Management accounts view
A nine-column analytical P&L frame:

| Column | Description |
|--------|-------------|
| Current month | Selected month actuals |
| Prior month | Month before |
| MoM % | Month-on-month change |
| Prior year month | Same month last year |
| YoY % | Year-on-year change |
| YTD current | Year to date, current year |
| YTD prior year | Year to date, prior year |
| YTD % | YTD change |
| TTM | Trailing twelve months |

Row structure mirrors the existing management accounts pack. Revenue rows broken out by account code. Whalar excluded from TTM until July 2026.

### Phase 3 — North Star metrics and executive summary
- ARR (annualised recurring revenue — 401 + 402 codes × 12)
- NRR (net revenue retention)
- Gross margin % (requires cost data — TBD)
- Client count, new vs churned
- Top 10 clients by TTM revenue

### Phase 4 — Runway and scenario modelling
- Current cash position (manual input or from Xero bank feeds)
- Monthly burn rate
- Runway calculator with scenario toggles (hire, win/lose client)

### Phase 5 — Drill-down and AI narrative
- Click a client in the summary to see their full invoice history
- AI-generated monthly narrative using the Anthropic API (claude-sonnet-4-6)

---

## Code style and conventions

- **Always produce complete files.** Never provide partial snippets. If any change is needed, rewrite the whole file.
- **Python 3.11+**. Use f-strings, type hints where helpful, no walrus operator for readability.
- **No unnecessary comments.** Code should be self-documenting. Comments only for non-obvious logic.
- **Streamlit patterns:** Use `st.cache_data` for data loading. Use `st.columns` for layout. Avoid `st.experimental_*` — use stable APIs only.
- **Plotly for all charts.** Use `plotly.express` for standard charts, `plotly.graph_objects` for custom layouts. Always set `use_container_width=True`.
- **Error handling:** Data files may not exist yet (first run). Always check with `path.exists()` before reading. Show a helpful `st.info()` message rather than crashing.
- **Currency:** All values in GBP. EHRL values converted from CAD at rate stored in `metadata.json`. Never display raw CAD values.
- **Whalar exclusion:** Any TTM or rolling growth chart must exclude Whalar invoices before July 2026. Use the `WHALAR_TTM_EXCLUDE_UNTIL` constant (`2026-07-01`).

---

## Running locally

```bash
# Install dependencies (first time only)
pip install -r requirements.txt

# Start the dashboard
streamlit run app.py
```

Opens at `http://localhost:8501`.

To run the data pipeline locally (requires secrets as environment variables):
```bash
python scripts/fetch_data.py
```

---

## Deployment (when ready)

The app will be hosted on an internal Element Human server at `finance.elementhuman.com`, behind Google SSO. An engineer will handle the hosting setup. To deploy: pull the repo, install requirements, run `streamlit run app.py`. No server-side scheduled jobs needed — data is refreshed by GitHub Actions and committed to the repo.
