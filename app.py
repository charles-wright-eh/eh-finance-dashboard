"""
Element Human — Finance Dashboard
Streamlit app that reads pre-fetched Xero data from /data/ and renders
an interactive finance dashboard.
"""

import json
import os
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Element Human — Finance",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 16px 20px;
        border-left: 4px solid #1a1a2e;
    }
    .metric-label {
        font-size: 12px;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a2e;
    }
    .metric-delta {
        font-size: 13px;
        margin-top: 4px;
    }
    .positive { color: #28a745; }
    .negative { color: #dc3545; }
    .section-header {
        font-size: 18px;
        font-weight: 600;
        color: #1a1a2e;
        margin: 24px 0 12px 0;
        padding-bottom: 8px;
        border-bottom: 1px solid #e9ecef;
    }
    [data-testid="stSidebar"] {
        background: #1a1a2e;
    }
    [data-testid="stSidebar"] * {
        color: #fff !important;
    }
    [data-testid="stSidebar"] input {
        color: #1a1a2e !important;
        background: #fff !important;
    }
    [data-testid="stSidebar"] [data-baseweb="input"] input,
    [data-testid="stSidebar"] [data-baseweb="datepicker"] input {
        color: #1a1a2e !important;
        background: #fff !important;
    }
</style>
""", unsafe_allow_html=True)


# ── Data loading ──────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"

CLIENT_CODES = {
    "AMA001": "Amazon",
    "AMA002": "Amazon",
    "BBC001": "BBC",
    "BBC002": "BBC",
    "BBC005": "BBC",
    "BDB001": "Billion Dollar Boy",
    "BEN001": "BenLabs",
    "BER001": "Bera",
    "C4001": "C4",
    "CAP002": "Captiv8",
    "COL001": "Collectively",
    "CRE001": "Creo",
    "DAI001": "Daivid",
    "DEN001": "Dentsu",
    "DMG001": "MailOnline",
    "FRE001": "Fresh Tape",
    "GAG001": "Gaggl",
    "HEL001": "Hello Fresh",
    "HIN001": "Hinge",
    "INF001": "Influencer",
    "MAI001": "Mail Media",
    "NEB001": "Nebula",
    "NET000": "Netflix",
    "NET001": "Netflix US",
    "NET002": "Netflix ES",
    "NET003": "Netflix IT",
    "NET004": "Netflix UK",
    "NET005": "Netflix AU",
    "NET006": "Netflix FR",
    "NET007": "Netflix DE",
    "NET008": "Netflix KR",
    "NOT001": "Notion",
    "OGI002": "Ogilvy",
    "OUT001": "Outbrain",
    "TEA002": "Teads HCo",
    "TEA004": "Teads",
    "UNI001": "Unilever",
    "WHA001": "Whalar",
}

CATEGORIES = {
    "Amazon": "CTV",
    "BBC": "Media",
    "Billion Dollar Boy": "Agency",
    "BDB": "Agency",
    "BenLabs": "Agency",
    "Bera": "Agency",
    "C4": "Media",
    "Captiv8": "Agency",
    "Collectively": "Agency",
    "Creo": "Agency",
    "Daivid": "Agency",
    "Dentsu": "Media",
    "MailOnline": "Media",
    "MMM": "Agency",
    "Fresh Tape": "Agency",
    "Gaggl": "Brand",
    "Hello Fresh": "Brand",
    "Hinge": "Brand",
    "Influencer": "Agency",
    "Mail Media": "Media",
    "Nebula": "Agency",
    "Netflix": "CTV",
    "Netflix US": "CTV",
    "Netflix ES": "CTV",
    "Netflix IT": "CTV",
    "Netflix UK": "CTV",
    "Netflix AU": "CTV",
    "Netflix FR": "CTV",
    "Netflix DE": "CTV",
    "Netflix KR": "CTV",
    "Notion": "Agency",
    "Ogilvy": "Agency",
    "Outbrain": "Agency",
    "Teads HCo": "Agency",
    "Teads": "Agency",
    "Unilever": "Brand",
    "Whalar": "Agency",
}

CONTACT_MAP = {
    # Netflix — map specific legal entities to their short names
    "Netflix Services UK": "Netflix UK",
    "Netflix Services Italy": "Netflix IT",
    "Netflix Services Spain": "Netflix ES",
    "Netflix Servicios": "Netflix ES",
    "Netflix Australia": "Netflix AU",
    "Netflix Services France": "Netflix FR",
    "Netflix Services Germany": "Netflix DE",
    "Netflix Services Korea": "Netflix KR",
    "Netflix, Inc.": "Netflix US",
    "Netflix Inc": "Netflix US",
    "Netflix Entertainment": "Netflix UK",
    # Amazon
    "Amazon Advertising": "Amazon",
    "Amazon.com": "Amazon",
    "Amazon": "Amazon",
    # BBC
    "BBC Global News": "BBC",
    "BBC Studios Americas": "BBC",
    "BBC Studios Singapore": "BBC",
    "BBC Studios": "BBC",
    "BBC": "BBC",
    # Others
    "BEN Group": "BenLabs",
    "Harris Poll": "Bera",
    "DMG Media": "MMM",
    "Billion Dollar Boy": "BDB",
    "Fresh Tape": "Fresh Tape",
    "Whalar": "Whalar",
    "Teads Holding": "Teads HCo",
    "Teads": "Teads",
    "Captiv8": "Captiv8",
    "Influencer": "Influencer",
    "Notion": "Notion",
    "Gaggl": "Gaggl",
    "Ogilvy": "Ogilvy",
    "Outbrain": "Outbrain",
    "Daivid": "Daivid",
    "Dentsu": "Dentsu",
    "Creo": "Creo",
    "Collectively": "Collectively",
    "Nebula": "Nebula",
    "Hinge": "Hinge",
    "Hello Fresh": "Hello Fresh",
    "HelloFresh": "Hello Fresh",
    "Unilever": "Unilever",
    "Mail Media": "Mail Media",
    "Channel 4": "C4",
    "C4 ": "C4",
}

REVENUE_ACCOUNT_NAMES = {
    "401": "Recurring",
    "402": "License",
    "403": "Retained",
    "409": "Overages",
    "410": "Ad hoc",
    "411": "Services",
    "430": "Audience Recharges",
}


@st.cache_data(ttl=300)
def load_data():
    """Load all data files. Returns empty DataFrames if files don't exist yet."""

    def load_json(filename):
        path = DATA_DIR / filename
        if not path.exists():
            return []
        with open(path) as f:
            return json.load(f)

    ehl_inv = load_json("ehl_invoices.json")
    ehrl_inv = load_json("ehrl_invoices.json")
    ehl_tx = load_json("ehl_transactions.json")
    ehrl_tx = load_json("ehrl_transactions.json")

    meta_path = DATA_DIR / "metadata.json"
    metadata = {}
    if meta_path.exists():
        with open(meta_path) as f:
            metadata = json.load(f)

    # Combine invoices
    all_invoices = ehl_inv + ehrl_inv
    df_inv = pd.DataFrame(all_invoices) if all_invoices else pd.DataFrame()

    # Combine transactions
    all_tx = ehl_tx + ehrl_tx
    df_tx = pd.DataFrame(all_tx) if all_tx else pd.DataFrame()

    if not df_inv.empty:
        df_inv["date"] = pd.to_datetime(df_inv["date"], errors="coerce")
        df_inv["paid_date"] = pd.to_datetime(df_inv["paid_date"], errors="coerce")
        df_inv["month"] = pd.to_datetime(df_inv["month"], errors="coerce")
        df_inv["net"] = pd.to_numeric(df_inv["net"], errors="coerce").fillna(0)
        df_inv["gross"] = pd.to_numeric(df_inv["gross"], errors="coerce").fillna(0)
        def resolve_client(row):
            if row["function"] in CLIENT_CODES:
                return CLIENT_CODES[row["function"]]
            contact = row["contact"] or ""
            for substring, name in CONTACT_MAP.items():
                if substring.lower() in contact.lower():
                    return name
            return contact.split(" ")[0] if contact else "Unknown"

        df_inv["client_short"] = df_inv.apply(resolve_client, axis=1)
        df_inv["category"] = df_inv["client_short"].map(CATEGORIES).fillna("Other")
        df_inv["revenue_type"] = df_inv["account_code"].map(REVENUE_ACCOUNT_NAMES).fillna("Other")
        # Revenue only — exclude inter-co and non-revenue codes
        df_inv["is_revenue"] = df_inv["account_code"].isin(REVENUE_ACCOUNT_NAMES.keys())

    if not df_tx.empty:
        df_tx["date"] = pd.to_datetime(df_tx["date"], errors="coerce")
        df_tx["month"] = pd.to_datetime(df_tx["month"], errors="coerce")
        df_tx["net"] = pd.to_numeric(df_tx["net"], errors="coerce").fillna(0)
        df_tx["revenue_type"] = df_tx["account_code"].map(REVENUE_ACCOUNT_NAMES).fillna("Other")

    return df_inv, df_tx, metadata


def fmt_gbp(value, decimals=0):
    """Format a number as GBP."""
    if value >= 1_000_000:
        return f"£{value/1_000_000:.1f}m"
    if value >= 1_000:
        return f"£{value/1_000:.{decimals}f}k"
    return f"£{value:,.{decimals}f}"


def fmt_pct(value):
    """Format a decimal as percentage."""
    return f"{value*100:+.1f}%" if value != 0 else "—"


# ── Load data ─────────────────────────────────────────────────────────────────

df_inv, df_tx, metadata = load_data()

data_exists = not df_inv.empty

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📊 Finance Dashboard")
    st.markdown("---")

    page = st.radio(
        "View",
        ["Summary", "Monthly Revenue", "Invoice Detail", "Account Transactions"],
        label_visibility="collapsed",
    )

    st.markdown("---")

    if data_exists:
        # Date range filter
        min_date = df_inv["date"].min()
        max_date = df_inv["date"].max()

        st.markdown("**Date range**")
        from_date = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date)
        to_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)

        st.markdown("**Entity**")
        entity_filter = st.multiselect(
            "Entity",
            options=["EHL", "EHRL"],
            default=["EHL", "EHRL"],
            label_visibility="collapsed",
        )

    st.markdown("---")

    if metadata:
        refreshed = metadata.get("last_refreshed", "Unknown")
        st.markdown(f"**Last refreshed**\n\n{refreshed}")
    else:
        st.markdown("*No data loaded yet.*\n\nRun the GitHub Actions workflow to populate data.")


