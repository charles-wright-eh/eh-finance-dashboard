# EH Finance Dashboard — Handoff

## Architecture

```
G-Accon (scheduled) → Google Sheets → GitHub Actions → data/*.json → Streamlit app
```

1. **G-Accon** runs daily at ~11pm BST, pulls all Xero transactions for EHL, EHRL, EHGL into a single Google Sheet tab (`AccountTransactions`)
2. **GitHub Actions** (`refresh_data.yml`) runs daily at 02:00 UTC, reads the sheet and writes clean JSON to `data/`, then commits
3. **Streamlit** (`app.py`) reads those JSON files and renders the dashboard — no external calls at runtime

There is no Xero API dependency. The original Xero app connection was replaced because `accounting.transactions` scope is blocked for apps created after March 2026, and Custom Connections aren't available for EHRL (Canada).

---

## Google Sheets

| Field | Value |
|-------|-------|
| Spreadsheet ID | `1ehDvGn8Mj5X0gB0gz7ypWxPAesZotxEDkZviimNaZdc` |
| Tab name | `AccountTransactions` |
| Headers | Row 1 |
| Data from | Row 2 |
| Refresh schedule | Daily ~11pm BST (current year only — historical data is stable) |
| Service account | `eh-finance-reader@eh-finance-dashboard.iam.gserviceaccount.com` |

G-Accon converts all CAD amounts to GBP using the exchange rate at time of pull. The `Net`, `Debit GBP`, `Credit GBP` columns are the GBP figures to use.

---

## GitHub Secrets

| Secret | Description |
|--------|-------------|
| `GOOGLE_SERVICE_ACCOUNT_KEY` | Full JSON content of the Google service account key file |
| `SLACK_BOT_TOKEN` | Slack bot token (same as other EH automations) |
| `SLACK_CHANNEL_ID` | `#xero_billing` channel ID |

Old Xero secrets (`XERO_CLIENT_ID`, `XERO_CLIENT_SECRET`, `XERO_ACCESS_TOKEN`, `XERO_REFRESH_TOKEN`, `GH_PAT`) can be removed from GitHub Secrets.

---

## Data files

All files live in `data/`. They are committed by GitHub Actions on each refresh.

| File | Contents |
|------|----------|
| `ehl_journals.json` | EHL revenue account transactions (codes 401–450) |
| `ehrl_journals.json` | EHRL revenue account transactions |
| `ehgl_journals.json` | EHGL revenue account transactions |
| `ehl_invoices.json` | EHL receivable invoice / credit note lines |
| `ehrl_invoices.json` | EHRL receivable invoice / credit note lines |
| `ehgl_invoices.json` | EHGL invoice lines |
| `tb_snapshots.json` | Monthly account 250 + 115 balances per entity |
| `metadata.json` | Refresh timestamp and record counts |

---

## Revenue account codes

| Code | Name |
|------|------|
| 401 | Recurring Revenue |
| 402 | License Revenue |
| 403 | Retained Revenue |
| 409 | Overages |
| 410 | Ad hoc Revenue |
| 411 | Services Revenue |
| 430 | Audience Recharges |
| 450 | Other Revenue (added April 2026 for Hinge/brand revenue) |

Excluded from revenue totals: `490` Inter-co Sales EHL, `491` Inter-co Sales EHGL, `250` Income in Advance, `111` Provision for Doubtful Debts.

---

## Opening balances (hardcoded in `fetch_data.py`)

Required because G-Accon only holds data from 2023 and the balance sheet accounts carry forward pre-2023 balances.

| Account | EHL | EHRL | EHGL |
|---------|-----|------|------|
| 250 — Deferred Revenue (Income in Advance) | £120,153.33 | £0 | £0 |
| 115 — Accrued Revenue | £5,772.74 | £0 | £0 |

These are stored in `OPENING_BALANCES` in `scripts/fetch_data.py`. The cumulative sum of monthly 250/115 transactions is added to these figures to produce each month-end balance.

**Validation:** EHL+EHRL consolidated deferred at May 2026 = £207,513 vs Charlie's expected ~£210k. ✓

