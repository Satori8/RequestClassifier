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
            max_output_tokens=settings.MAX_OUTPUT_TOKENS
        )
        if not result.processing_error:
            progress_tracker.mark_completed(req["id"])
            logger.info(f"Successfully processed request {req['id']}")
        else:
            logger.error(f"Failed to process request {req['id']}: {result.error_message}")
        return result


async def async_main():
    # 1. Load settings
    if not os.path.exists(".env"):
        logger.warning(".env file not found. Ensuring settings fall back to environment variables.")
    settings = Settings()

    # 2. Load taxonomy
    taxonomy = load_taxonomy("settings/taxonomy.yaml")
    categories = [cat["id"] for cat in taxonomy.get("categories", [])]
    departments = [dept["id"] for dept in taxonomy.get("departments", [])]

    # 3. Generate dynamic schema
    response_schema = get_classified_request_model(categories, departments)

    # 4. Load input requests
    requests = read_input_requests(settings.INPUT_CSV_PATH)
    logger.info(f"Loaded {len(requests)} requests from CSV.")

    # Build full batch context (ID and summary)
    batch_context = "\n".join([f"- {r['id']}: {r['raw_text'][:150]}..." for r in requests])

    # 5. Initialize helpers
    progress_tracker = ProgressTracker("output/progress.json")
    rate_limiter = RateLimiter(rpm_limit=settings.RPM_LIMIT, tpm_limit=settings.TPM_LIMIT)
    semaphore = asyncio.Semaphore(settings.SEMAPHORE_LIMIT)

    # Filter out already processed requests
    unprocessed_requests = [r for r in requests if not progress_tracker.is_processed(r["id"])]
    logger.info(f"Found {len(unprocessed_requests)} unprocessed requests.")

    if not unprocessed_requests:
        logger.info("All requests have already been processed. Generating reports with existing progress.")

    # Load existing results if any to prevent silent drops on resume
    existing_results: list[ProcessingResult] = []
    output_json_path = "output/output.json"
    if os.path.exists(output_json_path):
        try:
            with open(output_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    if item.get("processing_error"):
                        existing_results.append(ProcessingResult(
                            processing_error=True,
                            error_message=item.get("error_message"),
                            raw_llm_response=item.get("raw_llm_response"),
                            retries=item.get("retries", 0)
                        ))
                    else:
                        # Parse back into the dynamic model
                        req_obj = response_schema.model_validate(item)
                        existing_results.append(ProcessingResult(request=req_obj))
            logger.info(f"Loaded {len(existing_results)} existing results from output.json.")
        except Exception as e:
            logger.warning(f"Could not load existing results from output.json: {e}")

    # Initialize client
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    # 6. Concurrency Loop
    tasks = [
        process_single_request(
            req, client, settings, response_schema, taxonomy, rate_limiter, progress_tracker, semaphore, batch_context
        )
        for req in unprocessed_requests
    ]
    
    # Run all tasks concurrently
    new_results = await asyncio.gather(*tasks) if tasks else []

    # Merge existing and new results (avoiding duplicates)
    new_ids = {r.request.id if r.request else None for r in new_results}
    merged_results = [r for r in existing_results if (r.request.id if r.request else None) not in new_ids] + list(new_results)

    # Generate reports on merged results
    analytics = generate_reports(merged_results, "output")

    # 7. Optional integrations
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

    # 8. Move output files to completed/ folder and reset progress if all requests are successfully processed
    if requests:
        all_processed = all(progress_tracker.is_processed(r["id"]) for r in requests)
        if all_processed:
            from datetime import datetime
            
            try:
                os.makedirs("completed", exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Move output.json
                output_json = "output/output.json"
                if os.path.exists(output_json):
                    dest_output = os.path.join("completed", f"output_{timestamp}.json")
                    shutil.move(output_json, dest_output)
                    logger.info(f"Output file successfully completed and archived to {dest_output}")
                
                # Move analytics.json
                analytics_json = "output/analytics.json"
                if os.path.exists(analytics_json):
                    dest_analytics = os.path.join("completed", f"analytics_{timestamp}.json")
                    shutil.move(analytics_json, dest_analytics)
                    logger.info(f"Analytics file successfully archived to {dest_analytics}")
                
                # Clear progress.json to allow a fresh run next time
                progress_json = "output/progress.json"
                if os.path.exists(progress_json):
                    os.remove(progress_json)
                    logger.info("Progress tracker reset for the next run.")
                    
            except Exception as e:
                logger.error(f"Failed to archive completed output files: {e}")

    logger.info("Request Classifier Service run completed successfully.")


def main():
    try:
        asyncio.run(async_main())
    except Exception as e:
        logger.critical(f"Unhandled exception in service main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
