"""
EH Finance Dashboard — Xero Data Pipeline
Pulls invoice detail and account transactions from Xero for EHL and EHRL.
Writes clean JSON files to /data/ for the Streamlit app to consume.
"""

import os
import json
import time
import requests
import base64
from datetime import datetime, date
from nacl.encoding import Base64Encoder
from nacl.public import PublicKey, SealedBox


# ── Config ──────────────────────────────────────────────────────────────────

TENANTS = {
    "EHL": "4f611f9d-0f19-4b1d-9847-15cbfb058820",
    "EHRL": "948b2ba0-6f1b-4e1f-8579-e9ff60a5c509",
}

# Revenue account codes to pull for the account transactions report
REVENUE_CODES = ["401", "402", "403", "409", "410", "411", "430"]

# History start — pull everything from Jan 2024 onwards
HISTORY_FROM = "2024-01-01"

XERO_API_BASE = "https://api.xero.com/api.xro/2.0"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
GH_PAT = os.environ["GH_PAT"]
GH_REPO = os.environ["GH_REPO"]  # e.g. "charles-wright-eh/eh-finance-dashboard"

XERO_CONFIG = json.loads(os.environ["XERO_CONFIG"])
# XERO_CONFIG format:
# {
#   "client_id": "...",
#   "client_secret": "...",
#   "access_token": "...",
#   "refresh_token": "..."
# }


# ── Token Management ─────────────────────────────────────────────────────────

def refresh_xero_token():
    """Refresh the Xero OAuth token and update GitHub Secrets."""
    client_id = XERO_CONFIG["client_id"]
    client_secret = XERO_CONFIG["client_secret"]
    refresh_token = XERO_CONFIG["refresh_token"]

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    response = requests.post(
        XERO_TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )

    if response.status_code != 200:
        raise Exception(f"Token refresh failed: {response.status_code} {response.text}")

    tokens = response.json()
    new_access_token = tokens["access_token"]
    new_refresh_token = tokens["refresh_token"]

    # Update XERO_CONFIG with new tokens
    updated_config = dict(XERO_CONFIG)
    updated_config["access_token"] = new_access_token
    updated_config["refresh_token"] = new_refresh_token

    # Save new tokens back to GitHub Secrets
    _update_github_secret("XERO_CONFIG", json.dumps(updated_config))

    return new_access_token


def _update_github_secret(secret_name, secret_value):
    """Encrypt and update a GitHub Actions secret."""
    repo = GH_REPO
    headers = {
        "Authorization": f"token {GH_PAT}",
        "Accept": "application/vnd.github+json",
    }

    # Get the repo's public key for encryption
    key_response = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers,
    )
    key_response.raise_for_status()
    key_data = key_response.json()
    public_key_id = key_data["key_id"]
    public_key_bytes = base64.b64decode(key_data["key"])

    # Encrypt the secret value
    public_key_obj = PublicKey(public_key_bytes)
    sealed_box = SealedBox(public_key_obj)
    encrypted = sealed_box.encrypt(secret_value.encode())
    encrypted_b64 = base64.b64encode(encrypted).decode()

    # Update the secret
    update_response = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted_b64, "key_id": public_key_id},
    )
    update_response.raise_for_status()


# ── Xero API Helpers ─────────────────────────────────────────────────────────

def xero_get(access_token, tenant_id, endpoint, params=None):
    """Make a paginated GET request to the Xero API, returning all records."""
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
            # Rate limited — wait and retry
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue

        if response.status_code != 200:
            raise Exception(f"Xero API error [{endpoint}]: {response.status_code} {response.text[:500]}")

        data = response.json()

        # Detect the key that holds the records (e.g. "Invoices", "Journals", etc.)
        record_key = None
        for key in data:
            if isinstance(data[key], list):
                record_key = key
                break

        if not record_key:
            break

        page_records = data[record_key]
        all_records.extend(page_records)

        # If we got a full page of 100, there may be more
        if len(page_records) < 100:
            break

        page += 1
        time.sleep(0.5)  # Be kind to the API

    return all_records


def serial_to_date(serial):
    """Convert an Excel/Xero date serial number to ISO date string."""
    if serial is None:
        return None
    try:
        # Xero returns dates as /Date(timestamp)/ milliseconds
        if isinstance(serial, str) and serial.startswith("/Date("):
            ms = int(serial[6:-2].split("+")[0].split("-")[0])
            return datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")
        return str(serial)
    except Exception:
        return str(serial)


