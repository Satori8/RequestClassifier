import asyncio
import json
import logging
import os
import shutil
import sys
from typing import Any

from google import genai

from src.classifier import classify_request
from src.config import Settings, load_taxonomy
from src.csv_reader import read_input_requests
from src.progress import ProgressTracker
from src.rate_limiter import RateLimiter
from src.report_generator import generate_reports
from src.schemas import ProcessingResult, get_classified_request_model
from src.sheets_export import export_to_sheets
from src.telegram_digest import send_telegram_digest

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("src.main")


async def process_single_request(
    req: dict[str, str],
    client: genai.Client,
    settings: Settings,
    response_schema: Any,
    taxonomy: dict[str, Any],
    rate_limiter: RateLimiter,
    progress_tracker: ProgressTracker,
    semaphore: asyncio.Semaphore,
    batch_context: str
) -> ProcessingResult:
    """Process one request under a concurrency semaphore.

    Wraps the classify_request call with semaphore acquisition so at most
    N requests run concurrently (N = SEMAPHORE_LIMIT). Tracks completion
    via ProgressTracker for resumability.

    Args:
        req: Single request dict with 'id', 'channel', 'timestamp', 'raw_text'.
        client: Authenticated google-genai client.
        settings: Application settings (model, temperature, etc.).
        response_schema: Dynamic Pydantic model for validation.
        taxonomy: Loaded taxonomy dict.
        rate_limiter: RateLimiter for RPM/TPM control.
        progress_tracker: ProgressTracker for resumable processing.
        semaphore: asyncio.Semaphore limiting concurrency.
        batch_context: Batch-wide context for duplicate detection.

    Returns:
        ProcessingResult with the classified request or error details.
    """
    async with semaphore:
        logger.info(f"Starting processing for request {req['id']}")
        result = await classify_request(
            request_data=req,
            client=client,
            model_name=settings.MODEL_NAME,
            response_schema=response_schema,
            taxonomy=taxonomy,
            rate_limiter=rate_limiter,
            batch_context=batch_context,
            temperature=settings.TEMPERATURE,
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,
            prompt_template_path=settings.PROMPT_TEMPLATE_PATH
        )
        # Mark progress only on success so failed requests retry on resume
        if not result.processing_error:
            progress_tracker.mark_completed(req["id"])
            logger.info(f"Successfully processed request {req['id']}")
        else:
            logger.error(f"Failed to process request {req['id']}: {result.error_message}")
        return result


