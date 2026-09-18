import streamlit as st
import json
import os
from datetime import datetime, date

st.set_page_config(
    page_title="VitalTrack - Health History and Consultation Prep",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@500;600;700&family=Baloo+2:wght@500;600;700;800&display=swap');

        html, body, [class*="css"], .stApp * { font-family: 'Quicksand', sans-serif; font-weight: 600; }
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

        #MainMenu, footer, header { visibility: hidden; }
        [data-testid="stToolbar"], [data-testid="stStatusWidget"],
        [data-testid="stDecoration"], [data-testid="stHeader"] { display: none !important; }
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
        if st.button("Log Out", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            go("login")

def show_login():
    left, mid, right = st.columns([1, 1.4, 1])
    with mid:
        st.markdown(
            "<div class='vt-hero' style='text-align:center;margin-top:2.5rem;'>"
            "<div class='vt-bob' style='font-size:3.8rem;'>🩺</div>"
            "<h1 style='margin:0;font-size:2.7rem;background:linear-gradient(90deg,#a78bfa,#5eead4);"
            "-webkit-background-clip:text;-webkit-text-fill-color:transparent;'>VitalTrack</h1>"
            "<p style='color:#a6b0d0;'>Track your health over time and prepare for "
            "your next appointment.</p></div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.subheader("Welcome back")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Log In", type="primary", use_container_width=True):
                if username.strip():
                    st.session_state.username = username.strip()
                go("dashboard")
            st.caption("Don't have an account?")
            if st.button("Create Account", use_container_width=True):
                go("register")

def show_register():
    left, mid, right = st.columns([1, 1.4, 1])
    with mid:
        st.markdown("<div class='vt-hero' style='text-align:center;margin-top:2rem;'>"
                    "<h1 style='margin:0;'>Create Account</h1></div>",
                    unsafe_allow_html=True)
        with st.container(border=True):
            st.text_input("Username")
            st.text_input("Email")
            st.text_input("Password", type="password")
            if st.button("Create Account", type="primary", use_container_width=True):
                st.success("Account creation will be implemented later.")
            if st.button("Back to Login", use_container_width=True):
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
                st.markdown("**" + t["metric"] + "**")
                st.caption(t["note"])
            with cols[1]:
                st.markdown("<div style='font-size:1.4rem;font-weight:800;color:#f4f6ff;font-family:Baloo 2;'>"
                            + str(t["latest"]) + " <span style='font-size:0.8rem;font-weight:600;"
                            "color:#a6b0d0;'>" + t["unit"] + "</span></div>", unsafe_allow_html=True)
            with cols[2]:
                st.markdown(severity_badge(t["severity"]), unsafe_allow_html=True)

def show_upload():
    hero("Add a Medical Report", "Upload feature is built by a teammate")
    st.info("Medical report upload will go here.")

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
                st.markdown("**" + t["metric"] + "** &nbsp; " + severity_badge(t["severity"]),
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
    hero("Health Trends", "Trend graphs are built by a teammate")
    st.info("Health trend graphs will go here.")

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
