"""Immutable stage-calibration projections; no research or qualification writes."""
import hashlib,json
from pathlib import Path
from .assessments import content_version
from .errors import ServiceError
from .settings import APP_ROOT
from .state import now
from .agent_bridge import comparison_packet

REGISTRY=APP_ROOT/'config/pre-outreach-review.json'


def active_sources(registry_path=REGISTRY):
    """Only the server-selected, pinned overlay and guidance can be active."""
    path=Path(registry_path)
    try:
        registry=json.loads(path.read_text(encoding='utf-8-sig'))
        if registry.get('active') is not True:raise ValueError('inactive')
        for key in ('policy_overlay','case_guidance'):
            entry=registry[key];source=APP_ROOT/entry['path']
            if hashlib.sha256(source.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('source changed')
        return registry
    except (OSError,KeyError,ValueError,TypeError) as exc:
        raise ServiceError('pre_outreach_unavailable','The pinned pre-outreach policy/guidance is inactive, missing or changed; no current calibration is claimed.',409) from exc


def _validate_review(value):
    # Pure agent DTO validation is deliberately shared by acceptance and reads.
    from agents.pre_outreach import PreOutreachReview
    return PreOutreachReview.model_validate(value).model_dump(mode='json')


def accept_review(state,context,assessment_id,review,*,sources,registry_path=REGISTRY):
    """Trusted local publication only. HTTP offers no review/status write route."""
    review=_validate_review(review)
    packet=comparison_packet(context,output_tokens=0)
    if review['input_ref']!=packet.ref.model_dump(mode='json') or review['assessment_ref']!=assessment_id:
        raise ServiceError('stale_version','Calibration projection does not bind the supplied case snapshot and actual assessment',409)
    overlay=review['overlay'];pin=sources['policy_overlay']
    if (overlay['source_path'],overlay['source_sha256'],overlay['version'])!=(pin['path'],pin['sha256'],pin['version']) or overlay['base_reference_sha256']!=context.reference_material.document_sha256:
        raise ServiceError('stale_version','Calibration overlay differs from the pinned source and unchanged base mandate',409)
    guidance_pin=sources['case_guidance']
    if (review['guidance_source_path'],review['guidance_source_sha256'],review['guidance_version'])!=(guidance_pin['path'],guidance_pin['sha256'],guidance_pin['version']):
        raise ServiceError('stale_version','Calibration guidance differs from the pinned source',409)
    known={e.id for e in context.evidence};people={p.id for p in packet.people}
    def check_refs(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key=='evidence_ids' and not set(item)<=known:raise ServiceError('invalid_evidence','Calibration cites evidence outside this case',422)
                if key=='person_ids' and not set(item)<=people:raise ServiceError('invalid_evidence','Calibration cites people outside this case',422)
                if key=='person_id' and item is not None and item not in people:raise ServiceError('invalid_evidence','Calibration contact route cites a person outside this case',422)
                check_refs(item)
        elif isinstance(value,list):
            for item in value:check_refs(item)
    check_refs(review)
    payload={'backend_versions':context.versions.model_dump(mode='json'),'assessment_id':assessment_id,'sources':sources,'review':review,'created_at':now()}
    binding={k:payload[k] for k in ('backend_versions','assessment_id','sources')}
    binding_key=content_version(binding);record_id='pre_outreach:'+binding_key[:28]
    with state.connection(write=True) as db:
        current=state._assessment_context(db,context.case.id)
        latest=db.execute('SELECT id,payload FROM semantic_assessments WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(context.case.id,)).fetchone()
        if current.versions!=context.versions or not latest or latest['id']!=assessment_id or json.loads(latest['payload'])['backend_versions']!=payload['backend_versions']:
            raise ServiceError('stale_version','Pre-outreach publication requires the current evidence snapshot and actual assessment',409)
        if active_sources(registry_path)!=sources:
            raise ServiceError('stale_version','Pinned pre-outreach overlay/guidance changed before publication',409)
        prior=db.execute('SELECT payload FROM pre_outreach_reviews WHERE binding_key=?',(binding_key,)).fetchone()
        if prior:
            old=json.loads(prior[0])
            if old['review']!=review:raise ServiceError('invalid_transition','A different review cannot overwrite the same immutable calibration binding',409)
            return record_id
        db.execute('INSERT INTO pre_outreach_reviews VALUES (?,?,?,?,?,?)',(record_id,context.case.id,assessment_id,binding_key,json.dumps(payload),now()))
    return record_id


def pre_outreach_review(state,case_id,*,registry_path=REGISTRY):
    with state.connection(snapshot=True) as db:
        context=state._assessment_context(db,case_id)
        latest=db.execute('SELECT id,payload FROM semantic_assessments WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)).fetchone()
        row=db.execute('SELECT id,payload FROM pre_outreach_reviews WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)).fetchone()
    base={'status':'unavailable','case_id':case_id,'case_version':context.case.version,'assessment_id':latest['id'] if latest else None,'review_id':None,'review':None,'sources':None,'stale_reasons':[],'qualification_accepted':False,'authority':'Human-authorized stage-calibration interpretation of saved evidence; not a new model assessment, formal readiness, qualification or sending permission.'}
    if row is None:return base
    saved=json.loads(row['payload']);reasons=[]
    if saved['backend_versions']!=context.versions.model_dump(mode='json'):reasons.append('case_or_evidence_snapshot_changed')
    if not latest or latest['id']!=saved['assessment_id'] or json.loads(latest['payload'])['backend_versions']!=saved['backend_versions']:reasons.append('current_assessment_changed')
    try:
        if active_sources(registry_path)!=saved['sources']:reasons.append('policy_overlay_or_guidance_changed')
    except ServiceError:reasons.append('policy_overlay_or_guidance_inactive_missing_or_changed')
    return {**base,'status':'stale' if reasons else 'ready','assessment_id':saved['assessment_id'],'review_id':row['id'],'review':_validate_review(saved['review']),'sources':saved['sources'],'stale_reasons':reasons}
