"""Health History screen (table, date correction, original files, trends)."""

from datetime import date

import streamlit as st

from core import (
    hero, severity_badge, current_user, data_service, ai_service,
    records_for_current_user, build_record_trends, build_readings_table_rows,
)

def show_history():
    hero("Health History", "Every reading you have recorded, over time")
    data_service.backfill_record_ids()
    all_records = data_service.load_health_records()
    my_records = records_for_current_user(all_records)
    if not my_records:
        with st.container(border=True):
            st.markdown("### Nothing to display yet")
            st.write("Once you add records, they appear here as a table and trend charts.")
        return

    trends = build_record_trends(my_records)
    st.subheader("All readings")
    sorted_by_date_desc = sorted(my_records, key=lambda r: r.get("date") or "", reverse=True)
    table_rows = build_readings_table_rows(my_records)
    for row, record in zip(table_rows, sorted_by_date_desc):
        row["Outcome"] = record.get("decision", "")
    decisions = ["All"] + sorted({r["Outcome"] for r in table_rows if r["Outcome"]})
    chosen = st.selectbox("Filter by outcome", decisions)
    view = table_rows if chosen == "All" else [r for r in table_rows if r["Outcome"] == chosen]
    st.dataframe(view, width="stretch", hide_index=True)

    csv_lines = ["Report Date,Outcome,Heart Rate,Systolic BP,Diastolic BP,Blood Glucose"]
    for r in view:
        csv_lines.append(",".join(str(r[k]) for k in
                         ("Report Date", "Outcome", "Heart Rate", "Systolic BP", "Diastolic BP", "Blood Glucose")))
    st.download_button("Download history (CSV)", data=chr(10).join(csv_lines).encode("utf-8"),
                       file_name="health_history.csv", mime="text/csv")

    with st.expander("Edit a report date"):
        st.caption("If a report was saved with the wrong date, correct it here. "
                   "Nothing else about the report changes.")
        sorted_records = sorted(my_records, key=lambda r: r.get("date") or "")
        record_options = {
            r["record_id"]: (f"{r.get('date', 'Unknown date')} - {r.get('decision', '')} "
                             f"(heart rate {r.get('metrics', {}).get('heart_rate', 'Not Available')})")
            for r in sorted_records if r.get("record_id")
        }
        if not record_options:
            st.caption("No editable records found.")
        else:
            selected_id = st.selectbox("Select a report to correct", options=list(record_options.keys()),
                                       format_func=lambda rid: record_options[rid])
            selected_record = next((r for r in sorted_records if r.get("record_id") == selected_id), None)
            new_date = st.date_input("Correct report date", value=date.today())
            if st.button("Update Date"):
                if data_service.update_record_date(selected_id, new_date.isoformat()):
                    st.success("Date updated.")
                    st.rerun()
                else:
                    st.error("Could not update this record's date. Please try again.")
            original_entry = (data_service.get_original_report_by_id(selected_record["report_id"])
                              if selected_record and selected_record.get("report_id") else None)
            if original_entry:
                st.write("")
                if st.button("Detect date from original file with AI"):
                    with st.spinner("Asking the AI Manager to re-read the report date..."):
                        original_bytes = data_service.get_original_report_bytes(original_entry["stored_filename"])
                        extracted_file = (ai_service.extract_file(
                            original_bytes, original_entry.get("mime_type", "application/pdf"),
                            original_entry["stored_filename"])
                            if original_bytes else None)
                    detected_date = extracted_file.report_date if extracted_file else None
                    if detected_date:
                        st.session_state["detected_date_" + selected_id] = detected_date
                    else:
                        st.warning("The AI Manager could not confidently detect a date from the original file.")
                detected_key = "detected_date_" + selected_id
                if detected_key in st.session_state:
                    st.info(f"AI detected report date: {st.session_state[detected_key]}")
                    if st.button("Use this detected date"):
                        if data_service.update_record_date(selected_id, st.session_state[detected_key]):
                            del st.session_state[detected_key]
                            st.success("Date updated from AI detection.")
                            st.rerun()
                        else:
                            st.error("Could not update this record's date. Please try again.")
            else:
                st.caption("No original file is archived for this record, so automatic AI date "
                           "detection isn't available - correct it manually above.")

    st.divider()
    st.subheader("Original Medical Reports")
    original_reports = data_service.list_original_reports(current_user())
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
                    file_bytes = data_service.get_original_report_bytes(entry["stored_filename"])
                    if file_bytes:
                        st.download_button("Download", data=file_bytes,
                                           file_name=entry.get("filename") or entry["stored_filename"],
                                           mime=entry.get("mime_type") or "application/octet-stream",
                                           key="original_" + entry["report_id"])
                    else:
                        st.caption("File unavailable")

    st.divider()
    st.subheader("Trends over time")
    for t in trends:
        with st.container(border=True):
            cols = st.columns([3, 1])
            with cols[0]:
                st.markdown("*" + t["metric"] + "* &nbsp; " + severity_badge(t["severity"]), unsafe_allow_html=True)
            with cols[1]:
                st.markdown("<div style='text-align:right;font-weight:800;font-size:1.2rem;"
                            "color:var(--text-strong);'>" + str(t["latest"])
                            + " <span style='font-size:0.78rem;font-weight:600;color:var(--text-muted);'>"
                            + t["unit"] + "</span></div>", unsafe_allow_html=True)
            if len(t["values"]) < 2:
                st.caption("Only one reading (" + str(t["values"][0]) + " " + t["unit"]
                           + ") - a chart needs at least two.")
            else:
                st.area_chart({t["metric"]: t["values"]}, height=200, color="#a78bfa")
            st.caption(t["note"])
