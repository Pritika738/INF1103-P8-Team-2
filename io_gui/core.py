"""
core.py

Shared foundations for the PASSAY GUI: the single AIManager/DataManager
services, session helpers, record filtering, trend + chart builders,
display formatters, auth + quick-login PIN, and shared constants.
Imported by every screen module (from core import *).
"""

import json
import os
import re
import sys
import hashlib
import hmac
import secrets
from pathlib import Path
from datetime import datetime, date, timedelta

import pandas as pd
import altair as alt

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import io_manager
import logic_manager
import data_manager
import ai_manager
from user import User

# One AIManager, DataManager and LogicManager for the whole app.
ai_service = ai_manager.AIManager(ai_manager.GeminiClient())
data_service = data_manager.DataManager.create()
logic_service = logic_manager.LogicManager.default()

if "page" not in st.session_state:
    st.session_state.page = "login"

RECORDS_PATH = os.path.join("data", "health_records.json")

# --- Shared display constants ---
SEVERITY_STYLE = {
    "info": {"color": "#5eead4", "bg": "rgba(94,234,212,0.15)", "label": "Normal"},
    "watch": {"color": "#fcd34d", "bg": "rgba(252,211,77,0.15)", "label": "Watch"},
    "important": {"color": "#fda4af", "bg": "rgba(253,164,175,0.15)", "label": "Review"},
}
DECISION_SEVERITY = {"ACCEPTED": "info", "FLAGGED": "watch", "URGENT": "important"}
METRIC_UNITS = {
    "heart_rate": "bpm",
    "blood_pressure_systolic": "mmHg",
    "blood_pressure_diastolic": "mmHg",
    "blood_glucose": "mmol/L",
}

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
PASSWORD_ITERATIONS = 200_000
ALLOWED_FILE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_PDF_SIZE_MB = 30
MAX_IMAGE_SIZE_MB = 10
BLOOD_GROUP_OPTIONS = ["Not set", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
DOSAGE_UNIT_OPTIONS = [
    "", "mg", "mcg", "g", "ml", "L", "IU", "%",
    "units", "tablet(s)", "drop(s)", "puff(s)", "patch(es)",
]
PIN_PATTERN = re.compile(r"^\d{4}$")
PIN_MAX_ATTEMPTS = 5

# Self-logged vitals services + constants.
vitals_validator = logic_manager.ManualVitalsValidator()
vitals_logic = logic_manager.LogicManager.default()
VITAL_COLUMNS = [
    ("blood_pressure_systolic", "Systolic BP", "mmHg"),
    ("blood_pressure_diastolic", "Diastolic BP", "mmHg"),
    ("heart_rate", "Heart Rate", "bpm"),
    ("blood_glucose", "Blood Glucose", "mmol/L"),
]
VITALS_PERIODS = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "All time": None}

# --- Small shared UI pieces ---
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

def severity_badge(severity):
    s = SEVERITY_STYLE.get(severity, SEVERITY_STYLE["info"])
    return ("<span class='vt-badge' style='background:" + s["bg"] + ";color:" + s["color"]
            + ";padding:4px 13px;border-radius:999px;font-size:0.72rem;font-weight:700;"
            "border:1.5px solid " + s["color"] + "55;white-space:nowrap;'>"
            + s["label"] + "</span>")

def go(page):
    if page != st.session_state.get("page"):
        # Leaving a page discards its unsaved edits, so it reloads from the
        # database next time (used by the Medical Profile row editor).
        st.session_state.pop("profile_draft", None)
    st.session_state.page = page
    st.rerun()

# --- Session / user helpers ---
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

def records_for_current_user(records):
    user = current_user()
    if not user:
        return records
    tagged = [r for r in records if "username" in r]
    if not tagged:
        return records
    return [r for r in records if r.get("username") == user]

def latest_record_for_user(records):
    latest = data_service.get_latest_reports(records, limit=1)
    return latest[0] if latest else None

# --- Trend + chart builders ---
def build_record_trends(records):
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
                "date": record.get("date"), "value": value,
                "severity": severity, "feedback": recent_changes_by_metric.get(label),
            })
    trends = []
    for metric_key, info in by_metric.items():
        points = info["points"]
        values = [p["value"] for p in points]
        dates = [p["date"] for p in points]
        latest_point = points[-1]
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
            "metric": info["label"], "unit": METRIC_UNITS.get(metric_key, ""),
            "values": values, "dates": dates, "latest": latest_point["value"],
            "direction": direction, "severity": latest_point["severity"], "note": note,
        })
    return trends

