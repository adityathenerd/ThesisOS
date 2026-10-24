"""One explicitly authorized thesis-linked search; receipt prevents repeat spend."""
import json
import re
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from backend.app.assessments import AssessmentCoordinator, load_reference_material
from backend.app.discovery import ApprovedCompanySearchProvider, CompanyCatalog, DiscoveryApproval, DiscoveryBranchInput, DiscoveryHypothesisInput, DiscoveryStore, RankedMapping, compile_discovery
from backend.app.evaluators import FixtureEvaluator, FixtureEvaluatorAdapter
from backend.app.models import CreateMandate
from backend.app.providers import FixtureCatalog
from backend.app.settings import APP_ROOT, Settings
from backend.app.state import StateService


def run():
    folder=APP_ROOT/'backend/work/first-scout';folder.mkdir(exist_ok=True)
    receipt_path=folder/'search.json'
    if receipt_path.exists():
        receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
        print(json.dumps({'reused_receipt':True,'status':receipt['status'],'case_id':receipt.get('case_id'),'mandate_id':receipt.get('mandate_id')}))
        return
    settings=Settings.from_environment()
    reference=load_reference_material(APP_ROOT,settings.reference_source_config)
    plan_path=APP_ROOT/'agents/work/live-smoke-orchestrator-retry.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    if plan['reference_document_hash']!=reference.document_sha256:
        raise RuntimeError('Saved plan reference hash mismatch; do not execute a stale hypothesis')
    hypothesis=DiscoveryHypothesisInput.model_validate(next(h for h in plan['orchestrator']['result']['discovery_hypotheses'] if h['id']=='H-referral-workflow'))
    state=StateService(settings.sqlite_path(),reference);state.initialize()
    core=re.search(r"## 1\. The investment thesis\s+\*\*(.*?)\*\*",reference.document_text,re.S).group(1)
    thesis_text=f"Source: {reference.document_path} v{reference.document_version}. Human-reviewed direction; detailed qualification normalization inactive. Full document/outline retained in the detached reference context.\n\n{core}"
    mandate=state.create_mandate(CreateMandate(title='First live scout - v0.3 health/bio, discovery only',thesis_text=thesis_text,target_count=1,reference_status='user_supplied'))
    catalog=CompanyCatalog.model_validate_json((APP_ROOT/'config/provider-catalog/company-search.json').read_text())
    branch=DiscoveryBranchInput(id='first-scout-H-referral-intake',mandate_id=mandate.id,reference_path=reference.document_path,reference_version=reference.document_version,reference_sha256=reference.document_sha256,action='crustdata.company.search',hypothesis=hypothesis,ranked=RankedMapping(criterion_ids=hypothesis.criterion_ids,query='referral intake workflow products for referral coordinators and clinic operations managers, with a working product or attributable deployment',mode='hybrid',explanation='Reviewed direction and saved orchestrator hypothesis; ranked problem/user vocabulary, no size/revenue/pedigree/AI hard filters or product-proof claim.'),fields=['basic_info.name','basic_info.primary_domain'],limit=1)
    compiled=compile_discovery(branch,catalog,reference)
    approval=DiscoveryApproval(id='human-authorized-first-scout-H',mandate_id=mandate.id,branch_digest=compiled.branch_digest,request_digest=compiled.request_digest,catalog_digest=compiled.catalog_digest,scope='discovery_only',approved=True,reviewer='Backend executing explicit human first-scout authorization; not qualification approval',lossy_filters_reviewed=False,max_calls=1,max_result_slots=1,max_quoted_microcredits=compiled.quoted_microcredits_ceiling)
    DiscoveryStore(state).register(compiled,approval,catalog)
    selector=folder/'selection.json';selector.write_text(json.dumps({'approval_id':approval.id,'attempt_key':'initial'}))
    provider=ApprovedCompanySearchProvider(replace(settings,provider_mode='live',crustdata_search_config=selector),state)
    task,_=state.enqueue_run(mandate.id);state.start_task(task.id)
    receipt={'status':'started','mandate_id':mandate.id,'task_id':task.id,'approval_id':approval.id,'branch':branch.model_dump(mode='json'),'request':compiled.request,'orchestrator_plan_reused':str(plan_path),'orchestrator_prompt_version':plan['orchestrator']['result']['prompt_version'],'orchestrator_plan_is_historical':True,'qualification_policy_active':False,'new_model_calls':0,'max_provider_search_calls':1}
    receipt_path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    start=perf_counter()
    try:
        candidates=provider.discover(mandate,1,task_id=task.id)
        catalog_fixture=FixtureCatalog(settings.fixture_path)
        AssessmentCoordinator(state,FixtureEvaluatorAdapter(FixtureEvaluator(catalog_fixture))).complete_discovery(task.id,candidates)
        cases=state.cases(mandate.id)
        receipt.update(status='succeeded' if cases else 'empty',elapsed_seconds=round(perf_counter()-start,3),case_id=cases[0].id if cases else None,company_name=cases[0].company_name if cases else None,canonical_domain=cases[0].canonical_domain if cases else None,returned_count=len(candidates),provider_search_attempts=1,provider='Crustdata Company Search',mode='live',billed_credits='not independently reconciled; conservative quote retained')
    except Exception:
        state.fail_task(task.id,'First-scout search failed; saved execution/usage retained. No automatic retry.')
        receipt.update(status='failed',elapsed_seconds=round(perf_counter()-start,3),provider_search_attempts=1,error='Bounded search/ingestion failed; inspect saved execution. No raw provider/secret details returned.')
    receipt_path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({k:receipt.get(k) for k in ['status','mandate_id','case_id','company_name','canonical_domain','elapsed_seconds','returned_count']}))


if __name__=='__main__':run()
