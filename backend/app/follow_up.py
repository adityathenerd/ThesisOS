"""Read-only agent obligations plus an explicit bounded owned task executor."""
import json
import hashlib
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from .state import now
from .settings import APP_ROOT
from agents.models import MatcherResult
from agents.follow_through import (ResearchPoint,ResearchAttempt,Section9Readiness,ReviewCheck,
    ProductReviewCheck,FounderReviewCheck,MaterialContradiction,plan_follow_through)
from .agent_bridge import comparison_packet
from .errors import ServiceError


def _check(assessment,criterion):
    f=next((f for f in assessment.findings if f.criterion_id==criterion),None)
    if f is None:return {'status':'unknown','explanation':'No current sourced semantic finding supplied.','evidence_ids':[]}
    status='supported' if f.result=='meets' and f.evidence_sufficient and not f.conflicted and f.comparison_state=='supported' else ('contradicted' if f.result=='fails' and f.evidence_sufficient and not f.conflicted else ('mixed' if f.evidence_ids else 'unknown'))
    return {'status':status,'explanation':f.rationale,'evidence_ids':list(dict.fromkeys(f.evidence_ids+f.counterevidence_ids))}


def readiness(context,result,assessment_id):
    research=context.research_context or {};basis=research.get('follow_up',{}).get('readiness_basis')
    if not basis or result.ref!=comparison_packet(context,output_tokens=0).ref:return None
    packet=comparison_packet(context,output_tokens=0);a=result.assessment
    founder=_check(a,'C2');finding=next((f for f in a.findings if f.criterion_id=='C2'),None)
    ids=finding.person_ids if finding else []
    if not ids and a.case_brief:ids=[x.person_id for x in a.case_brief.founder_signals]
    # Mixed/unknown evidence is not a material contrary fact. Only explicit,
    # source-backed intake metadata may identify a contradiction of the core bet.
    contradictions=[MaterialContradiction.model_validate(c) for c in basis.get('material_contradictions',[])]
    return Section9Readiness(assessment_ref=assessment_id,input_ref=packet.ref,primary_track=basis['track'],identity_and_scope=ReviewCheck.model_validate(basis['identity_and_scope']),problem_or_program=ReviewCheck(**_check(a,'C1')),founder_contribution=FounderReviewCheck(**founder,person_ids=ids),differentiated_approach=ReviewCheck(**_check(a,'C3')),product_or_experimental_gate=ProductReviewCheck(**_check(a,'C4'),basis=basis['artifact_basis']),material_contradictions=contradictions,remaining_risks=basis['remaining_risks'])


