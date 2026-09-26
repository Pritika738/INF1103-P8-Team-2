import streamlit as st
import json
from logic_manager import process_vitals_extraction, process_summary_report, save_analysis_by_report_date
import pandas as pd
import io_manager
import logic_manager
import data_manager
from datetime import date
# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Health History & Consultation Preparation",
    page_icon="🩺",
    layout="centered"
)


# --------------------------------------------------
# PAGE STATE
# --------------------------------------------------

# When the app first opens, start on the login page.
if "page" not in st.session_state:
    st.session_state.page = "login"


# --------------------------------------------------
# LOGIN SCREEN
# --------------------------------------------------

def show_login():
    st.title("Health History & Consultation Preparation")

    st.subheader("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        st.session_state.page = "dashboard"
        st.rerun()

    st.write("Don't have an account?")

    if st.button("Create Account"):
        st.session_state.page = "register"
        st.rerun()


# --------------------------------------------------
# CREATE ACCOUNT SCREEN
# --------------------------------------------------

def show_register():
    st.title("Create Account")

    st.text_input("Username")
    st.text_input("Email")
    st.text_input("Password", type="password")

    if st.button("Create Account"):
        st.success("Account creation will be implemented later.")

    if st.button("Back to Login"):
        st.session_state.page = "login"
        st.rerun()


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

def show_dashboard():
    st.title("Profile Dashboard")

    st.subheader("User's Profile")

    records = data_manager.load_health_records()
    if records:
        latest = records[-1]
        latest_summary = f"{latest.get('date', 'Unknown date')} ({latest.get('decision', 'N/A')})"
    else:
        latest_summary = "No records yet"

    st.write(f"**Records Stored:** {len(records)}")
    st.write(f"**Latest Record:** {latest_summary}")

    st.divider()

    if st.button("➕ Add Medical Report"):
        st.session_state.page = "upload"
        st.rerun()

    if st.button("View Health History"):
        st.session_state.page = "history"
        st.rerun()

    if st.button("View Health Trends"):
        st.session_state.page = "trends"
        st.rerun()

    if st.button("Generate Consultation Report"):
        st.session_state.page = "consultation"
        st.rerun()

    st.divider()

    if st.button("Log Out"):
        st.session_state.page = "login"
        st.rerun()


# --------------------------------------------------
# TEMPORARY EMPTY SCREENS
# --------------------------------------------------

def show_upload():
    st.title("Add Medical Report")

    st.subheader("Upload Medical Report")

    uploaded_file = st.file_uploader(
        "Upload Medical Report",
        type=["pdf", "png", "jpg", "jpeg"],
        label_visibility="collapsed",
    )
    st.caption("Supported: PDF, PNG, JPG/JPEG")

    if uploaded_file is not None:
        if not io_manager.is_supported_upload_type(uploaded_file.type):
            st.error("Unsupported file type. Please upload a PDF, PNG, or JPG/JPEG file.")
        else:
            st.write(f"Selected: {uploaded_file.name}")

            if st.button("Process Report"):
                with st.spinner("Processing report..."):
                    ai_extracted = io_manager.process_uploaded_report(
                        uploaded_file.getvalue(), uploaded_file.type
                    )
                    historical_records = data_manager.load_health_records()
                    processed_record = logic_manager.process_ai_record(
                        ai_extracted, historical_records
                    )

                if processed_record["decision"] == "REJECTED":
                    st.error(processed_record["recommended_action"])
                else:
                    if data_manager.save_record(processed_record):
                        st.success(f"Report processed and saved. Decision: {processed_record['decision']}")
                    else:
                        st.error("Report was processed but could not be saved. Please try again.")


    st.write(processed_record["summary"])
    st.json(processed_record["metrics"])

    st.write(f"Selected: {uploaded_file.name}")
    
    if st.button("Process Report"):
        with st.spinner("Processing report..."):
            try:
                file_bytes = uploaded_file.read()
                
                # Hand control right over to the Logic Layer
                extracted_data = process_vitals_extraction(
                    file_bytes=file_bytes, 
                    mime_type=uploaded_file.type
                )

                print("json file saved.")
                # Save the file into your "./data" directory automatically named after the report date
                saved_disk_path = save_analysis_by_report_date(extracted_data, "report")
                st.success(f"Extraction Complete! File archived on server at: {saved_disk_path}")
                
                # Cache the resulting object in session state so it survives the download trigger
                st.session_state["extracted_json_data"] = extracted_data
                        
                # Safely look for the extracted date inside your dictionary or Pydantic model
                # Adjust this line depending on whether extracted_data is a dict or a Pydantic model
                report_date = "unknown_date"
                if isinstance(extracted_data, dict):
                    report_date = extracted_data.get("database_vitals", {}).get("date", "unknown_date")
                else:
                    # If it's a Pydantic object
                    report_date = getattr(getattr(extracted_data, "database_vitals", None), "date", "unknown_date")
        
                # Serialize the data to a clean string format
                if isinstance(extracted_data, dict):
                    json_string = json.dumps(extracted_data, indent=2, ensure_ascii=False)
                else:
                    json_string = json.dumps(extracted_data.model_dump(), indent=2, ensure_ascii=False)
        
                # Provide the Download Button safely linked to the extracted report date name
                st.download_button(
                    label="💾 Download JSON File",
                    data=json_string,
                    file_name=f"report_{report_date}.json",
                    mime="application/json"
                )


                # Display your structured payload visually in the dashboard
                st.json(extracted_data)
            except Exception as e:
                st.error(f"An error occurred during extraction: {e}")



    

    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()



def show_history():
    st.title("Health History")

    filter_date = st.date_input("Filter by date (optional)", value=None)

    if filter_date is not None:
        records = data_manager.get_records_by_date(filter_date.isoformat())
        if not records:
            st.info(f"No records found for {filter_date.isoformat()}.")
    else:
        records = data_manager.load_health_records()

    if not records:
        st.write("No health records found.")
    else:
        for record in records:
            label = f"{record.get('date', 'Unknown date')} - {record.get('decision', 'N/A')}"
            with st.expander(label):
                st.json(record)

    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()


def show_trends():
    st.title("Health Trends")

    records = data_manager.load_health_records()

    if not records:
        st.write("No health records yet - upload a report to start tracking trends.")
    else:
        chart_rows = []
        for record in records:
            # Tolerate both the AI-pipeline shape (a "metrics" sub-dict)
            # and the flat CLI-entry shape, so older manually-entered
            # records can still be plotted.
            metrics = record.get("metrics", record)
            chart_rows.append({
                "date": record.get("date", ""),
                "Heart Rate": metrics.get("heart_rate"),
                "Systolic BP": metrics.get("blood_pressure_systolic"),
                "Diastolic BP": metrics.get("blood_pressure_diastolic"),
                "Blood Glucose": metrics.get("blood_glucose"),
            })

        chart_data = pd.DataFrame(chart_rows).set_index("date")
        st.line_chart(chart_data)

    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()


def show_consultation():
    st.title("Consultation Preparation Report")

    if st.button("Process Report"):
        with st.spinner("Processing report..."):
            try:
                # Hand control right over to the Logic Layer
                extracted_data = process_summary_report()
                
                # Save the file into your "./data" directory automatically named after the report date
                saved_disk_path = save_analysis_by_report_date(extracted_data, "summary")
                st.success(f"Summary Complete! File archived on server at: {saved_disk_path}")
                
                # Cache the resulting object in session state so it survives the download trigger
                st.session_state["extracted_json_data"] = extracted_data
        
                # Serialize the data to a clean string format
                if isinstance(extracted_data, dict):
                    json_string = json.dumps(extracted_data, indent=2, ensure_ascii=False)
                else:
                    json_string = json.dumps(extracted_data.model_dump(), indent=2, ensure_ascii=False)
        
                # Provide the Download Button safely linked to the extracted report date name
                st.download_button(
                    label="💾 Download JSON File",
                    data=json_string,
                    file_name=f"report_{date.today().strftime("%B_%d_%Y")}.json",
                    mime="application/json"
                )


                # Display your structured payload visually in the dashboard
                st.json(extracted_data)
            except Exception as e:
                st.error(f"An error occurred during extraction: {e}")

    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()


# --------------------------------------------------
# DECIDE WHICH SCREEN TO SHOW
# --------------------------------------------------

if st.session_state.page == "login":
    show_login()

elif st.session_state.page == "register":
    show_register()

elif st.session_state.page == "dashboard":
    show_dashboard()

elif st.session_state.page == "upload":
    show_upload()

elif st.session_state.page == "history":
    show_history()

elif st.session_state.page == "trends":
    show_trends()

elif st.session_state.page == "consultation":
    show_consultation()