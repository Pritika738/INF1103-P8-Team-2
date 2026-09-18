"""Health History screen. Self-contained (reuses helpers from dashboard_screen).
Shows the logged-in user's records."""

from __future__ import annotations
import streamlit as st
from dashboard_screen import (
    load_records, clean_records, records_for_user, current_user,
    build_trends, severity_badge, empty_state,
)

def show_history_screen() -> None:
    st.title("▪ Health History")
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
        empty_state("Nothing to display",
                    "No valid records were found. Add records on the Upload "
                    "screen and they'll appear here.", icon="📂")
        if st.button("➕ Go to Upload"):
            st.session_state.page = "upload"; st.rerun()
        return

    trends = build_trends(my_records)

    st.subheader("All readings")
    rows = []
    for r in sorted(my_records, key=lambda x: x["date"]):
        rows.append({"Date": r["date"].isoformat(), "Metric": r["metric"],
                     "Value": r["value"], "Unit": r["unit"]})
    metrics = ["All metrics"] + sorted({r["Metric"] for r in rows})
    chosen = st.selectbox("Filter by metric", metrics)
    view = rows if chosen == "All metrics" else [r for r in rows if r["Metric"] == chosen]
    st.dataframe(view, use_container_width=True, hide_index=True)

    csv_lines = ["Date,Metric,Value,Unit"]
    for r in view:
        csv_lines.append(f"{r['Date']},{r['Metric']},{r['Value']},{r['Unit']}")
    st.download_button("⬇️ Download history (CSV)",
                       data="
".join(csv_lines).encode("utf-8"),
                       file_name=f"health_history_{user or 'me'}.csv", mime="text/csv")

    st.divider()
    st.subheader("Trends over time")
    for t in trends:
        with st.container(border=True):
            st.markdown(f"**{t['metric']}** &nbsp; {severity_badge(t['severity'])}",
                        unsafe_allow_html=True)
            if len(t["values"]) < 2:
                st.caption(f"Only one reading ({t['values'][0]} {t['unit']}) — a chart needs at least two.")
            else:
                st.line_chart({t["metric"]: t["values"]}, height=220)
            st.caption(t["note"])
