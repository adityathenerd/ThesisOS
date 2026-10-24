"""Trusted backend ingestion of a bounded, attributable research packet."""
import json

from agents.models import Person, Relationship
from agents.research_graph import AssertionSpec, EntitySpec, ObservationGraphMetadata, ResearchQuestion

from .errors import ServiceError
from .models import Case, Mandate
from .state import now, uid


def accept_research(state, case_id, observations, packet, *, expected_case_version):
    with state.connection(write=True) as db:
        case = state._read(db, "cases", Case, case_id)
        if case.version != expected_case_version:
            raise ServiceError("stale_version", "Research ingestion expected a different case version", 409)
        people = [Person.model_validate(p) for p in packet.get("people", [])]
        relationships = [Relationship.model_validate(r) for r in packet.get("relationships", [])]
        people_ids, role_ids = {p.id for p in people}, {r.id for r in relationships}
        if len(people_ids) != len(people) or len(role_ids) != len(relationships):
            raise ServiceError("invalid_evidence", "Research identities must be unique", 422)
        allowed = {e.id for e in state._evidence(db, case_id)} | {e.id for e in observations}
        for e in observations:
            if e.company_id != case.company_id or not (e.source_key or e.source_url):
                raise ServiceError("invalid_evidence", "Research observations require case ownership and provenance", 422)
        for rel in relationships:
            if rel.company_id != case.company_id or rel.person_id not in people_ids or not rel.evidence_ids or not set(rel.evidence_ids) <= allowed:
                raise ServiceError("invalid_evidence", "Relationship lacks supplied attribution evidence or belongs elsewhere", 422)
        for evidence_id, subject in packet.get("subjects", {}).items():
            scopes = {"company": {case.company_id}, "person": people_ids, "relationship": role_ids}
            if evidence_id not in allowed or subject["kind"] not in scopes or subject["id"] not in scopes[subject["kind"]]:
                raise ServiceError("invalid_evidence", "Research subject attribution is outside this saved case packet", 422)
        for field, model in (("observation_metadata", ObservationGraphMetadata), ("entities", EntitySpec), ("assertions", AssertionSpec), ("questions", ResearchQuestion)):
            for data in packet.get(field, []):
                item = model.model_validate(data)
                refs = [item.evidence_id] if field == "observation_metadata" else getattr(item, "evidence_ids", [])
                if not set(refs) <= allowed:
                    raise ServiceError("invalid_evidence", "Research graph mapping cites unavailable evidence", 422)
        for e in observations:
            db.execute("INSERT INTO evidence VALUES (?,?,?,?)", (e.id, e.company_id, e.source_key, e.model_dump_json()))
            db.execute("INSERT INTO case_evidence VALUES (?,?)", (case_id, e.id))
        packet_id = uid("research")
        db.execute("INSERT INTO case_research_packets VALUES (?,?,?,?)", (packet_id, case_id, json.dumps(packet), now()))
        state._invalidate_human_review(db, case)
        case.version, case.updated_at = case.version + 1, now()
        db.execute("UPDATE cases SET payload=? WHERE id=?", (case.model_dump_json(), case_id))
        db.execute("UPDATE case_assessment_state SET pending=1,updated_at=? WHERE case_id=?", (now(), case_id))
        state._event(db, case_id, "research_observations_saved", "Bounded public-source observations and explicit person/role/entity mappings saved. Claims remain source-reported; no product, clinical, YC novelty or qualification is certified.", [e.id for e in observations], data_mode=case.data_mode)
        state._reconcile(db, state._read(db, "mandates", Mandate, case.mandate_id))
        return packet_id
