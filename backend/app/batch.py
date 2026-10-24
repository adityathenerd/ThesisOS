"""Bounded research batch progress/pool; no hidden discovery/model scheduler."""
import json
import re
from dataclasses import asdict
from pathlib import Path

from .assessments import content_version
from .errors import ServiceError
from .models import CreateMandate, Mandate
from .state import now, uid


class BatchStore:
    def __init__(self,state):self.state=state

    def create(self,title,*,target=9):
        if target != 9:raise ServiceError('invalid_batch','This approved batch targets nine new researched cases',422)
        reference=self.state.reference_material
        if reference is None:raise ServiceError('reference_unavailable','Pinned source required',409)
        core=re.search(r'## 1\. The investment thesis\s+\*\*(.*?)\*\*',reference.document_text,re.S).group(1)
        text=f'Research batch: nine NEW source-backed company/founder cases, graphs and genuine research recommendations. Source {reference.document_path} v{reference.document_version}. Human qualification remains separate. Legacy target_count is only a required compatibility field, not this batch completion metric.\n\n{core}'
        mandate=self.state.create_mandate(CreateMandate(title=title,thesis_text=text,target_count=1,reference_status='user_supplied'))
        batch={'id':uid('batch'),'mandate_id':mandate.id,'title':title,'status':'awaiting_revised_plan','target_new_researched_cases':9,'legacy_outreach_target_status':'compatibility_placeholder_not_user_selected','limits':{'search_calls':4,'results_per_search':8,'encounters':32,'successful_matchers':9,'public_urls_per_selected_case':7,'automatic_retries':0},'search_receipts':[],'model_receipts':[],'plan':None,'created_at':now(),'updated_at':now(),'shortfall_reason':None}
        with self.state.connection(write=True) as db:db.execute('INSERT INTO scout_batches VALUES (?,?,?,?)',(batch['id'],mandate.id,json.dumps(batch),batch['created_at']))
        return batch

    def get(self,batch_id):
        with self.state.connection(snapshot=True) as db:
            row=db.execute('SELECT payload FROM scout_batches WHERE id=?',(batch_id,)).fetchone()
            if not row:raise ServiceError('not_found','Research batch not found',404)
            batch=json.loads(row[0]);pool=[json.loads(r[0]) for r in db.execute('SELECT payload FROM scout_batch_candidates WHERE batch_id=? ORDER BY rowid',(batch_id,))]
        stages={}
        for candidate in pool:stages[candidate['stage']]=stages.get(candidate['stage'],0)+1
        complete=[p for p in pool if p['stage']=='complete']
        return {**batch,'progress':{'unique_pool':len(pool),'encounters':sum(len(p['encounters']) for p in pool),'completed_cases':len(complete),'selected_cases':sum(p.get('selected',False) for p in pool),'stage_counts':stages,'new_case_ids':[p['case_id'] for p in pool if p.get('case_id')],'completed_case_ids':[p['case_id'] for p in complete]},'candidates':pool}

    def list(self):
        with self.state.connection() as db:ids=[r[0] for r in db.execute('SELECT id FROM scout_batches ORDER BY rowid')]
        return [{k:v for k,v in self.get(id).items() if k!='candidates'} for id in ids]

    def update(self,batch_id,**changes):
        with self.state.connection(write=True) as db:
            row=db.execute('SELECT payload FROM scout_batches WHERE id=?',(batch_id,)).fetchone()
            if not row:raise ServiceError('not_found','Research batch not found',404)
            batch=json.loads(row[0]);batch.update(changes);batch['updated_at']=now()
            db.execute('UPDATE scout_batches SET payload=? WHERE id=?',(json.dumps(batch),batch_id))

    def candidate_update(self,candidate_id,**changes):
        with self.state.connection(write=True) as db:
            row=db.execute('SELECT payload FROM scout_batch_candidates WHERE id=?',(candidate_id,)).fetchone()
            if not row:raise ServiceError('not_found','Pool candidate not found',404)
            candidate=json.loads(row[0]);candidate.update(changes);candidate['updated_at']=now()
            db.execute('UPDATE scout_batch_candidates SET payload=? WHERE id=?',(json.dumps(candidate),candidate_id))
        return candidate

    def record_pool(self,batch_id,branch,candidates):
        batch=self.get(batch_id)
        old={(p['identity_key'],e['branch_id'],e['rank']) for p in batch['candidates'] for e in p['encounters']}
        by_provider={p['encounters'][0]['candidate'].get('provider_company_id'):p['identity_key'] for p in batch['candidates'] if p['encounters'][0]['candidate'].get('provider_company_id')}
        identities=[by_provider.get(c.provider_company_id,(c.canonical_domain or ('crustdata:'+c.key)).casefold()) for c in candidates]
        additions={(key,branch.id,rank) for rank,key in enumerate(identities,1)}-old
        if len(old)+len(additions)>batch['limits'].get('retained_pool_encounters',32):raise ServiceError('resource_limit','Batch encounter cap reached',409)
        with self.state.connection(write=True) as db:
            for rank,c in enumerate(candidates,1):
                key=identities[rank-1]
                prior=db.execute('SELECT id,payload FROM scout_batch_candidates WHERE batch_id=? AND identity_key=?',(batch_id,key)).fetchone()
                encounter={'branch_id':branch.id,'track':branch.hypothesis.track,'rank':rank,'candidate':asdict(c)}
                if prior:
                    p=json.loads(prior['payload'])
                    if any(e['branch_id']==branch.id and e['rank']==rank for e in p['encounters']):continue
                    p['encounters'].append(encounter)
                    if branch.hypothesis.track not in p['tracks']:p['tracks'].append(branch.hypothesis.track)
                    db.execute('UPDATE scout_batch_candidates SET payload=? WHERE id=?',(json.dumps(p),prior['id']));continue
                known=db.execute('SELECT id FROM companies WHERE canonical_domain=? OR source_key=?',(c.canonical_domain,'crustdata:'+c.key)).fetchone()
                p={'id':uid('pool'),'batch_id':batch_id,'identity_key':key,'company_name':c.company_name,'domain':c.canonical_domain,'description':c.description,'tracks':[branch.hypothesis.track],'encounters':[encounter],'stage':'excluded_existing' if known else 'unreviewed','selected':False,'case_id':None,'screen_reason':'Already exists in saved universe; original scout/old cases are not new-batch successes' if known else None,'source_receipts':[],'created_at':now(),'updated_at':now()}
                db.execute('INSERT INTO scout_batch_candidates VALUES (?,?,?,?)',(p['id'],batch_id,key,json.dumps(p)))

    def brief(self,case_id):
        with self.state.connection(snapshot=True) as db:
            row=db.execute('SELECT payload FROM case_briefs WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)).fetchone()
            if not row:raise ServiceError('not_found','No concise batch brief is saved for this case',404)
            brief=json.loads(row[0]);current=self.state._assessment_context(db,case_id).versions.model_dump(mode='json')
        return {'status':'ready' if brief['backend_versions']==current else 'stale','case_id':case_id,'brief':brief['brief'],'assessment_id':brief['assessment_id']}

    def save_brief(self,case_id,assessment_id,brief):
        with self.state.connection(write=True) as db:
            row=db.execute('SELECT payload FROM semantic_assessments WHERE id=? AND case_id=?',(assessment_id,case_id)).fetchone()
            if not row:raise ServiceError('not_found','Brief requires its saved rich assessment',404)
            data=json.loads(row[0]);context=self.state._assessment_context(db,case_id)
            if data['backend_versions']!=context.versions.model_dump(mode='json'):raise ServiceError('stale_version','Brief assessment is stale',409)
            from agents.models import MatcherResult
            from agents.brief import to_case_brief
            projection=to_case_brief(MatcherResult.model_validate(data['result']),assessment_ref=assessment_id)
            if projection is None or projection.model_dump(mode='json')!=brief:raise ServiceError('invalid_proposal','Brief must be the exact saved matcher projection',422)
            # The brief is a projection, never a fresh factual observation.
            refs=set()
            def visit(v):
                if isinstance(v,dict):
                    for k,x in v.items():
                        if k in {'evidence_ids','source_evidence_ids'} and isinstance(x,list):refs.update(x)
                        else:visit(x)
                elif isinstance(v,list):
                    for x in v:visit(x)
            visit(brief)
            if not refs <= {e.id for e in context.evidence}:raise ServiceError('invalid_evidence','Brief cites evidence outside saved case',422)
            payload={'assessment_id':assessment_id,'backend_versions':data['backend_versions'],'brief':brief}
            if db.execute('SELECT 1 FROM case_briefs WHERE case_id=? AND assessment_id=?',(case_id,assessment_id)).fetchone():return
            db.execute('INSERT INTO case_briefs VALUES (?,?,?,?,?)',(uid('brief'),case_id,assessment_id,json.dumps(payload),now()))