def extract_account_code(account_ref):
    """Safely extract account code from a Xero account reference dict."""
    if not account_ref:
        return None
    return account_ref.get("Code") or account_ref.get("AccountCode")


# ── Invoice Detail Fetch ──────────────────────────────────────────────────────

def fetch_invoices(access_token, tenant_name, tenant_id):
    """
    Fetch all sales invoices and credit notes for a tenant from HISTORY_FROM.
    Returns a list of flat dicts, one per line item.
    """
    print(f"  Fetching invoices for {tenant_name}...")

    params = {
        "where": f'Type=="ACCREC" AND Date>=DateTime.Parse("{HISTORY_FROM}")',
        "unitdp": 4,
    }

    invoices = xero_get(access_token, tenant_id, "Invoices", params)
    print(f"    {len(invoices)} invoices retrieved")

    rows = []
    for inv in invoices:
        inv_number = inv.get("InvoiceNumber", "")
        inv_type = inv.get("Type", "")
        inv_status = inv.get("Status", "")
        contact_name = inv.get("Contact", {}).get("Name", "")
        inv_date = serial_to_date(inv.get("DateString") or inv.get("Date"))
        paid_date = serial_to_date(inv.get("FullyPaidOnDate"))
        function_code = inv.get("Reference", "")

        # Try to get tracking categories for Function/Sub-function
        tracking = inv.get("TrackingCategories", []) or []
        function_val = ""
        subfunction_val = ""
        for t in tracking:
            name = t.get("Name", "")
            option = t.get("Option", "")
            if "function" in name.lower() and "sub" not in name.lower():
                function_val = option
            elif "sub" in name.lower():
                subfunction_val = option

        for line in inv.get("LineItems", []):
            account_code = extract_account_code(line.get("AccountCode") or {"Code": line.get("AccountCode")})
            # LineItems may have AccountCode directly as string
            if isinstance(line.get("AccountCode"), str):
                account_code = line["AccountCode"]

            account_name = ""
            account_str = line.get("AccountCode", "")
            # Map known codes to names
            code_map = {
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
            account_name = code_map.get(str(account_str), account_str)

            net = line.get("LineAmount", 0) or 0
            tax = line.get("TaxAmount", 0) or 0
            gross = net + tax
            qty = line.get("Quantity", 0) or 0
            unit_price = line.get("UnitAmount", 0) or 0
            discount = line.get("DiscountRate", 0) or 0
            description = line.get("Description", "")
            item_code = line.get("ItemCode", "")
            tax_type = line.get("TaxType", "")

            # Derive month as first day of the invoice month
            try:
                d = datetime.strptime(inv_date, "%Y-%m-%d")
                month = date(d.year, d.month, 1).isoformat()
            except Exception:
                month = inv_date

            rows.append({
                "entity": tenant_name,
                "invoice_number": inv_number,
                "type": "CR" if inv_type == "ACCRECRECCREDIT" or "CREDIT" in inv_type else "INV",
                "contact": contact_name,
                "date": inv_date,
                "paid_date": paid_date,
                "item_code": item_code,
                "account_code": str(account_str),
                "account_name": account_name,
                "description": description,
                "quantity": qty,
                "unit_price": unit_price,
                "discount": discount,
                "net": net,
                "tax": tax,
                "gross": gross,
                "status": inv_status,
                "function": function_val,
                "month": month,
            })

    return rows


# ── Account Transactions Fetch ────────────────────────────────────────────────

def fetch_account_transactions(access_token, tenant_name, tenant_id):
    """
    Fetch account transactions for revenue account codes from HISTORY_FROM.
    Returns a list of flat dicts.
    """
    print(f"  Fetching account transactions for {tenant_name}...")

    all_rows = []

    for code in REVENUE_CODES:
        params = {
            "where": f'Account.Code=="{code}" AND Date>=DateTime.Parse("{HISTORY_FROM}")',
        }

        try:
            journals = xero_get(access_token, tenant_id, "Journals", params)
        except Exception as e:
            print(f"    Warning: could not fetch journals for code {code}: {e}")
            journals = []

        for journal in journals:
            journal_date = serial_to_date(journal.get("JournalDate"))
            source_type = journal.get("SourceType", "")
            source_id = journal.get("SourceID", "")
            reference = journal.get("Reference", "")
            narration = journal.get("Narration", "")

            try:
                d = datetime.strptime(journal_date, "%Y-%m-%d")
                month = date(d.year, d.month, 1).isoformat()
            except Exception:
                month = journal_date

            for line in journal.get("JournalLines", []):
                line_account_code = line.get("AccountCode", "")
                if str(line_account_code) not in REVENUE_CODES:
                    continue

                net_amount = line.get("NetAmount", 0) or 0
                gross_amount = line.get("GrossAmount", 0) or 0
                tax_amount = line.get("TaxAmount", 0) or 0

                code_map = {
                    "401": "Recurring Revenue",
                    "402": "License Revenue",
                    "403": "Retained Revenue",
                    "409": "Overages",
                    "410": "Ad hoc Revenue",
                    "411": "Services Revenue",
                    "430": "Audience Recharges",
                }

                all_rows.append({
                    "entity": tenant_name,
                    "date": journal_date,
                    "month": month,
                    "account_code": str(line_account_code),
                    "account_name": code_map.get(str(line_account_code), str(line_account_code)),
                    "source_type": source_type,
                    "description": narration or reference,
                    "reference": reference,
                    "net": net_amount,
                    "gross": gross_amount,
                    "tax": tax_amount,
                    "contact": line.get("TaxName", ""),  # Best available field
                })

    print(f"    {len(all_rows)} transaction lines retrieved for {tenant_name}")
    return all_rows


# ── Slack Notification ────────────────────────────────────────────────────────

def post_slack(blocks):
    requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"channel": SLACK_CHANNEL_ID, "blocks": blocks},
    )