# ── No data state ─────────────────────────────────────────────────────────────

if not data_exists:
    st.title("Element Human — Finance Dashboard")
    st.info(
        "**No data loaded yet.** \n\n"
        "Run the data refresh workflow in GitHub Actions to populate this dashboard. "
        "Once the workflow completes, the data files will be committed to the repo and "
        "this dashboard will load automatically on next refresh."
    )
    st.stop()


# ── Filter data ───────────────────────────────────────────────────────────────

from_dt = pd.Timestamp(from_date)
to_dt = pd.Timestamp(to_date)

df_filtered = df_inv[
    (df_inv["date"] >= from_dt)
    & (df_inv["date"] <= to_dt)
    & (df_inv["entity"].isin(entity_filter))
].copy()

df_rev = df_filtered[df_filtered["is_revenue"]].copy()

df_tx_filtered = df_tx[
    (df_tx["date"] >= from_dt)
    & (df_tx["date"] <= to_dt)
    & (df_tx["entity"].isin(entity_filter))
].copy() if not df_tx.empty else pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

if page == "Summary":
    st.title("Summary")

    # ── Top KPI cards ──────────────────────────────────────────────────────────

    # Split into invoiced (gross billed) vs recognised (account transactions)
    total_invoiced = df_rev["net"].sum()

    ehl_invoiced = df_rev[df_rev["entity"] == "EHL"]["net"].sum()
    ehrl_invoiced = df_rev[df_rev["entity"] == "EHRL"]["net"].sum()

    # Recognised revenue from account transactions
    total_recognised = df_tx_filtered["net"].sum() if not df_tx_filtered.empty else 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Invoiced (net)", fmt_gbp(total_invoiced))
    with col2:
        st.metric("EHL Invoiced", fmt_gbp(ehl_invoiced))
    with col3:
        st.metric("EHRL Invoiced", fmt_gbp(ehrl_invoiced))
    with col4:
        st.metric("Recognised Revenue", fmt_gbp(total_recognised))

    st.markdown("---")

    # ── Revenue by entity ──────────────────────────────────────────────────────

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<div class="section-header">Invoiced Revenue by Entity</div>', unsafe_allow_html=True)
        entity_summary = df_rev.groupby("entity")["net"].sum().reset_index()
        entity_summary.columns = ["Entity", "Net Revenue"]
        fig_entity = px.pie(
            entity_summary,
            values="Net Revenue",
            names="Entity",
            color_discrete_sequence=["#1a1a2e", "#e94560"],
            hole=0.4,
        )
        fig_entity.update_traces(textinfo="label+percent+value",
                                  texttemplate="%{label}<br>£%{value:,.0f}<br>(%{percent})")
        fig_entity.update_layout(showlegend=False, margin=dict(t=20, b=20))
        st.plotly_chart(fig_entity, use_container_width=True)

    with col_right:
        st.markdown('<div class="section-header">Invoiced Revenue by Type</div>', unsafe_allow_html=True)
        type_summary = df_rev.groupby("revenue_type")["net"].sum().reset_index()
        type_summary = type_summary.sort_values("net", ascending=False)
        type_summary.columns = ["Revenue Type", "Net Revenue"]
        fig_type = px.bar(
            type_summary,
            x="Revenue Type",
            y="Net Revenue",
            color_discrete_sequence=["#1a1a2e"],
            text_auto=".3s",
        )
        fig_type.update_layout(xaxis_title="", yaxis_title="£", margin=dict(t=20, b=20))
        st.plotly_chart(fig_type, use_container_width=True)

    st.markdown("---")

    # ── Client summary table ───────────────────────────────────────────────────

    st.markdown('<div class="section-header">Revenue by Client</div>', unsafe_allow_html=True)

    client_summary = (
        df_rev.groupby(["client_short", "category", "entity"])["net"]
        .sum()
        .reset_index()
    )

    # Pivot to show EHL / EHRL side by side
    client_pivot = client_summary.pivot_table(
        index=["client_short", "category"],
        columns="entity",
        values="net",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    client_pivot.columns.name = None

    # Ensure both entity columns exist
    for col in ["EHL", "EHRL"]:
        if col not in client_pivot.columns:
            client_pivot[col] = 0

    client_pivot["Total"] = client_pivot.get("EHL", 0) + client_pivot.get("EHRL", 0)
    client_pivot = client_pivot.sort_values("Total", ascending=False)

    # Format for display
    display_cols = ["client_short", "category", "EHL", "EHRL", "Total"]
    display_df = client_pivot[display_cols].copy()
    display_df.columns = ["Client", "Category", "EHL (£)", "EHRL (£)", "Total (£)"]

    for col in ["EHL (£)", "EHRL (£)", "Total (£)"]:
        display_df[col] = display_df[col].apply(lambda x: f"£{x:,.0f}")

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ── Revenue by category ────────────────────────────────────────────────────

    st.markdown('<div class="section-header">Revenue by Category</div>', unsafe_allow_html=True)

    cat_summary = df_rev.groupby("category")["net"].sum().reset_index()
    cat_summary = cat_summary.sort_values("net", ascending=True)

    fig_cat = px.bar(
        cat_summary,
        x="net",
        y="category",
        orientation="h",
        color_discrete_sequence=["#e94560"],
        text_auto=".3s",
    )
    fig_cat.update_layout(xaxis_title="£", yaxis_title="", margin=dict(t=20, b=20))
    st.plotly_chart(fig_cat, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MONTHLY REVENUE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Monthly Revenue":
    st.title("Monthly Revenue")

    if df_rev.empty:
        st.warning("No revenue data available for the selected filters.")
        st.stop()

    # ── Monthly total chart ────────────────────────────────────────────────────

    monthly_total = (
        df_rev.groupby(df_rev["month"].dt.to_period("M"))["net"]
        .sum()
        .reset_index()
    )
    monthly_total["month"] = monthly_total["month"].dt.to_timestamp()
    monthly_total = monthly_total.sort_values("month")

    fig_monthly = px.bar(
        monthly_total,
        x="month",
        y="net",
        color_discrete_sequence=["#1a1a2e"],
        labels={"net": "£", "month": "Month"},
        text_auto=".3s",
    )
    fig_monthly.update_layout(
        title="Monthly Invoiced Revenue (net)",
        xaxis_title="",
        yaxis_title="£",
        margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig_monthly, use_container_width=True)

    st.markdown("---")

    # ── Rolling metrics ────────────────────────────────────────────────────────

    latest_month = monthly_total["month"].max()
    months_data = monthly_total.set_index("month")["net"]

    def rolling_sum(months_back):
        cutoff = latest_month - pd.DateOffset(months=months_back)
        return months_data[months_data.index > cutoff].sum()

    ttm = rolling_sum(12)
    t6m = rolling_sum(6)
    t3m = rolling_sum(3)

    # Prior period comparisons
    def prior_rolling_sum(months_back):
        end = latest_month - pd.DateOffset(months=months_back)
        start = end - pd.DateOffset(months=months_back)
        return months_data[(months_data.index > start) & (months_data.index <= end)].sum()

    prior_ttm = prior_rolling_sum(12)
    prior_t6m = prior_rolling_sum(6)
    prior_t3m = prior_rolling_sum(3)

    col1, col2, col3 = st.columns(3)

    with col1:
        delta_ttm = (ttm - prior_ttm) / prior_ttm if prior_ttm else 0
        st.metric("TTM Revenue", fmt_gbp(ttm), delta=fmt_pct(delta_ttm))

    with col2:
        delta_t6m = (t6m - prior_t6m) / prior_t6m if prior_t6m else 0
        st.metric("T6M Revenue", fmt_gbp(t6m), delta=fmt_pct(delta_t6m))

    with col3:
        delta_t3m = (t3m - prior_t3m) / prior_t3m if prior_t3m else 0
        st.metric("T3M Revenue", fmt_gbp(t3m), delta=fmt_pct(delta_t3m))

    st.markdown("---")

    # ── Monthly by client heatmap ──────────────────────────────────────────────

    st.markdown('<div class="section-header">Monthly Revenue by Client</div>', unsafe_allow_html=True)

    monthly_client = (
        df_rev.groupby([df_rev["month"].dt.to_period("M"), "client_short"])["net"]
        .sum()
        .reset_index()
    )
    monthly_client["month"] = monthly_client["month"].dt.to_timestamp()

    pivot = monthly_client.pivot_table(
        index="client_short",
        columns="month",
        values="net",
        aggfunc="sum",
        fill_value=0,
    )

    # Sort by total descending, show top 20
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("Total", ascending=False).drop(columns="Total").head(20)

    # Format columns as MMM YY
    pivot.columns = [pd.Timestamp(c).strftime("%b %y") for c in pivot.columns]

    # Add totals row
    totals = pivot.sum(axis=0)
    pivot.loc["TOTAL"] = totals

    # Format values
    display_pivot = pivot.map(lambda x: f"£{x:,.0f}" if x != 0 else "—")
    st.dataframe(display_pivot, use_container_width=True)

    st.markdown("---")

    # ── Revenue by type over time ──────────────────────────────────────────────

    st.markdown('<div class="section-header">Revenue by Type Over Time</div>', unsafe_allow_html=True)

    monthly_type = (
        df_rev.groupby([df_rev["month"].dt.to_period("M"), "revenue_type"])["net"]
        .sum()
        .reset_index()
    )
    monthly_type["month"] = monthly_type["month"].dt.to_timestamp()
    monthly_type = monthly_type.sort_values("month")

    fig_type = px.bar(
        monthly_type,
        x="month",
        y="net",
        color="revenue_type",
        labels={"net": "£", "month": "Month", "revenue_type": "Type"},
        barmode="stack",
    )
    fig_type.update_layout(xaxis_title="", yaxis_title="£", margin=dict(t=20, b=20))
    st.plotly_chart(fig_type, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: INVOICE DETAIL
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Invoice Detail":
    st.title("Invoice Detail")

    if df_filtered.empty:
        st.warning("No invoice data available for the selected filters.")
        st.stop()

    # ── Filters ────────────────────────────────────────────────────────────────

    col1, col2, col3 = st.columns(3)

    with col1:
        status_options = sorted(df_filtered["status"].dropna().unique())
        selected_status = st.multiselect("Status", status_options, default=status_options)

    with col2:
        account_options = sorted(df_filtered["account_code"].dropna().unique())
        selected_accounts = st.multiselect(
            "Account code",
            account_options,
            default=[c for c in account_options if c in REVENUE_ACCOUNT_NAMES],
        )

    with col3:
        client_options = sorted(df_filtered["contact"].dropna().unique())
        selected_clients = st.multiselect("Client", client_options, default=[])

    # Apply filters
    mask = df_filtered["status"].isin(selected_status)
    if selected_accounts:
        mask &= df_filtered["account_code"].isin(selected_accounts)
    if selected_clients:
        mask &= df_filtered["contact"].isin(selected_clients)

    df_display = df_filtered[mask].copy()

    # ── Summary metrics ────────────────────────────────────────────────────────

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Invoices", f"{df_display['invoice_number'].nunique():,}")
    with col2:
        st.metric("Total Net", fmt_gbp(df_display["net"].sum()))
    with col3:
        st.metric("Total Tax", fmt_gbp(df_display["tax"].sum()))
    with col4:
        st.metric("Total Gross", fmt_gbp(df_display["gross"].sum()))

    st.markdown("---")

    # ── Table ──────────────────────────────────────────────────────────────────

    display_cols = [
        "entity", "invoice_number", "type", "contact", "date", "paid_date",
        "account_code", "account_name", "description",
        "quantity", "unit_price", "net", "tax", "gross", "status",
    ]

    # Format for display
    df_table = df_display[display_cols].copy()
    df_table["date"] = df_table["date"].dt.strftime("%d %b %Y")
    df_table["paid_date"] = df_table["paid_date"].dt.strftime("%d %b %Y").fillna("—")
    df_table["net"] = df_table["net"].apply(lambda x: f"£{x:,.2f}")
    df_table["tax"] = df_table["tax"].apply(lambda x: f"£{x:,.2f}")
    df_table["gross"] = df_table["gross"].apply(lambda x: f"£{x:,.2f}")
    df_table["unit_price"] = df_table["unit_price"].apply(lambda x: f"£{x:,.2f}")

    df_table.columns = [
        "Entity", "Invoice", "Type", "Contact", "Date", "Paid Date",
        "Code", "Account", "Description",
        "Qty", "Unit Price", "Net", "Tax", "Gross", "Status",
    ]

    st.dataframe(df_table, use_container_width=True, hide_index=True, height=500)

    # ── Download ───────────────────────────────────────────────────────────────

    csv = df_display[display_cols].to_csv(index=False)
    st.download_button(
        "Download as CSV",
        data=csv,
        file_name=f"eh_invoice_detail_{date.today().isoformat()}.csv",
        mime="text/csv",
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ACCOUNT TRANSACTIONS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Account Transactions":
    st.title("Account Transactions")

    if df_tx_filtered.empty:
        st.warning("No account transaction data available for the selected filters.")
        st.stop()

    # ── Filters ────────────────────────────────────────────────────────────────

    col1, col2 = st.columns(2)

    with col1:
        code_options = sorted(df_tx_filtered["account_code"].dropna().unique())
        selected_codes = st.multiselect("Account code", code_options, default=code_options)

    with col2:
        source_options = sorted(df_tx_filtered["source_type"].dropna().unique())
        selected_sources = st.multiselect("Source type", source_options, default=source_options)

    mask = (
        df_tx_filtered["account_code"].isin(selected_codes)
        & df_tx_filtered["source_type"].isin(selected_sources)
    )
    df_tx_display = df_tx_filtered[mask].copy()

    # ── Summary metrics ────────────────────────────────────────────────────────

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Transactions", f"{len(df_tx_display):,}")
    with col2:
        st.metric("Total Net", fmt_gbp(df_tx_display["net"].sum()))
    with col3:
        st.metric("Total Gross", fmt_gbp(df_tx_display["gross"].sum()))

    st.markdown("---")

    # ── By account chart ───────────────────────────────────────────────────────

    tx_by_code = (
        df_tx_display.groupby(["account_code", "revenue_type"])["net"]
        .sum()
        .reset_index()
        .sort_values("net", ascending=False)
    )

    fig_tx = px.bar(
        tx_by_code,
        x="revenue_type",
        y="net",
        color="account_code",
        labels={"net": "£", "revenue_type": "Account", "account_code": "Code"},
        barmode="group",
        text_auto=".3s",
    )
    fig_tx.update_layout(xaxis_title="", yaxis_title="£", margin=dict(t=20, b=20))
    st.plotly_chart(fig_tx, use_container_width=True)

    st.markdown("---")

    # ── Table ──────────────────────────────────────────────────────────────────

    display_cols = [
        "entity", "date", "month", "account_code", "account_name",
        "source_type", "description", "reference", "net", "gross", "tax",
    ]

    df_tx_table = df_tx_display[display_cols].copy()
    df_tx_table["date"] = df_tx_table["date"].dt.strftime("%d %b %Y")
    df_tx_table["month"] = df_tx_table["month"].dt.strftime("%b %Y")
    df_tx_table["net"] = df_tx_table["net"].apply(lambda x: f"£{x:,.2f}")
    df_tx_table["gross"] = df_tx_table["gross"].apply(lambda x: f"£{x:,.2f}")
    df_tx_table["tax"] = df_tx_table["tax"].apply(lambda x: f"£{x:,.2f}")

    df_tx_table.columns = [
        "Entity", "Date", "Month", "Code", "Account",
        "Source", "Description", "Reference", "Net", "Gross", "Tax",
    ]

    st.dataframe(df_tx_table, use_container_width=True, hide_index=True, height=500)

    # Download
    csv = df_tx_display[display_cols].to_csv(index=False)
    st.download_button(
        "Download as CSV",
        data=csv,
        file_name=f"eh_account_transactions_{date.today().isoformat()}.csv",
        mime="text/csv",
    )
