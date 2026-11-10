"""Add a Medical Report screen (upload + AI/Logic/Data pipeline)."""

import calendar
from datetime import date
from pathlib import Path

import streamlit as st

import logic_manager

from core import (
    hero, severity_badge, current_user, data_service, ai_service, logic_service,
    records_for_current_user, validate_uploaded_report,
    DECISION_SEVERITY, METRIC_UNITS,
)

def show_upload():
    hero("Add a Medical Report",
         "Upload one medical report for validation before health information is extracted.")

    with st.container(border=True):
        st.subheader("Report details")
        date_type = st.radio("What date information is available on the report?",
                             ["Exact date", "Year only"], horizontal=True)
        if date_type == "Exact date":
            st.markdown("**Report Date**")
            current_date = date.today()
            col1, col2, col3 = st.columns(3)
            with col1:
                selected_year = st.selectbox("Year", options=list(range(current_date.year, 1939, -1)))
            months = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
                      "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12}
            with col2:
                if selected_year == current_date.year:
                    available_months = list(months.keys())[:current_date.month]
                    default_month_index = len(available_months) - 1
                else:
                    available_months = list(months.keys())
                    default_month_index = 0
                selected_month_name = st.selectbox("Month", options=available_months, index=default_month_index)
                selected_month = months[selected_month_name]
            days_in_month = calendar.monthrange(selected_year, selected_month)[1]
            if selected_year == current_date.year and selected_month == current_date.month:
                maximum_day = current_date.day
                default_day_index = maximum_day - 1
            else:
                maximum_day = days_in_month
                default_day_index = 0
            with col3:
                selected_day = st.selectbox("Day", options=list(range(1, maximum_day + 1)), index=default_day_index)
            report_date = date(selected_year, selected_month, selected_day)
            report_date_info = {"date_precision": "exact", "date": report_date.isoformat(), "year": report_date.year}
        else:
            current_year = date.today().year
            report_year = st.number_input("Report Year", min_value=1940, max_value=current_year,
                                          value=current_year, step=1)
            report_date_info = {"date_precision": "year", "date": None, "year": int(report_year)}

        uploaded_files = st.file_uploader("Medical Report", type=["pdf", "png", "jpg", "jpeg"],
                                          accept_multiple_files=True)
        st.caption("Upload one PDF, one image, or multiple image pages belonging to the same medical report. "
                   "Supported formats: PDF, PNG, JPG and JPEG. Maximum size: 30 MB for one PDF and 10 MB per image.")

        extensions = [Path(file.name).suffix.lower() for file in uploaded_files]
        pdf_count = extensions.count(".pdf")
        image_extensions = {".png", ".jpg", ".jpeg"}
        combo_valid = True
        if pdf_count > 1:
            st.error("Please upload only one PDF at a time.")
            combo_valid = False
        elif pdf_count == 1 and len(uploaded_files) > 1:
            st.error("Please upload either one PDF OR one or more image pages of the same report, not both.")
            combo_valid = False
        elif len(uploaded_files) > 1 and not all(e in image_extensions for e in extensions):
            st.error("Multiple-file upload is only supported for PNG, JPG or JPEG images.")
            combo_valid = False

        if uploaded_files:
            st.markdown(f"**{len(uploaded_files)} file(s) selected**")
            for number, uploaded_file in enumerate(uploaded_files, start=1):
                st.write(f"**{number}. {uploaded_file.name}**")
                st.caption(f"File size: {uploaded_file.size / 1024:.1f} KB")
        st.write("")

    st.write("")
    with st.container(border=True):
        st.subheader("AI Analysis")
        if uploaded_files:
            st.caption(
                f"Ready to analyse: {uploaded_files[0].name}"
                + (f" (plus {len(uploaded_files) - 1} more page(s) - only the first page is sent "
                   "for AI analysis today)" if len(uploaded_files) > 1 else "")
            )
        else:
            st.caption("Upload a medical report above, then click Analyze with AI.")

        if st.button("Analyze with AI", type="primary", width="stretch"):
            if not uploaded_files:
                st.error("Please select a medical report.")
            elif not combo_valid:
                pass
            else:
                validated_pages = []
                errors = []
                for uploaded_file in uploaded_files:
                    valid, message = validate_uploaded_report(uploaded_file)
                    if valid:
                        validated_pages.append({
                            "name": uploaded_file.name, "mime_type": uploaded_file.type,
                            "size": uploaded_file.size, "bytes": uploaded_file.getvalue(),
                        })
                    else:
                        errors.append(f"{uploaded_file.name}: {message}")
                if errors:
                    st.error("Some uploaded files failed validation:")
                    for error in errors:
                        st.write(f"- {error}")
                else:
                    first_page = validated_pages[0]
                    with st.spinner("Sending report to the AI Manager..."):
                        extracted_file = ai_service.extract_file(
                            first_page["bytes"], first_page["mime_type"], first_page["name"]
                        )
                        if extracted_file is None:
                            st.error("AI analysis could not complete successfully. Please try again.")
                            return
                        all_records = data_service.load_health_records()
                        user_records = records_for_current_user(all_records)
                        processed_record = logic_service.process_file(extracted_file, user_records)
                    if processed_record["decision"] == "NOT_MEDICAL_REPORT":
                        st.error("**Invalid Medical Report**")
                        st.write(processed_record["recommended_action"])
                        if processed_record["summary"]:
                            st.caption(processed_record["summary"])
                    elif processed_record["decision"] == "REJECTED":
                        st.error(processed_record["recommended_action"])
                    else:
                        record_to_save = dict(processed_record)
                        record_to_save["username"] = current_user()
                        ai_date = processed_record.get("ai_extracted_date")
                        if ai_date:
                            record_to_save["date"] = ai_date
                            date_source = "detected automatically from the report"
                        elif report_date_info["date_precision"] == "exact" and report_date_info["date"]:
                            record_to_save["date"] = report_date_info["date"]
                            date_source = "the date you entered"
                        else:
                            date_source = "today's date - no report date could be detected or entered"
                        original_entry = data_service.save_original_report(
                            file_bytes=first_page["bytes"], original_filename=first_page["name"],
                            mime_type=first_page["mime_type"], report_date=record_to_save.get("date"),
                            username=current_user())
                        if original_entry:
                            record_to_save["report_id"] = original_entry["report_id"]
                        else:
                            st.warning("Your extracted results were processed, but the original file "
                                       "could not be archived for Health History.")
                        saved = data_service.save_record(record_to_save)
                        if not saved:
                            st.error("The report was processed but could not be saved. Please try again.")
                        else:
                            severity = DECISION_SEVERITY.get(processed_record["decision"], "info")
                            st.markdown(severity_badge(severity), unsafe_allow_html=True)
                            st.success("Report processed and saved.")
                            st.caption(f"Report date: {record_to_save.get('date', 'Unknown')} ({date_source}).")
                            st.write(processed_record["summary"])
                            extracted_metrics = processed_record["metrics"]
                            metric_rows = [
                                {"Measurement": logic_manager.METRIC_LABELS.get(key, key),
                                 "Value": (f"{value} {METRIC_UNITS.get(key, '')}".strip()
                                           if value is not None else "Not Available")}
                                for key, value in extracted_metrics.items()
                            ]
                            st.table(metric_rows)

