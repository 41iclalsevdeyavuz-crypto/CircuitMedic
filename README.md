# 🩺 CircuitMedic

**Evidence-grounded debugging for Arduino firmware and embedded hardware.**

CircuitMedic is a debugging assistant for embedded projects. Instead of only reporting suspicious code patterns, it connects firmware findings with technical documentation and explains why a problem may affect the observed hardware behavior.

The current MVP focuses specifically on **Arduino Uno + HC-SR04 ultrasonic sensor firmware**.

> CircuitMedic is currently a focused prototype. It does not claim to analyze every C/C++ or embedded project.

---

## The Problem

Embedded bugs are often difficult to diagnose because the failure can sit between software and hardware.

For example, an obstacle-avoidance robot may occasionally miss objects because:

- the ultrasonic trigger pulse is too short,
- echo measurement relies on an unsuitable timeout,
- a missing echo is treated as a valid distance,
- or sensor timing does not follow the component documentation.

Finding these problems normally requires comparing firmware with datasheets and API documentation manually.

CircuitMedic brings those steps into one debugging workflow:

**Firmware → static checks → documentation retrieval → evidence-backed diagnosis → optional AI explanation**

---

## Current Scope

The current MVP supports:

- **Board:** Arduino Uno
- **Component:** HC-SR04 ultrasonic distance sensor
- **Firmware formats:** `.ino`, `.cpp`, `.h`
- Configurable TRIG and ECHO symbol names
- HC-SR04 trigger timing checks
- `pulseIn()` timeout checks
- no-echo handling checks
- comment-aware analysis
- basic control-flow-aware handling of supported no-echo guards

The analyzer intentionally has a narrow scope so that findings can be explained and grounded in technical evidence.

---

## What CircuitMedic Does

### 1. Firmware Analysis

CircuitMedic performs deterministic checks for supported HC-SR04 failure patterns.

Current checks include:

- trigger pulses shorter than the documented requirement,
- `pulseIn()` calls without an explicit timeout,
- supported cases where a no-echo result may be used without being handled.

The analyzer also avoids several known false positives, including unrelated LED `HIGH` operations and code inside comments.

---

### 2. Real Datasheet Ingestion

CircuitMedic includes an ingestion pipeline for a real HC-SR04 datasheet PDF.

The PDF is:

1. read page by page,
2. converted to text,
3. split into smaller chunks,
4. assigned metadata including:
   - document name,
   - page number,
   - unique chunk ID.

This allows a diagnosis to point back to the actual document passage that supports it.

Example evidence metadata:

```text
Source: hc_sr04_original.pdf
Page: 1
Chunk: hc_sr04_original_p1_c1
```

---

### 3. Embedding-Based Retrieval

CircuitMedic uses a small local semantic index for documentation retrieval.

PDF chunks are converted into embeddings and cached locally so they do not need to be regenerated for every analysis.

When the analyzer detects an issue, CircuitMedic searches for documentation relevant to that specific finding.

The retrieval layer includes a relevance threshold so an unrelated query is not automatically presented as evidence.

A separate Arduino `pulseIn()` reference is used for API-specific behavior instead of incorrectly attributing that behavior to the HC-SR04 datasheet.

---

### 4. Evidence-Grounded Diagnoses

Each supported finding is presented as a chain:

```text
Observed code
      ↓
Documented requirement
      ↓
Mismatch
      ↓
Suggested fix
```

Where relevant evidence is available, CircuitMedic also displays:

- source document,
- page number,
- chunk ID,
- retrieved passage,
- retrieval similarity.

Retrieval similarity represents semantic similarity between the search query and documentation passage. It is **not** presented as the probability that a diagnosis is correct.

Findings instead use interpretable assessment labels such as:

- **Direct rule match**
- **Possible issue**
- **Manual review required**

---

### 5. Optional AI Debugging Explanation

CircuitMedic can optionally use an OpenAI model to explain the deterministic findings in the context of the user's reported symptom.

The model receives:

- observed symptom,
- board and component context,
- firmware,
- analyzer findings,
- code locations,
- retrieved evidence,
- evidence IDs.

The structured AI response contains:

- possible cause,
- relationship to the symptom,
- technical explanation,
- recommended fix,
- evidence IDs used,
- uncertainty or additional checks.

The AI layer is not responsible for inventing new analyzer findings.

Evidence IDs returned by the model are validated against the evidence supplied to it.

If the API is unavailable, CircuitMedic continues to show the deterministic evidence-backed report instead of failing.

---

## Demo Workflow

CircuitMedic includes two firmware examples:

