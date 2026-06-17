import json
import os
from typing import Any


class ProgressTracker:
    def __init__(self, filepath: str = "output/progress.json"):
        self.filepath = filepath
        self.progress = self._load()

    def _load(self) -> dict[str, str]:
        if not os.path.exists(self.filepath):
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            return {}
        with open(self.filepath, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def is_processed(self, request_id: str) -> bool:
        return request_id in self.progress

    def mark_completed(self, request_id: str, status: str = "done"):
        self.progress[request_id] = status
        self._save()

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.progress, f, indent=2, ensure_ascii=False)