def build_multi_axis_trend_chart(records):
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
            continue
        metrics = record.get("metrics", {})
        for axis_title, members, _o, _of, _c in axis_groups:
            for metric_key, series_label in members:
                value = metrics.get(metric_key)
                if value is None:
                    continue
                rows.append({"date": record_date, "axis": axis_title,
                             "measurement": series_label, "value": value})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return None
    report_dates = sorted(set(df["date"]))
    layers = []
    for axis_title, _m, orient, offset, axis_color in axis_groups:
        subset = df[df["axis"] == axis_title]
        if subset.empty:
            continue
        layers.append(
            alt.Chart(subset).mark_line(point=True).encode(
                x=alt.X("date:T", title="Report Date",
                        axis=alt.Axis(format="%d %b %Y", labelAngle=0, values=report_dates)),
                y=alt.Y("value:Q", title=axis_title,
                        axis=alt.Axis(orient=orient, offset=offset, titleColor=axis_color,
                                      labelColor=axis_color, tickColor=axis_color)),
                color=alt.Color("measurement:N", legend=alt.Legend(title="Measurement")),
                tooltip=[alt.Tooltip("date:T", title="Date", format="%d %b %Y"),
                         alt.Tooltip("measurement:N", title="Measurement"),
                         alt.Tooltip("value:Q", title="Value")],
            )
        )
    if not layers:
        return None
    return (alt.layer(*layers).resolve_scale(y="independent")
            .properties(title="Health Trends - Multiple Y-Axes", height=380).interactive())

# --- Display formatters ---
def _format_report_date(raw_date):
    if not raw_date:
        return "Date Unavailable"
    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return "Date Unavailable"

def _format_summary_timestamp(raw_iso):
    if not raw_iso:
        return "Unknown"
    try:
        timestamp = datetime.fromisoformat(raw_iso)
    except ValueError:
        return "Unknown"
    hour_12 = timestamp.strftime("%I").lstrip("0") or "12"
    return (timestamp.strftime("%d %b %Y, ")
            + f"{hour_12}:{timestamp.strftime('%M')} {timestamp.strftime('%p')}")

def _format_measurement(value, unit):
    if value is None:
        return "-"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value} {unit}".strip()

def build_readings_table_rows(records):
    sorted_records = sorted(records, key=lambda r: r.get("date") or "", reverse=True)
    rows = []
    for record in sorted_records:
        metrics = record.get("metrics", {})
        rows.append({
            "Report Date": _format_report_date(record.get("date")),
            "Heart Rate": _format_measurement(metrics.get("heart_rate"), "bpm"),
            "Systolic BP": _format_measurement(metrics.get("blood_pressure_systolic"), "mmHg"),
            "Diastolic BP": _format_measurement(metrics.get("blood_pressure_diastolic"), "mmHg"),
            "Blood Glucose": _format_measurement(metrics.get("blood_glucose"), "mmol/L"),
        })
    return rows

def vitals_in_period(entries, days):
    if days is None:
        return list(entries)
    cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
    return [e for e in entries if (e.get("date") or "") >= cutoff]

def build_vitals_table_rows(entries):
    newest_first = sorted(entries, key=lambda e: (e.get("date") or "", e.get("time") or ""), reverse=True)
    rows = []
    for entry in newest_first:
        metrics = entry.get("metrics", {})
        row = {"Measured On": _format_report_date(entry.get("date")), "Time": entry.get("time") or "-"}
        for key, label, unit in VITAL_COLUMNS:
            row[label] = _format_measurement(metrics.get(key), unit)
        row["Outcome"] = entry.get("decision", "")
        row["Note"] = entry.get("note", "")
        rows.append(row)
    return rows

def build_vitals_chart(entries, members, title, unit):
    rows = []
    for entry in entries:
        if not entry.get("date"):
            continue
        when = entry["date"] + " " + (entry.get("time") or "00:00")
        for key, label in members:
            value = entry.get("metrics", {}).get(key)
            if value is not None:
                rows.append({"when": when, "measurement": label, "value": value})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["when"] = pd.to_datetime(df["when"], errors="coerce")
    df = df.dropna(subset=["when"])
    if df.empty:
        return None
    return (alt.Chart(df).mark_line(point=True).encode(
        x=alt.X("when:T", title="Measured", axis=alt.Axis(format="%d %b", labelAngle=0)),
        y=alt.Y("value:Q", title=f"{title} ({unit})", scale=alt.Scale(zero=False)),
        color=alt.Color("measurement:N", legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip("when:T", title="Measured", format="%d %b %Y, %H:%M"),
                 alt.Tooltip("measurement:N", title="Measurement"),
                 alt.Tooltip("value:Q", title=unit)],
    ).properties(height=260).interactive())

