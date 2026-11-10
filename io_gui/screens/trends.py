"""Health Trends screen (combined chart + per-metric detail cards)."""

import pandas as pd

import streamlit as st

from core import (
    hero, severity_badge, data_service, records_for_current_user,
    build_record_trends, build_multi_axis_trend_chart, build_readings_table_rows,
)

def show_trends():
    hero("Health Trends", "See how your recorded measurements have changed over time.")
    all_records = data_service.load_health_records()
    my_records = records_for_current_user(all_records)
    if not my_records:
        with st.container(border=True):
            st.markdown("### No trend data yet")
            st.write("Once medical records have been added, their measurements will appear here over time.")
            st.caption("At least two readings for a metric are needed before a trend graph can be displayed.")
        return

    recent_records = data_service.get_latest_reports(my_records)
    trends = build_record_trends(recent_records)
    st.caption(f"Based on your latest {len(recent_records)} report(s)"
               + (f" out of {len(my_records)} on file." if len(my_records) > len(recent_records) else "."))

    st.subheader("Combined trend chart")
    combined_chart = build_multi_axis_trend_chart(recent_records)
    if combined_chart is not None:
        st.altair_chart(combined_chart, width="stretch")
        st.caption("Blood pressure, heart rate, and blood glucose each use their own scale (right), "
                   "so they are never compared on one misleading shared axis. Hover a point for its exact reading.")
    else:
        st.info("Not enough dated measurements yet to draw a combined chart.")

    st.divider()
    st.subheader("Measurement table")
    st.dataframe(build_readings_table_rows(recent_records), width="stretch", hide_index=True)

    st.divider()
    st.subheader("Measurement details")
    for t in sorted(trends, key=lambda t: t["metric"]):
        with st.container(border=True):
            top_left, top_right = st.columns([3, 1])
            with top_left:
                st.markdown(f"### {t['metric']}")
                st.caption(f"{len(t['values'])} reading(s)")
            with top_right:
                st.markdown("<div style='text-align:right;font-size:1.45rem;font-weight:800;"
                            "color:var(--text-strong);font-family:Baloo 2;'>" + str(t["latest"]) + " "
                            + "<span style='font-size:0.8rem;color:var(--text-muted);'>"
                            + t["unit"] + "</span></div>", unsafe_allow_html=True)
            if len(t["values"]) >= 2:
                chart_data = pd.DataFrame({"Date": t["dates"], t["metric"]: t["values"]}).set_index("Date")
                st.line_chart(chart_data, height=250, color="#a78bfa")
            else:
                st.info("Add another reading to display a trend graph.")
            st.markdown(severity_badge(t["severity"]), unsafe_allow_html=True)
            st.caption(t["note"])
