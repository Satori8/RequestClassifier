# AI-Powered Internal Request Classifier Service

An asynchronous Python-based CLI service that automatically classifies and structures incoming internal requests using Google Gemini 3.5 Flash and a configurable YAML taxonomy.

## Key Features

1. **Dynamic Pydantic Schema Factory:** Dynamically generates the Pydantic schema (`ClassifiedRequest`) at runtime based on the loaded taxonomy from `settings/taxonomy.yaml` and passes it directly to Gemini's `response_schema` for 100% API-enforced schema compliance.
2. **Sliding Window Rate Limiter:** Implements a sliding-window RPM (Requests Per Minute) and TPM (Tokens Per Minute) rate limiter that proactively pauses execution and logs warnings when approaching limits to prevent HTTP 429 errors on Gemini's free tier (15 RPM, 1,000,000 TPM limit).
3. **Robust Error Handling & Tenacity Retry:** Retries failed LLM calls up to 3 times with exponential backoff on transient errors (e.g., rate limits, validation errors). If all retries fail, it saves the request with a `processing_error=True` flag and the error details, ensuring no silent drops.
4. **Progress Checkpointing:** Maintains a JSON-based progress file (`output/progress.json`) to allow resuming interrupted runs seamlessly without re-processing already-classified requests.
5. **Asynchronous Orchestration:** Processes requests concurrently using `asyncio.Semaphore(5)` to limit concurrent API calls and optimize speed.
6. **Optional Integrations:** Export results directly to Google Sheets and send daily aggregated reports/digests via Telegram. Both integrations degrade gracefully if credentials or configurations are missing.
7. **Completed File Archiving:** Once all requests in the input CSV are successfully processed, the input file is safely archived in the `completed/` directory with a unique timestamp, keeping the input directory clean and avoiding accidental reprocessing.

---

## Installation & Setup

### Prerequisites
- Python >= 3.11
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip`
- Google Gemini API Key

### 1. Clone the Repository & Install Dependencies
Using `uv`:
```bash
uv sync
```

Or using standard `pip`:
```bash
pip install -r pyproject.toml
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your Gemini API key:
```bash
cp .env.example .env
```

Edit `.env`:
```env
GOOGLE_API_KEY=your_actual_gemini_api_key_here
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

## Running the Service

To run the classifier service locally:
```bash
python -m src.main
```

Or using `uv`:
```bash
uv run python -m src.main
```

The service will:
1. Read the input requests from the configured CSV path (default: `input_requests.csv`).
2. Skip already processed requests using `output/progress.json`.
3. Classify unprocessed requests concurrently using Google Gemini.
4. Save the results to `output/output.json` and analytics to `output/analytics.json`.
5. Run optional Google Sheets and Telegram integrations if configured.
6. If all requests are successfully processed, move the input file to the `completed/` folder with a date/time timestamp (e.g., `completed/input_requests_20260617_122608.csv`) to prevent accidental overwriting or re-processing in subsequent runs.

---

## Running with Docker

You can run the service inside a Docker container using Docker Compose. This mounts the local directories as volumes, so output files are saved directly to your host machine.

### 1. Build and Run
```bash
docker-compose up --build
```

---

## Running Tests

We have a comprehensive test suite with 100% test coverage of core modules.

To run the tests:
```bash
uv run pytest -v
```

---

## Project Structure

```
├── .env.example              # Environment variables template
├── Dockerfile                # Multi-stage Docker build using uv
├── docker-compose.yml        # Docker Compose configuration
├── pyproject.toml            # Project dependencies and configuration
├── input_requests.csv        # Input requests CSV file
├── completed/                # Folder where completed input files are moved/archived
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

## Future Improvements

- **Duplicate & Relation Detection:** Pass the full batch context (request IDs and short text summaries) to the LLM in a single call to detect related requests (e.g., REQ-013 referencing REQ-001) and link them in the output schema.
- **Web Dashboard:** A simple web UI to visualize classified requests, search/filter by category or department, and view analytics charts.
