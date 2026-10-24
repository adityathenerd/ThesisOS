"""Explicit bounded research ingestion/matcher stages, no automatic retries."""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor
import httpx

from backend.scout_batch import environment,ROOT
from backend.app.assessments import AssessmentCoordinator
from backend.app.evaluators import FixtureEvaluator,FixtureEvaluatorAdapter
from backend.app.providers import Candidate,FixtureCatalog
from backend.app.models import Evidence
from backend.app.research_ingest import accept_research
from backend.app.agent_bridge import AgentAssessmentStore,ScriptedGraphTransport,comparison_packet
from backend.app.research_graph import record_research_decision,saved_research_graph,scout_result
from backend.app.state import now
from agents.brief import to_case_brief
from agents.models import MatcherResult
from agents.research_graph import to_mermaid,ResearchGraph


def current():
    settings,state,store=environment()
    return settings,state,store,store.get(json.loads((ROOT/'current.json').read_text())['batch_id'])


def progress(store,batch_id):
    (ROOT/'progress.json').write_text(json.dumps(store.get(batch_id),indent=2),encoding='utf-8')


def prepare(spec_path):
    settings,state,store,batch=current();spec=json.loads(Path(spec_path).read_text(encoding='utf-8-sig'))
    candidate=next(x for x in batch['candidates'] if x['domain']==spec['domain'])
    folder=ROOT/spec['domain'];folder.mkdir(exist_ok=True)
    if (folder/'research.json').exists():print('Research already saved: '+spec['domain']);return
    sources=spec['sources']
    if len({s['url'] for s in sources})>7:raise RuntimeError('Public source bound exceeded')
    task_id=batch.get('research_task_id')
    if not task_id or state.task(task_id).status!='running':
        task,_=state.enqueue_run(batch['mandate_id']);state.start_task(task.id);task_id=task.id
        store.update(batch['id'],research_task_id=task_id,status='researching')
    if candidate.get('case_id'):case=state.detail(candidate['case_id'])
    else:
        state.persist_discovery(task_id,[Candidate(**candidate['encounters'][0]['candidate'])])
        case=next(x for x in state.cases(batch['mandate_id']) if x.company_name==candidate['company_name'])
        # Initial public compatibility state stays unknown; no model or invented score.
        AssessmentCoordinator(state,FixtureEvaluatorAdapter(FixtureEvaluator(FixtureCatalog(settings.fixture_path)))).assess_case(case.id,task_id=task_id)
        case=state.detail(case.id);store.candidate_update(candidate['id'],case_id=case.id,selected=True,stage='researching',screen_reason=spec['selection_reason'])
    def fetch(index_source):
        i,s=index_source;path=folder/f'source-{i}.json'
        if path.exists():return json.loads(path.read_text(encoding='utf-8'))
        receipt={'url':s['url'],'retrieved_at':now(),'retrieval_mode':'direct_public_http','http_status':None}
        try:
            with httpx.Client(timeout=15,follow_redirects=True,max_redirects=5,trust_env=False) as client:r=client.get(s['url'],headers={'User-Agent':'ThesisOSResearch/0.1'})
            receipt.update(http_status=r.status_code,final_url=str(r.url),sha256=hashlib.sha256(r.content).hexdigest())
            (folder/f'source-{i}.html').write_bytes(r.content)
        except httpx.HTTPError as exc:receipt['error_kind']=type(exc).__name__
        path.write_text(json.dumps(receipt,indent=2),encoding='utf-8');return receipt
    with ThreadPoolExecutor(max_workers=3) as pool:receipts=list(pool.map(fetch,enumerate(sources)))
    observations=[];subjects={};metadata=[];people=[];relationships=[];entities=[];assertions=[]
    slug=spec['domain'].replace('.','-');company=case.company_id
    person_ids={p['name']:'person:'+slug+':'+str(i) for i,p in enumerate(spec.get('people',[]))}
    for name,pid in person_ids.items():people.append({'id':pid,'name':name})
    source_eids={};allids=[]
    for i,(s,r) in enumerate(zip(sources,receipts)):
        source_eids[s['url']]=[]
        for j,claim in enumerate(s['claims']):
            if isinstance(claim,str):claim={'text':claim}
            eid=f'evidence:{slug}:{i}:{j}';allids.append(eid);source_eids[s['url']].append(eid)
            # A successful previous source-prep read may support captured text even
            # if direct refetch fails; do not relabel a failed fetch as live proof.
            mode='live' if r['http_status']==200 else 'captured'
            summary=claim['text']+' Limits: '+' '.join(s.get('limits',[]))
            observations.append(Evidence(id=eid,company_id=company,claim_type=claim.get('kind','source_reported_product_or_team_fact'),summary=summary,source_url=s['url'],source_key='batch-public:'+hashlib.sha256((s['url']+summary).encode()).hexdigest(),observed_at=None,retrieved_at=r['retrieved_at'],data_mode=mode))
            name=claim.get('person');subjects[eid]={'kind':'person','id':person_ids[name]} if name else {'kind':'company','id':company}
            date=s.get('publication_date');precision='day' if date and len(date)==10 else ('month' if date and len(date)==7 else 'year')
            metadata.append({'evidence_id':eid,'original_source_id':'source:'+hashlib.sha256(s['url'].encode()).hexdigest()[:16],'assertion_kind':'source_reported','support_status':'unknown','source_type':s.get('source_type','first_party_company_page'),'source_quality':s.get('source_group','source_reported_not_independently_verified'),'publication_time':{'precision':precision,'value':date,'basis':'publication'} if date else {'precision':'unknown'},'limitations':s.get('limits',[])+(['Direct refetch unavailable; claim transcribed from cited source-preparation web read, which may be cached.'] if mode=='captured' else [])})
    for i,p in enumerate(spec.get('people',[])):
        ids=[eid for url in p.get('role_source_urls',[]) for eid in source_eids[url]]
        relationships.append({'id':'role:'+slug+':'+str(i),'person_id':person_ids[p['name']],'company_id':company,'role':p['role'],'status':'supported','evidence_ids':ids})
    for i,artifact in enumerate(spec.get('artifacts',[])):
        eid=[eid for url in artifact['source_urls'] for eid in source_eids[url]];aid='product:'+slug+':'+str(i)
        entities.append({'id':aid,'kind':artifact.get('kind','product'),'label':artifact['name'],'evidence_ids':eid,'attributes':{'verification':'Source description inspected; independent operation/outcomes unknown'}})
        assertions.append({'id':'edge:'+slug+':offers:'+str(i),'from_id':company,'to_id':aid,'relation':artifact.get('relation','describes'),'label':'Source describes product/program','evidence_ids':eid,'assertion_kind':'source_reported','support_status':'unknown','limitation':'Description is not independent performance validation or proof of ownership.'})
    questions=[{'id':'question:'+slug+':'+str(i),'target_node_ids':[company],'criterion_ids':q.get('criterion_ids',[]),'question':q['question'],'decision_consequence':q['decision_consequence']} for i,q in enumerate(spec.get('questions',[]))]
    packet={'people':people,'relationships':relationships,'subjects':subjects,'observation_metadata':metadata,'entities':entities,'assertions':assertions,'questions':questions,'source_fetch_receipts':receipts,'limitations':spec.get('limitations',[])+['No People/Enrich calls. Backing and YC-universe novelty remain unknown unless explicitly sourced.','Named product, role and result claims are attributed reports; source ownership, date and verification limits remain attached.']}
    packet_id=accept_research(state,case.id,observations,packet,expected_case_version=case.version)
    receipt={'case_id':case.id,'pool_id':candidate['id'],'domain':spec['domain'],'research_packet_id':packet_id,'new_observations':len(observations),'sources':receipts,'source_spec':str(spec_path)}
    (folder/'research.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');(folder/'research-spec.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
    store.candidate_update(candidate['id'],stage='research_saved',source_receipts=receipts);progress(store,batch['id']);print(json.dumps(receipt),flush=True)


def match(domain):
    _,state,store,batch=current();folder=ROOT/domain;out=folder/'matcher.json';research=json.loads((folder/'research.json').read_text())
    if out.exists():print(json.dumps({'domain':domain,'existing_receipt':True,'status':json.loads(out.read_text())['status']}));return
    with state.connection(write=True) as db:
        # Durable reservation BEFORE subprocess creation, serialized across workers.
        row=db.execute('SELECT payload FROM scout_batches WHERE id=?',(batch['id'],)).fetchone();payload=json.loads(row[0]);attempts=payload['model_receipts']
        if len(attempts)>=9:raise RuntimeError('Nine model attempts reached; no automatic retries')
        attempts.append({'domain':domain,'status':'reserved','created_at':now()});payload['model_receipts']=attempts
        db.execute('UPDATE scout_batches SET payload=? WHERE id=?',(json.dumps(payload),batch['id']))
    context=state.load_assessment_context(research['case_id']);invocation=state.begin_assessment(context);packet=comparison_packet(context,output_tokens=6500)
    receipt={'status':'started','case_id':research['case_id'],'invocation_id':invocation,'context':packet.model_dump(mode='json'),'attempts':1};out.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    store.candidate_update(research['pool_id'],stage='matching');progress(store,batch['id']);start=perf_counter();transport=ScriptedGraphTransport(timeout_seconds=150,live_authorized=True)
    try:
        result=transport.invoke(packet);receipt.update(result=result.model_dump(mode='json'),metadata=transport.last_metadata)
        # Save the paid model output before any database/projection step.
        out.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        assessment_id=AgentAssessmentStore(state).record(context,invocation,packet,result,provenance='compiled_graph_live')
        receipt.update(status='stored_genuine_result',assessment_id=assessment_id)
    except Exception as exc:
        state.record_assessment_failure(invocation,'batch_matcher_failed','Bounded matcher/integration failed; no automatic retry.')
        receipt.update(status='failed',safe_error=str(exc)[:250])
    receipt['elapsed_seconds']=round(perf_counter()-start,3);out.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    store.candidate_update(research['pool_id'],stage='assessment_saved' if receipt['status']=='stored_genuine_result' else 'matcher_failed');progress(store,batch['id']);print(json.dumps({k:v for k,v in receipt.items() if k not in {'context','result'}}),flush=True)
    if receipt['status']=='stored_genuine_result':finalize(domain)


def finalize(domain):
    _,state,store,batch=current();folder=ROOT/domain;receipt=json.loads((folder/'matcher.json').read_text());research=json.loads((folder/'research.json').read_text())
    if receipt['status']!='stored_genuine_result':raise RuntimeError('No stored genuine result; no paid retry')
    result=MatcherResult.model_validate(receipt['result']);brief=to_case_brief(result,assessment_ref=receipt['assessment_id'])
    if brief is None:raise RuntimeError('Actual matcher did not produce the revised brief')
    store.save_brief(receipt['case_id'],receipt['assessment_id'],brief.model_dump(mode='json'))
    decision=record_research_decision(state,receipt['case_id'],receipt['assessment_id'],decision_consequence=result.assessment.stop_or_reopen_condition)
    graph=ResearchGraph.model_validate(saved_research_graph(state,receipt['case_id']))
    (folder/'research-graph.json').write_text(graph.model_dump_json(indent=2),encoding='utf-8');(folder/'research-graph.mmd').write_text(to_mermaid(graph),encoding='utf-8');(folder/'scout-result.json').write_text(json.dumps(scout_result(state,receipt['case_id']),indent=2),encoding='utf-8')
    with state.connection(write=True) as db:
        # Processing completed; evidence gaps/needs_evidence and human review stay
        # separate. This does not accept a qualification or a synthetic evaluation.
        db.execute('UPDATE case_assessment_state SET pending=0,last_error=NULL,updated_at=? WHERE case_id=?',(now(),receipt['case_id']))
    store.candidate_update(research['pool_id'],stage='complete',assessment_id=receipt['assessment_id'],graph_id=graph.graph_id,research_posture=decision['decision'],next_action=decision['next_action']);progress(store,batch['id'])
    print(json.dumps({'status':'complete','domain':domain,'case_id':receipt['case_id'],'assessment_id':receipt['assessment_id'],'graph_id':graph.graph_id,'research_posture':decision['decision']}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','match','finalize']);p.add_argument('value');p.add_argument('--execute',action='store_true');args=p.parse_args()
    if args.stage=='match' and not args.execute:p.error('Genuine paid matcher requires explicit execute')
    {'prepare':prepare,'match':match,'finalize':finalize}[args.stage](args.value)
