import unittest

from agents.drivers import ScriptedDriver
from agents.examples import scripted_assessment,test_context
from agents.graphs import build_matcher
from agents.pre_outreach import (CalibrationClaim,ContactRouteStatus,IntroBlocker,IntroCondition,IntroContraryFact,IntroMinimum,
    PreOutreachGuidance,PreOutreachOverlay,RelevantPersonStatus,build_pre_outreach_review)


def inputs():
    ctx=test_context();ctx=ctx.model_copy(update={'policy':ctx.policy.model_copy(update={'reference_document_hash':'a'*64,'approved':False,'reference_direction_reviewed':True}),'mode':'reference_comparison'})
    a=scripted_assessment();a=a.model_copy(update={'findings':[f.model_copy(update={'result':'unknown','evidence_sufficient':False}) if f.criterion_id=='prototype' else f for f in a.findings]})
    result=build_matcher(ScriptedDriver(a)).invoke({'context':ctx})['result']
    overlay=PreOutreachOverlay(id='synthetic-stage-test',source_path='synthetic-policy',source_sha256='b'*64,base_reference_sha256='a'*64,authorization_ref='synthetic-software-test-not-human-approval')
    claim=IntroCondition(text='Synthetic sourced concrete referral software/problem merits a conversation.',evidence_ids=['e-company'],status='supported')
    guide=PreOutreachGuidance(source_path='synthetic-guidance',source_sha256='c'*64,version='test1',entry_id=ctx.ref.case_id,input_ref=ctx.ref,assessment_ref='stored',author='synthetic-test',suggested_category='outreach_candidate',
        rationale=CalibrationClaim(text='Understand the documented referral product and team approach.',evidence_ids=['e-company']),minimum=IntroMinimum(identity_and_scope=claim,concrete_product_program_or_problem=claim,useful_conversation_reason=claim),
        call_questions=[CalibrationClaim(text='Can you show the product and explain who built it?',evidence_ids=['e-prototype','e-role']),CalibrationClaim(text='What validation and rights/access remain unresolved?',evidence_ids=[])],
        relevant_person=RelevantPersonStatus(status='unknown',explanation='Founder/operator currentness remains unknown.'),contact_route=ContactRouteStatus(status='not_established',explanation='No contact route established.'))
    return ctx,result,overlay,guide


def run(**changes):
    ctx,result,overlay,guide=inputs()
    return build_pre_outreach_review(changes.pop('context',ctx),changes.pop('result',result),assessment_ref='stored',overlay=changes.pop('overlay',overlay),guidance=changes.pop('guidance',guide),**changes)


