"""Bounded nine-case batch CLI. Paid stages require explicit execute + final plan."""
import argparse
import hashlib
import json
from dataclasses import asdict,replace
from pathlib import Path
from time import perf_counter

from backend.app.assessments import load_reference_material
from backend.app.batch import BatchStore
from backend.app.discovery import ApprovedCompanySearchProvider,CompanyCatalog,DiscoveryApproval,DiscoveryBranchInput,DiscoveryHypothesisInput,DiscoveryStore,RankedMapping,compile_discovery
from backend.app.settings import APP_ROOT,Settings
from backend.app.state import StateService

ROOT=APP_ROOT/'backend/work/scout-batch'
PLAN=APP_ROOT/'planning/agents/nine-case-discovery-plan.json'


def environment():
    settings=Settings.from_environment();reference=load_reference_material(APP_ROOT,settings.reference_source_config)
    state=StateService(settings.sqlite_path(),reference);state.initialize()
    ROOT.mkdir(exist_ok=True)
    return settings,state,BatchStore(state)


def prepare():
    _,state,store=environment();pointer=ROOT/'current.json'
    if pointer.exists():batch=store.get(json.loads(pointer.read_text())['batch_id'])
    else:
        batch=store.create('Nine-company product/program research batch - v0.3')
        pointer.write_text(json.dumps({'batch_id':batch['id'],'mandate_id':batch['mandate_id']},indent=2))
    plan=json.loads(PLAN.read_text())
    if plan['max_search_requests']>4 or len(plan['branches'])>4 or any(b['limit']>8 for b in plan['branches']):raise RuntimeError('Plan exceeds user-approved batch bound')
    catalog=CompanyCatalog.model_validate_json((APP_ROOT/'config/provider-catalog/company-search.json').read_text())
    compiled=[]
    for b in plan['branches']:
        # Literal anchors are taken from the exact revised query, no extra filter.
        anchors={'H':('clinical documentation','healthcare providers'),'R':('bioscience research tools','scientists'),'D':('diagnostic tests','clinical use'),'T':('therapeutic assets','drug discovery')}
        problem,buyer=anchors[b['track']]
        h=DiscoveryHypothesisInput(id=b['id']+':hypothesis',criterion_ids=b['criterion_ids'],track=b['track'],route='company_first',hypothesis=b['rationale'],problem_terms=[problem],user_or_buyer_terms=[buyer],artifact_or_milestone_terms=b['artifact_hints'],semantic_checks=['Verify product/program identity and actual artifact before expensive assessment.','Attribute founder/team accomplishments from sources; keep gaps unknown.','Known YC is not novel; operational allowance does not decide merit.'],recall_risks=b['recall_risks'])
        branch=DiscoveryBranchInput(id=b['id'],mandate_id=batch['mandate_id'],reference_path=state.reference_material.document_path,reference_version=state.reference_material.document_version,reference_sha256=state.reference_material.document_sha256,action='crustdata.company.search',hypothesis=h,ranked=RankedMapping(criterion_ids=b['criterion_ids'],query=b['query'],mode=plan['mode'],explanation=b['rationale']),fields=plan['fields'],limit=b['limit'])
        compiled.append(compile_discovery(branch,catalog,state.reference_material))
    payload={'plan_path':str(PLAN),'plan_id':plan['plan_id'],'plan_version':plan['plan_version'],'plan_sha256':hashlib.sha256(PLAN.read_bytes()).hexdigest(),'prompt_version_required':plan['prompt_version'],'branches':[c.model_dump(mode='json') for c in compiled]}
    store.update(batch['id'],plan=payload)
    (ROOT/'compiled-plan.json').write_text(json.dumps(payload,indent=2))
    progress=store.get(batch['id']);(ROOT/'progress.json').write_text(json.dumps(progress,indent=2))
    print(json.dumps({'batch_id':batch['id'],'mandate_id':batch['mandate_id'],'status':batch['status'],'compiled_branches':len(compiled),'required_prompt':plan['prompt_version'],'paid_calls':0}))


