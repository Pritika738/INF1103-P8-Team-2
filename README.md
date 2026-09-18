# AI-Assisted Health History & Consultation Preparation System

INF1103 team project (Team 2). A CLI application that will help users track
their health measurements over time, use AI to help interpret them, and
prepare a summary to bring to a doctor's consultation.

This starter version implements the project structure, module boundaries,
and basic record entry/viewing. AI analysis, trend detection, and PDF
scanning are not implemented yet - see "Current Development Status" below.

## Folder Structure

```
inf1103_p8_team2/
├── main.py              # Entry point / CLI menu loop
├── io_manager.py         # All input()/print() operations
├── ai_manager.py         # AI prompt building, API calls, response parsing (placeholders)
├── logic_manager.py      # Business rules (placeholders)
├── data_manager.py       # JSON file persistence
├── config.py              # Configuration constants
├── data/
│   └── health_records.json   # Local JSON "database" of health records
├── tests/                 # Automated tests (to be added)
├── .env                    # API key placeholder (not committed with real values)
├── .gitignore
├── requirements.txt
├── Dockerfile
└── README.md
```

## Architecture

```
User
  |
io_manager.py         (input/output only)
  |
ai_manager.py          (AI calls - placeholders)
  |
logic_manager.py       (business rules - placeholders)
  |
data_manager.py        (JSON persistence)
  |
health_records.json
```

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

From inside the `INF1103-P8-Team-2/` directory:

```
python main.py
```

You will see a menu:

```
1. Add Health Record
2. View Health History
3. Analyse Health Records
4. Generate Consultation Report
5. Exit
```

## Current Development Status

**Functional:**
- CLI menu loop (`main.py`, `io_manager.py`)
- Adding a health record and saving it to `data/health_records.json` (`data_manager.py`)
- Viewing stored health records
- Loading/saving JSON safely, including handling a missing or corrupted `health_records.json`

**Placeholders (not yet implemented):**
- AI-powered analysis of health records (`ai_manager.py`)
- Health trend detection, medication dosage verification, allergy verification, and report-content selection (`logic_manager.py`)
- Consultation report generation
- Scanned PDF report ingestion

Planned health measurements: blood pressure (systolic/diastolic), heart rate,
blood glucose, and cholesterol. Additional planned fields: medication name
and dosage, allergy information, and record date.
