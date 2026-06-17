import json
import os
from typing import Any


class ProgressTracker:
    """Tracks which requests have been processed using a persistent JSON file.

    Enables resumable processing: if the service is interrupted mid-run,
    already-completed requests are skipped on the next invocation. Progress
    is persisted to a JSON file mapping request IDs to their status strings.

    Args:
        filepath: Path to the progress JSON file. Defaults to "output/progress.json".
    """
    def __init__(self, filepath: str = "output/progress.json"):
        self.filepath = filepath
        self.progress = self._load()

    def _load(self) -> dict[str, str]:
        """Load progress from the JSON file on disk.

        Creates the output directory if it doesn't exist. Returns an empty
        dict if the file is missing or contains invalid JSON, allowing a
        clean start without crashing.

        Returns:
            Dictionary mapping request IDs to their status strings.
        """
        if not os.path.exists(self.filepath):
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            return {}
        with open(self.filepath, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def is_processed(self, request_id: str) -> bool:
        """Check if a request has already been processed.

        Args:
            request_id: The unique identifier of the request.

        Returns:
            True if the request ID exists in the progress file.
        """
        return request_id in self.progress

    def mark_completed(self, request_id: str, status: str = "done"):
        """Record a request as processed and persist to disk.

        Args:
            request_id: The unique identifier of the completed request.
            status: Status string to store (default: "done").
        """
        self.progress[request_id] = status
        self._save()

    def _save(self):
        """Persist the current progress dictionary to the JSON file.

        Uses ensure_ascii=False to preserve Ukrainian characters in status
        strings, and indent=2 for manual inspection if needed.
        """
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.progress, f, indent=2, ensure_ascii=False)
