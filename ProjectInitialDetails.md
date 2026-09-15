# Project Initial Details

### Problem Statement
Patients often possess years of medical information but may find it difficult to understand and organise how their health has changed over time, identify unusual changes, and determine which information should be clarified with a healthcare professional. Moreover, existing record systems often present information as separate documents or isolated results, requiring patients to spend a lot of time and effort manually comparing their history.

### Target Users
The target users are individuals who have repeated health check-ups over several years and accumulated medical reports or those who regularly need to prepare information for healthcare appointments. Our application will organise the user’s medical history, analyse changes over time, and allow the user to generate a personalised summary for their next medical consultation, ensuring that difficult medical information is explained in plain language for the ease of comprehension.

### User Inputs
Account Details [Login] - Username, Password, Email

Past medical records - Scanned and uploaded into a database as a PDF/image with AI used to extract relevant health information (heart rate [BPM], blood pressure [systolic/diastolic], blood glucose)

### Use of AI
AI will be used to analyse the user's current and historical health measurements (heart rate, blood pressure, and blood glucose) from their scanned medical reports to identify trends and unusual changes over time.

The AI will generate a structured JSON response identifying patterns such as increasing or decreasing trends, stable measurements, and significant changes. It can also highlight readings that may require the user's attention or further review by a healthcare professional.

These AI-generated results will then be displayed on the dashboard and the consultation-preparation report.

### Business Rules
Input Validation (io_manager): The system will verify that uploaded medical documents are in a supported format and contain processable information before sending them for AI analysis.

Targeted Metric Validation (ai_manager): AI-generated output must follow a predefined JSON structure and may only contain the three health metrics tracked by the application (Blood Pressure, Blood Glucose, and Heart Rate). Missing, malformed, or unsupported values will be rejected or flagged for verification.

Trend Detection (logic_manager): New measurements will be compared with the user's historical records. Persistent increases, decreases, or significant changes across multiple readings will be flagged as notable trends for the user.

Safety Rules (logic_manager): AI-generated outputs will not provide medical diagnoses, prescribe treatment, or recommend medication changes. Findings will instead be presented as informational observations and, where appropriate, users will be advised to discuss notable trends with a healthcare professional.

Data Storage and Record Management (data_manager): Only AI-extracted health measurements that pass the application's validation rules will be stored in the user's health history. Each record will be associated with the relevant date to preserve chronological history. For the prototype, records will be stored using JSON/flat-file storage, while the data_manager will keep storage operations separate from the application's business logic.

### GitHub Repository
* Repository URL: https://github.com/Pritika738/INF1103-P8-Team-2.git