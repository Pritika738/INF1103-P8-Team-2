"""Consultation Report screen + report/PDF/text builders."""

from datetime import date

import streamlit as st

from core import (
    hero, severity_badge, current_user, display_name, data_service, ai_service,
    records_for_current_user, latest_record_for_user, build_record_trends,
    vitals_in_period, _format_summary_timestamp,
)

def show_consultation():
    who = display_name() or "you"
    hero("Consultation Report", "A summary to bring to your appointment. Not medical advice.")
    data_service.backfill_record_ids()
    all_records = data_service.load_health_records()
    my_records = records_for_current_user(all_records)
    manual_vitals = data_service.list_manual_vitals(current_user())
    recent_manual_vitals = vitals_in_period(manual_vitals, 30)
    manual_vital_trends = build_record_trends(recent_manual_vitals)
    latest_manual_vital = recent_manual_vitals[-1] if recent_manual_vitals else None

    if not my_records and not manual_vitals:
        with st.container(border=True):
            st.markdown("### No information to prepare")
            st.write("Add a medical report or log some readings in My Vitals first.")
        return

    recent_records = data_service.get_latest_reports(my_records)
    trends = build_record_trends(recent_records)
    latest_processed_record = latest_record_for_user(recent_records)
    report_record_id = latest_processed_record.get("record_id") if latest_processed_record else None
    vital_record_id = latest_manual_vital.get("record_id") if latest_manual_vital else None
    source_record_id = f"report:{report_record_id or 'none'}|vital:{vital_record_id or 'none'}"

    ai_narrative = None
    if latest_processed_record:
        with st.spinner("Preparing your consultation summary..."):
            ai_narrative = ai_service.generate_narrative(latest_processed_record)

    report = build_report(who, trends, ai_narrative, manual_vital_trends, latest_manual_vital)

    with st.container(border=True):
        st.markdown("<div style='border-bottom:1px solid var(--border);padding-bottom:12px;margin-bottom:8px;'>"
                    "<div style='font-size:1.5rem;font-weight:800;color:var(--text-strong);font-family:Baloo 2;'>"
                    "Consultation summary</div>"
                    "<div style='color:var(--text-muted);font-size:0.9rem;'>For " + who + " on "
                    + date.today().strftime("%d %B %Y") + "</div></div>", unsafe_allow_html=True)
        if report["summary"]:
            st.markdown("##### Summary")
            st.write(report["summary"])
        if report["trends"]:
            st.markdown("##### Notable changes over time")
            for t in report["trends"]:
                st.markdown(
                    "<div style='display:flex;justify-content:space-between;align-items:center;"
                    "padding:10px 14px;background:var(--surface);border:1px solid var(--border-soft);"
                    "border-radius:16px;margin-bottom:7px;'>"
                    "<div><b style='color:var(--text-strong);'>" + t["metric"] + "</b><br>"
                    "<span style='color:var(--text-muted);font-size:0.85rem;'>" + t["note"] + "</span></div>"
                    "<div>" + severity_badge(t["severity"]) + "</div></div>",
                    unsafe_allow_html=True,
                )
        if report.get("manual_vital_trends"):
            st.divider()
            st.markdown("##### My Vitals - Self-logged readings")
            st.caption("These readings were entered by you and are shown separately from "
                       "measurements extracted from medical reports.")
            for t in report["manual_vital_trends"]:
                with st.container(border=True):
                    left, right = st.columns([3, 1])
                    with left:
                        st.markdown(f"**{t['metric']}**")
                        st.caption(t["note"])
                    with right:
                        st.markdown("<div style='text-align:right;font-size:1.25rem;font-weight:800;"
                                    "color:var(--text-strong);'>" + str(t["latest"]) + " "
                                    + t["unit"] + "</div>", unsafe_allow_html=True)
                        st.markdown(severity_badge(t["severity"]), unsafe_allow_html=True)
            latest_manual = report.get("latest_manual_vital")
            if latest_manual and latest_manual.get("requires_doctor_review"):
                st.warning(latest_manual.get("recommended_action", ""))
        if report["notes"]:
            st.markdown("##### Note")
            for n in report["notes"]:
                st.markdown("- " + n)

    st.write("")
    pdf_bytes, err = build_pdf(who, report)
    report_date = latest_processed_record.get("date") if latest_processed_record else None
    if err:
        st.info("PDF not available (" + err + "). A text download is offered instead.")
        st.download_button("Download report (TXT)", data=report_text(who, report).encode("utf-8"),
                           file_name="consultation_report.txt", mime="text/plain")
    else:
        st.download_button("Download consultation report (PDF)", data=pdf_bytes,
                           file_name="consultation_report.pdf", mime="application/pdf", type="primary")
        existing_entry = data_service.find_consultation_pdf_by_source(current_user(), source_record_id)
        if not existing_entry:
            saved_entry = data_service.save_consultation_pdf(
                pdf_bytes=pdf_bytes, report_date=report_date,
                username=current_user(), source_record_id=source_record_id)
            if not saved_entry:
                st.error("This summary could not be saved to Summary History. "
                         "You can still download it above.")

    st.divider()
    st.subheader("Summary History")
    saved_summaries = data_service.list_consultation_pdfs(current_user())
    if not saved_summaries:
        st.caption("Summaries you save will appear here for later download.")
    else:
        for entry in saved_summaries:
            with st.container(border=True):
                st.markdown(f"\U0001F4C4 **{entry['filename']}**")
                cols = st.columns([2, 2, 1])
                with cols[0]:
                    st.caption(f"Report date: {entry.get('report_date') or 'Unknown'}")
                with cols[1]:
                    st.caption(f"Generated {_format_summary_timestamp(entry.get('generated_at'))}")
                with cols[2]:
                    pdf_data = data_service.get_consultation_pdf_bytes(entry["filename"])
                    if pdf_data:
                        st.download_button("Download", data=pdf_data, file_name=entry["filename"],
                                           mime="application/pdf", key="summary_" + entry["filename"])
                    else:
                        st.caption("File unavailable")

