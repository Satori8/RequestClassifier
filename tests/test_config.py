import pytest
from src.config import load_taxonomy


def test_load_taxonomy_success():
    taxonomy = load_taxonomy("settings/taxonomy.yaml")
    assert "categories" in taxonomy
    assert "departments" in taxonomy
    assert "priority_rules" in taxonomy
    assert len(taxonomy["categories"]) > 0


def test_load_taxonomy_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_taxonomy("nonexistent_file.yaml")