def build_slack_success(ehl_inv_count, ehrl_inv_count, ehl_tx_count, ehrl_tx_count, run_time):
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Finance Dashboard — Data Refresh Complete*\n{run_time}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Invoices pulled*\n"
                    f"• EHL: {ehl_inv_count:,} line items\n"
                    f"• EHRL: {ehrl_inv_count:,} line items\n\n"
                    f"*Account transactions pulled*\n"
                    f"• EHL: {ehl_tx_count:,} lines\n"
                    f"• EHRL: {ehrl_tx_count:,} lines"
                ),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Data files updated in repo. Dashboard will reflect latest Xero data on next page load.",
            },
        },
    ]


def build_slack_error(error_msg, run_time):
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Finance Dashboard — Data Refresh Failed*\n{run_time}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Error:*\n```{error_msg[:500]}```",
            },
        },
    ]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    run_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    print(f"Finance Dashboard data refresh — {run_time}")

    try:
        # Refresh Xero token
        print("Refreshing Xero token...")
        access_token = refresh_xero_token()
        print("Token refreshed.")

        # Fetch invoice detail for both entities
        print("\nFetching invoice data...")
        ehl_invoices = fetch_invoices(access_token, "EHL", TENANTS["EHL"])
        ehrl_invoices = fetch_invoices(access_token, "EHRL", TENANTS["EHRL"])

        # Fetch account transactions for both entities
        print("\nFetching account transactions...")
        ehl_transactions = fetch_account_transactions(access_token, "EHL", TENANTS["EHL"])
        ehrl_transactions = fetch_account_transactions(access_token, "EHRL", TENANTS["EHRL"])

        # Write data files
        os.makedirs("data", exist_ok=True)

        with open("data/ehl_invoices.json", "w") as f:
            json.dump(ehl_invoices, f, indent=2)

        with open("data/ehrl_invoices.json", "w") as f:
            json.dump(ehrl_invoices, f, indent=2)

        with open("data/ehl_transactions.json", "w") as f:
            json.dump(ehl_transactions, f, indent=2)

        with open("data/ehrl_transactions.json", "w") as f:
            json.dump(ehrl_transactions, f, indent=2)

        # Write metadata file so the app knows when data was last refreshed
        metadata = {
            "last_refreshed": run_time,
            "ehl_invoice_lines": len(ehl_invoices),
            "ehrl_invoice_lines": len(ehrl_invoices),
            "ehl_transaction_lines": len(ehl_transactions),
            "ehrl_transaction_lines": len(ehrl_transactions),
            "from_date": HISTORY_FROM,
        }
        with open("data/metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"\nData files written successfully.")
        print(f"  EHL invoices: {len(ehl_invoices)} lines")
        print(f"  EHRL invoices: {len(ehrl_invoices)} lines")
        print(f"  EHL transactions: {len(ehl_transactions)} lines")
        print(f"  EHRL transactions: {len(ehrl_transactions)} lines")

        post_slack(build_slack_success(
            len(ehl_invoices),
            len(ehrl_invoices),
            len(ehl_transactions),
            len(ehrl_transactions),
            run_time,
        ))

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"ERROR: {error_detail}")
        post_slack(build_slack_error(str(e), run_time))
        raise


if __name__ == "__main__":
    main()
