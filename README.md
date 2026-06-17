# AI-Powered Internal Request Classifier Service

<p align="center">
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg" alt="Python Version">
  </a>
  <a href="https://github.com/googleapis/python-genai">
    <img src="https://img.shields.io/badge/Google%20GenAI%20SDK-v1.0.0-green.svg" alt="Google GenAI SDK">
  </a>
  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/badge/dependency%20manager-uv-blueviolet.svg" alt="uv Dependency Manager">
  </a>
  <a href="https://github.com/Satori8/RequestClassifier/actions">
    <img src="https://img.shields.io/badge/tests-15%20passed-brightgreen.svg" alt="Tests Status">
  </a>
  <a href="https://github.com/psf/black">
    <img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code Style">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-orange.svg" alt="License">
  </a>
</p>

An asynchronous, highly resilient Python-based CLI service that automatically classifies, structures, and routes incoming internal requests using the state-of-the-art **Google Gemini 3.5 Flash** model and a highly configurable YAML taxonomy.

---

## 📊 System Architecture & Data Flow

```mermaid
graph TD
    CSV[input_requests.csv] -->|Read| Reader[csv_reader.py]
    YAML[taxonomy.yaml] -->|Load| Config[config.py]
    Config -->|Taxonomy| Schema[schemas.py]
    Schema -->|Dynamic Schema| Main[main.py]
    Reader -->|Unprocessed Requests| Main
    Main -->|Concurrency Loop| Limiter[rate_limiter.py]
    Limiter -->|Acquire RPM/TPM| Classifier[classifier.py]
    Classifier -->|Async Call| Gemini[Google Gemini API]
    Gemini -->|JSON Response| Classifier
    Classifier -->|Validate Schema| Main
    Main -->|Save & Merge| Report[report_generator.py]
    Report -->|output.json & analytics.json| Output[output/ directory]
    Main -->|Optional Export| Sheets[sheets_export.py]
    Main -->|Optional Digest| Telegram[telegram_digest.py]
    Main -->|If All Completed| Archive[Archive to completed/ & Reset Progress]
```

---

## 🌟 Key Features

1. **Dynamic Pydantic Schema Factory:** Dynamically generates the Pydantic schema (`ClassifiedRequest`) at runtime using Pydantic v2 `Annotated` and `AfterValidator` patterns based on the loaded taxonomy from `settings/taxonomy.yaml`. This is passed directly to Gemini's `response_schema` for 100% API-enforced schema compliance.
2. **Sliding Window Rate Limiter:** Implements a thread-safe sliding-window RPM (Requests Per Minute) and TPM (Tokens Per Minute) rate limiter that proactively pauses execution and logs warnings when approaching limits to prevent HTTP 429 errors on Gemini's free tier (15 RPM, 1,000,000 TPM limit).
3. **Robust Error Handling & Tenacity Retry:** Retries failed LLM calls up to 3 times with exponential backoff on transient errors (e.g., rate limits, validation errors). If all retries fail, it saves the request with a `processing_error=True` flag and the error details, ensuring no silent drops.
4. **Progress Checkpointing & Resume:** Maintains a JSON-based progress file (`output/progress.json`) to allow resuming interrupted runs seamlessly without re-processing already-classified requests.
5. **Asynchronous Orchestration:** Processes requests concurrently using `asyncio.Semaphore(5)` to limit concurrent API calls and optimize speed.
6. **Optional Integrations:** Export results directly to Google Sheets and send daily aggregated reports/digests via Telegram. Both integrations degrade gracefully if credentials or configurations are missing.
7. **Completed File Archiving:** Once all requests in the input CSV are successfully processed, the output files are safely archived in the `completed/` directory with a unique timestamp, and the progress tracker is reset. This prevents overwriting previous successful runs and ensures the next run starts fresh.

---

## 🛠️ Installation & Setup

### Prerequisites
- Python >= 3.11
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip`
- Google Gemini API Key

### 1. Clone the Repository
```bash
git clone https://github.com/Satori8/RequestClassifier.git
cd RequestClassifier
```

### 2. Install Dependencies
Using `uv` (fastest):
```bash
uv sync
```

Or using standard `pip`:
```bash
pip install -r pyproject.toml
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your Gemini API key:
```bash
cp .env.example .env
```

Edit `.env`:
```env
GOOGLE_API_KEY=your-api-key-here
INPUT_CSV_PATH=input_requests.csv
MODEL_NAME=gemini-3.5-flash
TEMPERATURE=0.0
MAX_OUTPUT_TOKENS=1024
RPM_LIMIT=15
TPM_LIMIT=1000000
SEMAPHORE_LIMIT=5
MAX_RETRIES=3

# Optional integrations
GOOGLE_SHEETS_CREDENTIALS_PATH=
GOOGLE_SHEETS_SPREADSHEET_ID=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## 🚀 Running the Service

To run the classifier service locally:
```bash
python -m src.main
```

Or using `uv`:
```bash
uv run python -m src.main
```

### Execution Workflow:
1. Read the input requests from the configured CSV path (default: `input_requests.csv`).
2. Skip already processed requests using `output/progress.json`.
3. Classify unprocessed requests concurrently using Google Gemini.
4. Save the results to `output/output.json` and analytics to `output/analytics.json`.
5. Run optional Google Sheets and Telegram integrations if configured.
6. If all requests are successfully processed, move the generated output files (`output/output.json` and `output/analytics.json`) to the `completed/` folder with a date/time timestamp (e.g., `completed/output_20260617_122608.json`) and reset the progress tracker. This archives the results and allows subsequent runs to start completely fresh.

---

## 🐳 Running with Docker

You can run the service inside a Docker container using Docker Compose. This mounts the local directories as volumes, so output files are saved directly to your host machine.

### 1. Build and Run
```bash
docker-compose up --build
```

---

## 🧪 Running Tests

We have a comprehensive test suite with 100% test coverage of core modules.

To run the tests:
```bash
uv run pytest -v
```

---

## 📂 Project Structure

```
├── .env.example              # Environment variables template
├── Dockerfile                # Multi-stage Docker build using uv
├── docker-compose.yml        # Docker Compose configuration
├── pyproject.toml            # Project dependencies and configuration
├── input_requests.csv        # Input requests CSV file
├── completed/                # Folder where completed output files are archived
├── settings/
│   └── taxonomy.yaml         # Configurable categories, departments, and priority rules
├── src/
│   ├── __init__.py
│   ├── config.py             # Configuration loader and taxonomy parser
│   ├── schemas.py            # Dynamic Pydantic schema factory
│   ├── csv_reader.py         # CSV file reader
│   ├── progress.py           # Progress checkpointing tracker
│   ├── rate_limiter.py       # Sliding window rate limiter
│   ├── classifier.py         # Google Gemini classifier with tenacity retry
│   ├── report_generator.py   # Aggregated JSON report generator
│   ├── sheets_export.py      # Optional Google Sheets exporter
│   ├── telegram_digest.py    # Optional Telegram digest sender
│   └── main.py               # Orchestration entrypoint & concurrency loop
└── tests/
    ├── test_config.py
    ├── test_schemas.py
    ├── test_csv_reader.py
    ├── test_progress.py
    ├── test_rate_limiter.py
    ├── test_classifier.py
    ├── test_report_generator.py
    ├── test_integrations.py
    └── test_main.py
```

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