```text
data/sample_projects/obstacle_robot/
├── broken_robot.ino
└── fixed_robot.ino
```

### Broken example

Click:

**Load broken example → Analyze firmware**

The application demonstrates supported HC-SR04 problems and shows their corresponding code locations and documentation evidence.

### Fixed example

Click:

**Load fixed example → Analyze firmware**

The corrected example uses the supported fixes, allowing the user to compare the before/after behavior of the analyzer.

You can also edit firmware directly in the application and analyze the modified version again.

This makes the core demo:

**Detect → understand → fix → re-analyze**

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/41iclalsevdeyavuz-crypto/CircuitMedic.git
cd CircuitMedic
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

The embedding model may be downloaded the first time the retrieval system is initialized.

---

## OpenAI API Configuration

An OpenAI API key is **optional**.

The deterministic analyzer, documentation retrieval, and evidence-backed findings can still operate without the AI explanation layer.

To enable AI explanations, create a `.env` file in the repository root:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=your_model_name
```

Set `OPENAI_MODEL` to a model available to your OpenAI API account.

An example configuration is provided in:

```text
.env.example
```

Do not commit your real `.env` file or API key.

If the API call fails, CircuitMedic falls back to the rule-based diagnostic report.

---

## Run CircuitMedic

With the virtual environment activated:

```bash
python -m streamlit run app/main.py
```

Then open the local Streamlit address displayed in the terminal.

---

## Run Tests

```bash
python -m pytest -q
```

The test suite covers important MVP scenarios including:

- broken robot detection,
- corrected robot behavior,
- unrelated LED code,
- commented-out firmware,
- supported no-echo guards,
- irrelevant documentation queries,
- AI API fallback behavior,
- edited firmware re-analysis behavior.

---

## Report Export

After analysis, the structured diagnostic report can be downloaded as JSON.

The report contains the detected issues, evidence metadata, assessment information, and AI explanation when one was successfully generated.

---

## Architecture

```text
Arduino Firmware
       │
       ▼
HC-SR04 Static Analyzer
       │
       ├── Trigger timing rules
       ├── pulseIn timeout checks
       └── No-echo handling checks
       │
       ▼
Evidence Query
       │
       ▼
Embedding-Based Local Retriever
       │
       ├── HC-SR04 Datasheet PDF Chunks
       └── Arduino pulseIn Reference
       │
       ▼
Evidence-Grounded Diagnostic Report
       │
       ├── Observed code
       ├── Requirement
       ├── Mismatch
       ├── Suggested fix
       └── Source / page / chunk
       │
       ▼
Optional LLM Explanation
       │
       ▼
Streamlit UI + JSON Report
```

---

## Known Limitations

CircuitMedic is currently an MVP with deliberately limited hardware and language understanding.

Current limitations include:

- Only HC-SR04-specific checks are implemented.
- Arduino Uno is the currently supported board context.
- The analyzer does not perform complete C++ parsing or full program analysis.
- Complex control flow may require manual review.
- Pin roles are supplied through TRIG/ECHO symbol names rather than inferred from arbitrary firmware.
- The tool does not verify electrical wiring or physical hardware faults.
- Retrieval is limited to the documentation included in the project.
- AI explanations depend on external API availability and should not override deterministic evidence.
- A report with no findings means **no issue was found within the currently supported checks**; it does not guarantee that the firmware or hardware is completely correct or safe.

---

## Demo & Screenshots

### Application Screenshot

![CircuitMedic evidence-grounded HC-SR04 diagnosis](docs/images/circuitmedic-demo.png)

### Demo Video

The final CircuitMedic demo video will be added before submission.

---

## Project Structure

```text
CircuitMedic/
├── app/
│   ├── analyzers/
│   │   └── hc_sr04.py
│   ├── rag/
│   │   ├── ingest.py
│   │   └── retriever.py
│   ├── services/
│   │   ├── diagnostic_engine.py
│   │   └── llm_service.py
│   ├── main.py
│   └── models.py
│
├── data/
│   ├── datasheets/
│   └── sample_projects/
│       └── obstacle_robot/
│           ├── broken_robot.ino
│           └── fixed_robot.ino
│
├── docs/
│   └── images/
│       └── circuitmedic-demo.png
│
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

---

## Why CircuitMedic?

CircuitMedic's goal is not to replace an embedded engineer or claim that an LLM can automatically debug arbitrary hardware.

The goal is narrower:

> **Turn embedded debugging findings into traceable explanations backed by the code and the documentation engineers actually use.**

For the current MVP, that workflow is demonstrated end-to-end with Arduino Uno and HC-SR04 firmware.