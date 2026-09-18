"""Dashboard screen. Self-contained: reads data/health_records.json directly.
Shows the logged-in user's records. Falls back to sample data if the file is
empty so it always demos. Record format:
{"username","metric","value","unit","date"}"""

from __future__ import annotations
import json, os
from datetime import datetime
import streamlit as st

RECORDS_PATH = os.path.join("data", "health_records.json")

SAMPLE_RECORDS = [
    {"metric": "LDL cholesterol", "value": 2.8, "unit": "mmol/L", "date": "2022-03-01"},
    {"metric": "LDL cholesterol", "value": 3.0, "unit": "mmol/L", "date": "2023-03-04"},
    {"metric": "LDL cholesterol", "value": 3.5, "unit": "mmol/L", "date": "2024-02-28"},
    {"metric": "LDL cholesterol", "value": 4.1, "unit": "mmol/L", "date": "2025-03-01"},
    {"metric": "Systolic BP", "value": 116, "unit": "mmHg", "date": "2022-03-01"},
    {"metric": "Systolic BP", "value": 121, "unit": "mmHg", "date": "2023-03-04"},
    {"metric": "Systolic BP", "value": 128, "unit": "mmHg", "date": "2024-02-28"},
    {"metric": "Systolic BP", "value": 134, "unit": "mmHg", "date": "2025-03-01"},
]

def load_records() -> list[dict]:
    if not os.path.exists(RECORDS_PATH):
        return list(SAMPLE_RECORDS)
    try:
        with open(RECORDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return list(SAMPLE_RECORDS)
    if not isinstance(data, list) or len(data) == 0:
        return list(SAMPLE_RECORDS)
    return data

def clean_records(records: list[dict]) -> tuple[list[dict], list[str]]:
    good, errors = [], []
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            errors.append(f"Record {i + 1} is not valid and was skipped.")
            continue
        metric = str(r.get("metric", "")).strip()
        unit = str(r.get("unit", "")).strip()
        if not metric:
            errors.append(f"Record {i + 1} has no metric name and was skipped.")
            continue
        try:
            value = float(r.get("value", None))
        except (TypeError, ValueError):
            errors.append(f"Record {i + 1} ({metric}) has an invalid value and was skipped.")
            continue
        parsed = _parse_date(r.get("date", ""))
        if parsed is None:
            errors.append(f"Record {i + 1} ({metric}) has an invalid date and was skipped.")
            continue
        rec = {"metric": metric, "value": value, "unit": unit, "date": parsed}
        for f in ("username", "user", "owner", "account", "user_id", "userid"):
            if f in r:
                rec[f] = str(r[f]).strip()
        good.append(rec)
    return good, errors

def _parse_date(raw):
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(raw).strip(), fmt).date()
        except ValueError:
            continue
    return None

def current_user() -> str:
    """Auto-detect the logged-in username from session_state. '' if none."""
    for key in ("username", "user", "current_user", "logged_in_user",
                "user_name", "userid", "user_id"):
        val = st.session_state.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, dict):
            for k in ("username", "user", "name", "id"):
                if isinstance(val.get(k), str) and val[k].strip():
                    return val[k].strip()
    return ""