async def async_main():
    """Main async entry point orchestrating the full classification pipeline.

    Execution flow:
    1. Load settings from .env / environment variables.
    2. Load taxonomy from YAML and extract category/department lists.
    3. Dynamically generate the Pydantic response schema with validators.
    4. Read input requests from CSV.
    5. Build batch context for duplicate detection across requests.
    6. Initialize helpers: ProgressTracker, RateLimiter, concurrency Semaphore.
    7. Filter out already-processed requests (resumability).
    8. Load any existing results from a previous run (prevents silent drops).
    9. Run classification on unprocessed requests concurrently.
    10. Merge new results with existing results (deduplicated by request ID).
    11. Generate output.json and analytics.json reports.
    12. Optional: export to Google Sheets and send Telegram digest.
    13. Archive completed output files and reset progress for the next run.
    """
    # 1. Load settings from .env file or environment variables
    if not os.path.exists(".env"):
        logger.warning(".env file not found. Ensuring settings fall back to environment variables.")
    settings = Settings()

    # --- 2. Load taxonomy from YAML ---
    # Extract category and department IDs for dynamic schema generation
    taxonomy = load_taxonomy("settings/taxonomy.yaml")
    categories = [cat["id"] for cat in taxonomy.get("categories", [])]
    departments = [dept["id"] for dept in taxonomy.get("departments", [])]

    # --- 3. Generate dynamic Pydantic schema with runtime validators ---
    # The schema is built from the loaded taxonomy lists, not hardcoded,
    # so taxonomy changes don't require code changes.
    response_schema = get_classified_request_model(categories, departments)

    # --- 4. Load input requests from CSV ---
    requests = read_input_requests(settings.INPUT_CSV_PATH)
    logger.info(f"Loaded {len(requests)} requests from CSV.")

    # Build full batch context (ID + truncated raw text) for the LLM prompt.
    # This enables the model to detect duplicates and cross-references between
    # requests in the same batch (e.g., REQ-013 referencing REQ-001).
    batch_context = "\n".join([f"- {r['id']}: {r['raw_text'][:150]}..." for r in requests])

    # --- 5. Initialize helper objects ---
    # ProgressTracker persists completed request IDs to a JSON file,
    # allowing the service to resume from where it left off if interrupted.
    progress_tracker = ProgressTracker("output/progress.json")
    # RateLimiter prevents hitting API rate limits using a sliding window
    rate_limiter = RateLimiter(rpm_limit=settings.RPM_LIMIT, tpm_limit=settings.TPM_LIMIT)
    # Semaphore caps concurrent API calls (default 5) to avoid overwhelming
    # both the API endpoint and local resources.
    semaphore = asyncio.Semaphore(settings.SEMAPHORE_LIMIT)

    # --- Filter out already processed requests for resumability ---
    unprocessed_requests = [r for r in requests if not progress_tracker.is_processed(r["id"])]
    logger.info(f"Found {len(unprocessed_requests)} unprocessed requests.")

    if not unprocessed_requests:
        logger.info("All requests have already been processed. Generating reports with existing progress.")

    # --- Load existing results for merge (prevents silent drops on resume) ---
    # When resuming, we need to preserve results from the previous run so that
    # every request from the original batch still appears in the final output.
    existing_results: list[ProcessingResult] = []
    output_json_path = "output/output.json"
    if os.path.exists(output_json_path):
        try:
            with open(output_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Deserialize each entry: errors become ProcessingResult with error,
                # successful entries are re-validated through the dynamic schema.
                for item in data:
                    if item.get("processing_error"):
                        existing_results.append(ProcessingResult(
                            processing_error=True,
                            error_message=item.get("error_message"),
                            raw_llm_response=item.get("raw_llm_response"),
                            retries=item.get("retries", 0)
                        ))
                    else:
                        # Re-validate the stored request data through the dynamic
                        # schema to ensure it's still structurally valid
                        req_obj = response_schema.model_validate(item)
                        existing_results.append(ProcessingResult(request=req_obj))
            logger.info(f"Loaded {len(existing_results)} existing results from output.json.")
        except Exception as e:
            logger.warning(f"Could not load existing results from output.json: {e}")

    # Initialize the Gemini client with the API key from settings
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    # --- 6. Create concurrent tasks for unprocessed requests ---
    # Each task is wrapped in process_single_request which acquires a semaphore
    # slot before calling the LLM, ensuring at most SEMAPHORE_LIMIT concurrent calls.
    tasks = [
        process_single_request(
            req, client, settings, response_schema, taxonomy, rate_limiter, progress_tracker, semaphore, batch_context
        )
        for req in unprocessed_requests
    ]
    
    # Run all tasks concurrently via asyncio.gather. If all requests are already
    # processed (empty tasks list), gather returns an empty list.
    new_results = await asyncio.gather(*tasks) if tasks else []

    # --- Merge existing and new results (deduplicate by request ID) ---
    # Strategy: take all existing results whose IDs don't appear in new_results,
    # then append new_results. This avoids duplicating requests that were
    # processed in a previous (incomplete) run and still appear in output.json.
    new_ids = {r.request.id if r.request else None for r in new_results}
    merged_results = [r for r in existing_results if (r.request.id if r.request else None) not in new_ids] + list(new_results)

    # --- Generate output.json and analytics.json reports ---
    analytics = generate_reports(merged_results, "output")

    # --- 7. Optional integrations (graceful skip if not configured) ---
    export_to_sheets(
        merged_results,
        settings.GOOGLE_SHEETS_CREDENTIALS_PATH,
        settings.GOOGLE_SHEETS_SPREADSHEET_ID
    )
    
    await send_telegram_digest(
        analytics,
        settings.TELEGRAM_BOT_TOKEN,
        settings.TELEGRAM_CHAT_ID
    )

    # --- 8. Archive completed run and reset progress ---
    # Only archive when ALL requests in the batch have been successfully processed.
    # This prevents archiving mid-way through a resumed run.
    if requests:
        all_processed = all(progress_tracker.is_processed(r["id"]) for r in requests)
        if all_processed:
            from datetime import datetime

            try:
                os.makedirs("completed", exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                # Archive output.json with a timestamp to preserve run history
                output_json = "output/output.json"
                if os.path.exists(output_json):
                    dest_output = os.path.join("completed", f"output_{timestamp}.json")
                    shutil.move(output_json, dest_output)
                    logger.info(f"Output file successfully completed and archived to {dest_output}")

                # Archive analytics.json alongside the output
                analytics_json = "output/analytics.json"
                if os.path.exists(analytics_json):
                    dest_analytics = os.path.join("completed", f"analytics_{timestamp}.json")
                    shutil.move(analytics_json, dest_analytics)
                    logger.info(f"Analytics file successfully archived to {dest_analytics}")

                # Clear progress.json so the next run starts fresh, without
                # incorrectly skipping all requests.
                progress_json = "output/progress.json"
                if os.path.exists(progress_json):
                    os.remove(progress_json)
                    logger.info("Progress tracker reset for the next run.")

            except Exception as e:
                logger.error(f"Failed to archive completed output files: {e}")

    logger.info("Request Classifier Service run completed successfully.")


def main():
    """CLI entry point: runs the async classification pipeline.

    Wraps async_main() in asyncio.run() and catches any unhandled exceptions
    at the top level, logging them as critical errors before exiting with
    a non-zero status code.
    """
    try:
        asyncio.run(async_main())
    except Exception as e:
        logger.critical(f"Unhandled exception in service main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
