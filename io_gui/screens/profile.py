"""Medical Profile screen + its PDF builder."""

from datetime import datetime

import streamlit as st

import logic_manager

from core import (
    hero, current_user, display_name, data_service,
    _format_summary_timestamp, BLOOD_GROUP_OPTIONS, DOSAGE_UNIT_OPTIONS,
)

def build_medical_profile_pdf(who, profile):
    try:
        from fpdf import FPDF
    except Exception:
        return None, "PDF library is not installed."

    def safe(text):
        return str(text).encode("latin-1", "replace").decode("latin-1")

    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, safe("PASSAY Medical Profile"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, safe(f"Patient: {who}"), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 7, safe("Generated: " + datetime.now().strftime("%d %B %Y, %H:%M")),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        def section(title):
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, safe(title), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)

        def line(text):
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 6, safe(text))

        section("Blood Group")
        line(profile.get("blood_group") or "Not recorded")
        pdf.ln(2)

        section("Current Medications")
        medications = profile.get("medications", [])
        if medications:
            for medication in medications:
                dosage = ""
                if medication.get("dosage_amount") is not None:
                    dosage = str(medication.get("dosage_amount"))
                    if medication.get("dosage_unit"):
                        dosage += " " + medication["dosage_unit"]
                text = "- " + medication.get("name", "")
                if dosage:
                    text += ": " + dosage
                if medication.get("frequency"):
                    text += ", " + medication["frequency"]
                line(text)
        else:
            line("None recorded")
        pdf.ln(2)

        section("Allergies")
        allergies = profile.get("allergies", [])
        if allergies:
            for allergy in allergies:
                text = "- " + allergy.get("allergen", "")
                if allergy.get("reaction"):
                    text += " - Reaction: " + allergy["reaction"]
                if allergy.get("severity"):
                    text += " - Severity: " + allergy["severity"]
                line(text)
        else:
            line("None recorded")
        pdf.ln(2)

        section("Emergency Contacts")
        contacts = profile.get("emergency_contacts", [])
        if contacts:
            for contact in contacts:
                text = "- " + contact.get("name", "")
                if contact.get("relationship"):
                    text += " (" + contact["relationship"] + ")"
                if contact.get("phone"):
                    text += " - " + contact["phone"]
                if contact.get("email"):
                    text += " - " + contact["email"]
                line(text)
        else:
            line("None recorded")
        pdf.ln(2)

        section("Hereditary Illness")
        hereditary = profile.get("hereditary_illness", {})
        conditions = []
        if hereditary.get("diabetes"):
            conditions.append("Diabetes")
        if hereditary.get("blood_pressure"):
            conditions.append("Blood pressure")
        if hereditary.get("heart_disease"):
            conditions.append("Heart disease")
        if hereditary.get("asthma"):
            conditions.append("Asthma")
        if hereditary.get("other"):
            conditions.append(hereditary["other"])
        if conditions:
            for condition in conditions:
                line("- " + condition)
        else:
            line("None recorded")
        if hereditary.get("notes"):
            pdf.ln(1)
            line("Notes: " + hereditary["notes"])
        pdf.ln(5)

        pdf.set_font("Helvetica", "I", 8)
        line("This document contains information entered by the user and is intended to "
             "help communicate medical history to healthcare professionals.")

        output = pdf.output()
        if isinstance(output, (bytes, bytearray)):
            return bytes(output), None
        return output.encode("latin-1"), None
    except Exception as exc:
        return None, str(exc)