def _log_out() -> None:
    """Log the user out: clear the session and return to the login page."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.page = "login"
    st.rerun()

def records_for_user(records: list[dict], user: str) -> list[dict]:
    """Records for the logged-in user. Shows all if no user / records untagged."""
    if not user:
        return records
    user_fields = ("username", "user", "owner", "account", "user_id", "userid")
    tagged = [r for r in records if any(f in r for f in user_fields)]
    if not tagged:
        return records
    mine = []
    for r in records:
        for f in user_fields:
            if f in r and str(r[f]).strip() == user:
                mine.append(r); break
    return mine

def build_trends(records: list[dict]) -> list[dict]:
    by_metric = {}
    for r in records:
        by_metric.setdefault(r["metric"], []).append(r)
    trends = []
    for metric, items in by_metric.items():
        items = sorted(items, key=lambda x: x["date"])
        values = [i["value"] for i in items]
        dates = [i["date"] for i in items]
        unit = items[-1]["unit"]
        direction, severity, note = _summarise(values, unit)
        trends.append({"metric": metric, "unit": unit, "values": values, "dates": dates,
                       "latest": values[-1], "direction": direction,
                       "severity": severity, "note": note})
    return trends

def _summarise(values, unit):
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
    note = (f"Changed from {values[0]} to {values[-1]} {unit} "
            f"({sign}{round(change, 2)} {unit}) over {len(values)} readings.")
    return direction, severity, note

SEVERITY_STYLE = {
    "info": {"emoji": "ℹ️", "color": "#6c757d", "label": "Info"},
    "watch": {"emoji": "👀", "color": "#cc8500", "label": "Watch"},
    "important": {"emoji": "⚠️", "color": "#c83c1e", "label": "Important"},
}
ARROW = {"rising": "▲", "falling": "▼", "stable": "▬", "unknown": "•"}

def severity_badge(severity: str) -> str:
    s = SEVERITY_STYLE.get(severity, SEVERITY_STYLE["info"])
    return (f"<span style='background:{s['color']};color:white;padding:2px 10px;"
            f"border-radius:12px;font-size:0.75rem;font-weight:600;'>"
            f"{s['emoji']} {s['label']}</span>")

def empty_state(title: str, message: str, icon: str = "📭") -> None:
    st.markdown(
        f"""<div style="text-align:center;padding:2.5rem 1rem;border:1px dashed
        #c9c9c9;border-radius:12px;background:#fafafa;">
        <div style="font-size:3rem;">{icon}</div>
        <h3 style="margin:0.5rem 0 0.25rem 0;color:#333;">{title}</h3>
        <p style="color:#666;margin:0;">{message}</p></div>""",
        unsafe_allow_html=True)

def show_dashboard_screen() -> None:
    st.title("🩺 Dashboard")
    records = load_records()
    good, errors = clean_records(records)
    if errors:
        with st.expander(f"⚠️ {len(errors)} record(s) had problems and were skipped"):
            for e in errors:
                st.markdown(f"- {e}")

    user = current_user()
    if user:
        st.caption(f"Logged in as: **{user}**")
    my_records = records_for_user(good, user)

    if not my_records:
        empty_state("No health history yet",
                    "There are no records to summarise. Add records on the "
                    "Upload screen to see trends here.", icon="🩺")
        if st.button("➕ Go to Upload"):
            st.session_state.page = "upload"; st.rerun()
        st.divider()
        if st.button("🚪 Log Out"):
            _log_out()
        return

    trends = build_trends(my_records)

    st.subheader("Key measurements")
    cols = st.columns(min(len(trends), 3) or 1)
    for i, t in enumerate(trends):
        with cols[i % len(cols)]:
            delta = None
            if len(t["values"]) > 1:
                change = round(t["values"][-1] - t["values"][0], 2)
                delta = f"{'+' if change > 0 else ''}{change} {t['unit']}"
            st.metric(label=f"{ARROW.get(t['direction'], '•')} {t['metric']}",
                      value=f"{t['latest']} {t['unit']}", delta=delta, delta_color="inverse")
            st.markdown(severity_badge(t["severity"]), unsafe_allow_html=True)

    st.divider()
    st.subheader("Needs attention")
    flagged = [t for t in trends if t["severity"] in ("watch", "important")]
    if flagged:
        for t in flagged:
            st.markdown(f"{severity_badge(t['severity'])} &nbsp; **{t['metric']}** — {t['note']}",
                        unsafe_allow_html=True)
    else:
        st.success("Nothing is currently flagged for attention.", icon="✓")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("▪ View full history", use_container_width=True):
            st.session_state.page = "history"; st.rerun()
    with c2:
        if st.button("📝 Prepare consultation report", use_container_width=True):
            st.session_state.page = "consultation"; st.rerun()

    st.divider()
    if st.button("🚪 Log Out"):
        _log_out()

