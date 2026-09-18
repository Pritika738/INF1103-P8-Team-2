"""Consultation Report screen. Self-contained. PDF via fpdf2, text fallback.
Prepares a report for the logged-in user."""

from __future__ import annotations
from datetime import date
import streamlit as st
from dashboard_screen import (
    load_records, clean_records, records_for_user, current_user,
    build_trends, severity_badge, empty_state,
)

def _build_report(who, trends):
    summary, questions, notes = "", [], []
    if trends:
        rising = [t["metric"] for t in trends if t["direction"] == "rising"]
        if rising:
            summary = "Your readings increased over time for: " + ", ".join(rising) + "."
            questions.append("Are the upward trends in " + ", ".join(rising) + " something I should act on?")
        notes.append("Trends are based only on the records provided and are not a "
                     "diagnosis. Please confirm with your doctor.")
    return {"summary": summary, "questions": questions, "notes": notes, "trends": trends}

def _report_text(who, report):
    lines = [f"Consultation Report for {who}", f"Generated {date.today().isoformat()}", "=" * 40, ""]
    if report["summary"]:
        lines += ["SUMMARY", report["summary"], ""]
    if report["trends"]:
        lines += ["NOTABLE CHANGES OVER TIME"]
        for t in report["trends"]:
            lines.append(f"- {t['metric']}: {t['latest']} {t['unit']}  ({t['note']})")
        lines.append("")
    if report["notes"]:
        lines += ["IN PLAIN LANGUAGE"] + [f"- {n}" for n in report["notes"]] + [""]
    if report["questions"]:
        lines += ["QUESTIONS TO ASK YOUR DOCTOR"] + [f"- {q}" for q in report["questions"]]
    return "
".join(lines)

def _build_pdf(who, report):
    try:
        from fpdf import FPDF
    except Exception:
        return None, "PDF library (fpdf2) is not installed."

    def safe(txt):
        return str(txt).encode("latin-1", "replace").decode("latin-1")
    try:
        pdf = FPDF(); pdf.add_page()
        pdf.set_font("Helvetica", "B", 15)
        pdf.cell(0, 10, safe(f"Consultation Report - {who}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, safe(f"Generated {date.today().isoformat()}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        def section(title):
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, safe(title), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10.5)
        if report["summary"]:
            section("Summary"); pdf.multi_cell(0, 6, safe(report["summary"])); pdf.ln(2)
        if report["trends"]:
            section("Notable changes over time")
            for t in report["trends"]:
                pdf.multi_cell(0, 6, safe(f"- {t['metric']}: {t['latest']} {t['unit']} ({t['note']})"))
            pdf.ln(2)
        if report["notes"]:
            section("In plain language")
            for n in report["notes"]:
                pdf.multi_cell(0, 6, safe(f"- {n}"))
            pdf.ln(2)
        if report["questions"]:
            section("Questions to ask your doctor")
            for q in report["questions"]:
                pdf.multi_cell(0, 6, safe(f"- {q}"))
        out = pdf.output()
        return (bytes(out) if isinstance(out, (bytes, bytearray)) else out.encode("latin-1")), None
    except Exception as exc:
        return None, f"Could not generate PDF: {exc}"

def show_consultation_screen() -> None:
    st.title("📝 Consultation Report")
    st.caption("A summary to bring to your next appointment. Not medical advice.")
    records = load_records()
    good, errors = clean_records(records)
    if errors:
        with st.expander(f"⚠️ {len(errors)} record(s) had problems and were skipped"):
            for e in errors:
                st.markdown(f"- {e}")

    user = current_user()
    who = user or "you"
    my_records = records_for_user(good, user)

    if not my_records:
        empty_state("No report to prepare yet",
                    "There isn't enough information to build a consultation "
                    "summary. Add some records first.", icon="📝")
        if st.button("➕ Go to Upload"):
            st.session_state.page = "upload"; st.rerun()
        return

    trends = build_trends(my_records)
    report = _build_report(who, trends)

    if not (report["summary"] or report["trends"] or report["questions"]):
        empty_state("No report to prepare yet", "There isn't enough information yet.", icon="📝")
        return
    if report["summary"]:
        st.subheader("Summary"); st.write(report["summary"])
    if report["trends"]:
        st.subheader("Notable changes over time")
        for t in report["trends"]:
            st.markdown(f"{severity_badge(t['severity'])} &nbsp; **{t['metric']}** — {t['note']}",
                        unsafe_allow_html=True)
    if report["notes"]:
        st.subheader("In plain language")
        for n in report["notes"]:
            st.markdown(f"- {n}")
    if report["questions"]:
        st.subheader("Questions to ask your doctor")
        for q in report["questions"]:
            st.markdown(f"- {q}")

    st.divider()
    st.subheader("Export")
    pdf_bytes, err = _build_pdf(who, report)
    if err:
        st.info(f"PDF not available ({err}) — offering a text download instead.", icon="💡")
        st.download_button("⬇️ Download consultation report (TXT)",
                           data=_report_text(who, report).encode("utf-8"),
                           file_name=f"consultation_report_{user or 'me'}.txt", mime="text/plain")
    else:
        st.download_button("⬇️ Download consultation report (PDF)", data=pdf_bytes,
                           file_name=f"consultation_report_{user or 'me'}.pdf",
                           mime="application/pdf", type="primary")
