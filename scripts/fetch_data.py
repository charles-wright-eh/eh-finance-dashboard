"""
EH Finance Dashboard — Xero Data Pipeline
Pulls invoice, manual journal, and trial balance data from Xero for EHL and EHRL.
Writes clean JSON files to /data/ for the Streamlit app to consume.
"""

import os
import json
import time
import requests
import base64
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from nacl.public import PublicKey, SealedBox


# ── Config ──────────────────────────────────────────────────────────────────

TENANTS = {
    "EHL": "4f611f9d-0f19-4b1d-9847-15cbfb058820",
    "EHRL": "948b2ba0-6f1b-4e1f-8579-e9ff60a5c509",
}

REVENUE_CODES = ["401", "402", "403", "409", "410", "411", "430"]
DEFERRED_CODE = "250"

HISTORY_FROM = "2024-01-01"

XERO_API_BASE = "https://api.xero.com/api.xro/2.0"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"

XERO_CLIENT_ID = os.environ["XERO_CLIENT_ID"]
XERO_CLIENT_SECRET = os.environ["XERO_CLIENT_SECRET"]
XERO_ACCESS_TOKEN = os.environ["XERO_ACCESS_TOKEN"]
XERO_REFRESH_TOKEN = os.environ["XERO_REFRESH_TOKEN"]

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
GH_PAT = os.environ["GH_PAT"]
GH_REPO = os.environ["GH_REPO"]


# ── Token Management ─────────────────────────────────────────────────────────

def refresh_xero_token():
    credentials = base64.b64encode(f"{XERO_CLIENT_ID}:{XERO_CLIENT_SECRET}".encode()).decode()

    response = requests.post(
        XERO_TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": XERO_REFRESH_TOKEN,
        },
    )

    if response.status_code != 200:
        raise Exception(f"Token refresh failed: {response.status_code} {response.text}")

    tokens = response.json()
    _update_github_secret("XERO_ACCESS_TOKEN", tokens["access_token"])
    _update_github_secret("XERO_REFRESH_TOKEN", tokens["refresh_token"])
    return tokens["access_token"]


def _update_github_secret(secret_name, secret_value):
    headers = {
        "Authorization": f"token {GH_PAT}",
        "Accept": "application/vnd.github+json",
    }

    key_response = requests.get(
        f"https://api.github.com/repos/{GH_REPO}/actions/secrets/public-key",
        headers=headers,
    )
    key_response.raise_for_status()
    key_data = key_response.json()

    public_key_obj = PublicKey(base64.b64decode(key_data["key"]))
    encrypted_b64 = base64.b64encode(SealedBox(public_key_obj).encrypt(secret_value.encode())).decode()

    requests.put(
        f"https://api.github.com/repos/{GH_REPO}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted_b64, "key_id": key_data["key_id"]},
    ).raise_for_status()


# ── Xero API Helpers ─────────────────────────────────────────────────────────

def xero_get(access_token, tenant_id, endpoint, params=None):
    """Paginated GET — returns all records."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-Tenant-Id": tenant_id,
        "Accept": "application/json",
    }

    all_records = []
    page = 1

    while True:
        page_params = dict(params or {})
        page_params["page"] = page

        response = requests.get(
            f"{XERO_API_BASE}/{endpoint}",
            headers=headers,
            params=page_params,
        )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue

        if response.status_code != 200:
            raise Exception(f"Xero API error [{endpoint}]: {response.status_code} {response.text[:500]}")

        data = response.json()
        record_key = next((k for k, v in data.items() if isinstance(v, list)), None)
        if not record_key:
            break

        page_records = data[record_key]
        all_records.extend(page_records)

        if len(page_records) < 100:
            break

        page += 1
        time.sleep(0.5)

    return all_records


def xero_report(access_token, tenant_id, report_name, params=None):
    """Fetch a single Xero report."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-Tenant-Id": tenant_id,
        "Accept": "application/json",
    }
    response = requests.get(
        f"{XERO_API_BASE}/Reports/{report_name}",
        headers=headers,
        params=params or {},
    )
    if response.status_code == 429:
        time.sleep(int(response.headers.get("Retry-After", 60)))
        return xero_report(access_token, tenant_id, report_name, params)
    if response.status_code != 200:
        raise Exception(f"Xero report error [{report_name}]: {response.status_code} {response.text[:500]}")
    return response.json()


