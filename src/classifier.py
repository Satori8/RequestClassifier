import logging
from typing import Any, Type
from pydantic import BaseModel, ValidationError
from google import genai
from google.genai import types
from google.genai.errors import APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.schemas import ProcessingResult

logger = logging.getLogger(__name__)


def log_retry_attempt(retry_state):
    logger.warning(
        f"LLM call failed (attempt {retry_state.attempt_number}). "
        f"Error: {retry_state.outcome.exception()}. "
        f"Retrying in {retry_state.next_action.sleep} seconds..."
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=16),
    retry=retry_if_exception_type((APIError, ValidationError)),
    before_sleep=log_retry_attempt,
    reraise=True
)
async def _call_llm_with_retry(client: genai.Client, model_name: str, prompt: str, response_schema: Type[BaseModel], temperature: float, max_output_tokens: int):
    response = await client.aio.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
            response_schema=response_schema,
        )
    )
    # Validate result instantly within retry block
    response_schema.model_validate_json(response.text)
    return response


def build_system_prompt(taxonomy: dict[str, Any], batch_context: str) -> str:
    categories_str = ""
    for cat in taxonomy.get("categories", []):
        categories_str += f"- ID: '{cat['id']}'\n  Description: {cat['description']}\n  Examples: {cat.get('examples', [])}\n"
        
    departments_str = ""
    for dept in taxonomy.get("departments", []):
        departments_str += f"- ID: '{dept['id']}'\n  Aliases: {dept.get('aliases', [])}\n"

    priority_rules_str = ""
    for level, rule in taxonomy.get("priority_rules", {}).items():
        priority_rules_str += f"- Level '{level}': {rule['description']}. Markers: {rule.get('markers', [])}\n"

    return f"""You are an AI request classifier for an internal AI unit at a digital agency.
Your task is to classify and structure the incoming internal requests.

### Taxonomy Categories:
{categories_str}

### Target Departments:
{departments_str}

### Priority Rules:
{priority_rules_str}

### Full Batch Context (for duplicate/relation detection):
Use this list of all requests in the current batch to detect duplicates or related requests.
{batch_context}

### Output Rules:
1. `short_summary`, `requested_actions`, and `clarification_questions` MUST be in Ukrainian.
2. `category` and `target_department` MUST strictly match the taxonomy IDs.
3. `needs_clarification` is true if the request is vague, missing context, or out-of-scope. If true, provide 1-3 `clarification_questions`. If false, `clarification_questions` must be empty.
4. Do NOT translate IDs (category, department, priority, estimated_complexity).
"""


async def classify_request(
    request_data: dict[str, str],
    client: genai.Client,
    model_name: str,
    response_schema: Type[BaseModel],
    taxonomy: dict[str, Any],
    rate_limiter: Any,
    batch_context: str,
    temperature: float = 0.0,
    max_output_tokens: int = 1024
) -> ProcessingResult:
    request_id = request_data["id"]
    system_prompt = build_system_prompt(taxonomy, batch_context)
    user_prompt = f"""Classify this request:
ID: {request_id}
Channel: {request_data['channel']}
Timestamp: {request_data['timestamp']}
Raw Text: {request_data['raw_text']}
"""
    full_prompt = f"{system_prompt}\n{user_prompt}"
    estimated_tokens = 1000

    try:
        await rate_limiter.acquire(estimated_tokens)
        response = await _call_llm_with_retry(
            client, model_name, full_prompt, response_schema, temperature, max_output_tokens
        )
        
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count
        rate_limiter.record_actual(estimated_tokens, input_tokens + output_tokens)

        classified_req = response_schema.model_validate_json(response.text)
        return ProcessingResult(
            request=classified_req,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            retries=0
        )
    except Exception as e:
        logger.error(f"Failed to process request {request_id} after retries: {str(e)}")
        return ProcessingResult(
            processing_error=True,
            error_message=str(e),
            raw_llm_response=getattr(e, 'text', None) or str(e)
        )
