import csv
import os
from typing import Any


def read_input_requests(csv_path: str = "input_requests.csv") -> list[dict[str, str]]:
    """Read and parse the input CSV file containing raw requests.

    Uses csv.DictReader to map CSV columns to dictionary keys. Each row is
    expected to have at least 'id', 'channel', 'timestamp', and 'raw_text'
    columns. All string values are stripped of leading/trailing whitespace.

    Args:
        csv_path: Path to the CSV file. Defaults to "input_requests.csv".

    Returns:
        A list of dictionaries, each representing one request with keys
        matching the CSV header row and string values trimmed.

    Raises:
        FileNotFoundError: If the CSV file does not exist at the given path.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Input CSV file not found at {csv_path}")

    requests: list[dict[str, str]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Strip whitespace from all string fields to normalize input
            requests.append(
                {
                    "id": row["id"].strip(),
                    "channel": row["channel"].strip(),
                    "timestamp": row["timestamp"].strip(),
                    "raw_text": row["raw_text"].strip(),
                }
            )
    return requests
