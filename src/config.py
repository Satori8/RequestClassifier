import os
import yaml
from typing import Any
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    GOOGLE_API_KEY: str
    INPUT_CSV_PATH: str = "input_requests.csv"
    MODEL_NAME: str = "gemini-3.5-flash"
    TEMPERATURE: float = 0.0
    MAX_OUTPUT_TOKENS: int = 1024
    RPM_LIMIT: int = 15
    TPM_LIMIT: int = 1000000
    SEMAPHORE_LIMIT: int = 5
    MAX_RETRIES: int = 3
    GOOGLE_SHEETS_CREDENTIALS_PATH: str | None = None
    GOOGLE_SHEETS_SPREADSHEET_ID: str | None = None
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None


def load_taxonomy(yaml_path: str = "settings/taxonomy.yaml") -> dict[str, Any]:
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"Taxonomy file not found at {yaml_path}")
    with open(yaml_path, "r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format in taxonomy file: {e}")
