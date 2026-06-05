"""
EH Finance Dashboard — Google Sheets Data Pipeline
Reads account transaction data from the G-Accon Google Sheet.
Writes clean JSON files to /data/ for the Streamlit app to consume.
"""

import calendar
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import gspread
import requests
from google.oauth2.service_account import Credentials


# ── Config ────────────────────────────────────────────────────────────────────

SPREADSHEET_ID = "1ehDvGn8Mj5X0gB0gz7ypWxPAesZotxEDkZviimNaZdc"
SHEET_TRANSACTIONS = "AccountTransactions"

REVENUE_CODES = {"401", "402", "403", "409", "410", "411", "430", "450"}
EXCLUDE_STATUS = {"Deleted", "Voided", "Draft"}
INVOICE_SOURCES = {"Receivable Invoice", "Receivable Credit Note"}

ENTITY_MAP = {
    "Element Human Limited": "EHL",
    "Element Human Research Limited": "EHRL",
    "Element Human Group Limited": "EHGL",
    "Element Human Group": "EHGL",
}

CODE_NAMES = {
    "401": "Recurring Revenue",
    "402": "License Revenue",
    "403": "Retained Revenue",
    "409": "Overages",
    "410": "Ad hoc Revenue",
    "411": "Services Revenue",
    "430": "Audience Recharges",
    "450": "Other Revenue",
    "490": "Inter-co Sales - EHL",
    "491": "Inter-co Sales - EHGL",
    "250": "Income in Advance",
    "115": "Accrued Revenue",
}

# Opening balances as at 31 Dec 2022
OPENING_BALANCES = {
    "250": {"EHL": 120153.33, "EHRL": 0.0, "EHGL": 0.0},
    "115": {"EHL": 5772.74,   "EHRL": 0.0, "EHGL": 0.0},
}

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]


# ── Google Sheets ─────────────────────────────────────────────────────────────

def get_sheets_client() -> gspread.Client:
    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_KEY"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    return gspread.authorize(creds)


def read_transactions(client: gspread.Client) -> list[dict]:
    print(f"  Reading {SHEET_TRANSACTIONS} from Google Sheets...")
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_TRANSACTIONS)
    records = ws.get_all_records()
    print(f"    {len(records):,} rows read")
    return records


# ── Date helpers ──────────────────────────────────────────────────────────────

def parse_date(val) -> str | None:
    if not val:
        return None
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s[:10] if len(s) >= 10 else None


