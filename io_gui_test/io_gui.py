import streamlit as st
import json
import os
import re
import sys
import calendar
import hashlib
import hmac
import secrets
from pathlib import Path
from datetime import datetime, date

import pandas as pd
import altair as alt

# This file lives in io_gui_test/, one directory below the four manager
# modules (io_manager.py, ai_manager.py, logic_manager.py, data_manager.py).
# Streamlit inserts this file's own directory into sys.path, not the
# project root, so "import io_manager" etc. would fail without this.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import io_manager
import logic_manager
import data_manager

st.set_page_config(
    page_title="PASSAY - Health History and Consultation Prep",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@500;600;700&family=Baloo+2:wght@500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Quicksand', sans-serif;
            font-weight: 600;
        }
        .stApp p,
        .stApp label,
        .stApp input,
        .stApp textarea,
        .stApp button,
        .stApp li,
        .stApp [data-testid="stMarkdownContainer"] {
            font-family: 'Quicksand', sans-serif;
        }
        [data-testid="stIconMaterial"],
        .material-symbols-rounded,
        .material-symbols-outlined {
            font-family: "Material Symbols Rounded" !important;
            font-weight: normal !important;
            font-style: normal !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            white-space: nowrap !important;
            word-wrap: normal !important;
            direction: ltr !important;
            -webkit-font-feature-settings: "liga" !important;
            font-feature-settings: "liga" !important;
            -webkit-font-smoothing: antialiased !important;
        }
        h1,h2,h3,h4 { font-family: 'Baloo 2', cursive !important; letter-spacing: 0 !important; }

        @keyframes fadeUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes springIn {
            0% { opacity: 0; transform: translateY(24px) scale(0.94); }
            60% { opacity: 1; transform: translateY(-4px) scale(1.01); }
            100% { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes slideInLeft { from { opacity: 0; transform: translateX(-18px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes floaty { 0% { transform: translate(0,0) scale(1); } 50% { transform: translate(40px,-30px) scale(1.12); } 100% { transform: translate(0,0) scale(1); } }
        @keyframes floaty2 { 0% { transform: translate(0,0) scale(1); } 50% { transform: translate(-34px,30px) scale(1.1); } 100% { transform: translate(0,0) scale(1); } }
        @keyframes bob { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }

        /* ============================================================
           THEME TOKENS
           Defaults below are the DARK theme. The light-mode overrides
           further down flip these tokens when the user's Streamlit
           base theme is light (prefers-color-scheme: light).
           ============================================================ */
        :root {
            --app-bg-1: #2a1958;
            --app-bg-2: #10344a;
            --app-bg-3a: #0a0e1e;
            --app-bg-3b: #0e1226;
            --blob-1: rgba(167,139,250,0.5);
            --blob-2: rgba(94,234,212,0.4);

            --text-main: #cdd6ee;
            --text-strong: #f4f6ff;
            --text-muted: #a6b0d0;

            --surface: rgba(255,255,255,0.05);
            --surface-2: rgba(255,255,255,0.06);
            --border: rgba(255,255,255,0.12);
            --border-soft: rgba(255,255,255,0.09);
            --border-strong: rgba(255,255,255,0.14);
            --shadow: rgba(0,0,0,0.4);
            --shadow-soft: rgba(0,0,0,0.36);

            --input-bg: rgba(255,255,255,0.05);
            --input-border: rgba(255,255,255,0.14);

            --sidebar-bg: linear-gradient(180deg, #120a2e 0%, #131a38 60%, #16224a 130%);
            --sidebar-border: rgba(255,255,255,0.06);

            --accent: #a78bfa;
            --accent-2: #5eead4;
            --accent-ring: rgba(167,139,250,0.22);
            --accent-glow: rgba(167,139,250,0.3);

            --hero-grad: linear-gradient(115deg,#2a1958 0%,#6d28d9 50%,#0e7490 120%);
            --hero-shadow: rgba(109,40,217,0.42);
            --on-hero: #ffffff;
            --on-hero-soft: rgba(255,255,255,0.9);

            --metric-bg: rgba(255,255,255,0.05);
        }

        .stApp {
            background:
              radial-gradient(1000px 600px at 8% -5%, var(--app-bg-1) 0%, transparent 55%),
              radial-gradient(900px 600px at 100% 0%, var(--app-bg-2) 0%, transparent 55%),
              linear-gradient(180deg, var(--app-bg-3a) 0%, var(--app-bg-3b) 100%);
            overflow-x: hidden;
        }
        .stApp:before, .stApp:after {
            content: ""; position: fixed; border-radius: 50%; filter: blur(90px); z-index: 0; pointer-events: none;
        }
        .stApp:before {
            width: 560px; height: 560px;
            background: radial-gradient(circle at 30% 30%, var(--blob-1), transparent 70%);
            top: -140px; left: -100px; animation: floaty 18s ease-in-out infinite;
        }
        .stApp:after {
            width: 500px; height: 500px;
            background: radial-gradient(circle at 60% 40%, var(--blob-2), transparent 70%);
            bottom: -160px; right: -80px; animation: floaty2 22s ease-in-out infinite;
        }
        section.main .block-container { position: relative; z-index: 1; }

        section.main .block-container > div { animation: springIn 0.55s cubic-bezier(0.34,1.56,0.64,1) both; }
        section.main .block-container > div:nth-child(1) { animation-delay: 0.02s; }
        section.main .block-container > div:nth-child(2) { animation-delay: 0.10s; }
        section.main .block-container > div:nth-child(3) { animation-delay: 0.18s; }
        section.main .block-container > div:nth-child(4) { animation-delay: 0.26s; }
        section.main .block-container > div:nth-child(5) { animation-delay: 0.34s; }
        section.main .block-container > div:nth-child(6) { animation-delay: 0.42s; }
        section.main .block-container > div:nth-child(7) { animation-delay: 0.50s; }
        section.main .block-container > div:nth-child(n+8) { animation-delay: 0.58s; }

        div[data-testid="stMetric"] { animation: springIn 0.6s cubic-bezier(0.34,1.56,0.64,1) both; }
        section[data-testid="stSidebar"] .stButton { animation: slideInLeft 0.4s ease both; }

        #MainMenu, footer {
            visibility: hidden;
        }

        [data-testid="stStatusWidget"],
        [data-testid="stDecoration"] {
            display: none !important;
        }

        /* Toolbar must stay alive because it contains the sidebar reopen button */
        [data-testid="stToolbar"] {
            display: flex !important;
            visibility: visible !important;
        }

        /* Sidebar reopen button */
        [data-testid="stExpandSidebarButton"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
        }

        .block-container { padding-top: 2rem; max-width: 1150px; }

        .stApp, .stApp p, .stApp span, .stApp label, .stApp li,
        .main .block-container { color: var(--text-main) !important; }
        .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--text-strong) !important; font-weight: 700 !important; }

        .stTextInput input, .stNumberInput input, .stDateInput input,
        div[data-baseweb="input"] input, textarea, div[data-baseweb="select"] > div {
            background-color: var(--input-bg) !important;
            color: var(--text-strong) !important;
            border: 1.5px solid var(--input-border) !important;
            border-radius: 16px !important;
            transition: border-color 0.25s ease, box-shadow 0.25s ease !important;
        }
        .stTextInput input:focus, div[data-baseweb="input"]:focus-within {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 4px var(--accent-ring) !important;
        }
        .stTextInput label, .stSelectbox label, .stNumberInput label {
            color: var(--text-muted) !important; font-weight: 700 !important; font-size: 0.82rem !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--surface) !important;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1.5px solid var(--border) !important;
            border-radius: 26px !important;
            box-shadow: 0 16px 50px var(--shadow) !important;
            transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.3s ease, border-color 0.3s ease;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            transform: translateY(-6px);
            border-color: rgba(167,139,250,0.5) !important;
            box-shadow: 0 28px 62px rgba(167,139,250,0.24) !important;
        }

        section[data-testid="stSidebar"] {
            background: var(--sidebar-bg);
            border-right: 1px solid var(--sidebar-border);
        }
        section[data-testid="stSidebar"] * { color: var(--text-main) !important; }
        section[data-testid="stSidebar"] .stButton > button {
            background: var(--surface);
            border: 1.5px solid var(--border-soft);
            color: var(--text-strong) !important;
            border-radius: 16px;
            text-align: left;
            font-weight: 700;
            padding: 0.65rem 0.95rem;
            transition: all 0.25s cubic-bezier(0.34,1.56,0.64,1);
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(167,139,250,0.2);
            border-color: rgba(167,139,250,0.55);
            transform: translateX(6px) scale(1.02);
            box-shadow: 0 0 20px var(--accent-glow);
        }

        .stButton > button {
            border-radius: 16px;
            border: 1.5px solid var(--border-strong);
            padding: 0.6rem 1.15rem;
            font-weight: 700;
            background: var(--surface-2);
            color: var(--text-strong) !important;
            transition: all 0.25s cubic-bezier(0.34,1.56,0.64,1);
        }
        .stButton > button:hover {
            border-color: var(--accent);
            color: var(--text-strong) !important;
            transform: translateY(-2px) scale(1.02);
            box-shadow: 0 12px 28px rgba(167,139,250,0.34);
        }
        button[kind="primary"] {
            background: linear-gradient(100deg,#a78bfa,#8b5cf6 45%,#5eead4) !important;
            border: none !important;
            color: #17123a !important;
            box-shadow: 0 12px 30px rgba(167,139,250,0.5) !important;
            background-size: 200% 100% !important;
            transition: background-position 0.5s ease, transform 0.25s ease, box-shadow 0.25s ease !important;
            font-weight: 800 !important;
        }
        button[kind="primary"]:hover {
            transform: translateY(-2px) scale(1.02);
            background-position: 100% 0 !important;
            box-shadow: 0 18px 42px rgba(167,139,250,0.65) !important;
        }

        div[data-testid="stMetric"] {
            background: var(--metric-bg);
            border: 1.5px solid var(--border);
            border-radius: 24px;
            padding: 18px 20px;
            box-shadow: 0 14px 40px var(--shadow-soft);
            transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.3s ease, border-color 0.3s ease;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-6px) scale(1.02);
            border-color: rgba(167,139,250,0.5);
            box-shadow: 0 24px 54px rgba(167,139,250,0.26);
        }
        div[data-testid="stMetricValue"] { color: var(--text-strong) !important; font-weight: 800; font-family: 'Baloo 2'; }
        div[data-testid="stMetricLabel"] { color: var(--text-muted) !important; font-weight: 700; }

        hr { margin: 1rem 0; border: none; border-top: 1px solid var(--border-soft); }
        div[data-testid="stDataFrame"] { border-radius: 18px; overflow: hidden; box-shadow: 0 8px 26px var(--shadow-soft); }

        .vt-hero { animation: springIn 0.6s cubic-bezier(0.34,1.56,0.64,1) both; }
        .vt-badge { animation: fadeIn 0.7s ease both; }
        .vt-bob { display:inline-block; animation: bob 3s ease-in-out infinite; }
        /* Keep Streamlit header available for sidebar controls */
        [data-testid="stHeader"] {
            display: block !important;
            visibility: visible !important;
            background: transparent !important;
        }

        /* Keep sidebar collapse/reopen controls visible */
        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
        }

        /* ============================================================
           LIGHT MODE OVERRIDES
           When the user's Streamlit base theme is "light", Streamlit
           sets the OS/app colour scheme so prefers-color-scheme: light
           matches. We re-map every theme token to a bright palette
           that keeps the same purple/teal brand identity but on a
           soft, readable light background.
           ============================================================ */
        @media (prefers-color-scheme: light) {
            :root {
                --app-bg-1: #ede9fe;
                --app-bg-2: #cffafe;
                --app-bg-3a: #f7f8ff;
                --app-bg-3b: #eef1fb;
                --blob-1: rgba(167,139,250,0.35);
                --blob-2: rgba(45,212,191,0.28);

                --text-main: #3b3f58;
                --text-strong: #1e2140;
                --text-muted: #6b7290;

                --surface: rgba(255,255,255,0.75);
                --surface-2: rgba(255,255,255,0.85);
                --border: rgba(30,33,64,0.10);
                --border-soft: rgba(30,33,64,0.08);
                --border-strong: rgba(30,33,64,0.12);
                --shadow: rgba(79,70,139,0.14);
                --shadow-soft: rgba(79,70,139,0.12);

                --input-bg: rgba(255,255,255,0.9);
                --input-border: rgba(30,33,64,0.14);

                --sidebar-bg: linear-gradient(180deg, #f3eefe 0%, #eaf0fb 60%, #e4f3f6 130%);
                --sidebar-border: rgba(30,33,64,0.08);

                --accent: #7c3aed;
                --accent-2: #0d9488;
                --accent-ring: rgba(124,58,237,0.18);
                --accent-glow: rgba(124,58,237,0.22);

                --hero-grad: linear-gradient(115deg,#8b5cf6 0%,#7c3aed 50%,#0e7490 120%);
                --hero-shadow: rgba(124,58,237,0.28);
                --on-hero: #ffffff;
                --on-hero-soft: rgba(255,255,255,0.92);

                --metric-bg: rgba(255,255,255,0.8);
            }

            /* Card hover accents read better slightly stronger on light */
            div[data-testid="stVerticalBlockBorderWrapper"]:hover {
                border-color: rgba(124,58,237,0.5) !important;
                box-shadow: 0 28px 62px rgba(124,58,237,0.18) !important;
            }
            section[data-testid="stSidebar"] .stButton > button:hover {
                background: rgba(124,58,237,0.12);
                border-color: rgba(124,58,237,0.4);
            }
            .stButton > button:hover {
                box-shadow: 0 12px 28px rgba(124,58,237,0.22);
            }
            div[data-testid="stMetric"]:hover {
                border-color: rgba(124,58,237,0.45);
                box-shadow: 0 24px 54px rgba(124,58,237,0.18);
            }
            /* Primary button text stays dark on the bright gradient */
            button[kind="primary"] { color: #1e1240 !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def hero(title, subtitle=""):
    sub = ""
    if subtitle:
        sub = ("<div style='color:var(--on-hero-soft);font-size:1.05rem;margin-top:6px;"
               "font-weight:600;'>" + subtitle + "</div>")
    st.markdown(
        "<div class='vt-hero' style='background:var(--hero-grad);"
        "padding:34px 38px;border-radius:32px;margin-bottom:24px;"
        "box-shadow:0 24px 60px var(--hero-shadow);position:relative;overflow:hidden;"
        "border:1.5px solid rgba(255,255,255,0.14);'>"
        "<div style='position:absolute;right:-30px;top:-30px;width:200px;height:200px;"
        "background:rgba(255,255,255,0.12);border-radius:50%;'></div>"
        "<div style='position:absolute;right:100px;bottom:-70px;width:140px;height:140px;"
        "background:rgba(94,234,212,0.22);border-radius:50%;'></div>"
        "<div style='color:var(--on-hero);font-size:2.1rem;font-weight:800;font-family:Baloo 2;position:relative;'>"
        + title + "</div>" + sub + "</div>",
        unsafe_allow_html=True,
    )

def stat_tile(label, value, color):
    st.markdown(
        "<div style='background:var(--surface);border:1.5px solid var(--border);"
        "border-radius:24px;padding:20px 22px;box-shadow:0 14px 40px var(--shadow-soft);"
        "position:relative;overflow:hidden;'>"
        "<div style='position:absolute;right:-16px;top:-16px;width:74px;height:74px;"
        "border-radius:50%;background:" + color + "40;filter:blur(4px);'></div>"
        "<div style='font-size:2.1rem;font-weight:800;color:var(--text-strong);line-height:1;font-family:Baloo 2;'>"
        + str(value) + "</div>"
        "<div style='color:var(--text-muted);font-size:0.85rem;font-weight:700;margin-top:8px;'>" + label + "</div></div>",
        unsafe_allow_html=True,
    )

if "page" not in st.session_state:
    st.session_state.page = "login"

RECORDS_PATH = os.path.join("data", "health_records.json")

USERS_PATH = Path(__file__).resolve().parent.parent / "data" / "users.json"

def load_records():
    if not os.path.exists(RECORDS_PATH):
        return []
    try:
        with open(RECORDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return data

def clean_records(records):
    good, errors = [], []
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            errors.append("Record " + str(i + 1) + " is not valid and was skipped.")
            continue
        metric = str(r.get("metric", "")).strip()
        unit = str(r.get("unit", "")).strip()
        if not metric:
            errors.append("Record " + str(i + 1) + " has no metric name and was skipped.")
            continue
        try:
            value = float(r.get("value", None))
        except (TypeError, ValueError):
            errors.append("Record " + str(i + 1) + " (" + metric + ") has an invalid value and was skipped.")
            continue
        parsed = parse_date(r.get("date", ""))
        if parsed is None:
            errors.append("Record " + str(i + 1) + " (" + metric + ") has an invalid date and was skipped.")
            continue
        rec = {"metric": metric, "value": value, "unit": unit, "date": parsed}
        for f in ("username", "user", "owner", "name"):
            if f in r:
                rec[f] = str(r[f]).strip()
        good.append(rec)
    return good, errors

def parse_date(raw):
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(raw).strip(), fmt).date()
        except ValueError:
            continue
    return None

def current_user():
    for key in ("username", "user", "current_user"):
        val = st.session_state.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""

def display_name():
    for key in ("name", "full_name", "display_name", "first_name"):
        val = st.session_state.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    username = current_user()
    if not username:
        return ""
    cleaned = username.replace(".", " ").replace("_", " ").replace("-", " ")
    words = []
    for w in cleaned.split():
        w = w.rstrip("0123456789")
        if w:
            words.append(w.capitalize())
    return " ".join(words) if words else username

def records_for_user(records, user):
    if not user:
        return records
    fields = ("username", "user", "owner")
    tagged = [r for r in records if any(f in r for f in fields)]
    if not tagged:
        return records
    mine = []
    for r in records:
        for f in fields:
            if f in r and str(r[f]).strip() == user:
                mine.append(r)
                break
    return mine

def build_trends(records):
    by_metric = {}
    for r in records:
        by_metric.setdefault(r["metric"], []).append(r)
    trends = []
    for metric, items in by_metric.items():
        items = sorted(items, key=lambda x: x["date"])
        values = [i["value"] for i in items]
        dates = [i["date"] for i in items]
        unit = items[-1]["unit"]
        direction, severity, note = summarise(values, unit)
        trends.append({
            "metric": metric, "unit": unit, "values": values, "dates": dates,
            "latest": values[-1], "direction": direction,
            "severity": severity, "note": note,
        })
    return trends

def summarise(values, unit):
    if len(values) < 2:
        return ("unknown", "info", "Only one reading available - not enough to show a trend.")
    change = values[-1] - values[0]
    spread = max(abs(v) for v in values) or 1.0
    if abs(change) / spread < 0.05:
        direction = "stable"
    elif change > 0:
        direction = "rising"
    else:
        direction = "falling"
    ratio = abs(change) / (abs(values[0]) or 1.0)
    if direction == "rising" and ratio >= 0.30:
        severity = "important"
    elif ratio >= 0.15:
        severity = "watch"
    else:
        severity = "info"
    sign = "+" if change > 0 else ""
    note = ("Changed from " + str(values[0]) + " to " + str(values[-1]) + " " + unit
            + " (" + sign + str(round(change, 2)) + " " + unit + ") across "
            + str(len(values)) + " readings.")
    return direction, severity, note

SEVERITY_STYLE = {
    "info": {"color": "#5eead4", "bg": "rgba(94,234,212,0.15)", "label": "Normal"},
    "watch": {"color": "#fcd34d", "bg": "rgba(252,211,77,0.15)", "label": "Watch"},
    "important": {"color": "#fda4af", "bg": "rgba(253,164,175,0.15)", "label": "Review"},
}

# Maps logic_manager's "decision" values onto this GUI's existing
# three-level severity badge, so no severity is ever recomputed here -
# it is read straight from what Logic Manager already decided when the
# record was saved.
DECISION_SEVERITY = {
    "ACCEPTED": "info",
    "FLAGGED": "watch",
    "URGENT": "important",
}

METRIC_UNITS = {
    "heart_rate": "bpm",
    "blood_pressure_systolic": "mmHg",
    "blood_pressure_diastolic": "mmHg",
    "blood_glucose": "mmol/L",
}


def records_for_current_user(records):
    """
    Filter Data Manager records down to the signed-in user's own
    records, the same way records_for_user() does for the old
    metric/value/unit records above - records saved before per-user
    tagging existed (no "username" key on any record) are shown to
    everyone rather than hidden.
    """
    user = current_user()
    if not user:
        return records
    tagged = [r for r in records if "username" in r]
    if not tagged:
        return records
    return [r for r in records if r.get("username") == user]


def latest_record_for_user(records):
    """
    Return the single most recent record (by its own report "date",
    never by upload order) for the Dashboard - or None if there are no
    records at all.

    Deliberately NOT built on build_record_trends(): that function
    looks backward through history for each metric's latest non-null
    value, which would silently show an OLDER report's reading if the
    newest report is missing that particular measurement. The
    Dashboard must show exactly what the latest report says, including
    "Not Available" where it says nothing.
    """
    latest = data_manager.get_latest_reports(records, limit=1)
    return latest[0] if latest else None


def build_record_trends(records):
    """
    Group Data Manager records (the shape logic_manager.process_ai_record()
    returns) by metric, for the History/Trends/Consultation screens to
    chart - without recomputing any business rule. Each point's
    severity comes straight from that record's own "decision" (already
    decided by logic_manager.py when the record was saved), and the
    direction/note for the latest point comes from that record's own
    "recent_changes" (also already decided by logic_manager.py) rather
    than being worked out again here.

    Args:
        records: list of dicts from data_manager.load_health_records(),
            already filtered to one user if relevant.

    Returns:
        A list of dicts: {"metric", "unit", "values", "dates", "latest",
        "direction", "severity", "note"} - one per metric that has at
        least one non-null reading, sorted oldest reading first.
    """
    by_metric = {}

    for record in sorted(records, key=lambda r: r.get("date") or ""):
        metrics = record.get("metrics", {})
        decision = record.get("decision", "ACCEPTED")
        severity = DECISION_SEVERITY.get(decision, "info")
        recent_changes_by_metric = {
            change["metric"]: change["feedback"]
            for change in record.get("recent_changes", [])
        }

        for metric_key, value in metrics.items():
            if value is None:
                continue
            label = logic_manager.METRIC_LABELS.get(metric_key, metric_key)
            by_metric.setdefault(metric_key, {"label": label, "points": []})
            by_metric[metric_key]["points"].append({
                "date": record.get("date"),
                "value": value,
                "severity": severity,
                "feedback": recent_changes_by_metric.get(label),
            })

    trends = []
    for metric_key, info in by_metric.items():
        points = info["points"]
        values = [p["value"] for p in points]
        dates = [p["date"] for p in points]
        latest_point = points[-1]

        # Direction is read directly from the numbers, not guessed by
        # searching the feedback text - that text now also covers
        # classification-change wording ("changed from severe to
        # normal"), which doesn't contain the words "increased"/
        # "decreased" at all.
        if len(values) >= 2:
            if values[-1] > values[-2]:
                direction = "rising"
            elif values[-1] < values[-2]:
                direction = "falling"
            else:
                direction = "stable"
        else:
            direction = "unknown"

        if latest_point["feedback"]:
            note = latest_point["feedback"]
        elif len(values) >= 2:
            note = f"{len(values)} readings recorded; no significant change since the last visit."
        else:
            note = "Insufficient historical data for comparison."

        trends.append({
            "metric": info["label"],
            "unit": METRIC_UNITS.get(metric_key, ""),
            "values": values,
            "dates": dates,
            "latest": latest_point["value"],
            "direction": direction,
            "severity": latest_point["severity"],
            "note": note,
        })

    return trends


def build_multi_axis_trend_chart(records):
    """
    Build one combined, interactive trend chart for the Health Trends
    page, with an INDEPENDENT y-axis per measurement unit, so different
    scales (mmHg, bpm, mmol/L) are never forced onto one misleading
    shared scale. Built with Altair, which is already installed as a
    Streamlit dependency - no new charting library was needed: Altair's
    layered charts with resolve_scale(y="independent") give true
    multi-axis plots, plus built-in legends (via the color encoding)
    and hover tooltips, which is exactly what this page needs.

    Measurements that share a unit (systolic/diastolic blood pressure,
    both mmHg) share one y-axis and appear as two separately-coloured
    lines on it, so they stay individually identifiable; heart rate and
    blood glucose each get their own axis.

    Args:
        records: list of record dicts (the caller is expected to have
            already limited this to the latest N reports).

    Returns:
        An Altair chart ready for st.altair_chart(), or None if there
        is no plottable (dated, non-null) data at all.
    """
    # Each group gets its own axis, explicitly positioned: the first on
    # the left, the rest stacked on the right with increasing "offset"
    # (extra pixels pushed outward) so their tick labels sit in their
    # own vertical strip instead of overlapping each other - Altair/
    # Vega-Lite does NOT space out a 3rd+ independent axis automatically.
    axis_groups = [
        ("Blood Pressure (mmHg)", [
            ("blood_pressure_systolic", "Systolic BP"),
            ("blood_pressure_diastolic", "Diastolic BP"),
        ], "left", 0, "#5e35b1"),
        ("Heart Rate (bpm)", [("heart_rate", "Heart Rate")], "right", 0, "#d62728"),
        ("Blood Glucose (mmol/L)", [("blood_glucose", "Blood Glucose")], "right", 55, "#17becf"),
    ]

    rows = []
    for record in sorted(records, key=lambda r: r.get("date") or ""):
        record_date = record.get("date")
        if not record_date:
            continue  # cannot place an undated reading on a date axis
        metrics = record.get("metrics", {})
        for axis_title, members, _orient, _offset, _color in axis_groups:
            for metric_key, series_label in members:
                value = metrics.get(metric_key)
                if value is None:
                    continue  # never invent a value for a missing measurement
                rows.append({
                    "date": record_date,
                    "axis": axis_title,
                    "measurement": series_label,
                    "value": value,
                })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return None

    layers = []
    for axis_title, _members, orient, offset, axis_color in axis_groups:
        subset = df[df["axis"] == axis_title]
        if subset.empty:
            continue
        layers.append(
            alt.Chart(subset)
            .mark_line(point=True)
            .encode(
                x=alt.X(
                    "date:T",
                    title="Report Date",
                    axis=alt.Axis(format="%d %b %Y", labelAngle=-40),
                ),
                y=alt.Y(
                    "value:Q",
                    title=axis_title,
                    axis=alt.Axis(
                        orient=orient,
                        offset=offset,
                        titleColor=axis_color,
                        labelColor=axis_color,
                        tickColor=axis_color,
                    ),
                ),
                color=alt.Color("measurement:N", legend=alt.Legend(title="Measurement")),
                tooltip=[
                    alt.Tooltip("date:T", title="Date"),
                    alt.Tooltip("measurement:N", title="Measurement"),
                    alt.Tooltip("value:Q", title="Value"),
                ],
            )
        )

    if not layers:
        return None

    return (
        alt.layer(*layers)
        .resolve_scale(y="independent")
        .properties(title="Health Trends - Multiple Y-Axes", height=380)
        .interactive()
    )


def severity_badge(severity):
    s = SEVERITY_STYLE.get(severity, SEVERITY_STYLE["info"])
    return ("<span class='vt-badge' style='background:" + s["bg"] + ";color:" + s["color"]
            + ";padding:4px 13px;border-radius:999px;font-size:0.72rem;font-weight:700;"
            "border:1.5px solid " + s["color"] + "55;white-space:nowrap;'>"
            + s["label"] + "</span>")

def go(page):
    st.session_state.page = page
    st.rerun()

def sidebar_nav():
    with st.sidebar:
        st.markdown(
            "<div style='text-align:center;padding:14px 0 8px 0;'>"
            "<div class='vt-bob' style='font-size:2.6rem;'>🩺</div>"
            "<div style='font-size:1.55rem;font-weight:800;font-family:Baloo 2;"
            "background:linear-gradient(90deg,#a78bfa,#5eead4);-webkit-background-clip:text;"
            "-webkit-text-fill-color:transparent;'>PASSAY</div>"
            "<div style='font-size:0.72rem;opacity:0.65;'>Health history and consultation</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        name = display_name()
        if name:
            initial = name[0].upper()
            st.markdown(
                "<div style='display:flex;align-items:center;gap:10px;"
                "background:var(--surface-2);border:1.5px solid var(--border);"
                "border-radius:18px;padding:10px 12px;margin:10px 0 16px 0;'>"
                "<div style='width:40px;height:40px;border-radius:50%;background:"
                "linear-gradient(135deg,#a78bfa,#5eead4);display:flex;align-items:center;"
                "justify-content:center;font-weight:800;color:#17123a;box-shadow:0 0 18px rgba(167,139,250,0.55);'>"
                + initial + "</div>"
                "<div><div style='font-weight:800;font-size:0.95rem;color:var(--text-strong);'>" + name + "</div>"
                "<div style='font-size:0.72rem;opacity:0.6;'>Signed in</div></div></div>",
                unsafe_allow_html=True,
            )
        st.markdown("---")
        if st.button("Dashboard", use_container_width=True):
            go("dashboard")
        if st.button("Add Report", use_container_width=True):
            go("upload")
        if st.button("Health History", use_container_width=True):
            go("history")
        if st.button("Health Trends", use_container_width=True):
            go("trends")
        if st.button("Consultation", use_container_width=True):
            go("consultation")
        st.markdown("---")
        if st.button(
            "Log Out",
            use_container_width=True
        ):

            for key in list(
                st.session_state.keys()
        ):
                del st.session_state[key]

            st.session_state.page = "login"

            st.rerun()

# =========================================================
# INPUT VALIDATION
# =========================================================

USERNAME_PATTERN = re.compile(
    r"^[A-Za-z0-9_.-]{3,30}$"
)

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)

PASSWORD_ITERATIONS = 200_000

ALLOWED_FILE_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg"
}

MAX_PDF_SIZE_MB = 30
MAX_IMAGE_SIZE_MB = 10

def validate_username(username: str) -> str:

    username = username.strip()

    if not username:
        return "Please enter a username."

    if not USERNAME_PATTERN.fullmatch(username):
        return (
            "Username must be 3–30 characters and may only "
            "contain letters, numbers, '.', '_' or '-'."
        )

    return ""


def validate_email(email: str) -> str:

    email = email.strip()

    if not email:
        return "Please enter an email address."

    if not EMAIL_PATTERN.fullmatch(email):
        return "Please enter a valid email address."

    return ""


def validate_password(password: str) -> str:

    if not password:
        return "Please enter a password."

    if len(password) < 8:
        return "Password must contain at least 8 characters."

    if not any(character.isupper() for character in password):
        return "Password must contain at least one uppercase letter."

    if not any(character.islower() for character in password):
        return "Password must contain at least one lowercase letter."

    if not any(character.isdigit() for character in password):
        return "Password must contain at least one number."

    if not any(
        not character.isalnum()
        for character in password
    ):
        return "Password must contain at least one special character."

    return ""


def hash_password(
    password: str,
    salt_hex: str
) -> str:

    salt = bytes.fromhex(salt_hex)

    hashed_password = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS
    )

    return hashed_password.hex()

def load_accounts() -> dict:
    """
    Load registered accounts from the users JSON file.
    """

    if not USERS_PATH.exists():
        return {}

    try:

        with open(
            USERS_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            accounts = json.load(file)

        if isinstance(accounts, dict):
            return accounts

    except (
        json.JSONDecodeError,
        OSError
    ):
        pass

    return {}


def save_accounts(accounts: dict) -> None:
    """
    Save registered accounts permanently.
    """

    USERS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        USERS_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            accounts,
            file,
            indent=4
        )

def create_temporary_account(
    username: str,
    email: str,
    password: str
) -> tuple[bool, str]:
    """
    Create an account and save it permanently
    to data/users.json.

    Data Manager will take over this responsibility
    later during integration.
    """

    username = username.strip()
    email = email.strip().lower()

    username_key = username.lower()

    accounts = load_accounts()

    # Check duplicate username
    if username_key in accounts:

        return (
            False,
            "That username is already taken."
        )

    # Check duplicate email
    for account in accounts.values():

        if account.get(
            "email",
            ""
        ).lower() == email:

            return (
                False,
                "An account already exists "
                "with this email address."
            )

    # Create random salt for password hashing
    salt = secrets.token_hex(16)

    # Store HASH, not actual password
    accounts[username_key] = {
        "username": username,
        "email": email,
        "salt": salt,
        "password_hash": hash_password(
            password,
            salt
        )
    }

    save_accounts(
        accounts
    )

    return (
        True,
        "Account created successfully."
    )

def authenticate_temporary_account(
    username: str,
    password: str
) -> bool:

    username_key = username.strip().lower()

    accounts = load_accounts()

    account = accounts.get(username_key)

    if account is None:
        return False

    entered_hash = hash_password(
        password,
        account["salt"]
    )

    return hmac.compare_digest(
        entered_hash,
        account["password_hash"]
    )

def validate_uploaded_report(
    uploaded_file
) -> tuple[bool, str]:

    if uploaded_file is None:

        return False, "Please select a medical report."

    extension = (
        Path(uploaded_file.name)
        .suffix
        .lower()
    )

    if extension not in ALLOWED_FILE_EXTENSIONS:

        return (
            False,
            "Unsupported file format. "
            "Please upload PDF, PNG, JPG or JPEG."
        )

    file_bytes = uploaded_file.getvalue()

    if len(file_bytes) == 0:

        return False, "The selected file is empty."

    if extension == ".pdf":
        maximum_size_mb = MAX_PDF_SIZE_MB
    else:
        maximum_size_mb = MAX_IMAGE_SIZE_MB

    maximum_bytes = maximum_size_mb * 1024 * 1024

    if len(file_bytes) > maximum_bytes:
        return (
            False,
            f"File is too large. Maximum size is "
            f"{maximum_size_mb} MB for this file type."
        )

    if extension == ".pdf":

        if not file_bytes.startswith(b"%PDF-"):

            return (
                False,
                "This file does not appear to be a valid PDF."
            )

    elif extension == ".png":

        if not file_bytes.startswith(
            b"\x89PNG\r\n\x1a\n"
        ):

            return (
                False,
                "This file does not appear to be a valid PNG image."
            )

    elif extension in {
        ".jpg",
        ".jpeg"
    }:

        if not file_bytes.startswith(
            b"\xff\xd8\xff"
        ):

            return (
                False,
                "This file does not appear to be a valid JPEG image."
            )

    return True, ""


def show_login():

    left, mid, right = st.columns([1, 1.4, 1])

    with mid:

        st.markdown(
            "<div class='vt-hero' style='text-align:center;margin-top:2.5rem;'>"
            "<div class='vt-bob' style='font-size:3.8rem;'>🩺</div>"
            "<h1 style='margin:0;font-size:2.7rem;"
            "background:linear-gradient(90deg,#a78bfa,#5eead4);"
            "-webkit-background-clip:text;"
            "-webkit-text-fill-color:transparent;'>"
            "PASSAY"
            "</h1>"
            "<p style='color:var(--text-muted);'>"
            "Track your health over time and prepare for your next appointment."
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        with st.container(border=True):

            st.subheader("Welcome back")

            username = st.text_input(
                "Username",
                key="login_username"
            )

            password = st.text_input(
                "Password",
                type="password",
                key="login_password"
            )

            if st.button(
                "Log In",
                type="primary",
                use_container_width=True
            ):

                if not username.strip():

                    st.error(
                        "Please enter your username."
                    )

                elif not password:

                    st.error(
                        "Please enter your password."
                    )

                elif not authenticate_temporary_account(
                    username,
                    password
                ):

                    st.error(
                        "Incorrect username or password."
                    )

                else:

                    accounts = load_accounts()

                    account = accounts[
                        username.strip().lower()
                    ]

                    st.session_state.username = account[
                        "username"
                    ]

                    st.session_state.email = account[
                        "email"
                    ]

                    go("dashboard")

            st.caption(
                "Don't have an account?"
            )

            if st.button(
                "Create Account",
                use_container_width=True
            ):

                go("register")

def show_register():

    left, mid, right = st.columns([1, 1.4, 1])

    with mid:

        # Keep the same PASSAY visual style
        st.markdown(
            "<div class='vt-hero' style='text-align:center;margin-top:2rem;'>"
            "<div class='vt-bob' style='font-size:3rem;'>🩺</div>"
            "<h1 style='margin:0;"
            "background:linear-gradient(90deg,#a78bfa,#5eead4);"
            "-webkit-background-clip:text;"
            "-webkit-text-fill-color:transparent;'>"
            "Create Account"
            "</h1>"
            "<p style='color:var(--text-muted);'>"
            "Create your secure PASSAY profile."
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        with st.container(border=True):

            username = st.text_input(
                "Username",
                key="register_username"
            )

            email = st.text_input(
                "Email",
                placeholder="name@example.com",
                key="register_email"
            )

            password = st.text_input(
                "Password",
                type="password",
                key="register_password"
            )

            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
                key="register_confirm_password"
            )

            st.caption(
                "Password must contain at least 8 characters, "
                "including an uppercase letter, a lowercase "
                "letter, a number and a special character."
            )

            if st.button(
                "Create Account",
                type="primary",
                use_container_width=True
            ):

                # Check username
                username_error = validate_username(
                    username
                )

                # Check email
                email_error = validate_email(
                    email
                )

                # Check password strength
                password_error = validate_password(
                    password
                )

                if username_error:

                    st.error(
                        username_error
                    )

                elif email_error:

                    st.error(
                        email_error
                    )

                elif password_error:

                    st.error(
                        password_error
                    )

                elif password != confirm_password:

                    st.error(
                        "Passwords do not match."
                    )

                else:

                    created, message = (
                        create_temporary_account(
                            username,
                            email,
                            password
                        )
                    )

                    if created:

                        st.success(
                            "Account created successfully."
                        )

                        st.info(
                            "Your account is ready. "
                            "Return to Login to continue."
                        )

                    else:

                        st.error(
                            message
                        )

            if st.button(
                "Back to Login",
                use_container_width=True
            ):

                go("login")

def show_dashboard():
    name = display_name()
    hero("Dashboard", ("Welcome back, " + name + "!") if name else "Your health overview")

    # Loaded through the Data Manager - never read the JSON file here.
    all_records = data_manager.load_health_records()
    my_records = records_for_current_user(all_records)

    if not my_records:
        with st.container(border=True):
            st.markdown("### No records yet")
            st.write("You have not added any medical records. Getting started:")
            st.markdown("1. Add a medical report - a blood test, check-up or prescription reading.")
            st.markdown("2. Review your history - each measurement charted over time.")
            st.markdown("3. Prepare for a consultation - a one-page summary for your doctor.")
            st.write("")
            if st.button("Add your first record", type="primary"):
                go("upload")
        return

    # The Dashboard shows the LATEST report's own vitals only - never a
    # fuller consultation summary (that lives exclusively on the
    # Consultation page) and never an older report's value standing in
    # for a measurement the latest report doesn't have.
    latest_record = latest_record_for_user(my_records)
    latest_metrics = latest_record.get("metrics", {}) if latest_record else {}
    is_flagged = bool(latest_record and latest_record.get("requires_doctor_review"))

    c1, c2, c3 = st.columns(3)
    with c1:
        stat_tile("Reports on file", len(my_records), "#a78bfa")
    with c2:
        stat_tile("Latest report", latest_record.get("date", "Unknown") if latest_record else "-", "#5eead4")
    with c3:
        stat_tile("Flagged for review", "Yes" if is_flagged else "No", "#fda4af" if is_flagged else "#5eead4")

    st.write("")

    if st.button("+ Add Medical Report", type="primary"):
        go("upload")

    st.write("")
    st.subheader("Latest vitals")

    vital_fields = [
        ("heart_rate", "Heart Rate", "bpm"),
        ("blood_pressure_systolic", "Systolic BP", "mmHg"),
        ("blood_pressure_diastolic", "Diastolic BP", "mmHg"),
        ("blood_glucose", "Blood Glucose", "mmol/L"),
    ]

    for metric_key, label, unit in vital_fields:
        value = latest_metrics.get(metric_key)
        with st.container(border=True):
            cols = st.columns([3, 2])
            with cols[0]:
                st.markdown("*" + label + "*")
            with cols[1]:
                if value is None:
                    st.markdown(
                        "<div style='text-align:right;color:var(--text-muted);"
                        "font-weight:700;'>Not Available</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        "<div style='text-align:right;font-size:1.3rem;font-weight:800;"
                        "color:var(--text-strong);font-family:Baloo 2;'>"
                        + str(value) + " <span style='font-size:0.78rem;font-weight:600;"
                        "color:var(--text-muted);'>" + unit + "</span></div>",
                        unsafe_allow_html=True,
                    )

    if is_flagged:
        st.write("")
        st.markdown(
            severity_badge("important") + " &nbsp; "
            "<span style='color:var(--text-muted);font-size:0.88rem;'>"
            "One or more measurements in your latest report need review - "
            "see the Consultation page for details.</span>",
            unsafe_allow_html=True,
        )

def show_upload():

    hero(
        "Add a Medical Report",
        "Upload one medical report for validation "
        "before health information is extracted."
    )

    with st.container(border=True):

        st.subheader("Report details")

        # -------------------------------------------------
        # DATE INFORMATION
        # -------------------------------------------------

        date_type = st.radio(
            "What date information is available on the report?",
            [
                "Exact date",
                "Year only"
            ],
            horizontal=True
        )

        if date_type == "Exact date":

            st.markdown("**Report Date**")

            current_date = date.today()

            col1, col2, col3 = st.columns(3)

            # -------------------------
            # YEAR
            # -------------------------

            with col1:

                selected_year = st.selectbox(
                    "Year",
                    options=list(
                        range(
                            current_date.year,
                            1939,
                            -1
                        )
                    )
                )

            # -------------------------
            # MONTH
            # -------------------------

            months = {
                "January": 1,
                "February": 2,
                "March": 3,
                "April": 4,
                "May": 5,
                "June": 6,
                "July": 7,
                "August": 8,
                "September": 9,
                "October": 10,
                "November": 11,
                "December": 12
            }

            with col2:

                # If current year is selected,
                # do not allow future months.
                if selected_year == current_date.year:

                    available_months = list(
                        months.keys()
                    )[:current_date.month]
                    # The current month is the last entry in the
                    # truncated list above - default the widget to it
                    # instead of st.selectbox's own default (index 0,
                    # i.e. always "January"), which is what silently
                    # dated every report "January 1st" regardless of
                    # when it was actually uploaded.
                    default_month_index = len(available_months) - 1

                else:

                    available_months = list(
                        months.keys()
                    )
                    default_month_index = 0

                selected_month_name = st.selectbox(
                    "Month",
                    options=available_months,
                    index=default_month_index
                )

                selected_month = months[
                    selected_month_name
                ]

            # -------------------------
            # DAY
            # -------------------------

            days_in_month = calendar.monthrange(
                selected_year,
                selected_month
            )[1]

            # Prevent future days if current
            # month/year are selected.
            if (
                selected_year == current_date.year
                and selected_month == current_date.month
            ):

                maximum_day = current_date.day
                # Today's day is the last (maximum) option in this
                # case - default to it instead of st.selectbox's own
                # default (index 0, i.e. always day 1).
                default_day_index = maximum_day - 1

            else:

                maximum_day = days_in_month
                default_day_index = 0

            with col3:

                selected_day = st.selectbox(
                    "Day",
                    options=list(
                        range(
                            1,
                            maximum_day + 1
                        )
                    ),
                    index=default_day_index
                )

            report_date = date(
                selected_year,
                selected_month,
                selected_day
            )

            report_date_info = {
                "date_precision": "exact",
                "date": report_date.isoformat(),
                "year": report_date.year
            }

        else:

            current_year = date.today().year

            report_year = st.number_input(
                "Report Year",
                min_value=1940,
                max_value=current_year,
                value=current_year,
                step=1
            )

            report_date_info = {
                "date_precision": "year",
                "date": None,
                "year": int(report_year)
            }

        # -------------------------------------------------
        # FILE UPLOAD
        # -------------------------------------------------

        uploaded_files = st.file_uploader(
            "Medical Report",
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True
        )

        st.caption(
            "Upload one PDF, one image, or multiple image pages "
            "belonging to the same medical report. "
            "Supported formats: PDF, PNG, JPG and JPEG. "
            "Maximum size: 30 MB for one PDF and 10 MB per image."
        )

        extensions = [
            Path(file.name).suffix.lower()
            for file in uploaded_files
        ]

        pdf_count = extensions.count(".pdf")

        image_extensions = {
            ".png",
            ".jpg",
            ".jpeg"
        }

        # More than one PDF is not allowed
        if pdf_count > 1:

            st.error(
                "Please upload only one PDF at a time."
            )

        # PDF cannot be mixed with images
        elif (
            pdf_count == 1
            and len(uploaded_files) > 1
        ):

            st.error(
                "Please upload either one PDF OR one or more "
                "image pages of the same report, not both."
            )

        # Multiple files must all be images
        elif (
            len(uploaded_files) > 1
            and not all(
                extension in image_extensions
                for extension in extensions
            )
        ):

            st.error(
                "Multiple-file upload is only supported "
                "for PNG, JPG or JPEG images."
            )

        # -------------------------------------------------
        # SHOW SELECTED FILES
        # -------------------------------------------------

        if uploaded_files:

            st.markdown(
                f"**{len(uploaded_files)} file(s) selected**"
            )

            for number, uploaded_file in enumerate(
                uploaded_files,
                start=1
            ):

                size_kb = uploaded_file.size / 1024

                st.write(
                    f"**{number}. {uploaded_file.name}**"
                )

                st.caption(
                    f"File size: {size_kb:.1f} KB"
                )

        st.write("")



        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if st.button(
            "Validate Medical Report",
            type="primary",
            use_container_width=True
        ):

            if not uploaded_files:

                st.error(
                    "Please select a medical report."
                )

            else:

                extensions = [
                    Path(file.name).suffix.lower()
                    for file in uploaded_files
                ]

                pdf_count = extensions.count(".pdf")

                image_extensions = {
                    ".png",
                    ".jpg",
                    ".jpeg"
                }

                # More than one PDF is not one report submission
                if pdf_count > 1:

                    st.error(
                        "Please upload only one PDF at a time."
                    )

                # PDF cannot be mixed with image pages
                elif (
                    pdf_count == 1
                    and len(uploaded_files) > 1
                ):

                    st.error(
                        "Please upload either one PDF OR multiple "
                        "image pages of the same report, not both."
                    )

                # Multiple files must all be images
                elif (
                    len(uploaded_files) > 1
                    and not all(
                        extension in image_extensions
                        for extension in extensions
                    )
                ):

                    st.error(
                        "Multiple-file upload is only supported "
                        "for PNG, JPG or JPEG pages belonging "
                        "to the same medical report."
                    )

                else:

                    validated_pages = []
                    errors = []

                    for uploaded_file in uploaded_files:

                        valid, message = validate_uploaded_report(
                            uploaded_file
                        )

                        if valid:

                            validated_pages.append(
                                {
                                    "name": uploaded_file.name,
                                    "mime_type": uploaded_file.type,
                                    "size": uploaded_file.size,
                                    "bytes": uploaded_file.getvalue()
                                }
                            )

                        else:

                            errors.append(
                                f"{uploaded_file.name}: {message}"
                            )

                    if errors:

                        st.error(
                            "Some uploaded files failed validation:"
                        )

                        for error in errors:
                            st.write(f"• {error}")

                    else:

                        st.session_state["validated_report"] = {
                            "date_precision":
                                report_date_info["date_precision"],

                            "date":
                                report_date_info["date"],

                            "year":
                                report_date_info["year"],

                            "pages":
                                validated_pages
                        }

                        st.success(
                            "Medical report passed input validation."
                        )

                        if len(validated_pages) > 1:

                            st.info(
                                f"{len(validated_pages)} image pages "
                                "were recognised as one medical report."
                            )

                        else:

                            st.info(
                                "The report is ready for AI analysis."
                            )

    # -------------------------------------------------
    # AI / LOGIC / DATA MANAGER PIPELINE
    # -------------------------------------------------
    # Only shown once a report has passed input validation above.
    # This block never talks to Gemini directly, never applies
    # business-rule thresholds itself, and never writes JSON itself -
    # it only calls into io_manager -> ai_manager -> logic_manager ->
    # data_manager, exactly as the architecture requires.

    validated = st.session_state.get("validated_report")

    if validated:

        st.write("")

        with st.container(border=True):

            st.subheader("AI Analysis")

            first_page = validated["pages"][0]

            st.caption(
                f"Ready to analyse: {first_page['name']}"
                + (
                    f" (plus {len(validated['pages']) - 1} more page(s) - "
                    "only the first page is sent for AI analysis today)"
                    if len(validated["pages"]) > 1
                    else ""
                )
            )

            if st.button(
                "Analyze with AI",
                type="primary",
                use_container_width=True,
            ):

                with st.spinner("Sending report to the AI Manager..."):
                    ai_extracted = io_manager.process_uploaded_report(
                        first_page["bytes"], first_page["mime_type"]
                    )

                    all_records = data_manager.load_health_records()
                    user_records = records_for_current_user(all_records)

                    processed_record = logic_manager.process_ai_record(
                        ai_extracted, user_records
                    )

                if processed_record["decision"] == "REJECTED":

                    st.error(processed_record["recommended_action"])

                else:

                    record_to_save = dict(processed_record)
                    record_to_save["username"] = current_user()

                    # Decide the final report date. The AI Manager's own
                    # reading of the date PRINTED ON THE REPORT (via
                    # logic_manager's "ai_extracted_date") is preferred
                    # over the user's manual date-picker selection, since
                    # it reflects what the document itself actually says
                    # - the manual date is only a fallback for when
                    # Gemini could not confidently identify one (it is
                    # told to return null rather than guess).
                    ai_date = processed_record.get("ai_extracted_date")
                    if ai_date:
                        record_to_save["date"] = ai_date
                        date_source = "detected automatically from the report"
                    elif validated["date_precision"] == "exact" and validated["date"]:
                        record_to_save["date"] = validated["date"]
                        date_source = "the date you entered"
                    else:
                        date_source = (
                            "today's date - no report date could be "
                            "detected or entered"
                        )

                    # Archive the ORIGINAL uploaded file, byte-for-byte,
                    # separately from the extracted values above, and
                    # link the two via report_id. If this archiving step
                    # fails, the extracted health data is still saved
                    # below - losing the backup copy of the original
                    # file shouldn't also block the user's health data.
                    original_entry = data_manager.save_original_report(
                        file_bytes=first_page["bytes"],
                        original_filename=first_page["name"],
                        mime_type=first_page["mime_type"],
                        report_date=record_to_save.get("date"),
                        username=current_user(),
                    )
                    if original_entry:
                        record_to_save["report_id"] = original_entry["report_id"]
                    else:
                        st.warning(
                            "Your extracted results were processed, but the "
                            "original file could not be archived for Health "
                            "History."
                        )

                    saved = data_manager.save_record(record_to_save)

                    if not saved:
                        st.error(
                            "The report was processed but could not be "
                            "saved. Please try again."
                        )
                    else:
                        severity = DECISION_SEVERITY.get(
                            processed_record["decision"], "info"
                        )
                        st.markdown(
                            severity_badge(severity), unsafe_allow_html=True
                        )
                        st.success("Report processed and saved.")
                        st.caption(
                            f"Report date: {record_to_save.get('date', 'Unknown')} "
                            f"({date_source})."
                        )
                        st.write(processed_record["summary"])

                        extracted_metrics = processed_record["metrics"]
                        metric_rows = [
                            {
                                "Measurement": logic_manager.METRIC_LABELS.get(key, key),
                                "Value": (
                                    f"{value} {METRIC_UNITS.get(key, '')}".strip()
                                    if value is not None
                                    else "Not Available"
                                ),
                            }
                            for key, value in extracted_metrics.items()
                        ]
                        st.table(metric_rows)

                        del st.session_state["validated_report"]


def show_history():
    hero("Health History", "Every reading you have recorded, over time")

    # Give any record saved before record_id existed one now, so it can
    # be found and corrected below. A no-op write when nothing's missing.
    data_manager.backfill_record_ids()

    # Loaded through the Data Manager - never read the JSON file here.
    all_records = data_manager.load_health_records()
    my_records = records_for_current_user(all_records)

    if not my_records:
        with st.container(border=True):
            st.markdown("### Nothing to display yet")
            st.write("Once you add records, they appear here as a table and trend charts.")
        return

    trends = build_record_trends(my_records)

    st.subheader("All readings")
    rows = []
    for r in sorted(my_records, key=lambda r: r.get("date") or ""):
        metrics = r.get("metrics", {})
        rows.append({
            "Date": r.get("date", ""),
            "Decision": r.get("decision", ""),
            "Heart Rate (bpm)": metrics.get("heart_rate"),
            "Systolic (mmHg)": metrics.get("blood_pressure_systolic"),
            "Diastolic (mmHg)": metrics.get("blood_pressure_diastolic"),
            "Glucose (mmol/L)": metrics.get("blood_glucose"),
        })

    decisions = ["All"] + sorted({r["Decision"] for r in rows if r["Decision"]})
    chosen = st.selectbox("Filter by outcome", decisions)
    view = rows if chosen == "All" else [r for r in rows if r["Decision"] == chosen]
    st.dataframe(view, use_container_width=True, hide_index=True)

    csv_lines = ["Date,Decision,Heart Rate,Systolic,Diastolic,Glucose"]
    for r in view:
        csv_lines.append(",".join(str(r[k]) for k in
                          ("Date", "Decision", "Heart Rate (bpm)", "Systolic (mmHg)",
                           "Diastolic (mmHg)", "Glucose (mmol/L)")))
    st.download_button("Download history (CSV)",
                       data=chr(10).join(csv_lines).encode("utf-8"),
                       file_name="health_history.csv", mime="text/csv")

    # -------------------------------------------------
    # EDIT A REPORT DATE
    # -------------------------------------------------
    # Lets a user correct a record saved with the wrong date (e.g. an
    # upload form that defaulted incorrectly) without deleting or
    # recreating anything else about that record.
    with st.expander("Edit a report date"):
        st.caption(
            "If a report was saved with the wrong date, correct it here. "
            "Nothing else about the report changes."
        )

        sorted_records = sorted(my_records, key=lambda r: r.get("date") or "")
        record_options = {
            r["record_id"]: (
                f"{r.get('date', 'Unknown date')} - {r.get('decision', '')} "
                f"(heart rate {r.get('metrics', {}).get('heart_rate', 'Not Available')})"
            )
            for r in sorted_records
            if r.get("record_id")
        }

        if not record_options:
            st.caption("No editable records found.")
        else:
            selected_id = st.selectbox(
                "Select a report to correct",
                options=list(record_options.keys()),
                format_func=lambda rid: record_options[rid],
            )
            selected_record = next(
                (r for r in sorted_records if r.get("record_id") == selected_id), None
            )

            new_date = st.date_input("Correct report date", value=date.today())

            if st.button("Update Date"):
                if data_manager.update_record_date(selected_id, new_date.isoformat()):
                    st.success("Date updated.")
                    st.rerun()
                else:
                    st.error("Could not update this record's date. Please try again.")

            # Safe re-extraction: ask the AI Manager to re-read the date
            # off the ORIGINAL uploaded file (if one was archived for
            # this record), show what it found, and only apply it if
            # the user explicitly confirms - this never overwrites a
            # date on its own.
            original_entry = (
                data_manager.get_original_report_by_id(selected_record["report_id"])
                if selected_record and selected_record.get("report_id")
                else None
            )

            if original_entry:
                st.write("")
                if st.button("Detect date from original file with AI"):
                    with st.spinner("Asking the AI Manager to re-read the report date..."):
                        original_bytes = data_manager.get_original_report_bytes(
                            original_entry["stored_filename"]
                        )
                        ai_extracted = (
                            io_manager.process_uploaded_report(
                                original_bytes,
                                original_entry.get("mime_type", "application/pdf"),
                            )
                            if original_bytes
                            else None
                        )
                    detected_date = (ai_extracted or {}).get("report_date")
                    if detected_date:
                        st.session_state["detected_date_" + selected_id] = detected_date
                    else:
                        st.warning(
                            "The AI Manager could not confidently detect a "
                            "date from the original file."
                        )

                detected_key = "detected_date_" + selected_id
                if detected_key in st.session_state:
                    st.info(f"AI detected report date: {st.session_state[detected_key]}")
                    if st.button("Use this detected date"):
                        if data_manager.update_record_date(
                            selected_id, st.session_state[detected_key]
                        ):
                            del st.session_state[detected_key]
                            st.success("Date updated from AI detection.")
                            st.rerun()
                        else:
                            st.error(
                                "Could not update this record's date. "
                                "Please try again."
                            )
            else:
                st.caption(
                    "No original file is archived for this record, so "
                    "automatic AI date detection isn't available - "
                    "correct it manually above."
                )

    # -------------------------------------------------
    # ORIGINAL MEDICAL REPORTS
    # -------------------------------------------------
    # The actual uploaded files, byte-for-byte, kept forever regardless
    # of config.LATEST_REPORTS_LIMIT - that limit only affects Trends
    # and Consultation, never what stays visible here.
    st.divider()
    st.subheader("Original Medical Reports")

    original_reports = data_manager.list_original_reports(current_user())

    if not original_reports:
        st.caption("Original files you upload will be archived here.")
    else:
        for entry in original_reports:
            with st.container(border=True):
                cols = st.columns([2, 2, 2, 1])
                with cols[0]:
                    st.markdown(f"**Report date:** {entry.get('report_date') or 'Unknown'}")
                with cols[1]:
                    st.caption(f"Uploaded {entry.get('upload_date', '')}")
                with cols[2]:
                    st.caption(entry.get("filename", ""))
                with cols[3]:
                    file_bytes = data_manager.get_original_report_bytes(entry["stored_filename"])
                    if file_bytes:
                        st.download_button(
                            "Download",
                            data=file_bytes,
                            file_name=entry.get("filename") or entry["stored_filename"],
                            mime=entry.get("mime_type") or "application/octet-stream",
                            key="original_" + entry["report_id"],
                        )
                    else:
                        st.caption("File unavailable")

    st.divider()
    st.subheader("Trends over time")
    for t in trends:
        with st.container(border=True):
            cols = st.columns([3, 1])
            with cols[0]:
                st.markdown("*" + t["metric"] + "* &nbsp; " + severity_badge(t["severity"]),
                            unsafe_allow_html=True)
            with cols[1]:
                st.markdown("<div style='text-align:right;font-weight:800;font-size:1.2rem;color:var(--text-strong);'>"
                            + str(t["latest"]) + " <span style='font-size:0.78rem;font-weight:600;"
                            "color:var(--text-muted);'>" + t["unit"] + "</span></div>", unsafe_allow_html=True)
            if len(t["values"]) < 2:
                st.caption("Only one reading (" + str(t["values"][0]) + " " + t["unit"]
                           + ") - a chart needs at least two.")
            else:
                st.area_chart({t["metric"]: t["values"]}, height=200, color="#a78bfa")
            st.caption(t["note"])

def show_trends():

    hero(
        "Health Trends",
        "See how your recorded measurements "
        "have changed over time."
    )

    # Loaded through the Data Manager - never read the JSON file here.
    all_records = data_manager.load_health_records()
    my_records = records_for_current_user(all_records)

    # No records yet
    if not my_records:

        with st.container(
            border=True
        ):

            st.markdown(
                "### No trend data yet"
            )

            st.write(
                "Once medical records have been "
                "added, their measurements will "
                "appear here over time."
            )

            st.caption(
                "At least two readings for a metric "
                "are needed before a trend graph can "
                "be displayed."
            )

        return

    # Active trend analysis only uses the latest N report dates (see
    # config.LATEST_REPORTS_LIMIT) - Health History still shows every
    # report regardless, since it loads my_records directly, not this.
    recent_records = data_manager.get_latest_reports(my_records)

    # Grouped and classified by logic_manager's own stored evaluation -
    # not recomputed in this file. See build_record_trends().
    trends = build_record_trends(recent_records)

    st.caption(
        f"Based on your latest {len(recent_records)} report(s)"
        + (f" out of {len(my_records)} on file." if len(my_records) > len(recent_records) else ".")
    )

    st.subheader("Combined trend chart")

    combined_chart = build_multi_axis_trend_chart(recent_records)
    if combined_chart is not None:
        st.altair_chart(combined_chart, use_container_width=True)
        st.caption(
            "Blood pressure, heart rate, and blood glucose each use their "
            "own scale (right), so they are never compared on one "
            "misleading shared axis. Hover a point for its exact reading."
        )
    else:
        st.info("Not enough dated measurements yet to draw a combined chart.")

    st.divider()
    st.subheader(
        "Measurement details"
    )

    # Make one card/chart for each health metric
    for t in sorted(trends, key=lambda t: t["metric"]):

        with st.container(
            border=True
        ):

            top_left, top_right = (
                st.columns(
                    [3, 1]
                )
            )

            with top_left:

                st.markdown(
                    f"### {t['metric']}"
                )

                st.caption(
                    f"{len(t['values'])} reading(s)"
                )

            with top_right:

                st.markdown(
                    "<div style='"
                    "text-align:right;"
                    "font-size:1.45rem;"
                    "font-weight:800;"
                    "color:var(--text-strong);"
                    "font-family:Baloo 2;'>"
                    + str(t["latest"])
                    + " "
                    + "<span style='"
                    "font-size:0.8rem;"
                    "color:var(--text-muted);'>"
                    + t["unit"]
                    + "</span>"
                    + "</div>",
                    unsafe_allow_html=True
                )

            # Need at least two readings for a graph
            if len(t["values"]) >= 2:

                chart_data = (
                    pd.DataFrame(
                        {
                            "Date": t["dates"],
                            t["metric"]: t["values"],
                        }
                    )
                    .set_index(
                        "Date"
                    )
                )

                st.line_chart(
                    chart_data,
                    height=250,
                    color="#a78bfa"
                )

            else:

                st.info(
                    "Add another reading to "
                    "display a trend graph."
                )

            st.markdown(
                severity_badge(t["severity"]),
                unsafe_allow_html=True,
            )

            st.caption(t["note"])

def show_consultation():
    who = display_name() or "you"
    hero("Consultation Report", "A summary to bring to your appointment. Not medical advice.")

    # Loaded through the Data Manager - never read the JSON file here.
    all_records = data_manager.load_health_records()
    my_records = records_for_current_user(all_records)

    if not my_records:
        with st.container(border=True):
            st.markdown("### No report to prepare")
            st.write("Add some medical records first, then generate your summary here.")
        return

    # Consultation preparation only uses the latest N report dates (see
    # config.LATEST_REPORTS_LIMIT) - Health History still shows every
    # report regardless, since it loads my_records directly, not this.
    recent_records = data_manager.get_latest_reports(my_records)
    trends = build_record_trends(recent_records)

    # The AI Manager only ever phrases logic_manager's own already-
    # decided findings into plain language here - it never classifies
    # anything itself (see ai_manager.generate_consultation_narrative()).
    # If Gemini is unavailable or returns nothing usable, this is None
    # and build_report() below falls back to the deterministic,
    # rule-based summary rather than fabricating an AI result.
    latest_processed_record = latest_record_for_user(recent_records)
    ai_narrative = None
    if latest_processed_record:
        with st.spinner("Preparing your consultation summary..."):
            ai_narrative = io_manager.generate_consultation_summary(latest_processed_record)

    report = build_report(who, trends, ai_narrative)

    with st.container(border=True):
        st.markdown("<div style='border-bottom:1px solid var(--border);padding-bottom:12px;margin-bottom:8px;'>"
                    "<div style='font-size:1.5rem;font-weight:800;color:var(--text-strong);font-family:Baloo 2;'>Consultation summary</div>"
                    "<div style='color:var(--text-muted);font-size:0.9rem;'>For " + who + " on "
                    + date.today().strftime("%d %B %Y") + "</div></div>", unsafe_allow_html=True)

        if report["summary"]:
            st.markdown("##### Summary")
            st.write(report["summary"])

        if report["trends"]:
            st.markdown("##### Notable changes over time")
            for t in report["trends"]:
                st.markdown(
                    "<div style='display:flex;justify-content:space-between;align-items:center;"
                    "padding:10px 14px;background:var(--surface);border:1px solid var(--border-soft);"
                    "border-radius:16px;margin-bottom:7px;'>"
                    "<div><b style='color:var(--text-strong);'>" + t["metric"] + "</b><br>"
                    "<span style='color:var(--text-muted);font-size:0.85rem;'>" + t["note"] + "</span></div>"
                    "<div>" + severity_badge(t["severity"]) + "</div></div>",
                    unsafe_allow_html=True,
                )

        if report["notes"]:
            st.markdown("##### In plain language")
            for n in report["notes"]:
                st.markdown("- " + n)

        if report["questions"]:
            st.markdown("##### Questions to ask your doctor")
            for q in report["questions"]:
                st.markdown("- " + q)

    st.write("")
    pdf_bytes, err = build_pdf(who, report)
    report_date = latest_processed_record.get("date") if latest_processed_record else None

    if err:
        st.info("PDF not available (" + err + "). A text download is offered instead.")
        st.download_button("Download report (TXT)",
                           data=report_text(who, report).encode("utf-8"),
                           file_name="consultation_report.txt", mime="text/plain")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("Download consultation report (PDF)", data=pdf_bytes,
                               file_name="consultation_report.pdf",
                               mime="application/pdf", type="primary")
        with col2:
            if st.button("Save to Summary History"):
                saved_entry = data_manager.save_consultation_pdf(
                    pdf_bytes=pdf_bytes,
                    report_date=report_date,
                    username=current_user(),
                )
                if saved_entry:
                    st.success("Saved to Summary History below.")
                else:
                    st.error("Could not save this summary. Please try again.")

    # -------------------------------------------------
    # SUMMARY HISTORY
    # -------------------------------------------------
    st.divider()
    st.subheader("Summary History")

    saved_summaries = data_manager.list_consultation_pdfs(current_user())

    if not saved_summaries:
        st.caption("Summaries you save will appear here for later download.")
    else:
        for entry in saved_summaries:
            with st.container(border=True):
                st.markdown(f"\U0001F4C4 **{entry['filename']}**")
                cols = st.columns([2, 2, 1])
                with cols[0]:
                    st.caption(f"Report date: {entry.get('report_date') or 'Unknown'}")
                with cols[1]:
                    st.caption(f"Generated {entry.get('generated_at', '')}")
                with cols[2]:
                    pdf_data = data_manager.get_consultation_pdf_bytes(entry["filename"])
                    if pdf_data:
                        st.download_button(
                            "Download",
                            data=pdf_data,
                            file_name=entry["filename"],
                            mime="application/pdf",
                            key="summary_" + entry["filename"],
                        )
                    else:
                        st.caption("File unavailable")

def build_report(who, trends, ai_narrative=None):
    """
    ai_narrative, if provided, is Gemini's own plain-language phrasing
    of logic_manager's already-decided findings (see
    ai_manager.generate_consultation_narrative()) and is used as the
    summary text as-is. If it is None - Gemini was unavailable or
    returned nothing usable - this falls back to a summary built
    purely from trends' own rule-based classifications, so a missing
    AI result is never silently presented as if it had succeeded.
    """
    questions, notes = [], []
    if trends:
        rising = [t["metric"] for t in trends if t["direction"] == "rising"]
        if rising:
            questions.append("Are the upward trends in " + ", ".join(rising)
                             + " something I should act on?")
        notes.append("Trends are based only on the records provided and are not a "
                     "diagnosis. Please confirm with your doctor.")

    if ai_narrative:
        summary = ai_narrative
    elif trends:
        rising = [t["metric"] for t in trends if t["direction"] == "rising"]
        summary = ("Readings increased over time for: " + ", ".join(rising) + "."
                   ) if rising else ""
    else:
        summary = ""

    return {"summary": summary, "questions": questions, "notes": notes, "trends": trends}

def report_text(who, report):
    lines = ["Consultation Report for " + who,
             "Generated " + date.today().isoformat(),
             "========================================", ""]
    if report["summary"]:
        lines += ["SUMMARY", report["summary"], ""]
    if report["trends"]:
        lines += ["NOTABLE CHANGES OVER TIME"]
        for t in report["trends"]:
            lines.append("- " + t["metric"] + ": " + str(t["latest"]) + " " + t["unit"]
                         + "  (" + t["note"] + ")")
        lines.append("")
    if report["notes"]:
        lines += ["IN PLAIN LANGUAGE"] + ["- " + n for n in report["notes"]] + [""]
    if report["questions"]:
        lines += ["QUESTIONS TO ASK YOUR DOCTOR"] + ["- " + q for q in report["questions"]]
    return chr(10).join(lines)

def build_pdf(who, report):
    try:
        from fpdf import FPDF
    except Exception:
        return None, "PDF library (fpdf2) is not installed"

    def safe(txt):
        return str(txt).encode("latin-1", "replace").decode("latin-1")

    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 15)
        pdf.cell(0, 10, safe("Consultation Report - " + who), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, safe("Generated " + date.today().isoformat()), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        def section(title):
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_x(pdf.l_margin)
            pdf.cell(0, 8, safe(title), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10.5)

        def para(text):
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 6, safe(text))

        if report["summary"]:
            section("Summary")
            para(report["summary"])
            pdf.ln(2)
        if report["trends"]:
            section("Notable changes over time")
            for t in report["trends"]:
                para("- " + t["metric"] + ": " + str(t["latest"])
                     + " " + t["unit"] + " (" + t["note"] + ")")
            pdf.ln(2)
        if report["notes"]:
            section("In plain language")
            for n in report["notes"]:
                para("- " + n)
            pdf.ln(2)
        if report["questions"]:
            section("Questions to ask your doctor")
            for q in report["questions"]:
                para("- " + q)

        out = pdf.output()
        if isinstance(out, (bytes, bytearray)):
            return bytes(out), None
        return out.encode("latin-1"), None
    except Exception as exc:
        return None, "Could not generate PDF: " + str(exc)

inject_css()

if st.session_state.page in ("login", "register"):

    # Create the sidebar from the beginning so Streamlit
    # remembers its initial expanded state.
    with st.sidebar:
        st.markdown("")

    # Hide the sidebar while the user is on Login/Register.
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            display: none !important;
        }

        [data-testid="stExpandSidebarButton"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.page == "login":
        show_login()
    else:
        show_register()

else:

    sidebar_nav()

    if st.session_state.page == "dashboard":
        show_dashboard()

    elif st.session_state.page == "upload":
        show_upload()

    elif st.session_state.page == "history":
        show_history()

    elif st.session_state.page == "trends":
        show_trends()

    elif st.session_state.page == "consultation":
        show_consultation()

    else:
        show_dashboard()