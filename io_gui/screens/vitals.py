"""My Vitals screen - self-logged readings (log form, history, trends)."""

from datetime import date, datetime

import pandas as pd

import streamlit as st

import logic_manager

from core import (
    hero, severity_badge, current_user, data_service,
    vitals_validator, vitals_logic, build_record_trends,
    build_vitals_table_rows, build_vitals_chart, vitals_in_period,
    _format_report_date, _format_measurement,
    DECISION_SEVERITY, VITAL_COLUMNS, VITALS_PERIODS,
)

def show_vitals():
    hero("My Vitals", "Log readings you measure yourself - e.g. your daily blood pressure.")
    st.caption("Self-logged readings are kept separately from your medical reports. "
               "They do not appear in Health History or Health Trends. Relevant self-logged "
               "trends and changes are shown separately in your Consultation Report.")
    username = current_user()
    tab_log, tab_history, tab_trends = st.tabs(["Log a reading", "Vitals history", "Vitals trends"])
    with tab_log:
        show_vitals_log_form(username)
    entries = data_service.list_manual_vitals(username)
    with tab_history:
        show_vitals_history(username, entries)
    with tab_trends:
        show_vitals_trends(entries)

def show_vitals_log_form(username):
    st.subheader("New reading")
    selected_readings = st.multiselect(
        "What would you like to log?",
        options=["Blood pressure", "Heart rate", "Blood glucose"],
        placeholder="Select one or more readings",
        key="vitals_reading_types",
    )
    if not selected_readings:
        st.caption("Select at least one reading type to continue.")
        return
    systolic = diastolic = heart_rate = glucose = None
    with st.form("log_vitals_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            measured_date = st.date_input("Date measured", value=date.today(),
                                          max_value=date.today(), format="DD/MM/YYYY")
        with c2:
            measured_time = st.time_input("Time measured", value=datetime.now().time())
        if "Blood pressure" in selected_readings:
            st.markdown("*Blood pressure*")
            b1, b2 = st.columns(2)
            with b1:
                systolic = st.number_input("Systolic (top number, mmHg)", min_value=0, step=1, value=None)
            with b2:
                diastolic = st.number_input("Diastolic (bottom number, mmHg)", min_value=0, step=1, value=None)
        if "Heart rate" in selected_readings:
            heart_rate = st.number_input("Heart rate (bpm)", min_value=0, step=1, value=None)
        if "Blood glucose" in selected_readings:
            glucose = st.number_input("Blood glucose (mmol/L)", min_value=0.0, step=0.1, format="%.1f", value=None)
        note = st.text_input("Notes (optional)", placeholder="e.g. after morning walk, before breakfast",
                             max_chars=logic_manager.ManualVitalsValidator.MAX_NOTE_LENGTH)
        submitted = st.form_submit_button("Save reading", type="primary")
    if not submitted:
        return
    cleaned, errors = vitals_validator.validate({
        "date": measured_date.isoformat() if measured_date else "",
        "time": measured_time.strftime("%H:%M") if measured_time else "",
        "metrics": {
            "blood_pressure_systolic": systolic, "blood_pressure_diastolic": diastolic,
            "heart_rate": heart_rate, "blood_glucose": glucose,
        },
        "note": note,
    })
    if errors:
        for message in errors:
            st.error(message)
        return
    measured_at = (cleaned["date"], cleaned["time"])
    previous = [e for e in data_service.list_manual_vitals(username)
                if (e.get("date") or "", e.get("time") or "") <= measured_at]
    result = vitals_logic.process_manual_reading(cleaned["metrics"], previous)
    entry = dict(cleaned)
    entry.update({
        "username": username, "source": "manual", "decision": result["decision"],
        "urgent_findings": result["urgent_findings"], "flagged_trends": result["flagged_trends"],
        "recent_changes": result["recent_changes"], "requires_doctor_review": result["requires_doctor_review"],
        "recommended_action": result["recommended_action"], "summary": result["summary"],
    })
    if data_service.save_manual_vital(entry) is None:
        st.error("Could not save this reading. Please try again.")
        return
    severity = DECISION_SEVERITY.get(result["decision"], "info")
    with st.container(border=True):
        st.markdown("*Reading saved* &nbsp; " + severity_badge(severity), unsafe_allow_html=True)
        st.write(result["summary"])
        if result["requires_doctor_review"]:
            st.warning(result["recommended_action"])
        for change in result["recent_changes"]:
            st.caption(change["feedback"])