def month_start(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return date(d.year, d.month, 1).isoformat()
    except Exception:
        return None


def month_end_date(year: int, month: int) -> str:
    return date(year, month, calendar.monthrange(year, month)[1]).isoformat()


# ── Row builders ──────────────────────────────────────────────────────────────

def _str(val) -> str:
    return str(val or "").strip()


def _float(val) -> float:
    try:
        return float(val or 0)
    except (ValueError, TypeError):
        return 0.0


def build_journal_row(r: dict, entity: str, date_str: str | None) -> dict:
    account_code = _str(r.get("Account Code"))
    return {
        "entity": entity,
        "date": date_str,
        "month": month_start(date_str),
        "account_code": account_code,
        "account_name": CODE_NAMES.get(account_code, _str(r.get("Account Name"))),
        "source": _str(r.get("Source")),
        "description": _str(r.get("Description")),
        "narration": _str(r.get("Source")),
        "reference": _str(r.get("Reference")),
        "net": _float(r.get("Net")),
        "tax": _float(r.get("VAT")),
        "function": _str(r.get("Function")),
        "subfunction": _str(r.get("Sub-function")),
        "contact": _str(r.get("Contact Name")),
        "status": _str(r.get("Status")),
    }


def build_invoice_row(r: dict, entity: str, date_str: str | None) -> dict:
    account_code = _str(r.get("Account Code"))
    source = _str(r.get("Source"))
    net = _float(r.get("Net"))
    tax = _float(r.get("VAT"))
    return {
        "entity": entity,
        "invoice_number": _str(r.get("Number")),
        "type": "CR" if source == "Receivable Credit Note" else "INV",
        "contact": _str(r.get("Contact Name")),
        "date": date_str,
        "paid_date": parse_date(r.get("Paid Date")),
        "item_code": "",
        "account_code": account_code,
        "account_name": CODE_NAMES.get(account_code, _str(r.get("Account Name"))),
        "description": _str(r.get("Description")),
        "quantity": 1,
        "unit_price": net,
        "discount": 0,
        "net": net,
        "tax": tax,
        "gross": net + tax,
        "status": _str(r.get("Status")),
        "function": _str(r.get("Function")),
        "month": month_start(date_str),
    }


# ── Processing ────────────────────────────────────────────────────────────────

def process_records(records: list[dict]) -> dict:
    """
    Split AccountTransactions into:
    - journals: revenue code lines (recognised revenue)
    - invoices: receivable invoice/credit note lines (invoice detail)
    - tb_txns: account 250 and 115 lines (for deriving balance sheet balances)
    """
    journals: dict[str, list] = {"EHL": [], "EHRL": [], "EHGL": []}
    invoices: dict[str, list] = {"EHL": [], "EHRL": [], "EHGL": []}
    tb_txns: dict[str, dict[str, list]] = {
        "250": {"EHL": [], "EHRL": [], "EHGL": []},
        "115": {"EHL": [], "EHRL": [], "EHGL": []},
    }

    for r in records:
        if _str(r.get("Status")) in EXCLUDE_STATUS:
            continue

        entity = ENTITY_MAP.get(_str(r.get("Organisation")))
        if not entity:
            continue

        account_code = _str(r.get("Account Code"))
        source = _str(r.get("Source"))
        date_str = parse_date(r.get("Date"))

        if account_code in REVENUE_CODES:
            journals[entity].append(build_journal_row(r, entity, date_str))

        if source in INVOICE_SOURCES:
            invoices[entity].append(build_invoice_row(r, entity, date_str))

        if account_code in ("250", "115"):
            tb_txns[account_code][entity].append({
                "month": month_start(date_str),
                "net": _float(r.get("Net")),
            })

    return {"journals": journals, "invoices": invoices, "tb_txns": tb_txns}


def build_tb_snapshots(tb_txns: dict[str, dict[str, list]]) -> list[dict]:
    """
    Derive monthly account 250 (Deferred Revenue) and 115 (Accrued Revenue)
    balances from cumulative transaction sums, starting from opening balances
    as at 31 Dec 2022.
    """
    snapshots = []

    for entity in ("EHL", "EHRL", "EHGL"):
        monthly_250: dict[str, float] = {}
        for t in tb_txns["250"][entity]:
            if t["month"]:
                monthly_250[t["month"]] = monthly_250.get(t["month"], 0.0) + t["net"]

        monthly_115: dict[str, float] = {}
        for t in tb_txns["115"][entity]:
            if t["month"]:
                monthly_115[t["month"]] = monthly_115.get(t["month"], 0.0) + t["net"]

        all_months = sorted(set(monthly_250.keys()) | set(monthly_115.keys()))
        if not all_months:
            continue

        cum_250 = OPENING_BALANCES["250"][entity]
        cum_115 = OPENING_BALANCES["115"][entity]

        for month_str in all_months:
            cum_250 += monthly_250.get(month_str, 0.0)
            cum_115 += monthly_115.get(month_str, 0.0)
            d = datetime.strptime(month_str, "%Y-%m-%d")
            snapshots.append({
                "entity": entity,
                "date": month_end_date(d.year, d.month),
                "month": month_str,
                "account_250_balance": round(cum_250, 2),
                "account_115_balance": round(cum_115, 2),
            })

    return snapshots


# ── Slack ─────────────────────────────────────────────────────────────────────

def post_slack(blocks: list) -> None:
    requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"channel": SLACK_CHANNEL_ID, "blocks": blocks},
    )


def build_slack_success(counts: dict, run_time: str) -> list:
    lines = "\n".join(f"• {k}: {v:,}" for k, v in counts.items())
    return [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*Finance Dashboard — Data Refresh Complete*\n{run_time}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": lines}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": "Data files updated. Dashboard reflects latest data on next page load."}},
    ]


def build_slack_error(error_msg: str, run_time: str) -> list:
    return [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*Finance Dashboard — Data Refresh Failed*\n{run_time}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*Error:*\n```{error_msg[:500]}```"}},
    ]


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    run_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Finance Dashboard data refresh — {run_time}")

    try:
        print("Connecting to Google Sheets...")
        client = get_sheets_client()

        records = read_transactions(client)

        print("Processing records...")
        processed = process_records(records)
        journals = processed["journals"]
        invoices = processed["invoices"]
        tb_snapshots = build_tb_snapshots(processed["tb_txns"])

        Path("data").mkdir(exist_ok=True)

        for entity in ("EHL", "EHRL", "EHGL"):
            key = entity.lower()
            with open(f"data/{key}_journals.json", "w") as f:
                json.dump(journals[entity], f, indent=2)
            with open(f"data/{key}_invoices.json", "w") as f:
                json.dump(invoices[entity], f, indent=2)

        with open("data/tb_snapshots.json", "w") as f:
            json.dump(tb_snapshots, f, indent=2)

        counts = {
            "EHL revenue lines": len(journals["EHL"]),
            "EHRL revenue lines": len(journals["EHRL"]),
            "EHGL revenue lines": len(journals["EHGL"]),
            "EHL invoice lines": len(invoices["EHL"]),
            "EHRL invoice lines": len(invoices["EHRL"]),
            "EHGL invoice lines": len(invoices["EHGL"]),
            "TB snapshots": len(tb_snapshots),
            "Total rows processed": len(records),
        }

        with open("data/metadata.json", "w") as f:
            json.dump({"last_refreshed": run_time, **counts}, f, indent=2)

        print("\nData files written successfully.")
        for k, v in counts.items():
            print(f"  {k}: {v:,}")

        post_slack(build_slack_success(counts, run_time))

    except Exception as e:
        import traceback
        print(f"ERROR: {traceback.format_exc()}")
        post_slack(build_slack_error(str(e), run_time))
        raise


if __name__ == "__main__":
    main()
