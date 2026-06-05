"""
Element Human — Finance Dashboard
Reads pre-fetched data from /data/ and renders an interactive finance dashboard.
"""

import calendar as _cal
import json
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Element Human Finance",
    page_icon="💚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Brand styling ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

    html, body, [class*="css"], [data-testid], div, span, p, label, h1, h2, h3,
    input, select, textarea, button {
        font-family: 'Poppins', sans-serif !important;
    }

    h1 { color: #13202F !important; font-weight: 700 !important; }
    h2 { color: #13202F !important; font-weight: 600 !important; }

    .section-header {
        font-size: 14px;
        font-weight: 600;
        color: #13202F;
        margin: 24px 0 12px 0;
        padding: 8px 14px;
        border-left: 4px solid #10A8B7;
        background: #f4f7f9;
        border-radius: 0 6px 6px 0;
        letter-spacing: 0.3px;
        text-transform: uppercase;
    }

    [data-testid="stSidebar"] {
        background: #13202F !important;
    }
    [data-testid="stSidebar"] * {
        color: #fff !important;
    }
    [data-testid="stSidebar"] input {
        color: #13202F !important;
        background: #fff !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] div,
    [data-testid="stSidebar"] [data-baseweb="select"] span {
        color: #13202F !important;
    }

    [data-testid="metric-container"] {
        background: #f4f7f9;
        border-radius: 8px;
        padding: 12px 16px !important;
        border-top: 3px solid #10A8B7;
    }

    [data-testid="stDataFrame"] {
        border-radius: 8px;
        overflow: hidden;
    }

    div[data-testid="stHorizontalBlock"] > div {
        gap: 12px;
    }
</style>
""", unsafe_allow_html=True)


# ── Brand colours ──────────────────────────────────────────────────────────────

EH_TEAL    = "#10A8B7"
EH_GREEN   = "#54E42B"
EH_PINK    = "#FF2198"
EH_YELLOW  = "#F9BE00"
EH_BLUE    = "#007AFF"
EH_PURPLE  = "#8F21A1"
EH_RED     = "#F60000"
EH_NAVY    = "#13202F"
EH_INDIGO  = "#1818CE"

EH_PALETTE = [EH_TEAL, EH_GREEN, EH_PINK, EH_YELLOW, EH_BLUE, EH_PURPLE, EH_RED, EH_NAVY, EH_INDIGO]


# ── Constants ──────────────────────────────────────────────────────────────────

WHALAR_TTM_EXCLUDE_UNTIL = date(2026, 7, 1)

CLIENT_CODES = {
    "AMA001": "Amazon", "AMA002": "Amazon",
    "BBC001": "BBC", "BBC002": "BBC", "BBC005": "BBC",
    "BDB001": "BDB",
    "BEN001": "BenLabs",
    "BER001": "Bera",
    "C4001": "C4",
    "CAP002": "Captiv8",
    "COL001": "Collectively",
    "CRE001": "Creo",
    "DAI001": "Daivid",
    "DEN001": "Dentsu",
    "DMG001": "MMM",
    "FRE001": "Fresh Tape",
    "GAG001": "Gaggl",
    "HEL001": "Hello Fresh",
    "HIN001": "Hinge",
    "INF001": "Influencer",
    "MAI001": "Mail Media",
    "NEB001": "Nebula",
    "NET000": "Netflix",
    "NET001": "Netflix US", "NET002": "Netflix ES", "NET003": "Netflix IT",
    "NET004": "Netflix UK", "NET005": "Netflix AU", "NET006": "Netflix FR",
    "NET007": "Netflix DE", "NET008": "Netflix KR",
    "NOT001": "Notion",
    "OGI002": "Ogilvy",
    "OUT001": "Outbrain",
    "TEA002": "Teads HCo", "TEA004": "Teads",
    "UNI001": "Unilever",
    "WHA001": "Whalar",
}

CATEGORIES = {
    "Amazon": "CTV",
    "BBC": "Media", "MMM": "Media", "Mail Media": "Media",
    "Dentsu": "Media", "C4": "Media",
    "Netflix": "CTV", "Netflix US": "CTV", "Netflix ES": "CTV", "Netflix IT": "CTV",
    "Netflix UK": "CTV", "Netflix AU": "CTV", "Netflix FR": "CTV",
    "Netflix DE": "CTV", "Netflix KR": "CTV",
    "BDB": "Agency", "BenLabs": "Agency", "Bera": "Agency",
    "Captiv8": "Agency", "Collectively": "Agency", "Creo": "Agency",
    "Daivid": "Agency", "Fresh Tape": "Agency", "Influencer": "Agency",
    "Nebula": "Agency", "Notion": "Agency", "Ogilvy": "Agency",
    "Outbrain": "Agency", "Teads HCo": "Agency", "Teads": "Agency",
    "Whalar": "Agency",
    "Gaggl": "Brand", "Hello Fresh": "Brand", "Hinge": "Brand", "Unilever": "Brand",
}

CONTACT_MAP = {
    "Netflix Services UK": "Netflix UK", "Netflix Services Italy": "Netflix IT",
    "Netflix Servicios": "Netflix ES", "Netflix Services Spain": "Netflix ES",
    "Netflix Australia": "Netflix AU", "Netflix Services France": "Netflix FR",
    "Netflix Services Germany": "Netflix DE", "Netflix Services Korea": "Netflix KR",
    "Netflix, Inc.": "Netflix US", "Netflix Inc": "Netflix US",
    "Netflix Entertainment": "Netflix UK", "Netflix": "Netflix",
    "Amazon Advertising": "Amazon", "Amazon.com": "Amazon", "Amazon": "Amazon",
    "BBC Global News": "BBC", "BBC Studios Americas": "BBC",
    "BBC Studios Singapore": "BBC", "BBC Studios": "BBC", "BBC": "BBC",
    "BEN Group": "BenLabs", "Harris Poll": "Bera",
    "DMG Media": "MMM", "Billion Dollar Boy": "BDB", "Fresh Tape": "Fresh Tape",
    "Whalar": "Whalar", "Teads Holding": "Teads HCo", "Teads": "Teads",
    "Captiv8": "Captiv8", "Influencer": "Influencer", "Notion": "Notion",
    "Gaggl": "Gaggl", "Ogilvy": "Ogilvy", "Outbrain": "Outbrain",
    "Daivid": "Daivid", "Dentsu": "Dentsu", "Creo": "Creo",
    "Collectively": "Collectively", "Nebula": "Nebula", "Hinge": "Hinge",
    "Hello Fresh": "Hello Fresh", "HelloFresh": "Hello Fresh",
    "Unilever": "Unilever", "Mail Media": "Mail Media",
    "Channel 4": "C4", "C4 ": "C4",
}

REVENUE_CODES = {"401", "402", "403", "409", "410", "411", "430", "450"}

# Contacts that represent internal EH entities — excluded from Invoices Raised
EH_ENTITY_CONTACTS = {
    "Element Human Group Limited",
    "Element Human Group",
    "Element Human Limited",
    "Element Human Research Limited",
}

REVENUE_CODE_NAMES = {
    "401": "Recurring", "402": "License", "403": "Retained",
    "409": "Overages", "410": "Ad hoc", "411": "Services",
    "430": "Audience Recharges", "450": "Other Revenue",
}

ALL_ENTITIES = ["EHL", "EHRL", "EHGL"]

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_YEARS = list(range(2023, date.today().year + 2))


# ── Data loading ───────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"


@st.cache_data(ttl=300)
def load_data():
    def read(filename):
        p = DATA_DIR / filename
        return json.loads(p.read_text()) if p.exists() else []

    ehl_inv  = read("ehl_invoices.json")
    ehrl_inv = read("ehrl_invoices.json")
    ehgl_inv = read("ehgl_invoices.json")
    ehl_jnl  = read("ehl_journals.json")
    ehrl_jnl = read("ehrl_journals.json")
    ehgl_jnl = read("ehgl_journals.json")
    tb_raw   = read("tb_snapshots.json")

    meta_path = DATA_DIR / "metadata.json"
    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    # Invoices
    all_inv = ehl_inv + ehrl_inv + ehgl_inv
    df_inv = pd.DataFrame(all_inv) if all_inv else pd.DataFrame()
    if not df_inv.empty:
        df_inv["date"]     = pd.to_datetime(df_inv["date"], errors="coerce")
        df_inv["paid_date"]= pd.to_datetime(df_inv["paid_date"], errors="coerce")
        df_inv["month"]    = pd.to_datetime(df_inv["month"], errors="coerce")
        df_inv["net"]      = pd.to_numeric(df_inv["net"], errors="coerce").fillna(0)
        df_inv["gross"]    = pd.to_numeric(df_inv["gross"], errors="coerce").fillna(0)
        df_inv["tax"]      = pd.to_numeric(df_inv["tax"], errors="coerce").fillna(0)
        df_inv["client"]   = df_inv.apply(_resolve_client_invoice, axis=1)
        df_inv["category"] = df_inv["client"].map(CATEGORIES).fillna("Other")
        df_inv["revenue_type"] = df_inv["account_code"].map(REVENUE_CODE_NAMES).fillna("Other")
        df_inv["is_revenue"]   = df_inv["account_code"].isin(REVENUE_CODES)

    # Journals (recognised revenue)
    all_jnl = ehl_jnl + ehrl_jnl + ehgl_jnl
    df_jnl = pd.DataFrame(all_jnl) if all_jnl else pd.DataFrame()
    if not df_jnl.empty:
        df_jnl["date"]  = pd.to_datetime(df_jnl["date"], errors="coerce")
        df_jnl["month"] = pd.to_datetime(df_jnl["month"], errors="coerce")
        df_jnl["net"]   = pd.to_numeric(df_jnl["net"], errors="coerce").fillna(0)
        df_jnl["client"] = df_jnl["function"].map(CLIENT_CODES).fillna(
            df_jnl["contact"].apply(_resolve_client_contact)
        )
        df_jnl["category"]     = df_jnl["client"].map(CATEGORIES).fillna("Other")
        df_jnl["revenue_type"] = df_jnl["account_code"].map(REVENUE_CODE_NAMES).fillna("Other")

    # Trial balance snapshots
    df_tb = pd.DataFrame(tb_raw) if tb_raw else pd.DataFrame()
    if not df_tb.empty:
        df_tb["date"]  = pd.to_datetime(df_tb["date"], errors="coerce")
        df_tb["month"] = pd.to_datetime(df_tb["month"], errors="coerce")
        df_tb["account_250_balance"] = pd.to_numeric(
            df_tb["account_250_balance"], errors="coerce"
        ).fillna(0)
        df_tb["account_115_balance"] = pd.to_numeric(
            df_tb.get("account_115_balance", pd.Series(0, index=df_tb.index)),
            errors="coerce",
        ).fillna(0)

    return df_inv, df_jnl, df_tb, metadata


def _resolve_client_invoice(row):
    if row.get("function") in CLIENT_CODES:
        return CLIENT_CODES[row["function"]]
    return _resolve_client_contact(row.get("contact") or "")


def _resolve_client_contact(contact: str) -> str:
    contact = str(contact or "")
    for substr, name in CONTACT_MAP.items():
        if substr.lower() in contact.lower():
            return name
    return contact.split(" ")[0] if contact else "Unknown"


# ── Helpers ────────────────────────────────────────────────────────────────────

def fmt_gbp(value) -> str:
    if value is None:
        return "—"
    v = abs(value)
    sign = "-" if value < 0 else ""
    if st.session_state.get("full_numbers", False):
        return f"{sign}£{v:,.0f}"
    if v >= 1_000_000:
        return f"{sign}£{v/1_000_000:.1f}m"
    if v >= 1_000:
        return f"{sign}£{v/1_000:.1f}k"
    return f"{sign}£{v:,.0f}"


def fmt_pct(value) -> str:
    if value is None or value != value:
        return "—"
    return f"{value*100:+.1f}%"


def date_filter(key_prefix: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    today = date.today()
    default_to_m = today.month - 1
    default_to_y = _YEARS.index(today.year) if today.year in _YEARS else len(_YEARS) - 1

    col_from, col_to = st.columns(2)
    with col_from:
        st.caption("From")
        c1, c2 = st.columns(2)
        from_month = c1.selectbox("Month", _MONTHS, index=0,
                                  key=f"{key_prefix}_from_m", label_visibility="collapsed")
        from_year  = c2.selectbox("Year",  _YEARS, index=0,
                                  key=f"{key_prefix}_from_y", label_visibility="collapsed")
    with col_to:
        st.caption("To")
        c3, c4 = st.columns(2)
        to_month = c3.selectbox("Month", _MONTHS, index=default_to_m,
                                key=f"{key_prefix}_to_m", label_visibility="collapsed")
        to_year  = c4.selectbox("Year",  _YEARS, index=default_to_y,
                                key=f"{key_prefix}_to_y", label_visibility="collapsed")

    fm = _MONTHS.index(from_month) + 1
    tm = _MONTHS.index(to_month) + 1
    return (
        pd.Timestamp(date(from_year, fm, 1)),
        pd.Timestamp(date(to_year, tm, _cal.monthrange(to_year, tm)[1])),
    )


def section(title: str) -> None:
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def whalar_ttm_mask(df: pd.DataFrame, today: date | None = None) -> pd.Series:
    if today is None:
        today = date.today()
    if today < WHALAR_TTM_EXCLUDE_UNTIL:
        return df["client"] != "Whalar"
    return pd.Series(True, index=df.index)


def entity_kpis(label: str, df: pd.DataFrame, entities: list, value_col: str = "net") -> None:
    section(label)
    cols = st.columns(len(entities) + 1)
    cols[0].metric("Total", fmt_gbp(df[value_col].sum()))
    for i, e in enumerate(entities):
        cols[i + 1].metric(e, fmt_gbp(df[df["entity"] == e][value_col].sum()))



def tb_kpis(label: str, df_tb: pd.DataFrame, entities: list, col: str, to_dt: pd.Timestamp) -> None:
    """Show a TB balance (e.g. deferred/accrued) total and per entity."""
    section(label)
    cols = st.columns(len(entities) + 1)
    total = 0.0
    by_entity = {}
    for e in entities:
        v = _latest_tb_balance(df_tb, [e], col, to_dt)
        by_entity[e] = v
        total += v
    cols[0].metric("Total", fmt_gbp(total))
    for i, e in enumerate(entities):
        cols[i + 1].metric(e, fmt_gbp(by_entity[e]))


def _latest_tb_balance(df_tb: pd.DataFrame, entities: list, col: str, to_dt: pd.Timestamp) -> float:
    if df_tb.empty or not entities:
        return 0.0
    tb_f = df_tb[df_tb["entity"].isin(entities)]
    tb_at_end = tb_f[tb_f["date"] <= to_dt]
    if tb_at_end.empty:
        return 0.0
    latest_idx = tb_at_end.groupby("entity")["date"].idxmax()
    return float(df_tb.loc[latest_idx, col].sum())


# ── Load data ──────────────────────────────────────────────────────────────────

df_inv, df_jnl, df_tb, metadata = load_data()
data_exists = not df_inv.empty or not df_jnl.empty

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        "<div style='padding:16px 0 4px 0;'>"
        "<span style='font-size:20px;font-weight:700;color:#fff;letter-spacing:-0.5px;'>"
        "Element Human</span><br>"
        "<span style='font-size:11px;color:#10A8B7;font-weight:400;letter-spacing:1px;'>"
        "FINANCE DASHBOARD</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    page = st.radio(
        "View",
        ["Summary", "Monthly Revenue", "Invoice Detail", "Account Transactions"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown(
        "<span style='font-size:12px;font-weight:600;letter-spacing:0.5px;'>ENTITY</span>",
        unsafe_allow_html=True,
    )
    entity_filter = st.pills(
        "Entity",
        options=ALL_ENTITIES,
        default=ALL_ENTITIES,
        selection_mode="multi",
        label_visibility="collapsed",
    )
    if not entity_filter:
        entity_filter = ALL_ENTITIES

    st.markdown("---")
    st.checkbox("Full numbers", key="full_numbers", value=False)

    st.markdown("---")
    if metadata:
        st.markdown(
            f"<span style='font-size:11px;color:#aaa;'>Last refreshed</span><br>"
            f"<span style='font-size:11px;'>{metadata.get('last_refreshed', '—')}</span>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<span style='font-size:11px;color:#aaa;'>No data loaded yet.</span>",
                    unsafe_allow_html=True)

# ── No data guard ──────────────────────────────────────────────────────────────

if not data_exists:
    st.title("Element Human — Finance Dashboard")
    st.info(
        "**No data loaded yet.**\n\n"
        "Run the data refresh workflow in GitHub Actions to populate this dashboard."
    )
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

if page == "Summary":
    st.title("Summary")

    from_dt, to_dt = date_filter("summary")
    st.markdown("---")

    df_inv_f = df_inv[
        (df_inv["date"] >= from_dt) & (df_inv["date"] <= to_dt) &
        (df_inv["entity"].isin(entity_filter)) &
        (~df_inv["status"].isin(["VOIDED", "DELETED", "Voided", "Deleted"]))
    ].copy() if not df_inv.empty else pd.DataFrame()

    df_jnl_f = df_jnl[
        (df_jnl["date"] >= from_dt) & (df_jnl["date"] <= to_dt) &
        (df_jnl["entity"].isin(entity_filter))
    ].copy() if not df_jnl.empty else pd.DataFrame()

    # Invoices Raised — account 110 (AR control), external clients only
    df_ar = df_inv_f[
        (df_inv_f["account_code"] == "110") &
        (~df_inv_f["contact"].isin(EH_ENTITY_CONTACTS))
    ] if not df_inv_f.empty else pd.DataFrame()
    if not df_ar.empty:
        entity_kpis("Invoices Raised", df_ar, entity_filter)
    else:
        section("Invoices Raised")
        st.caption("No invoice data for selected filters.")

    # Recognised Revenue — single net figure per entity
    if not df_jnl_f.empty:
        entity_kpis("Recognised Revenue", df_jnl_f, entity_filter)
    else:
        section("Recognised Revenue")
        st.caption("No recognised revenue data for selected filters.")

    # Balance sheet balances
    tb_kpis("Deferred Revenue — 250 Income in Advance (as at period end)",
            df_tb, entity_filter, "account_250_balance", to_dt)
    tb_kpis("Accrued Revenue — 115 (as at period end)",
            df_tb, entity_filter, "account_115_balance", to_dt)

    st.markdown("---")

    # Charts
    if not df_jnl_f.empty:
        col_l, col_r = st.columns(2)

        with col_l:
            section("Recognised Revenue by Entity")
            entity_rev = df_jnl_f.groupby("entity")["net"].sum().reset_index()
            fig = px.pie(
                entity_rev, values="net", names="entity",
                color_discrete_sequence=EH_PALETTE, hole=0.4,
            )
            fig.update_traces(texttemplate="%{label}<br>%{percent}")
            fig.update_layout(showlegend=False, margin=dict(t=20, b=20),
                              font=dict(family="Poppins"))
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            section("Recognised Revenue by Type")
            type_rev = df_jnl_f.groupby("revenue_type")["net"].sum().reset_index()
            type_rev = type_rev.sort_values("net", ascending=False)
            fig = px.bar(
                type_rev, x="revenue_type", y="net",
                color_discrete_sequence=[EH_TEAL], text_auto=".3s",
            )
            fig.update_layout(xaxis_title="", yaxis_title="£", margin=dict(t=20, b=20),
                              font=dict(family="Poppins"))
            st.plotly_chart(fig, use_container_width=True)

        section("Recognised Revenue by Category")
        cat_rev = df_jnl_f.groupby("category")["net"].sum().reset_index().sort_values("net")
        fig = px.bar(
            cat_rev, x="net", y="category", orientation="h",
            color_discrete_sequence=[EH_PINK], text_auto=".3s",
        )
        fig.update_layout(xaxis_title="£", yaxis_title="", margin=dict(t=20, b=20),
                          font=dict(family="Poppins"))
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MONTHLY REVENUE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Monthly Revenue":
    st.title("Monthly Revenue")

    from_dt, to_dt = date_filter("monthly")
    st.markdown("---")

    if df_jnl.empty:
        st.warning("No recognised revenue data available.")
        st.stop()

    df_jnl_f = df_jnl[
        (df_jnl["date"] >= from_dt) & (df_jnl["date"] <= to_dt) &
        (df_jnl["entity"].isin(entity_filter))
    ].copy()

    if df_jnl_f.empty:
        st.warning("No recognised revenue data for the selected filters.")
        st.stop()

    # Monthly total bar
    monthly = (
        df_jnl_f.dropna(subset=["month"])
        .groupby(df_jnl_f["month"].dt.to_period("M"))["net"]
        .sum().reset_index()
    )
    monthly["month"] = monthly["month"].dt.to_timestamp()
    monthly = monthly.sort_values("month")

    if monthly.empty:
        st.info("No monthly data to chart for the selected period.")
        st.stop()

    fig = px.bar(
        monthly, x="month", y="net",
        color_discrete_sequence=[EH_TEAL],
        labels={"net": "£", "month": "Month"}, text_auto=".3s",
    )
    fig.update_layout(
        title="Monthly Recognised Revenue",
        xaxis_title="", yaxis_title="£", margin=dict(t=40, b=20),
        font=dict(family="Poppins"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Rolling metrics (Whalar excluded from TTM until July 2026)
    months_idx = monthly.set_index("month")["net"]
    latest = monthly["month"].max()

    whalar_mask = whalar_ttm_mask(df_jnl_f)
    ttm_monthly = (
        df_jnl_f[whalar_mask]
        .groupby(df_jnl_f["month"].dt.to_period("M"))["net"]
        .sum().reset_index()
    )
    ttm_monthly["month"] = ttm_monthly["month"].dt.to_timestamp()
    ttm_idx = ttm_monthly.set_index("month")["net"]

    def rolling(idx, months_back, ref=latest):
        return idx[idx.index > ref - pd.DateOffset(months=months_back)].sum()

    def prior_rolling(idx, months_back, ref=latest):
        end = ref - pd.DateOffset(months=months_back)
        return idx[(idx.index > end - pd.DateOffset(months=months_back)) & (idx.index <= end)].sum()

    ttm   = rolling(ttm_idx, 12)
    t6m   = rolling(months_idx, 6)
    t3m   = rolling(months_idx, 3)
    p_ttm = prior_rolling(ttm_idx, 12)
    p_t6m = prior_rolling(months_idx, 6)
    p_t3m = prior_rolling(months_idx, 3)

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "TTM Revenue" + (" (excl. Whalar)" if date.today() < WHALAR_TTM_EXCLUDE_UNTIL else ""),
        fmt_gbp(ttm),
        delta=fmt_pct((ttm - p_ttm) / p_ttm) if p_ttm else None,
    )
    c2.metric("T6M Revenue", fmt_gbp(t6m),
              delta=fmt_pct((t6m - p_t6m) / p_t6m) if p_t6m else None)
    c3.metric("T3M Revenue", fmt_gbp(t3m),
              delta=fmt_pct((t3m - p_t3m) / p_t3m) if p_t3m else None)

    st.markdown("---")

    # Monthly by client heatmap
    section("Monthly Recognised Revenue by Client")
    monthly_client = (
        df_jnl_f.groupby([df_jnl_f["month"].dt.to_period("M"), "client"])["net"]
        .sum().reset_index()
    )
    monthly_client["month"] = monthly_client["month"].dt.to_timestamp()
    pivot = monthly_client.pivot_table(
        index="client", columns="month", values="net", aggfunc="sum", fill_value=0,
    )
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("Total", ascending=False).drop(columns="Total")
    pivot.columns = [pd.Timestamp(c).strftime("%b %y") for c in pivot.columns]
    pivot.loc["TOTAL"] = pivot.sum(axis=0)
    st.dataframe(pivot.map(lambda x: fmt_gbp(x) if x != 0 else "—"), use_container_width=True)

    st.markdown("---")

    # Revenue by type stacked bar
    section("Recognised Revenue by Type Over Time")
    monthly_type = (
        df_jnl_f.groupby([df_jnl_f["month"].dt.to_period("M"), "revenue_type"])["net"]
        .sum().reset_index()
    )
    monthly_type["month"] = monthly_type["month"].dt.to_timestamp()
    monthly_type = monthly_type.sort_values("month")
    fig = px.bar(
        monthly_type, x="month", y="net", color="revenue_type",
        color_discrete_sequence=EH_PALETTE,
        labels={"net": "£", "month": "Month", "revenue_type": "Type"}, barmode="stack",
    )
    fig.update_layout(xaxis_title="", yaxis_title="£", margin=dict(t=20, b=20),
                      font=dict(family="Poppins"))
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: INVOICE DETAIL
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Invoice Detail":
    st.title("Invoice Detail")

    from_dt, to_dt = date_filter("invoice")
    st.markdown("---")

    if df_inv.empty:
        st.warning("No invoice data available.")
        st.stop()

    df_inv_f = df_inv[
        (df_inv["date"] >= from_dt) & (df_inv["date"] <= to_dt) &
        (df_inv["entity"].isin(entity_filter)) &
        (~df_inv["status"].isin(["VOIDED", "DELETED", "Voided", "Deleted"]))
    ].copy()

    if df_inv_f.empty:
        st.warning("No invoice data for the selected filters.")
        st.stop()

    c1, c2, c3 = st.columns(3)
    with c1:
        account_opts = sorted(df_inv_f["account_code"].dropna().unique())
        selected_codes = st.multiselect("Account code", account_opts, default=account_opts)
    with c2:
        status_opts = sorted(df_inv_f["status"].dropna().unique())
        selected_status = st.multiselect("Status", status_opts, default=status_opts)
    with c3:
        client_opts = sorted(df_inv_f["client"].dropna().unique())
        selected_clients = st.multiselect("Client", client_opts, default=[])

    mask = df_inv_f["account_code"].isin(selected_codes) & df_inv_f["status"].isin(selected_status)
    if selected_clients:
        mask &= df_inv_f["client"].isin(selected_clients)
    df_inv_f = df_inv_f[mask]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Invoices", f"{df_inv_f['invoice_number'].nunique():,}")
    c2.metric("Total Net", fmt_gbp(df_inv_f["net"].sum()))
    c3.metric("Total Tax", fmt_gbp(df_inv_f["tax"].sum()))
    c4.metric("Total Gross", fmt_gbp(df_inv_f["gross"].sum()))

    st.markdown("---")

    section("Invoiced Revenue by Client by Month")
    monthly_client = (
        df_inv_f[df_inv_f["is_revenue"]]
        .groupby([df_inv_f["month"].dt.to_period("M"), "client"])["net"]
        .sum().reset_index()
    )
    monthly_client["month"] = monthly_client["month"].dt.to_timestamp()
    monthly_client = monthly_client.sort_values("month")
    if not monthly_client.empty:
        fig = px.bar(
            monthly_client, x="month", y="net", color="client",
            color_discrete_sequence=EH_PALETTE,
            labels={"net": "£", "month": "Month", "client": "Client"}, barmode="stack",
        )
        fig.update_layout(xaxis_title="", yaxis_title="£", margin=dict(t=20, b=20),
                          font=dict(family="Poppins"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    section("Invoice Lines")

    display_cols = [
        "entity", "invoice_number", "type", "contact", "client", "date", "paid_date",
        "account_code", "account_name", "description", "net", "tax", "gross", "status",
    ]
    df_table = df_inv_f[display_cols].copy()
    df_table["date"]      = df_table["date"].dt.strftime("%d %b %Y")
    df_table["paid_date"] = df_table["paid_date"].dt.strftime("%d %b %Y").fillna("—")
    for col in ["net", "tax", "gross"]:
        df_table[col] = df_table[col].apply(lambda x: f"£{x:,.2f}")
    df_table.columns = [
        "Entity", "Invoice", "Type", "Contact", "Client", "Date", "Paid Date",
        "Code", "Account", "Description", "Net", "Tax", "Gross", "Status",
    ]
    st.dataframe(df_table, use_container_width=True, hide_index=True, height=500)

    csv = df_inv_f[display_cols].to_csv(index=False)
    st.download_button("Download CSV", data=csv,
                       file_name=f"eh_invoices_{date.today().isoformat()}.csv",
                       mime="text/csv")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ACCOUNT TRANSACTIONS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Account Transactions":
    st.title("Account Transactions")
    st.caption("Revenue account transactions — invoices, credit notes, and manual journal entries.")

    from_dt, to_dt = date_filter("tx")
    st.markdown("---")

    if df_jnl.empty:
        st.warning("No account transaction data available.")
        st.stop()

    df_jnl_f = df_jnl[
        (df_jnl["date"] >= from_dt) & (df_jnl["date"] <= to_dt) &
        (df_jnl["entity"].isin(entity_filter))
    ].copy()

    if df_jnl_f.empty:
        st.warning("No data for the selected filters.")
        st.stop()

    c1, c2, c3 = st.columns(3)
    with c1:
        code_opts = sorted(df_jnl_f["account_code"].dropna().unique())
        selected_codes = st.multiselect("Account code", code_opts, default=code_opts)
    with c2:
        source_opts = sorted(df_jnl_f["source"].dropna().unique())
        selected_sources = st.multiselect("Source", source_opts, default=source_opts)
    with c3:
        client_opts = sorted(df_jnl_f["client"].dropna().unique())
        selected_clients = st.multiselect("Client", client_opts, default=[])

    mask = df_jnl_f["account_code"].isin(selected_codes) & df_jnl_f["source"].isin(selected_sources)
    if selected_clients:
        mask &= df_jnl_f["client"].isin(selected_clients)
    df_jnl_f = df_jnl_f[mask]

    c1, c2, c3 = st.columns(3)
    c1.metric("Transaction lines", f"{len(df_jnl_f):,}")
    c2.metric("Total Net", fmt_gbp(df_jnl_f["net"].sum()))
    c3.metric("Entities", ", ".join(sorted(df_jnl_f["entity"].unique())))

    st.markdown("---")

    by_code = (
        df_jnl_f.groupby(["account_code", "revenue_type"])["net"]
        .sum().reset_index().sort_values("net", ascending=False)
    )
    fig = px.bar(
        by_code, x="revenue_type", y="net", color="account_code",
        color_discrete_sequence=EH_PALETTE,
        labels={"net": "£", "revenue_type": "Account", "account_code": "Code"},
        barmode="group", text_auto=".3s",
    )
    fig.update_layout(xaxis_title="", yaxis_title="£", margin=dict(t=20, b=20),
                      font=dict(family="Poppins"))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    section("Transaction Lines")

    display_cols = [
        "entity", "date", "month", "client", "account_code", "account_name",
        "source", "description", "net", "tax", "status",
    ]
    df_table = df_jnl_f[display_cols].copy()
    df_table["date"]  = df_table["date"].dt.strftime("%d %b %Y")
    df_table["month"] = df_table["month"].dt.strftime("%b %Y")
    df_table["net"]   = df_table["net"].apply(lambda x: f"£{x:,.2f}")
    df_table["tax"]   = df_table["tax"].apply(lambda x: f"£{x:,.2f}")
    df_table.columns = [
        "Entity", "Date", "Month", "Client", "Code", "Account",
        "Source", "Description", "Net", "Tax", "Status",
    ]
    st.dataframe(df_table, use_container_width=True, hide_index=True, height=500)

    csv = df_jnl_f[display_cols].to_csv(index=False)
    st.download_button(
        "Download CSV", data=csv,
        file_name=f"eh_account_transactions_{date.today().isoformat()}.csv",
        mime="text/csv",
    )
