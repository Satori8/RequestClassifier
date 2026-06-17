import pytest
from src.csv_reader import read_input_requests


def test_read_input_requests():
    requests = read_input_requests("input_requests.csv")
    assert len(requests) == 18
    assert requests[0]["id"] == "REQ-001"
    assert "Привіт!" in requests[0]["raw_text"]
