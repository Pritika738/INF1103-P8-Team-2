# AI-Assisted Health History & Consultation Preparation System

INF1103 team project (Team 2). A Streamlit application that lets a user
upload their medical reports (PDF/image), uses Google Gemini to extract
their health measurements, applies the project's own rule-based logic to
detect notable trends, and prepares a plain-language summary to bring to a
doctor's consultation - without ever generating a diagnosis.

## Folder Structure

```
INF1103-P8-Team-2/
├── io_gui/
│   └── io_gui.py          # Streamlit GUI (primary interface) - login,
│                            dashboard, history, trends, consultation
├── main.py                 # Legacy CLI entry point / menu loop
├── io_manager.py           # I/O facade - all input()/print(), and the
│                            one bridge the GUI/CLI uses to reach ai_manager
├── ai_manager.py           # Builds the Gemini prompt, calls the API,
│                            parses/validates the response, verifies every
│                            extracted value against the source file, and
│                            retries on failure
├── logic_manager.py        # Business rules: classification, trend/change
│                            detection, severity tiers, safety guardrails
├── data_manager.py         # JSON persistence - health records, archived
│                            original report files, consultation PDFs
├── config.py               # Configuration constants (file paths, model
│                            name, retry limits - no secrets)
├── data/
│   ├── health_records.json       # Extracted + validated health records
│   ├── users.json                 # Login credentials (salted hashes)
│   ├── original_reports.json      # Metadata for archived report files
│   ├── original_reports/          # The archived report files themselves
│   ├── consultation_summaries.json # Metadata for generated summary PDFs
│   └── consultation_pdfs/          # The generated summary PDFs themselves
├── tests/
│   └── test_ai_manager.py  # Automated tests for the AI Manager pipeline
├── .env                     # Local GEMINI_API_KEY (not committed)
├── .env.example
├── .dockerignore
├── Dockerfile
├── requirements.txt
└── README.md
```

## Architecture

Four procedural manager modules, each with one responsibility, plus the
Streamlit GUI that drives them. No custom classes - every manager is a
plain set of functions.

```
User
  |
io_gui/io_gui.py        (Streamlit screens: login, dashboard, upload,
  |                       history, trends, consultation)
  |
io_manager.py           (I/O facade: hands an uploaded file to ai_manager,
  |                       hands a processed record to ai_manager for a
  |                       narrative summary)
  |
ai_manager.py  <----->  Google Gemini API
  |                      (build prompt -> call -> parse -> validate ->
  |                       verify against source file -> retry on failure)
  |
logic_manager.py        (classify readings, detect trends/changes across
  |                       history, enforce "never diagnose" rules)
  |
data_manager.py         (atomic JSON read/write)
  |
data/*.json + data/original_reports/ + data/consultation_pdfs/
```

The GUI never calls `ai_manager.py` directly for extraction/narrative work -
it always goes through `io_manager.py`, keeping that boundary enforced in
code rather than just by convention.

## Setup Instructions

1. Ensure Python 3.11+ is installed.
2. From the `INF1103-P8-Team-2/` directory, create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   venv\Scripts\activate   # Windows
   source venv/bin/activate  # macOS/Linux
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and set a real key in `GEMINI_API_KEY` (get one from https://aistudio.google.com/apikey).

## How to Run

### Streamlit GUI (primary interface)

From inside the `INF1103-P8-Team-2/` directory:

```
streamlit run io_gui/io_gui.py
```

This opens the app in your browser with login/registration, a dashboard of
latest readings, a medical report upload flow, full health history (with
the original files you uploaded kept alongside each record), a multi-axis
health trends chart, and a consultation-preparation screen with a saved
summary history.

### Docker

```
docker build -t health-history-app .
docker run --rm -p 8501:8501 --env-file .env -v "${PWD}/data:/app/data" health-history-app
```

Then open `http://localhost:8501`. The volume mount keeps `data/`
persisted on the host across container restarts; `--env-file .env` passes
in `GEMINI_API_KEY` at runtime without baking it into the image.

### Legacy CLI

```
python main.py
```

A simpler terminal menu (add a record manually, view history). It only
talks to `io_manager.py`/`data_manager.py` - it does not use the AI
extraction pipeline or the business-rule engine.

## Current Development Status

**Functional:**
- Streamlit GUI: registration/login, dashboard, medical report upload,
  health history with original-file archive, multi-axis health trends
  chart, consultation-preparation screen with saved summary history
- AI Manager: Gemini-based extraction of heart rate, blood pressure, blood
  glucose, and the report's own date, with schema validation, source
  verification (rejecting any value Gemini can't back up against the
  actual file), and automatic retry
- Logic Manager: classification of readings, trend/change detection across
  a user's history (including classification-boundary crossings), two
  severity tiers (URGENT / FLAGGED), and safety guardrails so AI output is
  never presented as a diagnosis or treatment suggestion
- Data Manager: atomic JSON persistence for health records, archived
  original report files, and generated consultation-summary PDFs
- Automated tests for the AI Manager pipeline (`tests/test_ai_manager.py`)
- Dockerfile + `.dockerignore` for containerized deployment

**Known limitation:**
- The Gemini free tier used during development has a daily request quota.
  Once exhausted, uploads fail with a message asking for a clearer copy
  until the quota resets (or a different/billed API key is used) - this is
  an external API limit, not an application bug.

Tracked health measurements: blood pressure (systolic/diastolic), heart
rate, and blood glucose (AI-extracted). Cholesterol, medication, and
allergy fields exist in the legacy CLI's manual entry form but are not
part of the AI extraction pipeline.