def show_vitals_history(username, entries):
    if not entries:
        st.info("No self-logged readings yet. Use the 'Log a reading' tab to add one.")
        return
    rows = build_vitals_table_rows(entries)
    outcomes = ["All"] + sorted({r["Outcome"] for r in rows if r["Outcome"]})
    chosen = st.selectbox("Filter by outcome", outcomes, key="vitals_outcome_filter")
    view = rows if chosen == "All" else [r for r in rows if r["Outcome"] == chosen]
    st.dataframe(view, width="stretch", hide_index=True)
    st.download_button("Download my vitals (CSV)", data=pd.DataFrame(view).to_csv(index=False).encode("utf-8"),
                       file_name="my_vitals.csv", mime="text/csv", key="vitals_csv")
    with st.expander("Delete a reading"):
        st.caption("Logged something by mistake? Remove it here. This cannot be undone.")
        newest_first = list(reversed(entries))
        options = {
            e["record_id"]: (f"{_format_report_date(e.get('date'))} {e.get('time') or ''} - "
                             + ", ".join(f"{label} {_format_measurement(e['metrics'].get(key), unit)}"
                                         for key, label, unit in VITAL_COLUMNS
                                         if e.get("metrics", {}).get(key) is not None))
            for e in newest_first if e.get("record_id")
        }
        selected = st.selectbox("Reading", list(options.keys()),
                                format_func=lambda rid: options[rid], key="vitals_delete_choice")
        if st.button("Delete reading", key="vitals_delete_btn"):
            if data_service.delete_manual_vital(username, selected):
                st.success("Reading deleted.")
                st.rerun()
            else:
                st.error("Could not delete this reading. Please try again.")

def show_vitals_trends(entries):
    if not entries:
        st.info("Log a few readings to see your trends here.")
        return
    period_label = st.radio("Period", list(VITALS_PERIODS.keys()), horizontal=True, index=1, key="vitals_period")
    in_period = vitals_in_period(entries, VITALS_PERIODS[period_label])
    if not in_period:
        st.info("No readings in this period - try a longer one.")
        return
    st.caption(f"{len(in_period)} reading(s) in this period.")
    chart_groups = [
        ("Blood Pressure", "mmHg", [("blood_pressure_systolic", "Systolic"),
                                     ("blood_pressure_diastolic", "Diastolic")]),
        ("Heart Rate", "bpm", [("heart_rate", "Heart Rate")]),
        ("Blood Glucose", "mmol/L", [("blood_glucose", "Blood Glucose")]),
    ]
    trends_by_label = {t["metric"]: t for t in build_record_trends(in_period)}
    for title, unit, members in chart_groups:
        member_trends = [trends_by_label[logic_manager.METRIC_LABELS[key]]
                         for key, _ in members if logic_manager.METRIC_LABELS[key] in trends_by_label]
        if not member_trends:
            continue
        with st.container(border=True):
            st.markdown(f"### {title}")
            stat_cols = st.columns(len(member_trends))
            for col, t in zip(stat_cols, member_trends):
                with col:
                    values = t["values"]
                    average = sum(values) / len(values)
                    st.metric(t["metric"], _format_measurement(t["latest"], unit),
                              delta=(round(values[-1] - values[-2], 1) if len(values) >= 2 else None),
                              delta_color="inverse")
                    st.caption(f"Avg {average:.1f} - Min {min(values):g} - Max {max(values):g} "
                               f"- {len(values)} reading(s)")
                    st.markdown(severity_badge(t["severity"]), unsafe_allow_html=True)
            chart = build_vitals_chart(in_period, members, title, unit)
            if chart is not None and max(len(t["values"]) for t in member_trends) >= 2:
                st.altair_chart(chart, width="stretch")
            else:
                st.caption("Add another reading to see a trend line.")