def searches():
    settings,state,store=environment();batch=store.get(json.loads((ROOT/'current.json').read_text())['batch_id'])
    stored=batch['plan'];current=json.loads(PLAN.read_text())
    if hashlib.sha256(PLAN.read_bytes()).hexdigest()!=stored['plan_sha256']:raise RuntimeError('Plan changed; rerun free prepare before execution')
    from agents.prompts import PROMPT_VERSION
    if PROMPT_VERSION!=current['prompt_version']:raise RuntimeError('Revised prompt is not ready; no paid call made')
    catalog=CompanyCatalog.model_validate_json((APP_ROOT/'config/provider-catalog/company-search.json').read_text())
    from backend.app.discovery import CompiledDiscovery
    receipts=batch['search_receipts'];store.update(batch['id'],status='discovering')
    for item in stored['branches']:
        c=CompiledDiscovery.model_validate(item)
        if any(r['branch_id']==c.branch.id for r in receipts):continue
        if len(receipts)>=4:raise RuntimeError('Batch search cap reached')
        approval=DiscoveryApproval(id=batch['id']+':'+c.branch.id,mandate_id=batch['mandate_id'],branch_digest=c.branch_digest,request_digest=c.request_digest,catalog_digest=c.catalog_digest,scope='discovery_only',approved=True,reviewer='Backend executing explicit human nine-case scope and control-reviewed revised plan',lossy_filters_reviewed=False,max_calls=1,max_result_slots=c.branch.limit,max_quoted_microcredits=c.quoted_microcredits_ceiling)
        DiscoveryStore(state).register(c,approval,catalog)
        selector=ROOT/(c.branch.id+'.selection.json');selector.write_text(json.dumps({'approval_id':approval.id,'attempt_key':'initial'}))
        provider=ApprovedCompanySearchProvider(replace(settings,provider_mode='live',crustdata_search_config=selector),state)
        task,_=state.enqueue_run(batch['mandate_id']);state.start_task(task.id)
        receipt={'branch_id':c.branch.id,'track':c.branch.hypothesis.track,'approval_id':approval.id,'task_id':task.id,'request':c.request,'status':'started','created_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
        receipts.append(receipt);store.update(batch['id'],search_receipts=receipts)
        (ROOT/'search-receipts.json').write_text(json.dumps(receipts,indent=2))
        start=perf_counter()
        try:
            candidates=provider.discover(state.mandate(batch['mandate_id']),8,task_id=task.id)
            store.record_pool(batch['id'],c.branch,candidates)
            state.complete_task(task.id)
            receipt.update(status='succeeded',returned_count=len(candidates),elapsed_seconds=round(perf_counter()-start,3))
        except Exception:
            state.fail_task(task.id,'Batch search failed; no automatic retry. Inspect branch receipt before additional spending.')
            receipt.update(status='failed',elapsed_seconds=round(perf_counter()-start,3),usage='unknown on failure; reservation retained')
        store.update(batch['id'],search_receipts=receipts)
        progress=store.get(batch['id']);(ROOT/'progress.json').write_text(json.dumps(progress,indent=2));(ROOT/'search-receipts.json').write_text(json.dumps(receipts,indent=2))
        print(json.dumps({'track':receipt['track'],'status':receipt['status'],'returned_count':receipt.get('returned_count'),'unique_pool':progress['progress']['unique_pool']}),flush=True)
    store.update(batch['id'],status='screening')
    (ROOT/'progress.json').write_text(json.dumps(store.get(batch['id']),indent=2))


def recovery():
    """Explicit control-authorized once-per-branch recovery; no hidden retries."""
    settings,state,store=environment();batch=store.get(json.loads((ROOT/'current.json').read_text())['batch_id'])
    catalog=CompanyCatalog.model_validate_json((APP_ROOT/'config/provider-catalog/company-search.json').read_text())
    from backend.app.discovery import CompiledDiscovery
    receipts=batch['search_receipts']
    store.update(batch['id'],recovery_authority='Control explicitly authorized one R recovery, then D/T once each only if R succeeds; max seven total attempts. Original three HTTP200 responses lost during local normalization; usage reconciled at 0.24 credits each.',limits={**batch['limits'],'search_calls':7,'retained_pool_encounters':32,'original_provider_returned_encounters':32,'additional_recovery_encounters_max':24})
    for item in batch['plan']['branches']:
        c=CompiledDiscovery.model_validate(item);track=c.branch.hypothesis.track
        if track=='H':continue
        previous=next((r for r in receipts if r['branch_id']==c.branch.id and r.get('recovery')),None)
        if previous:
            if previous['status']!='succeeded':raise RuntimeError('Prior explicit recovery failed; no further automatic spending')
            continue
        approval=DiscoveryApproval(id=batch['id']+':'+c.branch.id+':recovery',mandate_id=batch['mandate_id'],branch_digest=c.branch_digest,request_digest=c.request_digest,catalog_digest=c.catalog_digest,scope='discovery_only',approved=True,reviewer='Explicit control recovery authorization after free usage reconciliation; one repeat only',lossy_filters_reviewed=False,max_calls=1,max_result_slots=8,max_quoted_microcredits=c.quoted_microcredits_ceiling)
        DiscoveryStore(state).register(c,approval,catalog)
        selector=ROOT/(c.branch.id+'.recovery.selection.json');selector.write_text(json.dumps({'approval_id':approval.id,'attempt_key':'explicit-recovery-1'}))
        provider=ApprovedCompanySearchProvider(replace(settings,provider_mode='live',crustdata_search_config=selector),state)
        rawpath=ROOT/(track+'-recovery-raw.json')
        provider.raw.response_sink=lambda payload:rawpath.write_text(json.dumps(payload,indent=2),encoding='utf-8')
        task,_=state.enqueue_run(batch['mandate_id']);state.start_task(task.id)
        receipt={'branch_id':c.branch.id,'track':track,'recovery':True,'approval_id':approval.id,'task_id':task.id,'status':'started','raw_response_path':str(rawpath),'request':c.request}
        receipts.append(receipt);store.update(batch['id'],search_receipts=receipts)
        start=perf_counter()
        try:
            candidates=provider.discover(state.mandate(batch['mandate_id']),8,task_id=task.id)
            store.record_pool(batch['id'],c.branch,candidates);state.complete_task(task.id)
            receipt.update(status='succeeded',returned_count=len(candidates))
        except Exception as exc:
            state.fail_task(task.id,'Explicit recovery failed; no automatic retry.');receipt.update(status='failed',safe_error=str(exc),diagnostic=provider.raw.last_diagnostic)
        receipt['elapsed_seconds']=round(perf_counter()-start,3)
        store.update(batch['id'],search_receipts=receipts,status='screening' if receipt['status']=='succeeded' else 'recovery_blocked')
        (ROOT/'search-receipts.json').write_text(json.dumps(receipts,indent=2));(ROOT/'progress.json').write_text(json.dumps(store.get(batch['id']),indent=2))
        print(json.dumps(receipt),flush=True)
        if receipt['status']!='succeeded':break


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['prepare','searches','recovery','progress']);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.stage=='prepare':prepare()
    elif args.stage in {'searches','recovery'}:
        if not args.execute:parser.error('Paid stage requires --execute under current authorization')
        (searches if args.stage=='searches' else recovery)()
    else:
        _,_,store=environment();print(json.dumps(store.get(json.loads((ROOT/'current.json').read_text())['batch_id']),indent=2))


if __name__=='__main__':main()
