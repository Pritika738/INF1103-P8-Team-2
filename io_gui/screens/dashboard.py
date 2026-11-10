"""Sidebar navigation and the Dashboard screen."""

import streamlit as st

from core import (
    hero, stat_tile, severity_badge, go, display_name, current_user,
    data_service, records_for_current_user, latest_record_for_user,
)

def sidebar_nav():
    with st.sidebar:
        st.markdown(
            "<div style='text-align:center;padding:14px 0 8px 0;'>"
            "<div class='vt-bob' style='font-size:2.6rem;'>🩺</div>"
            "<div style='font-size:1.55rem;font-weight:800;font-family:Baloo 2;"
            "background:linear-gradient(90deg,#a78bfa,#5eead4);-webkit-background-clip:text;"
            "-webkit-text-fill-color:transparent;'>PASSAY</div>"
            "<div style='font-size:0.72rem;opacity:0.65;'>Health history and consultation</div></div>",
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
                "justify-content:center;font-weight:800;color:#17123a;'>"
                + initial + "</div>"
                "<div><div style='font-weight:800;font-size:0.95rem;color:var(--text-strong);'>" + name + "</div>"
                "<div style='font-size:0.72rem;opacity:0.6;'>Signed in</div></div></div>",
                unsafe_allow_html=True,
            )
        st.markdown("---")
        if st.button("Dashboard", width="stretch"):
            go("dashboard")
        if st.button("Add Report", width="stretch"):
            go("upload")
        if st.button("Health History", width="stretch"):
            go("history")
        if st.button("Health Trends", width="stretch"):
            go("trends")
        if st.button("My Vitals", width="stretch"):
            go("vitals")
        if st.button("Consultation", width="stretch"):
            go("consultation")
        if st.button("Medical Profile", width="stretch"):
            go("profile")
        if st.button("Settings", width="stretch"):
            go("settings")
        st.markdown("---")
        if st.button("Log Out", width="stretch"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.session_state.page = "login"
            st.rerun()

def show_dashboard():
    name = display_name()
    hero("Dashboard", ("Welcome back, " + name + "!") if name else "Your health overview")
    all_records = data_service.load_health_records()
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
                    st.markdown("<div style='text-align:right;color:var(--text-muted);font-weight:700;'>"
                                "Not Available</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='text-align:right;font-size:1.3rem;font-weight:800;"
                                "color:var(--text-strong);font-family:Baloo 2;'>"
                                + str(value) + " <span style='font-size:0.78rem;font-weight:600;"
                                "color:var(--text-muted);'>" + unit + "</span></div>", unsafe_allow_html=True)
    if is_flagged:
        st.write("")
        st.markdown(
            severity_badge("important") + " &nbsp; "
            "<span style='color:var(--text-muted);font-size:0.88rem;'>"
            "One or more measurements in your latest report need review - "
            "see the Consultation page for details.</span>",
            unsafe_allow_html=True,
        )
