# CircuitMedic

AI-powered, evidence-grounded debugging copilot for embedded systems.

The MVP analyzes Arduino firmware for HC-SR04 timing and timeout failures, retrieves relevant component documentation, and returns structured diagnoses with severity, confidence, exact code location, evidence, and a fix.

## Demo

1. Load the included broken obstacle-robot firmware or upload an `.ino`, `.cpp`, or `.h` file.
2. Describe the symptom and click **Analyze firmware**.
3. Inspect three findings tied to source lines and retrieved HC-SR04 evidence.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
streamlit run app/main.py
```

Run tests with `pytest -q`.

## Architecture

`Firmware → HC-SR04 analyzer → retrieval query → TF-IDF datasheet index → evidence-backed diagnosis`

The current knowledge base is a concise HC-SR04 technical note. Next versions can ingest PDFs, use embeddings/LLM synthesis, and add L298N and SG90 checks without changing the report schema.
