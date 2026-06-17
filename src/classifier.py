import logging
import os
from typing import Any, Type
from pydantic import BaseModel, ValidationError
from google import genai
from google.genai import types
from google.genai.errors import APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.schemas import ProcessingResult

logger = logging.getLogger(__name__)


def log_retry_attempt(retry_state):
    """Callback for tenacity to log each retry attempt with error details.

    Args:
        retry_state: tenacity.RetryState containing attempt count, exception,
            and next_action sleep duration.
    """
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
async def _call_llm_with_retry(
    client: genai.Client,
    model_name: str,
    prompt: str,
    response_schema: Type[BaseModel],
    temperature: float,
    max_output_tokens: int
):
    """Call the Gemini LLM with structured output and automatic retry on failure.

    Sends the prompt to Gemini with a response_schema to enforce JSON structure.
    Validates the response against the schema immediately inside the retry block
    so that validation errors (e.g., wrong field types) also trigger retries.

    The @retry decorator uses exponential backoff (1s, 2s, 4s, 8s, 16s) and
    retries on APIError (network/server issues) and ValidationError (schema mismatch).

    Args:
        client: Authenticated google-genai client instance.
        model_name: Gemini model identifier string.
        prompt: Full system + user prompt to send.
        response_schema: Pydantic model class to validate the JSON response against.
        temperature: LLM sampling temperature.
        max_output_tokens: Maximum tokens in the response.

    Returns:
        The raw GenerateContentResponse from the API. Caller must extract .text.

    Raises:
        APIError: If all retries are exhausted for API/server errors.
        ValidationError: If all retries are exhausted for schema validation failures.
    """
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
    # Validate result instantly within retry block so that schema mismatches
    # trigger a retry rather than propagating as an unhandled error.
    response_schema.model_validate_json(response.text)
    return response


def build_system_prompt(taxonomy: dict[str, Any], batch_context: str, template_path: str = "settings/prompt_template.txt") -> str:
    """Build the system prompt for the LLM by injecting taxonomy definitions.

    Dynamically renders categories, departments, and priority rules from the
    taxonomy dict, loads the prompt template from the specified text file,
    and formats it with the dynamic taxonomy rules and batch context.

    Args:
        taxonomy: Parsed taxonomy dictionary with 'categories', 'departments',
            and 'priority_rules' keys.
        batch_context: Newline-separated string of all request IDs and raw text
            summaries in the current batch.
        template_path: Path to the prompt template text file.
            Defaults to "settings/prompt_template.txt".

    Returns:
        Fully formatted system prompt string ready to prepend to a user prompt.
    """
    categories_str = ""
    for cat in taxonomy.get("categories", []):
        categories_str += f"- ID: '{cat['id']}'\n  Description: {cat['description']}\n  Examples: {cat.get('examples', [])}\n"
        
    departments_str = ""
    for dept in taxonomy.get("departments", []):
        departments_str += f"- ID: '{dept['id']}'\n  Aliases: {dept.get('aliases', [])}\n"

    priority_rules_str = ""
    for level, rule in taxonomy.get("priority_rules", {}).items():
        priority_rules_str += f"- Level '{level}': {rule['description']}. Markers: {rule.get('markers', [])}\n"

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Prompt template file not found at {template_path}")
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    return template.format(
        categories=categories_str.strip(),
        departments=departments_str.strip(),
        priority_rules=priority_rules_str.strip(),
        batch_context=batch_context
    )


async def classify_request(
    request_data: dict[str, str],
    client: genai.Client,
    model_name: str,
    response_schema: Type[BaseModel],
    taxonomy: dict[str, Any],
    rate_limiter: Any,
    batch_context: str,
    temperature: float = 0.0,
    max_output_tokens: int = 1024,
    prompt_template_path: str = "settings/prompt_template.txt"
) -> ProcessingResult:
    """Classify a single request using the Gemini LLM.

    Orchestrates the full classification pipeline for one request:
    1. Build the system prompt with taxonomy context and batch context.
    2. Acquire a rate-limited slot before calling the API.
    3. Call the LLM with structured output and automatic retry.
    4. Validate the response against the dynamic schema.
    5. Record actual token usage for accurate rate limiting.
    6. Return a ProcessingResult — always, never raise (no silent drops).

    Args:
        request_data: Dictionary with 'id', 'channel', 'timestamp', 'raw_text'.
        client: Authenticated google-genai client instance.
        model_name: Gemini model identifier.
        response_schema: Dynamic Pydantic model for validated classification output.
        taxonomy: Loaded taxonomy dictionary for prompt building.
        rate_limiter: RateLimiter instance for RPM/TPM control.
        batch_context: Batch-wide context string for duplicate detection.
        temperature: LLM sampling temperature (default 0.0 for deterministic).
        max_output_tokens: Max tokens in LLM response (default 1024).

    Returns:
        ProcessingResult with either the validated classified request or
        error details. Never returns None — every request produces a result.
    """
    request_id = request_data["id"]
    # Build the system prompt with taxonomy context injected dynamically
    system_prompt = build_system_prompt(taxonomy, batch_context, prompt_template_path)
    user_prompt = f"""Classify this request:
ID: {request_id}
Channel: {request_data['channel']}
Timestamp: {request_data['timestamp']}
Raw Text: {request_data['raw_text']}
"""
    # Combine system and user prompts into a single prompt for the LLM
    full_prompt = f"{system_prompt}\n{user_prompt}"
    # Conservative token estimate for rate limiter before we know actual usage
    estimated_tokens = 1000

    try:
        # Wait for a rate-limited slot (may block if RPM/TPM limits are hot)
        await rate_limiter.acquire(estimated_tokens)
        # Call the LLM with retry logic for API errors and validation failures
        response = await _call_llm_with_retry(
            client, model_name, full_prompt, response_schema, temperature, max_output_tokens
        )
        
        # Extract actual token counts from the API response metadata
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count
        # Correct the rate limiter's estimate with real usage for accuracy
        rate_limiter.record_actual(estimated_tokens, input_tokens + output_tokens)

        # Final validation of the response text against the dynamic schema
        classified_req = response_schema.model_validate_json(response.text)
        return ProcessingResult(
            request=classified_req,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            retries=0
        )
    except Exception as e:
        # Catch-all: every failure produces a ProcessingResult with error info.
        # This guarantees zero silent drops — every input request has output.
        logger.error(f"Failed to process request {request_id} after retries: {str(e)}")
        return ProcessingResult(
            processing_error=True,
            error_message=str(e),
            raw_llm_response=getattr(e, 'text', None) or str(e)
        )
