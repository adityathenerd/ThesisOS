"""Offline demonstration of actual compiled graphs with labeled scripted findings."""
import json

from .drivers import ScriptedDriver
from .examples import mandate_context, scripted_assessment, test_context, with_founder_evidence
from .graphs import build_matcher, build_orchestrator
from .models import Intent, SemanticPlan


def run():
    context = test_context()
    matcher = build_matcher(ScriptedDriver(scripted_assessment(), scripted_assessment(True)))
    initial = matcher.invoke({"context": context})["result"]
    mandate = mandate_context(context, initial)
    intent = Intent(kind="investigate_claim", case_id=context.ref.case_id, action=initial.investigation.action,
        investigation=initial.investigation, max_calls=1, rationale="Resolve the required founder execution gap")
    orchestrator = build_orchestrator(ScriptedDriver(SemanticPlan(intents=[intent], explanation="Synthetic bounded plan", interpretation_question=None)))
    plan = orchestrator.invoke({"context": mandate})["result"]
    # This simulates backend accepting a NEW synthetic observation, not a provider call.
    updated = with_founder_evidence(context, initial.assessment)
    reassessed = matcher.invoke({"context": updated})["result"]
    return {"test_fixture": True, "model_calls": 0, "provider_calls": 0,
            "initial": initial.model_dump(mode="json"), "plan": plan.model_dump(mode="json"), "reassessed": reassessed.model_dump(mode="json")}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