def serial_to_date(serial):
    """Convert a Xero date value to ISO date string (YYYY-MM-DD)."""
    if serial is None:
        return None
    try:
        if isinstance(serial, str) and serial.startswith("/Date("):
            ms = int(serial[6:-2].split("+")[0].split("-")[0])
            return datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")
        if isinstance(serial, str) and "T" in serial:
            return serial.split("T")[0]
        return str(serial)
    except Exception:
        return str(serial)


def month_start(date_str):
    """Return YYYY-MM-01 for a given date string."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return date(d.year, d.month, 1).isoformat()
    except Exception:
        return date_str


def extract_tracking(tracking_list):
    """Extract Function and Sub-function from a Tracking array."""
    function_val = ""
    subfunction_val = ""
    for t in (tracking_list or []):
        name = t.get("Name", "")
        option = t.get("Option", "")
        if "function" in name.lower() and "sub" not in name.lower():
            function_val = option
        elif "sub" in name.lower():
            subfunction_val = option
    return function_val, subfunction_val


# ── Invoice Fetch ─────────────────────────────────────────────────────────────

CODE_NAMES = {
    "401": "Recurring Revenue",
    "402": "License Revenue",
    "403": "Retained Revenue",
    "409": "Overages",
    "410": "Ad hoc Revenue",
    "411": "Services Revenue",
    "430": "Audience Recharges",
    "490": "Inter-co Sales - EHL",
    "491": "Inter-co Sales - EHGL",
    "250": "Income in Advance",
}


def fetch_invoices(access_token, tenant_name, tenant_id):
    """Fetch all ACCREC invoices from HISTORY_FROM. One row per line item."""
    print(f"  Fetching invoices for {tenant_name}...")

    invoices = xero_get(access_token, tenant_id, "Invoices", {
        "where": f'Type=="ACCREC" AND Date>=DateTime.Parse("{HISTORY_FROM}")',
        "unitdp": 4,
    })
    print(f"    {len(invoices)} invoices retrieved")

    rows = []
    for inv in invoices:
        inv_number = inv.get("InvoiceNumber", "")
        inv_type = inv.get("Type", "")
        inv_status = inv.get("Status", "")
        contact_name = inv.get("Contact", {}).get("Name", "")
        inv_date = serial_to_date(inv.get("DateString") or inv.get("Date"))
        paid_date = serial_to_date(inv.get("FullyPaidOnDate"))
        reference = inv.get("Reference", "") or ""

        inv_function, _ = extract_tracking(inv.get("TrackingCategories", []))

        for line in inv.get("LineItems", []):
            account_str = line.get("AccountCode", "")
            if isinstance(account_str, dict):
                account_str = account_str.get("Code", "")

            line_function, line_subfunction = extract_tracking(line.get("Tracking", []))
            function_val = line_function or inv_function or reference

            net = line.get("LineAmount", 0) or 0
            tax = line.get("TaxAmount", 0) or 0

            rows.append({
                "entity": tenant_name,
                "invoice_number": inv_number,
                "type": "CR" if "CREDIT" in inv_type else "INV",
                "contact": contact_name,
                "date": inv_date,
                "paid_date": paid_date,
                "item_code": line.get("ItemCode", ""),
                "account_code": str(account_str),
                "account_name": CODE_NAMES.get(str(account_str), str(account_str)),
                "description": line.get("Description", ""),
                "quantity": line.get("Quantity", 0) or 0,
                "unit_price": line.get("UnitAmount", 0) or 0,
                "discount": line.get("DiscountRate", 0) or 0,
                "net": net,
                "tax": tax,
                "gross": net + tax,
                "status": inv_status,
                "function": function_val,
                "month": month_start(inv_date) if inv_date else None,
            })

    return rows


# ── Manual Journals Fetch ────────────────────────────────────────────────────

def fetch_manual_journals(access_token, tenant_name, tenant_id):
    """
    Fetch manual journal lines hitting revenue codes (401-430) from HISTORY_FROM.
    These are the revenue recognition entries (DR 250, CR 4xx).
    """
    print(f"  Fetching manual journals for {tenant_name}...")

    journals = xero_get(access_token, tenant_id, "ManualJournals", {
        "where": f'Date>=DateTime.Parse("{HISTORY_FROM}")',
    })
    print(f"    {len(journals)} manual journals retrieved")

    rows = []
    for jnl in journals:
        jnl_date = serial_to_date(jnl.get("DateString") or jnl.get("Date"))
        narration = jnl.get("Narration", "") or ""
        status = jnl.get("Status", "")

        if status == "DELETED":
            continue

        for line in jnl.get("JournalLines", []):
            account_code = str(line.get("AccountCode", ""))
            if account_code not in REVENUE_CODES:
                continue

            net = line.get("LineAmount", 0) or 0
            # Revenue recognition: CR to revenue code is negative in Xero double-entry
            # Flip sign so revenue is positive
            net = -net if net < 0 else net

            function_val, subfunction_val = extract_tracking(line.get("Tracking", []))

            rows.append({
                "entity": tenant_name,
                "date": jnl_date,
                "month": month_start(jnl_date) if jnl_date else None,
                "account_code": account_code,
                "account_name": CODE_NAMES.get(account_code, account_code),
                "description": line.get("Description", "") or narration,
                "narration": narration,
                "net": net,
                "tax": line.get("TaxAmount", 0) or 0,
                "function": function_val,
                "subfunction": subfunction_val,
                "status": status,
            })

    print(f"    {len(rows)} revenue recognition lines extracted for {tenant_name}")
    return rows


# ── Trial Balance Snapshots ──────────────────────────────────────────────────

def fetch_tb_snapshots(access_token, tenant_name, tenant_id):
    """
    Fetch Trial Balance as at each month-end from HISTORY_FROM to today.
    Returns list of {date, account_250_balance} dicts.
    """
    print(f"  Fetching TB snapshots for {tenant_name}...")

    history_start = datetime.strptime(HISTORY_FROM, "%Y-%m-%d")
    today = datetime.utcnow()

    # Build list of month-end dates
    month_ends = []
    current = date(history_start.year, history_start.month, 1)
    while current <= today.date():
        # Last day of the month
        next_month = current + relativedelta(months=1)
        month_end = next_month - relativedelta(days=1)
        if month_end <= today.date():
            month_ends.append(month_end.isoformat())
        current = next_month

    snapshots = []
    for month_end_date in month_ends:
        try:
            report = xero_report(access_token, tenant_id, "TrialBalance", {
                "date": month_end_date,
                "paymentsOnly": "false",
            })

            # Navigate the report rows to find account 250 (Income in Advance)
            balance_250 = 0.0
            found = False
            for section in report.get("Reports", [{}])[0].get("Rows", []):
                if found:
                    break
                for row in section.get("Rows", []):
                    cells = row.get("Cells", [])
                    if not cells:
                        continue
                    # Match on account code in value, attributes, or account name
                    is_250 = False
                    for cell in cells:
                        val = str(cell.get("Value", ""))
                        if "250" in val or "income in advance" in val.lower():
                            is_250 = True
                            break
                        for attr in cell.get("Attributes", []):
                            if "250" in str(attr.get("Value", "")):
                                is_250 = True
                                break
                        if is_250:
                            break
                    if is_250:
                        try:
                            debit = float(cells[1].get("Value", 0) or 0)
                            credit = float(cells[2].get("Value", 0) or 0)
                            # 250 is a liability — credit balance = deferred revenue
                            balance_250 = credit - debit
                        except (ValueError, IndexError):
                            pass
                        found = True
                        break

            snapshots.append({
                "entity": tenant_name,
                "date": month_end_date,
                "month": month_start(month_end_date),
                "account_250_balance": balance_250,
            })
            time.sleep(0.3)

        except Exception as e:
            print(f"    Warning: TB fetch failed for {month_end_date}: {e}")

    print(f"    {len(snapshots)} TB snapshots fetched for {tenant_name}")
    return snapshots


# ── Slack Notification ────────────────────────────────────────────────────────

def post_slack(blocks):
    requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"channel": SLACK_CHANNEL_ID, "blocks": blocks},
    )


def build_slack_success(counts, run_time):
    lines = "\n".join(f"• {k}: {v:,}" for k, v in counts.items())
    return [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*Finance Dashboard — Data Refresh Complete*\n{run_time}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": lines}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": "Data files updated. Dashboard will reflect latest Xero data on next page load."}},
    ]


def build_slack_error(error_msg, run_time):
    return [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*Finance Dashboard — Data Refresh Failed*\n{run_time}"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*Error:*\n```{error_msg[:500]}```"}},
    ]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    run_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"Finance Dashboard data refresh — {run_time}")

    try:
        print("Refreshing Xero token...")
        access_token = refresh_xero_token()
        print("Token refreshed.")

        print("\nFetching invoices...")
        ehl_invoices = fetch_invoices(access_token, "EHL", TENANTS["EHL"])
        ehrl_invoices = fetch_invoices(access_token, "EHRL", TENANTS["EHRL"])

        print("\nFetching manual journals (recognised revenue)...")
        ehl_journals = fetch_manual_journals(access_token, "EHL", TENANTS["EHL"])
        ehrl_journals = fetch_manual_journals(access_token, "EHRL", TENANTS["EHRL"])

        print("\nFetching trial balance snapshots (deferred revenue)...")
        ehl_tb = fetch_tb_snapshots(access_token, "EHL", TENANTS["EHL"])
        ehrl_tb = fetch_tb_snapshots(access_token, "EHRL", TENANTS["EHRL"])

        os.makedirs("data", exist_ok=True)

        with open("data/ehl_invoices.json", "w") as f:
            json.dump(ehl_invoices, f, indent=2)
        with open("data/ehrl_invoices.json", "w") as f:
            json.dump(ehrl_invoices, f, indent=2)
        with open("data/ehl_journals.json", "w") as f:
            json.dump(ehl_journals, f, indent=2)
        with open("data/ehrl_journals.json", "w") as f:
            json.dump(ehrl_journals, f, indent=2)
        with open("data/tb_snapshots.json", "w") as f:
            json.dump(ehl_tb + ehrl_tb, f, indent=2)

        metadata = {
            "last_refreshed": run_time,
            "ehl_invoice_lines": len(ehl_invoices),
            "ehrl_invoice_lines": len(ehrl_invoices),
            "ehl_journal_lines": len(ehl_journals),
            "ehrl_journal_lines": len(ehrl_journals),
            "ehl_tb_snapshots": len(ehl_tb),
            "ehrl_tb_snapshots": len(ehrl_tb),
            "from_date": HISTORY_FROM,
        }
        with open("data/metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        counts = {
            "EHL invoice lines": len(ehl_invoices),
            "EHRL invoice lines": len(ehrl_invoices),
            "EHL recognised revenue lines": len(ehl_journals),
            "EHRL recognised revenue lines": len(ehrl_journals),
            "TB snapshots": len(ehl_tb) + len(ehrl_tb),
        }
        print(f"\nData files written successfully.")
        for k, v in counts.items():
            print(f"  {k}: {v}")

        post_slack(build_slack_success(counts, run_time))

    except Exception as e:
        import traceback
        print(f"ERROR: {traceback.format_exc()}")
        post_slack(build_slack_error(str(e), run_time))
        raise


if __name__ == "__main__":
    main()
