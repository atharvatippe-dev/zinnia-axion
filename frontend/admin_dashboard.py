"""
Zinnia Axion Admin Dashboard — Central Productivity Leaderboard.

Two-page layout driven by URL query parameters:
  Page 1 (default)  — Leaderboard table with "View" links per user
  Page 2 (?user_id) — User detail: app breakdown + 7-day trend

Run with:
    streamlit run frontend/admin_dashboard.py --server.port 8502 --server.headless true
"""

from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta, date as _date_cls
from pathlib import Path

import time as _time_module

import requests
import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

from ai_summary import get_executive_summary, OPENAI_API_KEY

_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:5000")
_LOGO_PATH = _project_root / "Zinnia_Logo_VERTICAL_FC-WHT_RGB (1).png"

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Admin — Zinnia Axion",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Load logo as base64 ─────────────────────────────────────────────
_logo_b64 = ""
if _LOGO_PATH.exists():
    _logo_b64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode()

# ── CSS — Adaptive light / dark enterprise design ────────────────────
st.markdown(
    """
    <style>
    /* ═══ LIGHT MODE (default) — Enterprise ═══ */
    :root {
        --za-canvas: #f7f9fc;
        --za-surface: #ffffff;
        --za-surface-hover: #f1f5f9;
        --za-border: #e2e8f0;
        --za-text: #0f172a;
        --za-text-body: #334155;
        --za-text-muted: #64748b;
        --za-text-faint: #94a3b8;
        --za-th-bg: #f1f5f9;
        --za-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
        --za-shadow-hover: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.04);
        --za-green: #059669;
        --za-red: #dc2626;
        --za-amber: #d97706;
        --za-green-bg: #ecfdf5;  --za-green-bdr: #a7f3d0;
        --za-red-bg: #fef2f2;    --za-red-bdr: #fecaca;
        --za-amber-bg: #fffbeb;  --za-amber-bdr: #fde68a;
        --za-neutral-bg: #f1f5f9; --za-neutral-bdr: #e2e8f0;
        --za-btn: #1e40af;        --za-btn-hover: #1e3a8a;
        --za-del-bg: #ffffff;     --za-del-hover: #fef2f2;
        --za-back-bg: #eff6ff;    --za-back-bdr: #bfdbfe;
        --za-back-hover: #dbeafe;
        --za-chart-text: #334155;
        --za-row-stripe: #f8fafc;
    }

    /* ═══ DARK MODE — triggered by OS preference (initial load) ═══ */
    @media (prefers-color-scheme: dark) {
      :root {
        --za-canvas: #0e1117;
        --za-surface: #1a1d2e;
        --za-surface-hover: #22253a;
        --za-border: rgba(255,255,255,0.07);
        --za-text: #f1f5f9;
        --za-text-body: #cbd5e1;
        --za-text-muted: #94a3b8;
        --za-text-faint: #475569;
        --za-th-bg: rgba(0,0,0,0.25);
        --za-shadow: 0 2px 8px rgba(0,0,0,0.25);
        --za-shadow-hover: 0 4px 16px rgba(0,0,0,0.35);
        --za-green: #4ade80;
        --za-red: #f87171;
        --za-amber: #fbbf24;
        --za-green-bg: rgba(34,197,94,0.12);  --za-green-bdr: rgba(34,197,94,0.30);
        --za-red-bg: rgba(239,68,68,0.12);    --za-red-bdr: rgba(239,68,68,0.30);
        --za-amber-bg: rgba(251,191,36,0.12); --za-amber-bdr: rgba(251,191,36,0.30);
        --za-neutral-bg: rgba(100,116,139,0.12); --za-neutral-bdr: rgba(100,116,139,0.30);
        --za-btn: #3b82f6;        --za-btn-hover: #60a5fa;
        --za-del-bg: rgba(239,68,68,0.08);  --za-del-hover: rgba(239,68,68,0.18);
        --za-back-bg: rgba(96,165,250,0.10); --za-back-bdr: rgba(96,165,250,0.25);
        --za-back-hover: rgba(96,165,250,0.20);
        --za-chart-text: #94a3b8;
        --za-row-stripe: rgba(255,255,255,0.02);
      }
    }

    /* ═══ DARK MODE — triggered by Streamlit in-app toggle (JS-detected) ═══ */
    :root[data-za-theme="dark"] {
        --za-canvas: #0e1117;
        --za-surface: #1a1d2e;
        --za-surface-hover: #22253a;
        --za-border: rgba(255,255,255,0.07);
        --za-text: #f1f5f9;
        --za-text-body: #cbd5e1;
        --za-text-muted: #94a3b8;
        --za-text-faint: #475569;
        --za-th-bg: rgba(0,0,0,0.25);
        --za-shadow: 0 2px 8px rgba(0,0,0,0.25);
        --za-shadow-hover: 0 4px 16px rgba(0,0,0,0.35);
        --za-green: #4ade80;
        --za-red: #f87171;
        --za-amber: #fbbf24;
        --za-green-bg: rgba(34,197,94,0.12);  --za-green-bdr: rgba(34,197,94,0.30);
        --za-red-bg: rgba(239,68,68,0.12);    --za-red-bdr: rgba(239,68,68,0.30);
        --za-amber-bg: rgba(251,191,36,0.12); --za-amber-bdr: rgba(251,191,36,0.30);
        --za-neutral-bg: rgba(100,116,139,0.12); --za-neutral-bdr: rgba(100,116,139,0.30);
        --za-btn: #3b82f6;        --za-btn-hover: #60a5fa;
        --za-del-bg: rgba(239,68,68,0.08);  --za-del-hover: rgba(239,68,68,0.18);
        --za-back-bg: rgba(96,165,250,0.10); --za-back-bdr: rgba(96,165,250,0.25);
        --za-back-hover: rgba(96,165,250,0.20);
        --za-chart-text: #94a3b8;
        --za-row-stripe: rgba(255,255,255,0.02);
    }

    /* ═══ LIGHT MODE — force override when JS detects light ═══ */
    :root[data-za-theme="light"] {
        --za-canvas: #f7f9fc;
        --za-surface: #ffffff;
        --za-surface-hover: #f1f5f9;
        --za-border: #e2e8f0;
        --za-text: #0f172a;
        --za-text-body: #334155;
        --za-text-muted: #64748b;
        --za-text-faint: #94a3b8;
        --za-th-bg: #f1f5f9;
        --za-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
        --za-shadow-hover: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.04);
        --za-green: #059669;
        --za-red: #dc2626;
        --za-amber: #d97706;
        --za-green-bg: #ecfdf5;  --za-green-bdr: #a7f3d0;
        --za-red-bg: #fef2f2;    --za-red-bdr: #fecaca;
        --za-amber-bg: #fffbeb;  --za-amber-bdr: #fde68a;
        --za-neutral-bg: #f1f5f9; --za-neutral-bdr: #e2e8f0;
        --za-btn: #1e40af;        --za-btn-hover: #1e3a8a;
        --za-del-bg: #ffffff;     --za-del-hover: #fef2f2;
        --za-back-bg: #eff6ff;    --za-back-bdr: #bfdbfe;
        --za-back-hover: #dbeafe;
        --za-chart-text: #334155;
        --za-row-stripe: #f8fafc;
    }

    /* ── Streamlit overrides ── */
    .block-container {
        padding: 2rem 3rem 1rem 3rem !important;
        max-width: 100% !important;
    }
    .element-container { margin-bottom: 0; }
    [data-testid="stMetric"] { display: none; }
    .stPlotlyChart { margin-top: -0.5rem; margin-bottom: -0.5rem; }
    [data-testid="stSidebar"] {
        border-right: 1px solid var(--za-border) !important;
    }

    /* ── Header bar (brand strip) ── */
    .za-header {
        display: flex; align-items: center; gap: 20px;
        padding: 18px 28px;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-radius: 12px;
        margin-bottom: 28px;
        box-shadow: 0 2px 8px rgba(15,23,42,0.10);
    }
    .za-logo { height: 40px; width: auto; flex-shrink: 0; }
    .za-brand { display: flex; flex-direction: column; gap: 2px; }
    .za-title {
        font-size: 1.35rem; font-weight: 700; color: #f8fafc;
        letter-spacing: -0.3px; line-height: 1.2;
    }
    .za-subtitle {
        font-size: 0.6rem; color: #94a3b8;
        text-transform: uppercase; letter-spacing: 2.5px;
        font-weight: 500;
    }
    .za-spacer { flex: 1; }
    .za-date {
        font-size: 0.8rem; color: #94a3b8;
        text-align: right; font-weight: 500;
    }

    /* ── Metric cards ── */
    .za-metrics {
        display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
        margin-bottom: 28px;
    }
    .za-card {
        background: var(--za-surface);
        border-radius: 10px; padding: 20px 22px;
        border: 1px solid var(--za-border);
        position: relative; overflow: hidden;
        box-shadow: var(--za-shadow);
        transition: box-shadow 0.2s, transform 0.2s, background 0.3s;
    }
    .za-card:hover {
        box-shadow: var(--za-shadow-hover);
        transform: translateY(-1px);
    }
    .za-card::before {
        content: ''; position: absolute; top: 0; left: 0;
        width: 3px; height: 100%; border-radius: 0 2px 2px 0;
    }
    .za-card.card-neutral::before { background: #94a3b8; }
    .za-card.card-green::before  { background: #059669; }
    .za-card.card-red::before    { background: #dc2626; }
    .za-card.card-amber::before  { background: #d97706; }
    .za-card-label {
        font-size: 0.68rem; color: var(--za-text-muted);
        text-transform: uppercase; letter-spacing: 1px;
        font-weight: 600; margin-bottom: 10px;
    }
    .za-card-value {
        font-size: 1.9rem; font-weight: 700; color: var(--za-text);
        line-height: 1; letter-spacing: -0.3px;
    }
    .za-card-value.green { color: var(--za-green); }
    .za-card-value.red   { color: var(--za-red); }
    .za-card-value.amber { color: var(--za-amber); }

    /* ── Section divider ── */
    .za-section {
        font-size: 0.7rem; text-transform: uppercase;
        letter-spacing: 1.5px; color: var(--za-text-muted);
        font-weight: 600; margin: 8px 0 16px 0;
        padding-bottom: 10px;
        border-bottom: 1px solid var(--za-border);
    }

    /* ── Leaderboard table ── */
    .za-table-wrap {
        background: var(--za-surface);
        border-radius: 10px; overflow: hidden;
        border: 1px solid var(--za-border);
        box-shadow: var(--za-shadow);
        transition: background 0.3s;
    }
    .leader-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    .leader-table th {
        text-align: left; padding: 14px 22px;
        font-weight: 600; font-size: 0.68rem;
        text-transform: uppercase; letter-spacing: 0.8px;
        color: var(--za-text-muted); background: var(--za-th-bg);
        border-bottom: 1px solid var(--za-border);
    }
    .leader-table td {
        padding: 14px 22px;
        border-bottom: 1px solid var(--za-border);
        vertical-align: middle;
        color: var(--za-text-body);
    }
    .leader-table tbody tr { transition: background-color 0.15s; }
    .leader-table tbody tr:nth-child(even) { background-color: var(--za-row-stripe); }
    .leader-table tbody tr:hover { background-color: var(--za-surface-hover) !important; }
    .leader-table tbody tr:last-child td { border-bottom: none; }
    .user-name { font-weight: 600; font-size: 0.92rem; color: var(--za-text); }

    /* ── Status badges ── */
    .status-badge {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 0.8rem; font-weight: 500; color: var(--za-text-muted);
    }
    .status-badge .dot {
        width: 8px; height: 8px; border-radius: 50%;
        display: inline-block;
    }
    .dot-online { background: #059669; box-shadow: 0 0 6px rgba(5,150,105,0.45); }
    .dot-offline { background: #dc2626; }
    .dot-unknown { background: #94a3b8; }

    /* ── Percentage badges ── */
    .pct-badge {
        display: inline-block; padding: 4px 12px; border-radius: 6px;
        font-weight: 600; font-size: 0.8rem;
    }
    .pct-badge-red    { background: var(--za-red-bg);    color: var(--za-red);   border: 1px solid var(--za-red-bdr); }
    .pct-badge-green  { background: var(--za-green-bg);  color: var(--za-green); border: 1px solid var(--za-green-bdr); }
    .pct-badge-amber  { background: var(--za-amber-bg);  color: var(--za-amber); border: 1px solid var(--za-amber-bdr); }
    .pct-badge-neutral{ background: var(--za-neutral-bg); color: var(--za-text-muted); border: 1px solid var(--za-neutral-bdr); }

    /* ── Action buttons ── */
    .action-link {
        font-weight: 600; text-decoration: none;
        padding: 6px 16px; border-radius: 6px;
        font-size: 0.78rem; transition: all 0.15s;
        display: inline-block; cursor: pointer;
    }
    .action-view {
        background: var(--za-btn); color: #ffffff !important;
        box-shadow: 0 1px 2px rgba(30,64,175,0.18);
    }
    .action-view:hover {
        background: var(--za-btn-hover);
        box-shadow: 0 2px 4px rgba(30,64,175,0.25);
    }
    .action-delete {
        background: var(--za-del-bg); color: var(--za-red) !important;
        border: 1px solid var(--za-red-bdr);
    }
    .action-delete:hover { background: var(--za-del-hover); }

    /* ── Footer ── */
    .za-footer {
        margin-top: 32px; padding-top: 16px;
        border-top: 1px solid var(--za-border);
        display: flex; justify-content: space-between; align-items: center;
    }
    .za-footer span { font-size: 0.7rem; color: var(--za-text-faint); font-weight: 500; }

    /* ── Back link ── */
    .za-back {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 0.88rem; color: var(--za-btn); text-decoration: none;
        font-weight: 700; margin-bottom: 10px;
        padding: 8px 18px; border-radius: 8px;
        background: var(--za-back-bg); border: 1.5px solid var(--za-back-bdr);
        transition: all 0.15s;
    }
    .za-back:hover { background: var(--za-back-hover); }

    /* ── Detail page heading ── */
    .za-detail-title {
        font-size: 1.5rem; font-weight: 800; color: var(--za-text);
        margin: 4px 0 22px 0; letter-spacing: -0.3px;
    }

    /* ── Detail page — strong text for values ── */
    .za-detail-title, .za-detail-section .za-card-value,
    .za-detail-section .za-card-label,
    .za-detail-section .za-section {
        opacity: 1 !important;
    }
    .za-detail-section .za-card {
        border-width: 1.5px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04);
    }
    .za-detail-section .za-card-label {
        font-size: 0.72rem; font-weight: 700;
        color: var(--za-text-body);
    }
    .za-detail-section .za-card-value {
        font-size: 2rem; font-weight: 800;
    }
    .za-detail-section .za-section {
        font-size: 0.75rem; font-weight: 700;
        color: var(--za-text-body);
        border-bottom-width: 2px;
    }

    /* ── Streamlit button overrides ── */
    .stButton > button[kind="primary"] {
        background: var(--za-btn) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.3rem !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 2px rgba(30,64,175,0.15) !important;
        transition: all 0.15s !important;
        font-size: 0.85rem !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: var(--za-btn-hover) !important;
        box-shadow: 0 2px 4px rgba(30,64,175,0.22) !important;
    }
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.15s !important;
    }

    /* ── Summary dialog polish ── */
    [data-testid="stModal"] > div {
        border-radius: 12px !important;
        box-shadow: 0 8px 30px rgba(0,0,0,0.12) !important;
    }
    [data-testid="stModal"] [data-testid="stMarkdownContainer"] h2 {
        font-size: 1.1rem; font-weight: 700; color: var(--za-text);
        margin-bottom: 8px;
    }
    [data-testid="stModal"] [data-testid="stMarkdownContainer"] ul {
        padding-left: 18px;
    }

    /* ── Plotly chart wrapper ── */
    .stPlotlyChart > div { border-radius: 8px; }

    /* ── Detail page chart labels stronger ── */
    .za-detail-section .stPlotlyChart text {
        fill: var(--za-text-body) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── JS — Detect Streamlit theme toggle and set data attribute ────────
import streamlit.components.v1 as _components
_components.html("""
<script>
(function() {
  var doc = window.parent.document;
  function detect() {
    var el = doc.querySelector('[data-testid="stAppViewContainer"]');
    if (!el) return;
    var bg = getComputedStyle(el).backgroundColor;
    var m = bg.match(/\\d+/g);
    if (m) {
      var brightness = (parseInt(m[0]) + parseInt(m[1]) + parseInt(m[2])) / 3;
      doc.documentElement.setAttribute('data-za-theme', brightness < 128 ? 'dark' : 'light');
    }
  }
  detect();
  setInterval(detect, 500);
})();
</script>
""", height=0)

STATE_COLORS = {"productive": "#059669", "non_productive": "#dc2626"}
STATE_LABELS = {"productive": "Productive", "non_productive": "Non-Productive"}

_CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="system-ui, -apple-system, sans-serif", color="#64748b", size=12),
)


# ── API helpers ──────────────────────────────────────────────────────

def _auth_headers() -> dict:
    """Return headers that identify the current manager to the backend."""
    uid = st.session_state.get("user_id")
    if uid:
        return {"X-Manager-User-Id": str(uid)}
    return {}


def _get(path: str, params: dict | None = None):
    try:
        resp = requests.get(f"{API_BASE}{path}", params=params, headers=_auth_headers(), timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        st.error(f"API error ({path}): {exc}")
        return None


def _delete(path: str):
    try:
        resp = requests.delete(f"{API_BASE}{path}", headers=_auth_headers(), timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        st.error(f"API error ({path}): {exc}")
        return None


# ── SSO Login Gate ───────────────────────────────────────────────────

def _show_login_page():
    """Render a professional SSO login page. Returns True if user logs in."""
    st.markdown("""
    <style>
    .sso-container {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; min-height: 60vh; text-align: center;
    }
    .sso-card {
        background: var(--za-surface); border: 1px solid var(--za-border);
        border-radius: 16px; padding: 48px 56px; max-width: 440px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.06); text-align: center;
    }
    .sso-lock {
        font-size: 2.8rem; margin-bottom: 8px; opacity: 0.85;
    }
    .sso-heading {
        font-size: 1.6rem; font-weight: 800; color: var(--za-text);
        margin-bottom: 4px; letter-spacing: -0.5px;
    }
    .sso-sub {
        font-size: 0.85rem; color: var(--za-text-muted);
        margin-bottom: 32px; line-height: 1.5;
    }
    .sso-footer {
        margin-top: 24px; font-size: 0.7rem; color: var(--za-text-faint);
        line-height: 1.4;
    }
    .sso-badge {
        display: inline-block; padding: 3px 10px; border-radius: 4px;
        background: var(--za-green-bg); color: var(--za-green);
        border: 1px solid var(--za-green-bdr);
        font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.5px; margin-top: 16px;
    }
    </style>
    """, unsafe_allow_html=True)

    _logo_html = (
        f'<img src="data:image/png;base64,{_logo_b64}" '
        f'style="height:60px; margin-bottom:16px;">'
        if _logo_b64 else ""
    )

    st.markdown(f"""
    <div class="sso-container">
        <div class="sso-card">
            {_logo_html}
            <div class="sso-lock">&#128274;</div>
            <div class="sso-heading">Zinnia Axion</div>
            <div class="sso-sub">
                Manager Portal<br>
                <span style="font-size:0.75rem; color:var(--za-text-faint);">
                    Sign in with your corporate identity to access the dashboard.
                </span>
            </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1.2, 2, 1.2])
    with col2:
        _managers = {
            "Wasim Shaikh (Lifecad)": "demo_manager",
            "Atharva Tippe (Axion)": "atharva_mgr",
            "Nikhil Saxena (Engineering)": "nikhil",
        }
        _selected = st.selectbox(
            "Sign in as", list(_managers.keys()), index=0, key="sso_manager_pick",
        )
        clicked = st.button("Sign in with SSO", type="primary", use_container_width=True)
        if clicked:
            st.session_state["_login_lan_id"] = _managers[_selected]

    st.markdown("""
            <div class="sso-footer">
                Protected by OIDC / SAML Single Sign-On<br>
                Access is restricted to authorized managers only.
            </div>
            <div class="sso-badge">Enterprise SSO</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    return clicked


_SESSION_FILE = _project_root / ".admin_session.json"


def _save_session(data: dict):
    """Persist login state to a file so it survives full page reloads."""
    import json as _json
    _SESSION_FILE.write_text(_json.dumps(data))


def _load_session() -> dict | None:
    """Restore login state from file if session_state was lost."""
    import json as _json
    if _SESSION_FILE.exists():
        try:
            return _json.loads(_SESSION_FILE.read_text())
        except (ValueError, OSError):
            return None
    return None


def _clear_session():
    """Remove persisted login state."""
    _SESSION_FILE.unlink(missing_ok=True)


def _do_login():
    """Authenticate via backend and store manager identity."""
    lan_id = st.session_state.pop("_login_lan_id", None)

    if lan_id:
        resp = requests.get(
            f"{API_BASE}/admin/login", params={"as": lan_id},
            timeout=5, allow_redirects=False,
        )
        uid = resp.json().get("user_id") if resp.ok else None
    else:
        requests.get(f"{API_BASE}/admin/login", timeout=5, allow_redirects=False)
        uid = None

    if uid:
        st.session_state["user_id"] = uid
    headers = {"X-Manager-User-Id": str(uid)} if uid else {}

    try:
        me_resp = requests.get(f"{API_BASE}/admin/me", headers=headers, timeout=5)
        me_resp.raise_for_status()
        me = me_resp.json()
    except Exception:
        me = _get("/admin/me")

    if me and "manager_name" in me:
        session_data = {
            "logged_in": True,
            "user_id": me.get("user_id"),
            "manager_name": me["manager_name"],
            "manager_email": me.get("manager_email", ""),
            "team_name": me["team_name"],
            "team_id": me.get("team_id"),
            "role": me.get("role", "manager"),
            "allowed_team_ids": me.get("allowed_team_ids", []),
        }
        st.session_state.update(session_data)
        _save_session(session_data)
        return True
    st.error("Authentication failed. Please try again.")
    return False


# Restore session from file if lost (happens on full page reload via <a> links)
if not st.session_state.get("logged_in", False):
    _saved = _load_session()
    if _saved and _saved.get("logged_in"):
        st.session_state.update(_saved)

if not st.session_state.get("logged_in", False):
    if _show_login_page():
        with st.spinner("Authenticating via SSO..."):
            _time_module.sleep(0.8)
            if _do_login():
                st.rerun()
    st.stop()

_mgr_name = st.session_state.get("manager_name", "Manager")
_team_name = st.session_state.get("team_name", "Team")


def _fmt(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    h, remainder = divmod(s, 3600)
    m, sec = divmod(remainder, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if sec and not h:
        parts.append(f"{sec}s")
    return " ".join(parts)


def _pct_badge(value: float, invert: bool = False) -> str:
    if invert:
        cls = "pct-badge-red" if value >= 50 else ("pct-badge-amber" if value >= 35 else "pct-badge-green")
    else:
        cls = "pct-badge-green" if value >= 55 else ("pct-badge-amber" if value >= 40 else "pct-badge-red")
    return f'<span class="pct-badge {cls}">{value:.1f}%</span>'


# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    if _logo_b64:
        st.markdown(
            f'<div style="text-align:center; padding:20px 0 12px;">'
            f'<img src="data:image/png;base64,{_logo_b64}" style="height:80px;"></div>',
            unsafe_allow_html=True,
        )

    _n_scope = len(st.session_state.get("allowed_team_ids", []))
    _scope_label = f"{_n_scope} team{'s' if _n_scope != 1 else ''} in scope" if _n_scope else ""
    _scope_html = (
        f'<div style="font-size:0.7rem; color:var(--za-green); margin-top:4px; font-weight:600;">'
        f'{_scope_label}</div>'
    ) if _scope_label else ""

    st.markdown(
        f'<div style="padding:8px 0 4px; border-bottom: 1px solid var(--za-border); margin-bottom:12px;">'
        f'<div style="font-size:0.7rem; color:var(--za-text-muted); text-transform:uppercase; '
        f'letter-spacing:1px; font-weight:600;">Signed in as</div>'
        f'<div style="font-size:0.95rem; font-weight:700; color:var(--za-text); margin-top:2px;">'
        f'{_mgr_name}</div>'
        f'<div style="font-size:0.78rem; color:var(--za-text-muted);">'
        f'{st.session_state.get("role", "manager").title()} &middot; {_team_name}</div>'
        f'{_scope_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if st.button("Sign Out", use_container_width=True):
        for k in ["logged_in", "user_id", "manager_name", "manager_email",
                   "team_name", "team_id", "role", "allowed_team_ids"]:
            st.session_state.pop(k, None)
        _clear_session()
        st.rerun()

    st.markdown("**Admin Settings**")
    auto_refresh = st.checkbox("Auto-refresh (10 s)", value=True)

# ── Query params ─────────────────────────────────────────────────────
_qp = st.query_params
selected_user_id = _qp.get("user_id", None)
_delete_uid = _qp.get("delete_user", None)

if _delete_uid:
    result = _delete(f"/admin/user/{_delete_uid}")
    if result:
        st.success(f"Deleted {result.get('deleted', 0)} events for **{_delete_uid}**.")
    st.query_params.clear()
    _time_module.sleep(1.5)
    st.rerun()

# ── Header ───────────────────────────────────────────────────────────
_now_str = datetime.now().strftime("%b %d, %Y &middot; %H:%M")
_logo_tag = f'<img src="data:image/png;base64,{_logo_b64}" class="za-logo">' if _logo_b64 else ""

_role_label = st.session_state.get("role", "manager").title()
_mgr_initials = "".join(w[0] for w in _mgr_name.split() if w)[:2].upper()

st.markdown(
    f"""<div class="za-header">
        {_logo_tag}
        <div class="za-brand">
            <div class="za-title">Zinnia Axion</div>
            <div class="za-subtitle">Invisible Signals. Visible Performance.</div>
        </div>
        <div class="za-spacer"></div>
        <div style="display:flex; align-items:center; gap:14px;">
            <div style="text-align:right;">
                <div style="font-size:0.82rem; font-weight:600; color:#f1f5f9;">{_mgr_name}</div>
                <div style="font-size:0.65rem; color:#94a3b8; letter-spacing:0.5px;">
                    {_role_label} &middot; {_team_name}
                </div>
            </div>
            <div style="width:36px; height:36px; border-radius:50%;
                        background:linear-gradient(135deg,#3b82f6,#6366f1);
                        display:flex; align-items:center; justify-content:center;
                        font-size:0.78rem; font-weight:700; color:#fff;
                        letter-spacing:0.5px; flex-shrink:0;">
                {_mgr_initials}
            </div>
        </div>
        <div class="za-date" style="margin-left:14px;">{_now_str}</div>
    </div>""",
    unsafe_allow_html=True,
)


# ── Date filter ──────────────────────────────────────────────────────
_today = _date_cls.today()
_date_options: list[tuple[str, str]] = []
for _offset in range(5):
    _d = _today - timedelta(days=_offset)
    if _offset == 0:
        _label = f"Today — {_d.strftime('%a, %b %d')}"
    elif _offset == 1:
        _label = f"Yesterday — {_d.strftime('%a, %b %d')}"
    else:
        _label = _d.strftime("%a, %b %d")
    _date_options.append((_label, _d.isoformat()))

_date_labels = [opt[0] for opt in _date_options]
_date_values = [opt[1] for opt in _date_options]

_fc1, _fc2 = st.columns([3, 1])
with _fc2:
    _sel_idx = st.selectbox(
        "Filter Date",
        range(len(_date_labels)),
        format_func=lambda i: _date_labels[i],
        index=0,
        key="date_filter",
    )
_selected_date: str = _date_values[_sel_idx]
_is_today = _sel_idx == 0
_date_param: dict = {} if _is_today else {"date": _selected_date}

if not _is_today:
    _viewing = _date_options[_sel_idx][0]
    st.markdown(
        f'<div style="font-size:0.78rem;color:#64748b;margin:-12px 0 16px 0;">'
        f'Showing data for: <strong>{_viewing}</strong></div>',
        unsafe_allow_html=True,
    )

# =====================================================================
#  PAGE 2 — User Detail
# =====================================================================
if selected_user_id:
    st.markdown(
        '<a href="?" target="_self" class="za-back">&larr; Back to Leaderboard</a>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="za-detail-title">User Detail &mdash; {selected_user_id}</div>'
        f'<div class="za-detail-section">',
        unsafe_allow_html=True,
    )

    summary = _get("/summary/today", {"user_id": selected_user_id, **_date_param})
    app_breakdown = _get(f"/admin/user/{selected_user_id}/app-breakdown", _date_param or None)
    daily_data = _get("/daily", {"days": 7, "user_id": selected_user_id})

    _has_today = summary and summary.get("total_seconds", 0) > 0

    if _has_today:
        total = summary.get("total_seconds", 1)
        productive = summary.get("productive", 0)
        non_productive = summary.get("non_productive", 0)
        prod_pct = round(productive / total * 100, 1) if total else 0
        non_prod_pct = round(non_productive / total * 100, 1) if total else 0

        st.markdown(f"""
        <div class="za-metrics">
            <div class="za-card card-green">
                <div class="za-card-label">Productive</div>
                <div class="za-card-value green">{prod_pct}%</div>
            </div>
            <div class="za-card card-red">
                <div class="za-card-label">Non-Productive</div>
                <div class="za-card-value red">{non_prod_pct}%</div>
            </div>
            <div class="za-card card-green">
                <div class="za-card-label">Productive Time</div>
                <div class="za-card-value green">{_fmt(productive)}</div>
            </div>
            <div class="za-card card-neutral">
                <div class="za-card-label">Total Tracked</div>
                <div class="za-card-value">{_fmt(total)}</div>
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown(
            f'<div class="za-section">Apps Breakdown &mdash; {selected_user_id} ({_date_labels[_sel_idx].split(" — ")[0]})</div>',
            unsafe_allow_html=True,
        )

        if app_breakdown and len(app_breakdown) > 0:
            rows = []
            for entry in app_breakdown:
                name = entry["app_name"]
                p_sec = entry.get("productive", 0)
                np_sec = entry.get("non_productive", 0)
                if p_sec > 0:
                    rows.append({"App": name, "Seconds": p_sec, "Type": "Productive", "Duration": _fmt(p_sec)})
                if np_sec > 0:
                    rows.append({"App": name, "Seconds": np_sec, "Type": "Non-Productive", "Duration": _fmt(np_sec)})
            if rows:
                df_apps = pd.DataFrame(rows)
                app_order = [e["app_name"] for e in sorted(app_breakdown, key=lambda x: x["total"])]
                df_apps["App"] = pd.Categorical(df_apps["App"], categories=app_order, ordered=True)
                fig_apps = px.bar(
                    df_apps, y="App", x="Seconds", color="Type", orientation="h",
                    text="Duration",
                    color_discrete_map={"Productive": "#059669", "Non-Productive": "#dc2626"},
                    category_orders={"Type": ["Productive", "Non-Productive"]},
                )
                fig_apps.update_traces(textposition="outside", textfont_size=12, textfont_color="#0f172a")
                fig_apps.update_layout(
                    barmode="group",
                    yaxis={"title": "", "automargin": True, "tickfont": {"color": "#334155", "size": 13}},
                    xaxis_title="",
                    xaxis={"tickfont": {"color": "#334155"}},
                    margin=dict(t=5, b=5, l=10, r=50),
                    height=max(220, len(app_breakdown) * 52 + 60),
                    legend=dict(
                        orientation="h", yanchor="bottom", y=1.02,
                        xanchor="right", x=1, title_text="",
                        font={"color": "#334155", "size": 13},
                    ),
                    **_CHART_LAYOUT,
                )
                st.plotly_chart(fig_apps, use_container_width=True)
            else:
                st.info("No app usage data available.")
        else:
            st.info(f"No app breakdown data for {selected_user_id} today.")
    else:
        st.info(f"No data for {selected_user_id} today.")

    st.markdown(
        f'<div class="za-section">7-Day Trend &mdash; {selected_user_id}</div>',
        unsafe_allow_html=True,
    )

    if daily_data and isinstance(daily_data, list) and len(daily_data) > 0:
        line_rows = []
        for day in daily_data:
            d = day.get("date", "")
            for state_key, label in STATE_LABELS.items():
                secs = day.get(state_key, 0)
                line_rows.append({"Date": d, "State": label, "Minutes": round(secs / 60, 1)})
        df_line = pd.DataFrame(line_rows)
        fig_line = px.line(
            df_line, x="Date", y="Minutes", color="State", markers=True,
            color_discrete_map={v: STATE_COLORS[k] for k, v in STATE_LABELS.items()},
        )
        fig_line.update_layout(
            xaxis_title="", yaxis_title="min",
            xaxis={"tickfont": {"color": "#334155", "size": 12}},
            yaxis={"tickfont": {"color": "#334155", "size": 12}, "title_font": {"color": "#334155"}},
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        title_text="", font={"color": "#334155", "size": 13}),
            margin=dict(t=5, b=5, l=5, r=5), height=300,
            **_CHART_LAYOUT,
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No daily trend data available.")

    st.markdown('</div>', unsafe_allow_html=True)  # close za-detail-section

    st.markdown(
        f'<div class="za-footer"><span>{_mgr_name} &middot; {_team_name}</span><span>Zinnia Axion v1.0</span></div>',
        unsafe_allow_html=True,
    )
    if auto_refresh:
        _time_module.sleep(10)
        st.rerun()
    st.stop()


# =====================================================================
#  PAGE 1 — Leaderboard
# =====================================================================

leaderboard = _get("/admin/leaderboard", _date_param or None)
tracker_status = _get("/admin/tracker-status") or []
_status_map: dict[str, dict] = {s["user_id"]: s for s in tracker_status}

if not leaderboard or len(leaderboard) == 0:
    _no_data_msg = "No activity recorded for this date." if not _is_today else "No user data for today yet. Ensure trackers are running."
    st.info(_no_data_msg)
    st.stop()

# ── Metric cards ─────────────────────────────────────────────────────
total_users = len(leaderboard)
avg_prod = sum(r["productive_pct"] for r in leaderboard) / total_users if total_users else 0
avg_non_prod = sum(r["non_productive_pct"] for r in leaderboard) / total_users if total_users else 0
total_tracked = sum(r["total_sec"] for r in leaderboard)

_prod_cls = "card-green"
_prod_val = "green"
_np_cls = "card-red" if avg_non_prod >= 50 else ("card-amber" if avg_non_prod >= 40 else "card-green")
_np_val = "red" if avg_non_prod >= 50 else ("amber" if avg_non_prod >= 40 else "green")

st.markdown(f"""
<div class="za-metrics">
    <div class="za-card card-neutral">
        <div class="za-card-label">{_team_name} &mdash; Team Size</div>
        <div class="za-card-value">{total_users}</div>
    </div>
    <div class="za-card {_prod_cls}">
        <div class="za-card-label">Avg Productive</div>
        <div class="za-card-value {_prod_val}">{avg_prod:.1f}%</div>
    </div>
    <div class="za-card {_np_cls}">
        <div class="za-card-label">Avg Non-Productive</div>
        <div class="za-card-value {_np_val}">{avg_non_prod:.1f}%</div>
    </div>
    <div class="za-card card-neutral">
        <div class="za-card-label">Total Tracked</div>
        <div class="za-card-value">{_fmt(total_tracked)}</div>
    </div>
</div>""", unsafe_allow_html=True)

# ── Summary dialog ───────────────────────────────────────────────────
@st.dialog("Daily Ops Snapshot", width="large")
def _show_summary_dialog():
    st.session_state["_summary_open"] = True
    force = st.button("🔄 Regenerate", key="regen_summary")
    with st.spinner("Generating summary..."):
        text, is_ai = get_executive_summary(leaderboard, force_refresh=force)
    st.markdown(text)
    st.divider()
    col_ts, col_badge = st.columns([3, 1])
    with col_ts:
        st.caption(f"Generated at {datetime.now().strftime('%H:%M:%S')}")
    with col_badge:
        if is_ai:
            st.caption("Powered by OpenAI")
        else:
            st.caption("Heuristic summary" + (" (no API key)" if not OPENAI_API_KEY else ""))

if st.button("📋  View Summary", type="primary"):
    _show_summary_dialog()
else:
    st.session_state["_summary_open"] = False

# ── Leaderboard ──────────────────────────────────────────────────────
st.markdown(
    f'<div class="za-section">{_team_name} Team Leaderboard &mdash; ranked by non-productive % (highest first)</div>',
    unsafe_allow_html=True,
)


def _row_bg(np_pct: float) -> str:
    """Light-mode row tinting based on non-productive %."""
    if np_pct >= 50:
        t = min((np_pct - 50) / 50, 1.0)
        intensity = 0.04 + 0.08 * t
        return f"rgba(239,68,68,{intensity:.2f})"
    prod_pct = 100 - np_pct
    if prod_pct >= 70:
        t = min((prod_pct - 70) / 30, 1.0)
        intensity = 0.03 + 0.06 * t
        return f"rgba(34,197,94,{intensity:.2f})"
    return "transparent"


_header = (
    "<tr>"
    "<th>User</th><th>Status</th>"
    "<th>Non-Productive</th><th>Productive</th>"
    "<th>NP Time</th><th>P Time</th>"
    "<th>Total</th><th style='text-align:right;'>Actions</th>"
    "</tr>"
)

_rows_html = ""
for entry in leaderboard:
    uid = entry["user_id"]
    np_pct = entry["non_productive_pct"]
    p_pct = entry["productive_pct"]
    bg = _row_bg(np_pct)

    _st = _status_map.get(uid, {})
    _is_online = _st.get("status") == "online"
    _ago = _st.get("seconds_ago", -1)
    if _is_online:
        _status = '<span class="status-badge"><span class="dot dot-online"></span>Online</span>'
    elif _ago >= 0:
        _mins = _ago // 60
        _label = f"{_mins}m ago" if _mins > 0 else f"{_ago}s ago"
        _status = f'<span class="status-badge"><span class="dot dot-offline"></span>{_label}</span>'
    else:
        _status = '<span class="status-badge"><span class="dot dot-unknown"></span>&mdash;</span>'

    _rows_html += (
        f'<tr style="background:{bg};">'
        f'<td class="user-name">{uid}</td>'
        f"<td>{_status}</td>"
        f"<td>{_pct_badge(np_pct, invert=True)}</td>"
        f"<td>{_pct_badge(p_pct, invert=False)}</td>"
        f"<td>{_fmt(entry['non_productive_sec'])}</td>"
        f"<td>{_fmt(entry['productive_sec'])}</td>"
        f"<td>{_fmt(entry['total_sec'])}</td>"
        f'<td style="white-space:nowrap; text-align:right;">'
        f'<a href="?user_id={uid}" target="_self" class="action-link action-view">View</a> '
        f'<a href="?delete_user={uid}" target="_self" class="action-link action-delete"'
        f' onclick="return confirm(\'Delete all data for {uid}?\');">Delete</a>'
        f"</td></tr>"
    )

st.markdown(
    f'<div class="za-table-wrap"><table class="leader-table">'
    f'<thead>{_header}</thead><tbody>{_rows_html}</tbody></table></div>',
    unsafe_allow_html=True,
)

# ── Footer ───────────────────────────────────────────────────────────
st.markdown(
    f"""<div class="za-footer">
        <span>Auto-refresh {'enabled' if auto_refresh else 'paused'} &middot; {_mgr_name} &middot; {_team_name}</span>
        <span>Zinnia Axion v1.0</span>
    </div>""",
    unsafe_allow_html=True,
)

# ── Auto-refresh ─────────────────────────────────────────────────────
if auto_refresh and not st.session_state.get("_summary_open", False):
    _time_module.sleep(10)
    st.rerun()