class PreOutreachTests(unittest.TestCase):
    def test_credible_intro_is_not_blocked_by_unknown_demos_contribution_validation_or_rights(self):
        ctx,result,overlay,guide=inputs();before=result.model_dump_json()
        review=build_pre_outreach_review(ctx,result,assessment_ref='stored',overlay=overlay,guidance=guide)
        self.assertEqual(review.category,'outreach_candidate');self.assertFalse(review.changes_formal_readiness);self.assertFalse(review.changes_qualification)
        self.assertFalse(review.newly_executed_model);self.assertFalse(review.sending_authorized)
        self.assertEqual(before,result.model_dump_json());self.assertIsNone(result.disposition)
        self.assertEqual(len(review.call_questions),2)

    def test_unknown_person_or_route_does_not_nullify_merit_or_invent_actionability(self):
        review=run();self.assertEqual(review.next_step,'resolve_person_or_route_for_human_review');self.assertEqual(review.relevant_person.person_ids,[])
        ctx,result,overlay,guide=inputs();guide=guide.model_copy(update={'relevant_person':RelevantPersonStatus(status='historical_or_uncertain',person_ids=['test-person'],evidence_ids=['e-role'],explanation='Current role unconfirmed')})
        self.assertEqual(run(guidance=guide).category,'outreach_candidate')

    def test_current_operator_status_issue_can_require_research_first_without_validation_gate(self):
        ctx,result,overlay,guide=inputs();guide=guide.model_copy(update={'suggested_category':'research_first','pre_intro_blocker':IntroBlocker(kind='current_operator_or_status',text='Current operator and operating status unresolved.',evidence_ids=['e-role'],what_to_resolve='Confirm who currently operates the project.',decision_consequence='Would make a current introduction honest.')})
        self.assertEqual(run(guidance=guide).category,'research_first')

    def test_unresolved_exact_identity_downgrades_candidate_with_honest_reason(self):
        ctx,result,overlay,guide=inputs();minimum=guide.minimum.model_copy(update={'identity_and_scope':IntroCondition(text='Exact company identity is unresolved.',status='unresolved',evidence_ids=[])})
        review=run(guidance=guide.model_copy(update={'minimum':minimum}));self.assertEqual(review.category,'research_first');self.assertIn('identity is unresolved',review.rationale.text)

    def test_only_affirmative_sourced_mismatch_supports_outside_scope(self):
        ctx,result,overlay,guide=inputs();fact=IntroContraryFact(text='Synthetic confirmed unrelated sector.',effect='confirmed_outside_scope',evidence_ids=['e-company'])
        review=run(guidance=guide.model_copy(update={'contrary_facts':[fact]}));self.assertEqual(review.category,'outside_scope');self.assertEqual(review.rationale.text,fact.text)
        with self.assertRaises(ValueError):run(guidance=guide.model_copy(update={'suggested_category':'outside_scope'}))
        with self.assertRaises(ValueError):run(guidance=guide.model_copy(update={'contrary_facts':[fact.model_copy(update={'evidence_ids':[]})]}))

    def test_scientific_limitation_travels_to_call_not_automatic_rejection(self):
        ctx,result,overlay,guide=inputs();fact=IntroContraryFact(text='Synthetic biomarker limitation remains.',effect='limits_claim',evidence_ids=['e-company'])
        self.assertEqual(run(guidance=guide.model_copy(update={'contrary_facts':[fact]})).category,'outreach_candidate')
        self.assertEqual(run(guidance=guide.model_copy(update={'contrary_facts':[fact.model_copy(update={'effect':'prevents_honest_intro'})]})).category,'research_first')

    def test_monitor_requires_future_merit_not_missing_private_diligence_or_budget(self):
        ctx,result,overlay,guide=inputs()
        with self.assertRaises(ValueError):run(guidance=guide.model_copy(update={'suggested_category':'monitor'}))
        minimum=guide.minimum.model_copy(update={'useful_conversation_reason':IntroCondition(text='No useful conversation reason until a specific in-scope program is launched.',status='unresolved',evidence_ids=['e-company'])})
        guide=guide.model_copy(update={'suggested_category':'monitor','minimum':minimum,'future_merit_trigger':CalibrationClaim(text='A named in-scope program is launched.',evidence_ids=['e-company'])})
        self.assertEqual(run(guidance=guide).category,'monitor')
        with self.assertRaises(ValueError):run(guidance=guide.model_copy(update={'future_merit_trigger':None}))

    def test_stale_case_assessment_reference_and_unknown_citations_rejected(self):
        ctx,result,overlay,guide=inputs()
        for changed in [guide.model_copy(update={'assessment_ref':'other'}),guide.model_copy(update={'input_ref':guide.input_ref.model_copy(update={'case_version':8})}),guide.model_copy(update={'rationale':CalibrationClaim(text='Invented positive',evidence_ids=['invented'])})]:
            with self.assertRaises(ValueError):run(guidance=changed)
        with self.assertRaises(ValueError):run(overlay=overlay.model_copy(update={'base_reference_sha256':'d'*64}))

    def test_person_and_contact_route_claims_require_real_bound_evidence(self):
        ctx,result,overlay,guide=inputs()
        with self.assertRaises(ValueError):run(guidance=guide.model_copy(update={'relevant_person':RelevantPersonStatus(status='source_attributed_current',person_ids=['invented'],evidence_ids=['e-role'],explanation='Invented person')}))
        with self.assertRaises(ValueError):ContactRouteStatus(status='source_supported_route',explanation='No route',route_kind='person_route',person_id='test-person')
        with self.assertRaises(ValueError):ContactRouteStatus(status='source_supported_route',explanation='Company channel is not personal',route_kind='company_route',route_ref='source-ref',person_id='test-person',evidence_ids=['e-company'])


if __name__=='__main__':unittest.main()