def build_report(who, trends, ai_narrative=None, manual_vital_trends=None, latest_manual_vital=None):
    notes = []
    if trends:
        notes.append("Trends are based only on the records provided and are not a diagnosis. "
                     "Please confirm with your doctor.")
    if ai_narrative:
        summary = ai_narrative
    elif trends:
        rising = [t["metric"] for t in trends if t["direction"] == "rising"]
        summary = ("Readings increased over time for: " + ", ".join(rising) + ".") if rising else ""
    else:
        summary = ""
    return {
        "summary": summary, "notes": notes, "trends": trends,
        "manual_vital_trends": manual_vital_trends or [],
        "latest_manual_vital": latest_manual_vital,
    }

def report_text(who, report):
    lines = ["Consultation Report for " + who, "Generated " + date.today().isoformat(),
             "========================================", ""]
    if report["summary"]:
        lines += ["SUMMARY", report["summary"], ""]
    if report["trends"]:
        lines += ["NOTABLE CHANGES OVER TIME"]
        for t in report["trends"]:
            lines.append("- " + t["metric"] + ": " + str(t["latest"]) + " " + t["unit"] + "  (" + t["note"] + ")")
        lines.append("")
    if report["notes"]:
        lines += ["NOTE"] + ["- " + n for n in report["notes"]] + [""]
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
                para("- " + t["metric"] + ": " + str(t["latest"]) + " " + t["unit"] + " (" + t["note"] + ")")
            pdf.ln(2)
        if report.get("manual_vital_trends"):
            section("My Vitals - Self-logged readings")
            para("These readings were entered by the user and are shown separately from "
                 "measurements extracted from medical reports.")
            pdf.ln(1)
            for t in report["manual_vital_trends"]:
                para("- " + t["metric"] + ": " + str(t["latest"]) + " " + t["unit"] + " (" + t["note"] + ")")
            latest_manual = report.get("latest_manual_vital")
            if latest_manual and latest_manual.get("requires_doctor_review"):
                pdf.ln(1)
                para("Attention: " + latest_manual.get("recommended_action", ""))
            pdf.ln(2)
        if report["notes"]:
            section("Note")
            for n in report["notes"]:
                para("- " + n)
            pdf.ln(2)
        out = pdf.output()
        if isinstance(out, (bytes, bytearray)):
            return bytes(out), None
        return out.encode("latin-1"), None
    except Exception as exc:
        return None, "Could not generate PDF: " + str(exc)