# --- Auth ---
def validate_username(username: str) -> str:
    username = username.strip()
    if not username:
        return "Please enter a username."
    if not USERNAME_PATTERN.fullmatch(username):
        return ("Username must be 3-30 characters and may only "
                "contain letters, numbers, '.', '_' or '-'.")
    return ""

def validate_password(password: str) -> str:
    if not password:
        return "Please enter a password."
    if len(password) < 8:
        return "Password must contain at least 8 characters."
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in password):
        return "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number."
    if not any(not c.isalnum() for c in password):
        return "Password must contain at least one special character."
    return ""

def hash_password(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS).hex()

def create_temporary_account(username: str, password: str):
    user = User(username)
    if data_service.find_user(user.username) is not None:
        return (False, "That username is already taken.")
    salt = secrets.token_hex(16)
    credentials = {"salt": salt, "password_hash": hash_password(password, salt)}
    if not data_service.save_account(user, credentials):
        return (False, "Your account could not be saved. Please try again.")
    return (True, "Account created successfully.")

def authenticate_temporary_account(username: str, password: str) -> User | None:
    """The matching User if the username and password are correct, else None."""
    user = data_service.find_user(username)
    if user is None:
        return None
    account = data_service.get_account(user)
    entered_hash = hash_password(password, account["salt"])
    if hmac.compare_digest(entered_hash, account["password_hash"]):
        return user
    return None

# --- Quick-login PIN ---
def validate_pin(pin: str) -> str:
    pin = (pin or "").strip()
    if not pin:
        return "Please enter a PIN."
    if not PIN_PATTERN.fullmatch(pin):
        return "PIN must be exactly 4 digits."
    return ""

def hash_pin(pin: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, PASSWORD_ITERATIONS).hex()

def user_has_pin(username: str) -> bool:
    user = data_service.find_user(username)
    account = data_service.get_account(user) if user else None
    return bool(account and account.get("pin_hash") and account.get("pin_salt"))

def set_user_pin(username: str, pin: str) -> bool:
    user = data_service.find_user(username)
    if user is None:
        return False
    account = data_service.get_account(user)
    pin_salt = secrets.token_hex(16)
    account["pin_salt"] = pin_salt
    account["pin_hash"] = hash_pin(pin, pin_salt)
    return data_service.save_account(user, account)

def remove_user_pin(username: str) -> bool:
    user = data_service.find_user(username)
    if user is None:
        return False
    account = data_service.get_account(user)
    account.pop("pin_salt", None)
    account.pop("pin_hash", None)
    return data_service.save_account(user, account)

def authenticate_with_pin(username: str, pin: str) -> User | None:
    """The matching User if the username and PIN are correct, else None."""
    user = data_service.find_user(username)
    if user is None:
        return None
    account = data_service.get_account(user)
    if not (account.get("pin_hash") and account.get("pin_salt")):
        return None
    entered_hash = hash_pin(pin, account["pin_salt"])
    if hmac.compare_digest(entered_hash, account["pin_hash"]):
        return user
    return None

def validate_uploaded_report(uploaded_file):
    if uploaded_file is None:
        return False, "Please select a medical report."
    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in ALLOWED_FILE_EXTENSIONS:
        return (False, "Unsupported file format. Please upload PDF, PNG, JPG or JPEG.")
    file_bytes = uploaded_file.getvalue()
    if len(file_bytes) == 0:
        return False, "The selected file is empty."
    maximum_size_mb = MAX_PDF_SIZE_MB if extension == ".pdf" else MAX_IMAGE_SIZE_MB
    if len(file_bytes) > maximum_size_mb * 1024 * 1024:
        return (False, f"File is too large. Maximum size is {maximum_size_mb} MB for this file type.")
    if extension == ".pdf":
        if not file_bytes.startswith(b"%PDF-"):
            return (False, "This file does not appear to be a valid PDF.")
    elif extension == ".png":
       if not file_bytes.startswith(bytes.fromhex("89504e470d0a1a0a")):
            return (False, "This file does not appear to be a valid PNG image.")
    elif extension in {".jpg", ".jpeg"}:
        if not file_bytes.startswith(b"\xff\xd8\xff"):
            return (False, "This file does not appear to be a valid JPEG image.")
    return True, ""
