```markdown
# Project Initial Details

## Repository Information
* Repository URL: https://github.com/Pritika738/INF1103-P8-Team-2.git

### Problem Statement
Individuals and health-conscious users often track vital signs (such as Blood Pressure, Blood Glucose, Cholesterol, and Heart Rate) across multiple scattered medical reports and check-ups over several years[cite: 1]. It is difficult for users to manually spot persistent long-term health trends, identify critical metric spikes, and determine what key information should be highlighted during an upcoming doctor appointment.

Our application solves this by accepting scanned medical PDF reports, leveraging AI to convert clinical jargon into plain English, automatically extracting key vital metrics, detecting multi-condition longitudinal trends, and building a pre-consultation summary report.

### Target Users
* **Health-Conscious Individuals:** Primary users who track personal vital signs and want clear visibility into how their health indicators change over time.
* **Patients Preparing for Medical Visits:** Individuals who want a concise, organized summary of their vital trends and notable changes to review with their healthcare provider.

--

## 2. User Inputs

Users provide the following structured data to the application:
* **Scanned PDF File Path:** Terminal input specifying the local file path of a scanned medical report (e.g., `C:/documents/report_2026.pdf`).
* **CLI Navigation Commands:** Terminal menu selections to view timeline trends or generate consultation summary views.

--

## 3. Use of AI

### Utilization
Every input record passes through the `ai_manager` module to communicate with a free-tier vision-capable AI API (e.g., Google Gemini Flash). The AI performs two critical functions:
1. Translates complex clinical terms in the scanned report into plain-English explanations.
2. Parses unstructured PDF report text into a strict, validated JSON object containing four key metrics: Blood Pressure (mmHg), Blood Glucose (mmol/L), Lipid Profile/Cholesterol (mmol/L), and Heart Rate (bpm).

### Outputs & Insights Generated
* **Structured Parameters:** Standardized numerical key-value pairs representing vital signs[cite: 1, 4].
* **Plain-English Summary:** Simplified explanations of clinical report jargon.
* **Pattern Analysis:** AI-identified trends (increasing, decreasing, or stable measurements) extracted directly from report comparisons[cite: 1].

---## 4. Business Rules

The `logic_manager` evaluates the AI's JSON output against the following strict decision-making rules:

* **JSON Schema Validation (`ai_manager`):** The system validates that the AI output matches the expected JSON keys; malformed or non-JSON responses are rejected and safely retried without crashing the CLI application.
* **Multi-Condition Trend Detection (`logic_manager`):** The logic layer compares newly extracted metrics against saved historical records. If a metric (e.g., Systolic Blood Pressure or Fasting Glucose) shows a continuous upward trend across $\ge 3$ consecutive check-ups AND exceeds standard safe thresholds, the system flags it as a "Notable Change" for the summary report[cite: 1, 4].
* **Diagnostic Safety Guardrails (`logic_manager`):** The system enforces a strict boundary prohibiting medical diagnoses or prescription advice. The logic manager inspects the AI text; if unauthorized prescriptive language is detected, it overrides the text and routes the item to a standardized prompt (e.g., *"Discuss this persistent trend with your physician"*).