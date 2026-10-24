"""Bounded JSON subprocess: compiled graph in the agent-owned environment.

Scripted driver only. Does not load credentials or instantiate a network client.
"""
import json
import sys
from time import perf_counter


def main():
    from agents.drivers import ScriptedDriver, OpenAIResponsesDriver
    from agents.graphs import build_matcher
    from agents.models import CaseContext, SemanticAssessment
    packet = json.loads(sys.stdin.buffer.read(250001))
    context = CaseContext.model_validate(packet["context"])
    live = packet.get("driver") == "semantic"
    driver = OpenAIResponsesDriver.from_project(timeout_seconds=120) if live else ScriptedDriver(SemanticAssessment.model_validate(packet["scripted_assessment"]))
    start = perf_counter()
    result = build_matcher(driver).invoke({"context": context, "current_ref": context.ref})["result"]
    print(json.dumps({"result": result.model_dump(mode="json"), "metadata": {"driver_kind": driver.kind, "model": getattr(driver, "model", None), "reasoning_effort": getattr(driver, "effort", None), "latency_seconds": round(perf_counter()-start, 3), "input_tokens": result.input_tokens, "output_tokens": result.output_tokens, "usage_available": bool(result.input_tokens or result.output_tokens), "failure_usage_may_be_unknown": result.outcome == "model_failed"}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"error": "Agent subprocess failed validation/execution; raw details omitted"}))
        raise SystemExit(1)
