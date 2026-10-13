import json

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def build_prompt():
    """
    Build the instruction text sent to Gemini alongside an uploaded
    medical report (PDF or image).

    The prompt first asks Gemini to classify whether the document is
    genuinely a medical report at all (is_medical_report/
    classification_reason) - this is what lets call_ai_with_retry()
    reject something like an exam timetable before it ever reaches
    Health History, Health Trends, or a consultation summary, without
    a second API call: the same request that extracts measurements
    also answers the classification question.

    It then asks Gemini to extract heart rate, blood pressure
    (systolic/diastolic), blood glucose, and the report's own date, and
    to reply with ONLY a JSON object in an exact, fixed structure - no
    markdown, no explanation, no extra fields - so that
    parse_response() and validate_schema() can reliably check what
    comes back. It also forbids diagnosing conditions, recommending
    treatment, or inventing values that are not actually present in the
    report.

    Returns:
        A prompt string ready to be sent to the AI model together with
        the report file.
    """
    return (
        "You are a data extraction assistant. You will be given a "
        "document that is claimed to be a medical report, as a PDF or "
        "image.\n\n"
        "STEP 1 - CLASSIFY THE DOCUMENT:\n"
        "Decide whether this document is genuinely a medical report, "
        "such as a lab result, vital-signs printout, examination "
        "summary, or similar clinical document. A document can be a "
        "valid medical report even if it only contains SOME of the "
        "measurements below - it does not need to contain all of them. "
        "A document is NOT a medical report if it is something "
        "unrelated, such as a school timetable, an exam schedule, an "
        "invoice or receipt, a resume, a random photo, or any other "
        "non-clinical document. If you cannot confidently tell it is a "
        "genuine medical report, treat it as NOT a medical report "
        "rather than guessing.\n\n"
        "STEP 2 - EXTRACT (only if it is a medical report):\n"
        "Extract the following if they are clearly visible in the "
        "report: heart rate, blood pressure (systolic and diastolic), "
        "blood glucose, and the report's own date. If the document is "
        "NOT a medical report, set all of these to null - do not "
        "extract numbers from an unrelated document.\n\n"
        "REPORT DATE RULES:\n"
        '- The report date is the date the measurements were taken or '
        'recorded - look for labels such as "Report Date", '
        '"Collection Date", "Test Date", or "Date of Visit".\n'
        "- Do NOT use the patient's date of birth.\n"
        "- Do NOT use a document printing/generation date if a separate "
        "report/collection/test date is also present.\n"
        "- Do NOT assume the year is 2026, or any other specific year - "
        "read the actual year printed in the report.\n"
        "- The report may show the date in any common format, e.g. "
        '"10/10/2026", "10 Oct 2026", "2026-10-10", or '
        '"10 October 2026" - convert whichever format you find into '
        '"YYYY-MM-DD" in your answer.\n'
        "- If you are not confident which date is the report date, "
        "set it to null rather than guessing.\n\n"
        "Respond with ONLY valid JSON and nothing else - no markdown "
        "formatting, no code fences (```), no explanation, and no text "
        "before or after the JSON.\n\n"
        "The JSON must contain exactly these fields, with no additional "
        "fields:\n"
        "{\n"
        '  "is_medical_report": <true or false - your STEP 1 '
        "classification>,\n"
        '  "classification_reason": <short string explaining your '
        "STEP 1 decision, e.g. \"Contains lab test names and vital "
        'sign readings\" or \"Contains an exam timetable, no clinical '
        'content\">,\n'
        '  "heart_rate": <number, or null if not visible>,\n'
        '  "blood_pressure": {"systolic": <number, or null>, '
        '"diastolic": <number, or null>},\n'
        '  "blood_glucose": <number, or null if not visible>,\n'
        '  "report_date": <"YYYY-MM-DD" string, or null if not '
        "confidently identifiable>\n"
        "}\n\n"
        'If no blood pressure reading is visible at all, set '
        '"blood_pressure" itself to null instead of guessing either '
        "value.\n\n"
        "Rules you must follow:\n"
        "- Do not diagnose any medical condition.\n"
        "- Do not prescribe or suggest any medication.\n"
        "- Do not recommend starting, stopping, or changing any "
        "medication or dosage.\n"
        "- Do not recommend any treatment plan.\n"
        "- Do not claim to replace a doctor or qualified healthcare "
        "professional.\n"
        "- Do not invent, estimate, or guess a value or date that is "
        "not clearly present in the report - use null instead.\n"
        "- Do not include any field other than is_medical_report, "
        "classification_reason, heart_rate, blood_pressure, "
        "blood_glucose, and report_date."
    )


