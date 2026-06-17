import os
import yaml
from typing import Any
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file.

    Uses pydantic-settings to read configuration from environment variables,
    falling back to defaults where specified. All secrets and API keys are
    expected to be set in the .env file or system environment.

    Attributes:
        GOOGLE_API_KEY: API key for Google Generative AI (Gemini).
        INPUT_CSV_PATH: Path to the input CSV file with requests.
        MODEL_NAME: Gemini model identifier for classification.
        TEMPERATURE: LLM sampling temperature (0.0 = deterministic).
        MAX_OUTPUT_TOKENS: Maximum tokens per LLM response.
        RPM_LIMIT: Max requests per minute allowed by the API.
        TPM_LIMIT: Max tokens per minute allowed by the API.
        SEMAPHORE_LIMIT: Max concurrent API calls.
        MAX_RETRIES: Max retry attempts on API failures.
        GOOGLE_SHEETS_CREDENTIALS_PATH: Optional path to GCP service account JSON.
        GOOGLE_SHEETS_SPREADSHEET_ID: Optional Google Sheets document ID.
        TELEGRAM_BOT_TOKEN: Optional Telegram bot token for digest messages.
        TELEGRAM_CHAT_ID: Optional Telegram chat ID for digest delivery.
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    GOOGLE_API_KEY: str
    INPUT_CSV_PATH: str = "input_requests.csv"
    PROMPT_TEMPLATE_PATH: str = "settings/prompt_template.txt"
    MODEL_NAME: str = "gemini-3.1-flash-lite"
    TEMPERATURE: float = 0.0
    MAX_OUTPUT_TOKENS: int = 1024
    RPM_LIMIT: int = 15
    TPM_LIMIT: int = 250000
    SEMAPHORE_LIMIT: int = 5
    MAX_RETRIES: int = 3
    GOOGLE_SHEETS_CREDENTIALS_PATH: str | None = None
    GOOGLE_SHEETS_SPREADSHEET_ID: str | None = None
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None


def load_taxonomy(yaml_path: str = "settings/taxonomy.yaml") -> dict[str, Any]:
    """Load and parse the taxonomy YAML configuration file.

    Reads the taxonomy file containing categories, departments, and priority rules
    used to classify incoming requests. Validates the file exists and contains
    valid YAML before returning.

    Args:
        yaml_path: Relative or absolute path to the taxonomy YAML file.
            Defaults to "settings/taxonomy.yaml".

    Returns:
        Parsed dictionary with taxonomy structure. Returns an empty dict if the
        file is empty but valid YAML.

    Raises:
        FileNotFoundError: If the taxonomy file does not exist at the given path.
        ValueError: If the file contains invalid or malformed YAML.
    """
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"Taxonomy file not found at {yaml_path}")
    with open(yaml_path, "r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format in taxonomy file: {e}")
