import csv
import os
from typing import Any


def read_input_requests(csv_path: str = "input_requests.csv") -> list[dict[str, str]]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Input CSV file not found at {csv_path}")

    requests = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            requests.append(
                {
                    "id": row["id"].strip(),
                    "channel": row["channel"].strip(),
                    "timestamp": row["timestamp"].strip(),
                    "raw_text": row["raw_text"].strip(),
                }
            )
    return requests