def show_profile():
    hero("Medical Profile", "Your standing health information, ready for any appointment.")
    username = current_user()
    profile = data_service.load_medical_profile(username)

    with st.container(border=True):
        st.subheader("Blood group")
        current_bg = profile.get("blood_group") or "Not set"
        bg_index = BLOOD_GROUP_OPTIONS.index(current_bg) if current_bg in BLOOD_GROUP_OPTIONS else 0
        blood_group_choice = st.selectbox("Blood group", BLOOD_GROUP_OPTIONS, index=bg_index)

    with st.container(border=True):
        st.subheader("Medications")
        st.caption("List each current medication, its dose and how often you take it.")
        med_count = st.number_input("How many medications?", min_value=0, max_value=20,
                                    value=len(profile.get("medications", [])), step=1, key="med_count")
        medications = []
        for i in range(int(med_count)):
            existing = profile["medications"][i] if i < len(profile.get("medications", [])) else {}
            st.markdown(f"*Medication {i + 1}*")
            cols = st.columns([3, 2, 2, 3])
            with cols[0]:
                name = st.text_input("Name", value=existing.get("name", ""), key=f"med_name_{i}")
            with cols[1]:
                amount = st.text_input("Dose amount", value=str(existing.get("dosage_amount") or ""), key=f"med_amt_{i}")
            with cols[2]:
                unit_existing = existing.get("dosage_unit", "")
                unit_index = DOSAGE_UNIT_OPTIONS.index(unit_existing) if unit_existing in DOSAGE_UNIT_OPTIONS else 0
                unit = st.selectbox("Unit", DOSAGE_UNIT_OPTIONS, index=unit_index, key=f"med_unit_{i}")
            with cols[3]:
                freq = st.text_input("Frequency", value=existing.get("frequency", ""),
                                     key=f"med_freq_{i}", placeholder="e.g. twice daily")
            medications.append({"name": name, "dosage_amount": amount, "dosage_unit": unit, "frequency": freq})

    with st.container(border=True):
        st.subheader("Allergies")
        allergy_count = st.number_input("How many allergies?", min_value=0, max_value=20,
                                        value=len(profile.get("allergies", [])), step=1, key="allergy_count")
        allergies = []
        for i in range(int(allergy_count)):
            existing = profile["allergies"][i] if i < len(profile.get("allergies", [])) else {}
            st.markdown(f"*Allergy {i + 1}*")
            cols = st.columns([3, 3, 2])
            with cols[0]:
                allergen = st.text_input("Allergen", value=existing.get("allergen", ""), key=f"alg_name_{i}")
            with cols[1]:
                reaction = st.text_input("Reaction", value=existing.get("reaction", ""),
                                         key=f"alg_react_{i}", placeholder="e.g. skin/eye")
            with cols[2]:
                sev_options = ["", "mild", "moderate", "severe"]
                sev_existing = str(existing.get("severity", "")).lower()
                sev_index = sev_options.index(sev_existing) if sev_existing in sev_options else 0
                severity = st.selectbox("Severity", sev_options, index=sev_index, key=f"alg_sev_{i}")
            allergies.append({"allergen": allergen, "reaction": reaction, "severity": severity})

    with st.container(border=True):
        st.subheader("Emergency contacts")
        contact_count = st.number_input("How many contacts?", min_value=0, max_value=10,
                                        value=len(profile.get("emergency_contacts", [])), step=1, key="contact_count")
        emergency_contacts = []
        for i in range(int(contact_count)):
            existing = profile["emergency_contacts"][i] if i < len(profile.get("emergency_contacts", [])) else {}
            st.markdown(f"*Contact {i + 1}*")
            cols = st.columns([3, 2, 3, 3])
            with cols[0]:
                name = st.text_input("Name", value=existing.get("name", ""), key=f"ec_name_{i}")
            with cols[1]:
                relationship = st.text_input("Relationship", value=existing.get("relationship", ""),
                                             key=f"ec_rel_{i}", placeholder="e.g. mother")
            with cols[2]:
                phone = st.text_input("Phone (with country code)", value=existing.get("phone", ""),
                                      key=f"ec_phone_{i}", placeholder="e.g. +65 1234 5678")
            with cols[3]:
                email = st.text_input("Email", value=existing.get("email", ""), key=f"ec_email_{i}")
            emergency_contacts.append({"name": name, "relationship": relationship, "phone": phone, "email": email})

    with st.container(border=True):
        st.subheader("Hereditary illness")
        st.caption("Tick any conditions that run in your family.")
        hereditary = profile.get("hereditary_illness", {}) or {}
        cols = st.columns(4)
        with cols[0]:
            diabetes = st.checkbox("Diabetes", value=bool(hereditary.get("diabetes")))
        with cols[1]:
            blood_pressure = st.checkbox("Blood pressure", value=bool(hereditary.get("blood_pressure")))
        with cols[2]:
            heart_disease = st.checkbox("Heart disease", value=bool(hereditary.get("heart_disease")))
        with cols[3]:
            asthma = st.checkbox("Asthma", value=bool(hereditary.get("asthma")))
        other = st.text_input("Other hereditary condition", value=hereditary.get("other", ""))
        notes = st.text_input("Notes (e.g. which relative)", value=hereditary.get("notes", ""))

    st.write("")
    if st.button("Save medical profile", type="primary", width="stretch"):
        raw_profile = {
            "blood_group": "" if blood_group_choice == "Not set" else blood_group_choice,
            "medications": medications, "allergies": allergies,
            "emergency_contacts": emergency_contacts,
            "hereditary_illness": {
                "diabetes": diabetes, "blood_pressure": blood_pressure,
                "heart_disease": heart_disease, "asthma": asthma, "other": other, "notes": notes,
            },
        }
        cleaned, errors = logic_manager.validate_medical_profile(raw_profile)
        if errors:
            st.error("Please fix the following before saving:")
            for message in errors:
                st.write("- " + message)
        elif data_service.save_medical_profile(username, cleaned):
            st.success("Medical profile saved successfully.")
            pdf_bytes, pdf_error = build_medical_profile_pdf(display_name() or username, cleaned)
            if pdf_error:
                st.warning("Your medical profile was saved, but the PDF could not be generated.")
            else:
                saved_pdf = data_service.save_medical_profile_pdf(pdf_bytes, username)
                if saved_pdf:
                    st.success("Medical profile PDF created successfully.")
                    st.download_button("Download latest medical profile (PDF)", data=pdf_bytes,
                                       file_name=saved_pdf["filename"], mime="application/pdf",
                                       key="latest_medical_profile_pdf")
                else:
                    st.warning("Your profile was saved, but the PDF could not be archived.")
        else:
            st.error("Could not save your profile. Please try again.")

    st.divider()
    st.subheader("Medical Profile History")
    st.caption("Previous versions of your saved medical profile.")
    profile_pdfs = data_service.list_medical_profile_pdfs(username)
    if not profile_pdfs:
        st.caption("Saved medical profile PDFs will appear here.")
    else:
        for entry in profile_pdfs:
            with st.container(border=True):
                generated = _format_summary_timestamp(entry.get("generated_at"))
                cols = st.columns([3, 2, 1])
                with cols[0]:
                    st.markdown(f"**{entry['filename']}**")
                with cols[1]:
                    st.caption(f"Saved {generated}")
                with cols[2]:
                    pdf_data = data_service.get_medical_profile_pdf_bytes(entry["filename"])
                    if pdf_data:
                        st.download_button("Download", data=pdf_data, file_name=entry["filename"],
                                           mime="application/pdf", key="medical_profile_" + entry["filename"])
                    else:
                        st.caption("File unavailable")
