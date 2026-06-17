import pytest
from src.classifier import build_system_prompt
from src.config import load_taxonomy


def test_build_system_prompt():
    taxonomy = load_taxonomy("settings/taxonomy.yaml")
    prompt = build_system_prompt(taxonomy, "batch context")
    assert "автоматизація" in prompt
    assert "маркетинг" in prompt
    assert "Ukrainian" in prompt
    assert "batch context" in prompt