def build_verification_prompt(parsed_response):
    """
    Build a prompt asking Gemini to re-check the (same) medical report
    and confirm whether each non-null extracted value is explicitly
    present in it - a source/grounding check, not a medical judgment.

    Args:
        parsed_response: dict already confirmed by validate_schema() to
            have the expected shape.

    Returns:
        A prompt string ready to be sent to the AI model together with
        the same report file used for extraction.
    """
    return (
        "You will be given a medical report again, along with a set of "
        "values that were previously extracted from it.\n\n"
        "For EACH extracted value below that is not null, check whether "
        "that exact value is explicitly written in the report. Only "
        "check whether the number or date is actually present in the "
        "document - do not judge whether a measurement is medically "
        "normal, abnormal, high, or low, and do not judge whether a "
        "date is plausible, only whether it is the one printed in the "
        "report.\n\n"
        f"Extracted values to check:\n{json.dumps(parsed_response)}\n\n"
        "Respond with ONLY valid JSON and nothing else - no markdown, no "
        "explanation - in exactly this structure:\n"
        "{\n"
        '  "heart_rate_supported": <true or false>,\n'
        '  "blood_pressure_supported": <true or false>,\n'
        '  "blood_glucose_supported": <true or false>,\n'
        '  "report_date_supported": <true or false>\n'
        "}\n\n"
        "Set a field to false if the corresponding value cannot be "
        "found in the report, or if the extracted value was null."
    )


def build_narrative_prompt(processed_record):
    """
    Build a prompt asking Gemini to turn logic_manager's own,
    already-decided findings into short, plain-language consultation
    notes - phrasing only. Gemini is given the finished classifications
    (decision, urgent_findings, flagged_trends, recent_changes, each
    recent change already labelled "improved" or "worsened") and is
    explicitly told never to invent its own thresholds or severity -
    only to describe, in plain words, what Logic Manager already
    decided.

    Args:
        processed_record: the dict logic_manager.process_ai_record()
            returned.

    Returns:
        A prompt string ready to send to Gemini (text only, no file).
    """
    return (
        "You are writing short, factual notes to help a patient "
        "prepare for a doctor's appointment. You will be given "
        "already-finalised health findings as JSON - every "
        "classification (urgent, flagged, improved, worsened, stable) "
        "has ALREADY been decided by a separate rule-based system. "
        "Your only job is to phrase these existing findings in clear, "
        "plain language for a patient to read.\n\n"
        "STRICT RULES:\n"
        "- Do not diagnose any medical condition.\n"
        "- Do not prescribe or suggest any medication.\n"
        "- Do not recommend starting, stopping, or changing any "
        "medication or dosage.\n"
        "- Do not recommend any treatment plan.\n"
        "- Do not claim to replace a doctor or qualified healthcare "
        "professional.\n"
        "- Do not invent your own severity, thresholds, or "
        "classifications - only describe the findings exactly as given.\n"
        '- If a finding\'s "assessment" is "improved", say so clearly - '
        'never describe an improvement as "no significant change".\n'
        "- If a measurement is normal/stable, explain it in relation to "
        "the patient's previous reading(s) if given, rather than only "
        'saying "normal" or "everything is fine".\n'
        "- Do not state or imply that a normal reading proves the "
        "patient is healthy overall.\n"
        "- End with a brief reminder to discuss these findings with a "
        "qualified healthcare professional.\n\n"
        "Findings (already classified - do not reclassify):\n"
        f"{json.dumps(processed_record)}\n\n"
        "Respond with ONLY valid JSON and nothing else - no markdown, "
        "no code fences, no explanation outside the JSON - in exactly "
        "this structure:\n"
        "{\n"
        '  "narrative": "<3-6 sentences of plain-language notes>"\n'
        "}"
    )
