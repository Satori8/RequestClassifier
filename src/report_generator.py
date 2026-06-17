import json
import os
from typing import Any
from src.schemas import ProcessingResult


def generate_reports(results: list[ProcessingResult], output_dir: str = "output") -> dict[str, Any]:
    """Generate output.json and analytics.json from all processing results.

    Produces two output files in the specified directory:
    - output.json: Serialized list of all classified requests (or error records).
      Every input request produces exactly one entry — no silent drops.
    - analytics.json: Aggregated statistics including counts by category,
      department, priority, and average confidence score.

    Args:
        results: List of ProcessingResult objects from all requests.
        output_dir: Directory path for output files. Created if it doesn't exist.

    Returns:
        Dictionary containing summary analytics (total, successful, failed,
        average confidence, counts by category/department/priority).
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Save main output.json containing all results (no silent drops)
    # --- Serialize all results to output.json ---
    # Every ProcessingResult becomes an entry: successful requests are dumped
    # via model_dump(), failed ones carry error metadata.
    serialized_results = []
    for res in results:
        if res.processing_error:
            serialized_results.append({
                "processing_error": True,
                "error_message": res.error_message,
                "raw_llm_response": res.raw_llm_response,
                "retries": res.retries
            })
        elif res.request:
            serialized_results.append(res.request.model_dump())

    output_json_path = os.path.join(output_dir, "output.json")
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(serialized_results, f, indent=2, ensure_ascii=False)

    # --- Compute aggregations ---
    # Tally successful vs failed, and aggregate counts by category, department,
    # priority, and average confidence score for the analytics dashboard.
    total_processed = len(results)
    successful = sum(1 for r in results if not r.processing_error)
    failed = total_processed - successful

    category_counts: dict[str, int] = {}
    department_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    total_confidence = 0.0
    confidence_count = 0

    for r in results:
        if not r.processing_error and r.request:
            req = r.request
            # Category
            category_counts[req.category] = category_counts.get(req.category, 0) + 1
            # Department
            if req.target_department:
                department_counts[req.target_department] = department_counts.get(req.target_department, 0) + 1
            # Priority
            priority_counts[req.priority] = priority_counts.get(req.priority, 0) + 1
            # Confidence
            total_confidence += req.confidence_score
            confidence_count += 1

    avg_confidence = total_confidence / confidence_count if confidence_count > 0 else 0.0

    # Aggregate token usage across all results (successful or failed)
    total_input_tokens = sum(r.input_tokens for r in results if r.input_tokens is not None)
    total_output_tokens = sum(r.output_tokens for r in results if r.output_tokens is not None)
    total_tokens = total_input_tokens + total_output_tokens

    # Build the analytics dictionary with summary and breakdowns
    analytics = {
        "summary": {
            "total_requests": total_processed,
            "successfully_processed": successful,
            "failed_processing": failed,
            "average_confidence_score": round(avg_confidence, 4),
            "tokens_used": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_tokens
            }
        },
        "by_category": category_counts,
        "by_department": department_counts,
        "by_priority": priority_counts
    }

    # 3. Save analytics.json
    analytics_json_path = os.path.join(output_dir, "analytics.json")
    with open(analytics_json_path, "w", encoding="utf-8") as f:
        json.dump(analytics, f, indent=2, ensure_ascii=False)

    # 4. Save report.md containing aggregates and requests needing clarification
    report_md_path = os.path.join(output_dir, "report.md")
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write("# Звіт про класифікацію запитів (Request Classification Report)\n\n")
        f.write("## 📊 Агреговані показники (Aggregated Metrics)\n\n")
        
        f.write("### 📁 Кількість запитів за категоріями (Requests by Category)\n")
        for cat, count in sorted(category_counts.items()):
            f.write(f"- **{cat}**: {count} запитів\n")
        f.write("\n")
        
        f.write("### 🏢 Кількість запитів за відділами (Requests by Department)\n")
        for dept, count in sorted(department_counts.items()):
            f.write(f"- **{dept}**: {count} запитів\n")
        f.write("\n")
        
        f.write("### ⚡ Кількість запитів за пріоритетом (Requests by Priority)\n")
        for priority, count in sorted(priority_counts.items()):
            f.write(f"- **{priority}**: {count} запитів\n")
        f.write("\n")
        
        f.write("---\n\n")
        f.write("## ❓ Запити, що потребують уточнення (Requests Needing Clarification)\n\n")
        f.write("У цей список включено запити, які мають прапорець `needs_clarification = True` або оцінку впевненості `confidence_score < 0.8`.\n\n")
        
        # Filter requests needing clarification
        clarification_requests = []
        for r in results:
            if not r.processing_error and r.request:
                req = r.request
                needs_clar = req.needs_clarification
                low_conf = req.confidence_score < 0.8
                
                if needs_clar or low_conf:
                    reasons = []
                    if needs_clar:
                        reasons.append("За оцінкою LLM (needs_clarification = True)")
                    if low_conf:
                        reasons.append(f"Низька впевненість (score = {req.confidence_score} < 0.8)")
                    
                    clarification_requests.append({
                        "id": req.id,
                        "channel": req.channel,
                        "raw_text": req.raw_text,
                        "reason": " & ".join(reasons),
                        "questions": ", ".join(req.clarification_questions) if req.clarification_questions else "Немає питань"
                    })
        
        if clarification_requests:
            f.write("| ID | Джерело | Текст запиту | Причина уточнення | Питання для уточнення |\n")
            f.write("|---|---|---|---|---|\n")
            for cr in clarification_requests:
                # Escape pipe symbols in raw text to avoid breaking markdown table
                clean_text = cr["raw_text"].replace("|", "\\|").replace("\n", " ")
                f.write(f"| {cr['id']} | {cr['channel']} | {clean_text} | {cr['reason']} | {cr['questions']} |\n")
        else:
            f.write("Немає запитів, які потребують уточнення.\n")

    return analytics