import os
import pytest
from src.progress import ProgressTracker


def test_progress_tracker(tmp_path):
    progress_file = tmp_path / "progress.json"
    tracker = ProgressTracker(str(progress_file))

    assert not tracker.is_processed("REQ-001")
    tracker.mark_completed("REQ-001", "done")
    assert tracker.is_processed("REQ-001")

    # Reload tracker
    tracker2 = ProgressTracker(str(progress_file))
    assert tracker2.is_processed("REQ-001")