def research_follow_up(state,case_id):
    with state.connection(snapshot=True) as db:
        context=state._assessment_context(db,case_id)
        row=db.execute('SELECT id,payload FROM semantic_assessments WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)).fetchone()
        link=db.execute('SELECT payload FROM research_followup_links WHERE case_id=? AND assessment_id=?',(case_id,row['id'])).fetchone() if row else None
        executions=[json.loads(x[0]) for x in db.execute('SELECT payload FROM research_execution_tasks WHERE case_id=? AND assessment_id=?',(case_id,row['id']))] if row else []
    if not row:raise ServiceError('not_found','No saved recommendation exists for follow-through',404)
    saved=json.loads(row['payload']);result=MatcherResult.model_validate(saved['result'])
    if result.assessment is None:raise ServiceError('not_found','No rich recommendation exists for follow-through',404)
    research=context.research_context or {};follow=research.get('follow_up',{})
    # Historical source questions are not current unresolved questions. Rebuild
    # the latter from this exact saved reassessment, never from stale prose.
    questions=None
    if saved['backend_versions']==context.versions.model_dump(mode='json') and follow:
        a=result.assessment;brief=a.case_brief;inv=a.investigation
        question=inv.question if inv else ('What evidence resolves: '+brief.decisive_doubt.text if brief else a.next_action)
        questions=[ResearchPoint(id='question:current:'+hashlib.sha256(question.encode()).hexdigest()[:20],criterion_ids=[inv.criterion_id] if inv else [],question=question,decision_consequence=inv.decision_consequence if inv else a.stop_or_reopen_condition,what_to_obtain=brief.next_action if brief else a.next_action,evidence_ids=brief.decisive_doubt.evidence_ids if brief else [],investigation=inv)]
    attempts=[ResearchAttempt.model_validate(x) for x in follow.get('attempts',[])]
    binding=json.loads(link[0]) if link else None
    if binding and binding['backend_versions']==context.versions.model_dump(mode='json'):
        questions=[ResearchPoint.model_validate(x) for x in binding['questions']]
        by_task={x['task_id']:x for x in binding['attempt_question_links']}
        attempts=[a.model_copy(update={'question_id':by_task[a.task_id]['question_id']}) if a.task_id in by_task else a for a in attempts]
    for execution in executions:
        if execution['backend_versions']==context.versions.model_dump(mode='json'):attempts.append(ResearchAttempt.model_validate(execution['attempt']))
    packet=comparison_packet(context,output_tokens=0)
    report=readiness(context,result,row['id'])
    plan=plan_follow_through(packet,result,assessment_ref=row['id'],questions=questions,attempts=attempts,readiness=report,current_ref=packet.ref)
    current_binding=binding if binding and binding['backend_versions']==context.versions.model_dump(mode='json') else None
    supplements=current_binding.get('attempt_supplements',{}) if current_binding else {}
    details=[{**d,**supplements.get(d['task_id'],{})} for d in follow.get('attempt_details',[])]
    current_attempts={a.task_id:a for a in attempts}
    details=[{**d,'historical_question_id':d.get('question_id'),'question_id':current_attempts[d['task_id']].question_id} if d['task_id'] in current_attempts else d for d in details]
    return {'case_id':case_id,'case_version':context.case.version,'assessment_id':row['id'],'assessment_current':saved['backend_versions']==context.versions.model_dump(mode='json'),'workflow':plan.model_dump(mode='json'),'attempts':[a.model_dump(mode='json') for a in attempts],'attempt_details':details,'historical_questions':follow.get('questions',[]),'current_question_link_basis':current_binding['attempt_question_links'] if current_binding else [],'available_review_packet':current_binding.get('available_review_packet') if current_binding else None,'pass_id':follow.get('pass_id'),'material_delta_evidence_ids':research.get('changed_evidence_ids',[]),'qualification_accepted':False,'execution_note':'Intent is not execution. Only the explicit version-bound backend executor can reserve/run an allowed source action; private access and unresolved questions require the human.'}


def save_current_question_binding(state,case_id,assessment_id,questions,attempt_links):
    """Explicit reviewed semantic links; never match questions by keyword/hash."""
    with state.connection(write=True) as db:
        context=state._assessment_context(db,case_id);latest=db.execute('SELECT id,payload FROM semantic_assessments WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)).fetchone()
        if not latest or latest['id']!=assessment_id or json.loads(latest['payload'])['backend_versions']!=context.versions.model_dump(mode='json'):raise ServiceError('stale_version','Human research questions require the current saved assessment',409)
        points=[ResearchPoint.model_validate(q) for q in questions];known={e.id for e in context.evidence};task_ids={a['task_id'] for a in (context.research_context or {}).get('follow_up',{}).get('attempts',[])}
        qids={q.id for q in points}
        if any(not set(q.evidence_ids)<=known for q in points) or any(x['task_id'] not in task_ids or x['question_id'] not in qids or not x.get('why_relevant') for x in attempt_links):raise ServiceError('invalid_evidence','Question link requires actual matching case task/evidence and relevance explanation',422)
        if len({x['task_id'] for x in attempt_links})!=len(attempt_links):raise ServiceError('invalid_proposal','One attempt maps to one decisive current question; retain other context in history',422)
        payload={'backend_versions':context.versions.model_dump(mode='json'),'questions':[q.model_dump(mode='json') for q in points],'attempt_question_links':attempt_links}
        old=db.execute('SELECT payload FROM research_followup_links WHERE case_id=? AND assessment_id=?',(case_id,assessment_id)).fetchone()
        if old:
            if json.loads(old[0])!=payload:raise ServiceError('invalid_transition','Current question binding is immutable; preserve the reviewed record',409)
            return
        db.execute('INSERT INTO research_followup_links VALUES (?,?,?,?)',(case_id,assessment_id,json.dumps(payload),now()))


def execute_research_intent(state,case_id,request,*,transport=None):
    """One explicit synchronous source fetch; no scheduler or semantic invention.

    Future authorized contexts may advertise this capability and an exact public
    URL allowlist. The closed enrichment pass advertises no executable tasks.
    """
    flow=research_follow_up(state,case_id);context=state.load_assessment_context(case_id)
    if not flow['assessment_current'] or flow['assessment_id']!=request['assessment_id'] or context.case.version!=request['expected_case_version']:raise ServiceError('stale_version','Research task requires the current recommendation and inputs',409)
    follow=(context.research_context or {}).get('follow_up',{})
    task_id='research_task:'+hashlib.sha256((follow.get('pass_id','')+request['idempotency_key']+flow['workflow']['input_ref']['evidence_hash']).encode()).hexdigest()
    with state.connection() as db:
        prior=db.execute('SELECT payload FROM research_execution_tasks WHERE id=?',(task_id,)).fetchone()
    if prior:return json.loads(prior[0])
    intent=next((x for x in flow['workflow']['task_intents'] if x['idempotency_key']==request['idempotency_key']),None)
    if intent is None:raise ServiceError('invalid_transition','No current executable task is proposed; use the human research points',409)
    inv=intent['investigation'];url=inv['query'];parts=urlsplit(url)
    if inv['action']!='public.web.fetch' or url not in follow.get('allowed_public_urls',[]) or parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.hostname in ['localhost','127.0.0.1','api.crustdata.com']:raise ServiceError('capability_unavailable','This exact source action is not mapped to the bounded public executor',409)
    task_id='research_task:'+hashlib.sha256((follow.get('pass_id','')+intent['idempotency_key']+intent['input_ref']['evidence_hash']).encode()).hexdigest()
    record={'backend_versions':context.versions.model_dump(mode='json'),'url':url,'assessment_id':request['assessment_id'],'attempt':{'task_id':task_id,'question_id':intent['question_id'],'investigation_key':intent['idempotency_key'],'status':'running','summary':'Explicit owned public-source task is running; no result or resolution claimed.','accepted_evidence_ids':[],'source_urls':[url],'attempted_at':now()}}
    with state.connection(write=True) as db:
        actual=state._assessment_context(db,case_id)
        if actual.versions!=context.versions:raise ServiceError('stale_version','Inputs changed before research reservation',409)
        prior=db.execute('SELECT payload FROM research_execution_tasks WHERE id=?',(task_id,)).fetchone()
        if prior:return json.loads(prior[0])
        used=db.execute('SELECT COUNT(*) FROM research_execution_tasks WHERE case_id=? AND assessment_id=?',(case_id,request['assessment_id'])).fetchone()[0]
        if used>=follow.get('remaining_calls',0):raise ServiceError('resource_limit','This accepted source allowance is exhausted',409)
        db.execute('INSERT INTO research_execution_tasks VALUES (?,?,?,?,?)',(task_id,case_id,request['assessment_id'],json.dumps(record),now()))
    folder=APP_ROOT/'backend/work/follow-up-execution';folder.mkdir(exist_ok=True)
    try:
        with httpx.Client(transport=transport,timeout=httpx.Timeout(20,connect=5),trust_env=False,follow_redirects=False) as client:r=client.get(url)
        (folder/(hashlib.sha256(task_id.encode()).hexdigest()+'.response')).write_bytes(r.content)
        record['http_status']=r.status_code;record['response_sha256']=hashlib.sha256(r.content).hexdigest()
        record['attempt'].update(status='no_answer' if r.status_code==200 else 'inaccessible',summary='Exact public source fetched, HTTP '+str(r.status_code)+'. Raw response retained. Its contents have not been accepted as an answer; trusted analysis must establish any material factual delta before reassessment.')
    except httpx.HTTPError as exc:record['attempt'].update(status='failed',summary='Bounded public fetch failed ('+type(exc).__name__+'); no retry or negative company inference.')
    with state.connection(write=True) as db:db.execute('UPDATE research_execution_tasks SET payload=? WHERE id=?',(json.dumps(record),task_id))
    return record