---

## Entities

| Code | Full name | Currency | Xero Tenant ID |
|------|-----------|----------|----------------|
| EHL | Element Human Limited | GBP | `4f611f9d-0f19-4b1d-9847-15cbfb058820` |
| EHRL | Element Human Research Limited | CAD → GBP | `948b2ba0-6f1b-4e1f-8579-e9ff60a5c509` |
| EHGL | Element Human Group Limited | GBP | `586d2a29-b3b9-4a2d-9389-2288ca24cafb` |

EHGL has no external client revenue (uses inter-company codes 490/491 which are excluded). It appears in Invoice Detail and Account Transactions but shows £0 on revenue KPIs.

---

## Dashboard pages

| Page | Data source | Notes |
|------|-------------|-------|
| Summary | journals + invoices + tb_snapshots | Balance sheet section shows deferred (250) and accrued (115) closing balances |
| Monthly Revenue | journals | Monthly bar chart, TTM/T6M/T3M rolling metrics, client heatmap, type stacked bar |
| Invoice Detail | invoices | Filterable line-item table with CSV export |
| Account Transactions | journals | Revenue code transactions with CSV export |

---

## Key constants in app.py

```python
WHALAR_TTM_EXCLUDE_UNTIL = date(2026, 7, 1)
# Whalar excluded from TTM growth calculations until July 2026.
# They paid a £100k/month licence that ended mid-2024 and distorts the TTM rate.

REVENUE_CODES = {"401", "402", "403", "409", "410", "411", "430", "450"}
ALL_ENTITIES = ["EHL", "EHRL", "EHGL"]
```

---

## Local development

```powershell
# Install dependencies (first time)
pip install -r requirements.txt

# Run dashboard
streamlit run app.py
# Opens at http://localhost:8501
```

```powershell
# Run data pipeline locally (requires secrets as env vars)
$env:GOOGLE_SERVICE_ACCOUNT_KEY = Get-Content "eh-finance-dashboard-310e60d3b7a4.json" -Raw
$env:SLACK_BOT_TOKEN = "skip"
$env:SLACK_CHANNEL_ID = "skip"
python scripts/fetch_data.py
```

The service account key file (`eh-finance-dashboard-*.json`) is gitignored and must not be committed.

---

## G-Accon sign convention

G-Accon stores the `Net` column in the sheet's natural balance direction:
- **Revenue accounts (REVENUE type):** Net is positive for credits (recognised revenue). A credit to revenue = positive Net.
- **Liability accounts (CURRLIAB, e.g. 250 Income in Advance):** Net is positive for credits (deferring revenue increases the liability). A debit to 250 (releasing deferred revenue) = negative Net.
- **Asset accounts (CURRENT asset, e.g. 115 Accrued Revenue):** Net is positive for debits (accruing revenue increases the asset).

Cumulative sum of Net correctly gives the closing balance for each account when the opening balance is added.

---

## Planned next phases

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 2 | Management accounts — nine-column P&L frame (current month, prior month, MoM%, prior year, YoY%, YTD, YTD prior, YTD%, TTM) | Not started |
| Phase 3 | North Star metrics — ARR, NRR, gross margin, client count | Not started |
| Phase 4 | Runway and scenario modelling | Not started |
| Phase 5 | Drill-down + AI narrative (Anthropic API, claude-sonnet-4-6) | Not started |

---

## Known limitations

- G-Accon refreshes current year only. Historical data (2023–2024) is fixed after the year end. Manual re-pulls can be triggered from the G-Accon sidebar in Google Sheets if needed.
- TB snapshots only go back to Jan 2023 (first G-Accon data). Pre-2023 balances are approximated by the hardcoded opening balances above.
- EHRL data is in CAD at source. G-Accon converts to GBP using the rate at time of pull (monthly snapshot rate, not daily). Small rounding differences vs Xero GBP equivalent are expected.
- Client code mapping (`CLIENT_CODES` in app.py) is maintained manually. New clients need a new entry.
