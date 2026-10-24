"""Two explicitly authorized API calls; no Crustdata requests or fallback."""
import argparse
import json
from pathlib import Path
from time import perf_counter

from .drivers import ModelCallError, OpenAIResponsesDriver
from .graphs import build_matcher, build_orchestrator
from .models import MandateContext, Resources
from .reference import allodirect_reference_context


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Explicitly permit two bounded OpenAI calls")
    parser.add_argument("--only-orchestrator", action="store_true", help="One explicit targeted orchestrator retest, no automatic retries")
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    args = parser.parse_args()
    if not args.execute:
        parser.error("Add --execute only when real API testing is authorized")
    report = {"reference": "scouting-mandate.md v0.3", "provider_calls": 0, "api_attempts": 0,
              "scope": "Reference comparison and discovery hypothesis testing; no accepted investment transitions or executed search",
              "timeout_seconds": args.timeout_seconds, "usage_note": "Transport failures may have unknown billed usage; zero usage placeholders do not establish zero spend"}
    work = Path(__file__).parent / "work"
    work.mkdir(exist_ok=True)
    try:
        driver = OpenAIResponsesDriver.from_project(timeout_seconds=args.timeout_seconds)
    except ModelCallError as error:
        report["configuration_failure"] = {"code": error.code, "message": str(error)}
    else:
        report.update(model=driver.model, reasoning_effort=driver.effort, key_configured=True)
        context = allodirect_reference_context()
        report["reference_document_hash"] = context.policy.reference_document_hash
        if not args.only_orchestrator:
            started = perf_counter()
            report["api_attempts"] += 1
            matched = build_matcher(driver).invoke({"context": context})["result"]
            report["matcher"] = {"latency_seconds": round(perf_counter() - started, 3), "usage_available": bool(matched.input_tokens or matched.output_tokens), "result": matched.model_dump(mode="json")}
        # Independent reviewed-reference discovery test, not a fake accepted case projection.
        mandate = MandateContext(policy=context.policy, snapshot_id="reviewed-v03-discovery-test", cases=[],
            active_work_keys=[], completed_work_keys=[], attempted_investigation_keys=[], capabilities=[],
            resources=Resources(remaining_calls=0, remaining_output_tokens=6000), target_count=1,
            review_required_to_count=False, discovery_exhausted=False, mode="discovery_planning")
        started = perf_counter()
        report["api_attempts"] += 1
        planned = build_orchestrator(driver).invoke({"context": mandate})["result"]
        report["orchestrator"] = {"latency_seconds": round(perf_counter() - started, 3), "usage_available": bool(planned.input_tokens or planned.output_tokens), "result": planned.model_dump(mode="json")}
    report_path = work / ("live-smoke-orchestrator-retry.json" if args.only_orchestrator else "live-smoke.json")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    # Full structured results contain source evidence explanations, never the key or raw errors.
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
