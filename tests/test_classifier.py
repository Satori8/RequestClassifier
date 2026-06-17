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


@pytest.mark.asyncio
async def test_call_llm_with_retry_success():
    from src.classifier import _call_llm_with_retry
    from unittest.mock import AsyncMock, MagicMock
    from pydantic import BaseModel

    class DummySchema(BaseModel):
        test_field: str

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"test_field": "test_val"}'
    
    mock_generate_content = AsyncMock(return_value=mock_response)
    mock_client.aio.models.generate_content = mock_generate_content

    res = await _call_llm_with_retry(
        client=mock_client,
        model_name="gemini-3.5-flash",
        prompt="test prompt",
        response_schema=DummySchema,
        temperature=0.0,
        max_output_tokens=100
    )

    assert res == mock_response
    mock_generate_content.assert_called_once()

