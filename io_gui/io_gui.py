import streamlit as st
import json
import os
import re
import calendar
import hashlib
import hmac
import secrets

from pathlib import Path
from datetime import datetime, date

import pandas as pd

st.set_page_config(
    page_title="VitalTrack - Health History and Consultation Prep",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="locked",
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

        .stApp {
            background:
              radial-gradient(1000px 600px at 8% -5%, #2a1958 0%, transparent 55%),
              radial-gradient(900px 600px at 100% 0%, #10344a 0%, transparent 55%),
              linear-gradient(180deg, #0a0e1e 0%, #0e1226 100%);
            overflow-x: hidden;
        }
        .stApp:before, .stApp:after {
            content: ""; position: fixed; border-radius: 50%; filter: blur(90px); z-index: 0; pointer-events: none;
        }
        .stApp:before {
            width: 560px; height: 560px;
            background: radial-gradient(circle at 30% 30%, rgba(167,139,250,0.5), transparent 70%);
            top: -140px; left: -100px; animation: floaty 18s ease-in-out infinite;
        }
        .stApp:after {
            width: 500px; height: 500px;
            background: radial-gradient(circle at 60% 40%, rgba(94,234,212,0.4), transparent 70%);
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

        [data-testid="stToolbar"],
        [data-testid="stStatusWidget"],
        [data-testid="stDecoration"] {
            display: none !important;
        }

        /* Keep Streamlit header available so sidebar can be reopened */
        [data-testid="stHeader"] {
            background: transparent !important;
        }

        /* Keep sidebar collapse / reopen control visible */
        [data-testid="collapsedControl"] {
            display: flex !important;
            visibility: visible !important;
        }
        .block-container { padding-top: 2rem; max-width: 1150px; }

        .stApp, .stApp p, .stApp span, .stApp label, .stApp li,
        .main .block-container { color: #cdd6ee !important; }
        .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: #f4f6ff !important; font-weight: 700 !important; }

        .stTextInput input, .stNumberInput input, .stDateInput input,
        div[data-baseweb="input"] input, textarea, div[data-baseweb="select"] > div {
            background-color: rgba(255,255,255,0.05) !important;
            color: #f4f6ff !important;
            border: 1.5px solid rgba(255,255,255,0.14) !important;
            border-radius: 16px !important;
            transition: border-color 0.25s ease, box-shadow 0.25s ease !important;
        }
        .stTextInput input:focus, div[data-baseweb="input"]:focus-within {
            border-color: #a78bfa !important;
            box-shadow: 0 0 0 4px rgba(167,139,250,0.22) !important;
        }
        .stTextInput label, .stSelectbox label, .stNumberInput label {
            color: #a6b0d0 !important; font-weight: 700 !important; font-size: 0.82rem !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255,255,255,0.05) !important;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1.5px solid rgba(255,255,255,0.12) !important;
            border-radius: 26px !important;
            box-shadow: 0 16px 50px rgba(0,0,0,0.4) !important;
            transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.3s ease, border-color 0.3s ease;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            transform: translateY(-6px);
            border-color: rgba(167,139,250,0.5) !important;
            box-shadow: 0 28px 62px rgba(167,139,250,0.24) !important;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #120a2e 0%, #131a38 60%, #16224a 130%);
            border-right: 1px solid rgba(255,255,255,0.06);
        }
        section[data-testid="stSidebar"] * { color: #cdd6ee !important; }
        section[data-testid="stSidebar"] .stButton > button {
            background: rgba(255,255,255,0.05);
            border: 1.5px solid rgba(255,255,255,0.09);
            color: #eef1ff !important;
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
            box-shadow: 0 0 20px rgba(167,139,250,0.3);
        }

        .stButton > button {
            border-radius: 16px;
            border: 1.5px solid rgba(255,255,255,0.14);
            padding: 0.6rem 1.15rem;
            font-weight: 700;
            background: rgba(255,255,255,0.06);
            color: #eef1ff !important;
            transition: all 0.25s cubic-bezier(0.34,1.56,0.64,1);
        }
        .stButton > button:hover {
            border-color: #a78bfa;
            color: #ffffff !important;
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
            background: rgba(255,255,255,0.05);
            border: 1.5px solid rgba(255,255,255,0.12);
            border-radius: 24px;
            padding: 18px 20px;
            box-shadow: 0 14px 40px rgba(0,0,0,0.36);
            transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.3s ease, border-color 0.3s ease;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-6px) scale(1.02);
            border-color: rgba(167,139,250,0.5);
            box-shadow: 0 24px 54px rgba(167,139,250,0.26);
        }
        div[data-testid="stMetricValue"] { color: #f4f6ff !important; font-weight: 800; font-family: 'Baloo 2'; }
        div[data-testid="stMetricLabel"] { color: #a6b0d0 !important; font-weight: 700; }

        hr { margin: 1rem 0; border: none; border-top: 1px solid rgba(255,255,255,0.08); }
        div[data-testid="stDataFrame"] { border-radius: 18px; overflow: hidden; box-shadow: 0 8px 26px rgba(0,0,0,0.36); }

        .vt-hero { animation: springIn 0.6s cubic-bezier(0.34,1.56,0.64,1) both; }
        .vt-badge { animation: fadeIn 0.7s ease both; }
        .vt-bob { display:inline-block; animation: bob 3s ease-in-out infinite; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def hero(title, subtitle=""):
    sub = ""
    if subtitle:
        sub = ("<div style='color:rgba(255,255,255,0.9);font-size:1.05rem;margin-top:6px;"
               "font-weight:600;'>" + subtitle + "</div>")
    st.markdown(
        "<div class='vt-hero' style='background:linear-gradient(115deg,#2a1958 0%,#6d28d9 50%,#0e7490 120%);"
        "padding:34px 38px;border-radius:32px;margin-bottom:24px;"
        "box-shadow:0 24px 60px rgba(109,40,217,0.42);position:relative;overflow:hidden;"
        "border:1.5px solid rgba(255,255,255,0.14);'>"
        "<div style='position:absolute;right:-30px;top:-30px;width:200px;height:200px;"
        "background:rgba(255,255,255,0.12);border-radius:50%;'></div>"
        "<div style='position:absolute;right:100px;bottom:-70px;width:140px;height:140px;"
        "background:rgba(94,234,212,0.22);border-radius:50%;'></div>"
        "<div style='color:#ffffff;font-size:2.1rem;font-weight:800;font-family:Baloo 2;position:relative;'>"
        + title + "</div>" + sub + "</div>",
        unsafe_allow_html=True,
    )

def stat_tile(label, value, color):
    st.markdown(
        "<div style='background:rgba(255,255,255,0.05);border:1.5px solid rgba(255,255,255,0.12);"
        "border-radius:24px;padding:20px 22px;box-shadow:0 14px 40px rgba(0,0,0,0.36);"
        "position:relative;overflow:hidden;'>"
        "<div style='position:absolute;right:-16px;top:-16px;width:74px;height:74px;"
        "border-radius:50%;background:" + color + "40;filter:blur(4px);'></div>"
        "<div style='font-size:2.1rem;font-weight:800;color:#f4f6ff;line-height:1;font-family:Baloo 2;'>"
        + str(value) + "</div>"
        "<div style='color:#a6b0d0;font-size:0.85rem;font-weight:700;margin-top:8px;'>" + label + "</div></div>",
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
            "-webkit-text-fill-color:transparent;'>VitalTrack</div>"
            "<div style='font-size:0.72rem;opacity:0.65;'>Health history and consultation</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        name = display_name()
        if name:
            initial = name[0].upper()
            st.markdown(
                "<div style='display:flex;align-items:center;gap:10px;"
                "background:rgba(255,255,255,0.06);border:1.5px solid rgba(255,255,255,0.12);"
                "border-radius:18px;padding:10px 12px;margin:10px 0 16px 0;'>"
                "<div style='width:40px;height:40px;border-radius:50%;background:"
                "linear-gradient(135deg,#a78bfa,#5eead4);display:flex;align-items:center;"
                "justify-content:center;font-weight:800;color:#17123a;box-shadow:0 0 18px rgba(167,139,250,0.55);'>"
                + initial + "</div>"
                "<div><div style='font-weight:800;font-size:0.95rem;color:#f4f6ff;'>" + name + "</div>"
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

MAX_FILE_SIZE_MB = 10


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

    username = username.strip()
    email = email.strip().lower()

    username_key = username.lower()

    accounts = load_accounts()

    if username_key in accounts:
        return False, "That username is already taken."

    for account in accounts.values():

        if account["email"].lower() == email:

            return (
                False,
                "An account already exists with this email address."
            )

    salt = secrets.token_hex(16)

    accounts[username_key] = {
        "username": username,
        "email": email,
        "salt": salt,
        "password_hash": hash_password(
            password,
            salt
        )
    }

    save_accounts(accounts)

    return True, "Account created successfully."

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

    maximum_bytes = (
        MAX_FILE_SIZE_MB
        * 1024
        * 1024
    )

    if len(file_bytes) > maximum_bytes:

        return (
            False,
            f"File is too large. Maximum size is "
            f"{MAX_FILE_SIZE_MB} MB."
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

MAX_FILE_SIZE_MB = 10


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


def create_temporary_account(
    username: str,
    email: str,
    password: str
) -> tuple[bool, str]:

    username = username.strip()
    email = email.strip().lower()

    username_key = username.lower()

    accounts = load_accounts()

    if username_key in accounts:
        return False, "That username is already taken."

    for account in accounts.values():

        if account["email"].lower() == email:

            return (
                False,
                "An account already exists with this email address."
            )

    salt = secrets.token_hex(16)

    accounts[username_key] = {
        "username": username,
        "email": email,
        "salt": salt,
        "password_hash": hash_password(
            password,
            salt
        )
    }

    save_accounts(accounts)

    return True, "Account created successfully."


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

    maximum_bytes = (
        MAX_FILE_SIZE_MB
        * 1024
        * 1024
    )

    if len(file_bytes) > maximum_bytes:

        return (
            False,
            f"File is too large. Maximum size is "
            f"{MAX_FILE_SIZE_MB} MB."
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
            "VitalTrack"
            "</h1>"
            "<p style='color:#a6b0d0;'>"
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

        # Keep the same VitalTrack visual style
        st.markdown(
            "<div class='vt-hero' style='text-align:center;margin-top:2rem;'>"
            "<div class='vt-bob' style='font-size:3rem;'>🩺</div>"
            "<h1 style='margin:0;"
            "background:linear-gradient(90deg,#a78bfa,#5eead4);"
            "-webkit-background-clip:text;"
            "-webkit-text-fill-color:transparent;'>"
            "Create Account"
            "</h1>"
            "<p style='color:#a6b0d0;'>"
            "Create your secure VitalTrack profile."
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

    records = load_records()
    good, errors = clean_records(records)
    if errors:
        with st.expander(str(len(errors)) + " record(s) had problems and were skipped"):
            for e in errors:
                st.markdown("- " + e)

    my_records = records_for_user(good, current_user())

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

    trends = build_trends(my_records)
    flagged = [t for t in trends if t["severity"] in ("watch", "important")]

    c1, c2, c3 = st.columns(3)
    with c1:
        stat_tile("Records", len(my_records), "#a78bfa")
    with c2:
        stat_tile("Metrics tracked", len(trends), "#5eead4")
    with c3:
        stat_tile("Flagged for review", len(flagged), "#fda4af")

    st.write("")
    st.subheader("Latest measurements")
    for t in trends:
        with st.container(border=True):
            cols = st.columns([3, 1.4, 1])
            with cols[0]:
                st.markdown("*" + t["metric"] + "*")
                st.caption(t["note"])
            with cols[1]:
                st.markdown("<div style='font-size:1.4rem;font-weight:800;color:#f4f6ff;font-family:Baloo 2;'>"
                            + str(t["latest"]) + " <span style='font-size:0.8rem;font-weight:600;"
                            "color:#a6b0d0;'>" + t["unit"] + "</span></div>", unsafe_allow_html=True)
            with cols[2]:
                st.markdown(severity_badge(t["severity"]), unsafe_allow_html=True)

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

                else:

                    available_months = list(
                        months.keys()
                    )

                selected_month_name = st.selectbox(
                    "Month",
                    options=available_months
                )

                selected_month = months[
                    selected_month_name
                ]

            # -------------------------
            # DAY
            # -------------------------

            import calendar

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

            else:

                maximum_day = days_in_month

            with col3:

                selected_day = st.selectbox(
                    "Day",
                    options=list(
                        range(
                            1,
                            maximum_day + 1
                        )
                    )
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
            type=[
                "pdf",
                "png",
                "jpg",
                "jpeg"
            ],
            accept_multiple_files=True
        )

        st.caption(
            "Upload one PDF, one image, or multiple image pages "
            "belonging to the same medical report. "
            "Supported formats: PDF, PNG, JPG and JPEG. "
            "Maximum file size: 10 MB per file."
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
                                "The report is ready for AI analysis. "
                                "AI extraction will be connected when "
                                "the AI Manager is integrated."
                            )

def show_history():
    hero("Health History", "Every reading you have recorded, over time")

    records = load_records()
    good, errors = clean_records(records)
    if errors:
        with st.expander(str(len(errors)) + " record(s) had problems and were skipped"):
            for e in errors:
                st.markdown("- " + e)

    my_records = records_for_user(good, current_user())

    if not my_records:
        with st.container(border=True):
            st.markdown("### Nothing to display yet")
            st.write("Once you add records, they appear here as a table and trend charts.")
        return

    trends = build_trends(my_records)

    st.subheader("All readings")
    rows = []
    for r in sorted(my_records, key=lambda x: x["date"]):
        rows.append({
            "Date": r["date"].isoformat(),
            "Metric": r["metric"],
            "Value": r["value"],
            "Unit": r["unit"],
        })

    metrics = ["All metrics"] + sorted({r["Metric"] for r in rows})
    chosen = st.selectbox("Filter by metric", metrics)
    view = rows if chosen == "All metrics" else [r for r in rows if r["Metric"] == chosen]
    st.dataframe(view, use_container_width=True, hide_index=True)

    csv_lines = ["Date,Metric,Value,Unit"]
    for r in view:
        csv_lines.append(r["Date"] + "," + r["Metric"] + "," + str(r["Value"]) + "," + r["Unit"])
    st.download_button("Download history (CSV)",
                       data=chr(10).join(csv_lines).encode("utf-8"),
                       file_name="health_history.csv", mime="text/csv")

    st.divider()
    st.subheader("Trends over time")
    for t in trends:
        with st.container(border=True):
            cols = st.columns([3, 1])
            with cols[0]:
                st.markdown("*" + t["metric"] + "* &nbsp; " + severity_badge(t["severity"]),
                            unsafe_allow_html=True)
            with cols[1]:
                st.markdown("<div style='text-align:right;font-weight:800;font-size:1.2rem;color:#f4f6ff;'>"
                            + str(t["latest"]) + " <span style='font-size:0.78rem;font-weight:600;"
                            "color:#a6b0d0;'>" + t["unit"] + "</span></div>", unsafe_allow_html=True)
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

    # Load existing records
    records = load_records()

    # Remove malformed records
    good, errors = clean_records(
        records
    )

    if errors:

        with st.expander(
            str(len(errors))
            + " record(s) had problems "
            + "and were skipped"
        ):

            for error in errors:

                st.markdown(
                    "- " + error
                )

    # Only show current user's records
    my_records = records_for_user(
        good,
        current_user()
    )

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

    # Group records by measurement
    grouped = {}

    for record in my_records:

        metric = record[
            "metric"
        ]

        grouped.setdefault(
            metric,
            []
        ).append(
            record
        )

    st.subheader(
        "Measurements over time"
    )

    # Make one card/chart for each health metric
    for metric, items in sorted(
        grouped.items()
    ):

        items = sorted(
            items,
            key=lambda item: item[
                "date"
            ]
        )

        with st.container(
            border=True
        ):

            latest = items[-1]

            top_left, top_right = (
                st.columns(
                    [3, 1]
                )
            )

            with top_left:

                st.markdown(
                    f"### {metric}"
                )

                st.caption(
                    f"{len(items)} reading(s)"
                )

            with top_right:

                st.markdown(
                    "<div style='"
                    "text-align:right;"
                    "font-size:1.45rem;"
                    "font-weight:800;"
                    "color:#f4f6ff;"
                    "font-family:Baloo 2;'>"
                    + str(latest["value"])
                    + " "
                    + "<span style='"
                    "font-size:0.8rem;"
                    "color:#a6b0d0;'>"
                    + latest["unit"]
                    + "</span>"
                    + "</div>",
                    unsafe_allow_html=True
                )

            # Need at least two readings for a graph
            if len(items) >= 2:

                chart_data = (
                    pd.DataFrame(
                        {
                            "Date": [
                                item["date"]
                                for item in items
                            ],

                            metric: [
                                item["value"]
                                for item in items
                            ]
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

            st.caption(
                "Trend classification such as "
                "increasing, decreasing, stable or "
                "significant change will later be "
                "provided by the Logic Manager."
            )

def show_consultation():
    who = display_name() or "you"
    hero("Consultation Report", "A summary to bring to your appointment. Not medical advice.")

    records = load_records()
    good, errors = clean_records(records)
    if errors:
        with st.expander(str(len(errors)) + " record(s) had problems and were skipped"):
            for e in errors:
                st.markdown("- " + e)

    my_records = records_for_user(good, current_user())

    if not my_records:
        with st.container(border=True):
            st.markdown("### No report to prepare")
            st.write("Add some medical records first, then generate your summary here.")
        return

    trends = build_trends(my_records)
    report = build_report(who, trends)

    with st.container(border=True):
        st.markdown("<div style='border-bottom:1px solid rgba(255,255,255,0.10);padding-bottom:12px;margin-bottom:8px;'>"
                    "<div style='font-size:1.5rem;font-weight:800;color:#f4f6ff;font-family:Baloo 2;'>Consultation summary</div>"
                    "<div style='color:#a6b0d0;font-size:0.9rem;'>For " + who + " on "
                    + date.today().strftime("%d %B %Y") + "</div></div>", unsafe_allow_html=True)

        if report["summary"]:
            st.markdown("##### Summary")
            st.write(report["summary"])

        if report["trends"]:
            st.markdown("##### Notable changes over time")
            for t in report["trends"]:
                st.markdown(
                    "<div style='display:flex;justify-content:space-between;align-items:center;"
                    "padding:10px 14px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.09);"
                    "border-radius:16px;margin-bottom:7px;'>"
                    "<div><b style='color:#f4f6ff;'>" + t["metric"] + "</b><br>"
                    "<span style='color:#a6b0d0;font-size:0.85rem;'>" + t["note"] + "</span></div>"
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
    if err:
        st.info("PDF not available (" + err + "). A text download is offered instead.")
        st.download_button("Download report (TXT)",
                           data=report_text(who, report).encode("utf-8"),
                           file_name="consultation_report.txt", mime="text/plain")
    else:
        st.download_button("Download consultation report (PDF)", data=pdf_bytes,
                           file_name="consultation_report.pdf",
                           mime="application/pdf", type="primary")

def build_report(who, trends):
    summary, questions, notes = "", [], []
    if trends:
        rising = [t["metric"] for t in trends if t["direction"] == "rising"]
        if rising:
            summary = "Readings increased over time for: " + ", ".join(rising) + "."
            questions.append("Are the upward trends in " + ", ".join(rising)
                             + " something I should act on?")
        notes.append("Trends are based only on the records provided and are not a "
                     "diagnosis. Please confirm with your doctor.")
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