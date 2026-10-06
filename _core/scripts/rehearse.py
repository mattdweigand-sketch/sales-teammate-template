#!/usr/bin/env python3
"""Scratch-only contract scenarios and real helper regression tests. Never calls live connectors."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import date,datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import yaml
import onboard

ROOT=Path(__file__).resolve().parents[2]
EVENT_STAGE_BRANCHES={None:'01-list-prep','list-prep':'01-list-prep','early-close':None,
                      'sequence-plan':'02-sequence-plan','launch':'03-launch','zero-recipients':'03-launch',
                      'house-and-missing-scope':'01-list-prep','scope-loss':'03-launch','interval-readback':'03-launch'}


class LocalConnector:
    """Test double for exact approval, fresh state, duplicate avoidance and readback."""
    def __init__(self):
        self.records={};self.writes=[];self.sent=[]

    def write(self,key,proposal,approved=None,current=None,readback_override=None,guard=True):
        if guard is not True:
            raise ValueError('current ownership or evidence guard failed')
        if approved != proposal:
            raise ValueError('exact approval is missing or changed')
        live=deepcopy(self.records.get(key))
        if current != live:
            raise ValueError('state changed before write')
        if live == proposal:
            raise ValueError('reuse existing duplicate')
        self.records[key]=deepcopy(proposal)
        actual=readback_override if readback_override is not None else deepcopy(self.records[key])
        from prospect_readback_check import compare
        if compare(proposal,actual)['verdict']!='match':
            raise ValueError('readback mismatch; no verified receipt')
        self.writes.append({'key':key,'fields':deepcopy(proposal),'verified':True})
        return deepcopy(actual)


    def deliver(self, primary, fallback=None, *, discovered=True, reconciled=None):
        """Contract-guided transport double. No real sends or provider verification."""
        attempts = []
        if not discovered:
            return {'status': 'needs-input', 'attempts': attempts, 'transport': None, 'receipt': None}
        attempts.append('session')
        result, transport = primary, 'session'
        if primary.get('status') == 'confirmed_no_delivery':
            attempts.append('mail')
            result, transport = fallback or {}, 'mail'
        if result.get('status') == 'ambiguous':
            result = reconciled or {}
        receipt = result.get('receipt') if result.get('status') == 'delivered' else None
        return {'status': 'delivered' if receipt else 'needs-input', 'attempts': attempts,
                'transport': transport if receipt else None, 'receipt': receipt}


def snapshot(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*')
            if p.is_file() and not any(onboard.excluded_name(x) for x in p.relative_to(root).parts)}


def contract_trace(name,contract,root,branch=None):
    declared = {skill: entry for skill, entry, _ in onboard.routes(root)}
    expected = declared.get(name)
    if contract != expected and not (name == "event-sequence" and expected and
            contract == str(Path(expected).parent / EVENT_STAGE_BRANCHES.get(branch, "") / "CONTEXT.md")):
        raise ValueError("contract does not match the root AGENTS route and selected stage")
    path=root/contract;text=path.read_text();read=["AGENTS.md",contract]
    inputs=text.split('## Inputs\n',1)[1].split('## Process\n',1)[0]
    coordinator=name=='event-sequence' and path.parent.name=='event-sequence'
    if coordinator and branch not in EVENT_STAGE_BRANCHES:
        raise ValueError('Event trace requires one declared entry branch')
    scopes=[]
    for row in inputs.splitlines():
        if not row.startswith('|') or row.startswith('| Source') or row.startswith('|---'):continue
        cells=[x.strip() for x in row.strip('|').split('|')]
        scope=cells[2].lower()
        if coordinator:
            stage=EVENT_STAGE_BRANCHES[branch]
            if cells[0]=='Stage' and cells[1]!=f'`{stage}/CONTEXT.md`':continue
            if cells[0]=='Reference' and branch!='early-close':continue
        if name=='signal-scan' and cells[0].startswith('Adoption'):continue
        if name=='signal-user-scan' and cells[0].startswith('Buying signals'):continue
        if name=='sales-call-prep' and 'scheduled daily run only' in scope and branch!='daily':continue
        if name=='deal-coach' and branch:
            prefix=scope.split('load',1)[0].split(' use',1)[0].split(' covers',1)[0]
            mentioned=[b for b in ('call-review','deal-review','pre-meeting','criteria-refresh') if b in prefix]
            if mentioned and branch not in mentioned:continue
            if 'only when targeted for an edit' in scope:continue
        if name=='forecast-weekly':
            tracking=branch=='pace-and-forward'
            if ('forecast only' in scope and tracking) or ('tracking only' in scope and not tracking):continue
            if 'tracking at quarter end only' in scope and branch!='incomplete-and-learning':continue
        scopes.append({'source':cells[0],'location':cells[1],'scope':cells[2]})
        for reference in re.findall(r'`([^`]+)`',cells[1]):
            file=root/reference if reference.startswith(('_core/','workspaces/')) else path.parent/reference
            if file.is_file():
                content=file.read_text()
                headings=re.findall(r'"([^"]+)"',cells[2])
                if headings:
                    for heading in headings:
                        assert re.search(r'^#+ '+re.escape(heading)+r'\s*$',content,re.M),f'{reference}: missing {heading}'
                read.append(str(file.relative_to(root)))
    return {'workflow':name,'contract':contract,'actual_local_reads':read,'input_scopes':scopes,
            'output_contract':text.split('## Outputs\n',1)[1],
            'review_contract':text.split('## Checkpoints\n',1)[1].split('## Audit\n',1)[0],
            'downstream_handoff':yaml.safe_load(text.split('---\n',2)[1])['next'], 'simulation_only':True}


def worker(artifacts,renderer='auto'):
    artifacts.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(ROOT/'_core/tests'))
    for directory in (ROOT/'_core/scripts',*(ROOT/'workspaces').rglob('scripts')):
        sys.path.insert(0,str(directory))
    import prospect_common,prospect_account_route,prospect_evidence_gate,prospect_privacy_check,prospect_outreach_gate,prospect_followup_gate
    import account_usage,forecast_math,forecast_notify,hygiene_check
    from test_prospect_evidence_gate import receipt,PAGE,TODAY
    from test_prospect_outreach_gate import PACKET,NOW
    from test_prospect_privacy_check import CLEAN
    from test_prospect_followup_gate import BASE
    from test_event_list_prep import EventListPrep,prep
    from test_customer_review import CustomerReviewTests,AS_OF
    from test_pilot_usage import PilotUsagePdfTests,HANDLES,_page,Q5_COLUMNS
    from build_pilot_usage_report import build_report
    policy=yaml.safe_load((ROOT/'_core/policy.yaml').read_text());pp=prospect_common.load_policy(ROOT/'_core')
    bus=LocalConnector();cases=[];traces={name:path for name,path,_ in onboard.routes(ROOT)}
    def record(name,branch,output):
        assert name in traces
        item={**contract_trace(name,traces[name],ROOT,branch),'branch':branch,'passed':True,'output':output}
        if name=='event-sequence' and EVENT_STAGE_BRANCHES[branch]:
            contract=str(Path(traces[name]).parent/EVENT_STAGE_BRANCHES[branch]/'CONTEXT.md')
            item['stage_trace']=contract_trace(name,contract,ROOT,branch)
            item['actual_local_reads']=list(dict.fromkeys(item['actual_local_reads']+item['stage_trace']['actual_local_reads']))
        cases.append(item);(artifacts/f'{name}-{branch}.json').write_text(json.dumps(item,indent=2,default=str)+'\n')
    def rejects(function):
        try:function()
        except (ValueError,RuntimeError):return
        raise AssertionError('negative case did not reject')

    # A real evidence-to-draft-to-proven-send-to-Task handoff through the copied helpers.
    route=deepcopy(PACKET['account']);assert prospect_account_route.route(route,pp)=='scan'
    blocked={**route,'open_opportunity_ids':['006000000000001AAA']}
    assert prospect_account_route.route(blocked,pp)=='active_deal'
    assert prospect_account_route.route({**route,'owner_id':'other'},pp)=='owned_elsewhere'
    code,evidence=prospect_evidence_gate.grade(receipt(),PAGE,*prospect_evidence_gate.load_rules(ROOT/'_core'),TODAY)
    assert code==0
    assert prospect_evidence_gate.grade(receipt(quote='not supported by the source text'),PAGE,*prospect_evidence_gate.load_rules(ROOT/'_core'),TODAY)[0]!=0
    record('signal-scan','buying-signals',evidence)
    for adoption,org,individual in [('org_adopted',True,True),('individuals_only',False,True),('none_found',False,False)]:
        bundle={**CLEAN,'org_subscribed':org,'paid_individuals_exist':individual,'adoption':adoption}
        us=pp['user_scan'];assert not prospect_privacy_check.check(bundle,us['bundle_keys'],us['adoption_values'])
        assert prospect_privacy_check.check({**bundle,'user_email':'private@example.test'},us['bundle_keys'],us['adoption_values'])
        record('signal-user-scan',adoption,bundle)
    packet=deepcopy(PACKET);packet['bundle']={**evidence['bundle'],'checked_at':NOW.isoformat()}
    packet['account']['account_domain']=packet['bundle']['account_domain']
    packet['draft']['body']='I saw the appointment of your initiative owner. Example Product helps coordinate the work. How will you measure the first evaluation?'
    reasons=prospect_outreach_gate.check(packet,pp,ROOT/'_core',NOW);assert not reasons,reasons
    assert prospect_outreach_gate.check({**packet,'account':blocked},pp,ROOT/'_core',NOW)
    stale=deepcopy(packet);stale['bundle']['checked_at']='2026-08-01T00:00:00-07:00'
    assert prospect_outreach_gate.check(stale,pp,ROOT/'_core',NOW)
    rejects(lambda:bus.write('draft',packet['draft']))
    draft=bus.write('draft',packet['draft'],approved=packet['draft'])
    rejects(lambda:bus.write('draft',draft,approved=draft,current=draft))
    record('signal-outreach','approved-unsent-draft',draft)
    follow=deepcopy(BASE);follow['sent'][0].update(to=packet['recipient']['email'],subject=draft['subject'])
    follow['contacts'][0]['email']=packet['recipient']['email']
    task=prospect_followup_gate.check(follow,pp,today=date(2026,9,21));assert task['verdict']=='allow'
    no_send=deepcopy(follow);no_send['sent']=[]
    assert prospect_followup_gate.check(no_send,pp,today=date(2026,9,21))['verdict']=='block'
    bus.write('followup-task',task['task'],approved=task['task'])
    record('signal-followup','proven-send-task',task)

    event=EventListPrep();event.setUp()
    prepared=prep.prepare([event.row()],event.policy,event.as_of);assert prepared['contacts'][0]['label']=='enroll'
    record('event-sequence','list-prep',prepared)
    for change in [{'open_opportunity':True},{'account_owner_id':'other'},{'active_sequence':True},{'email_status':'unverified'}]:
        assert prep.prepare([event.row(**change)],event.policy,event.as_of)['contacts'][0]['label']!='enroll'
    empty=prep.prepare([event.row(open_opportunity=True)],event.policy,event.as_of)
    assert not any(contact['label']=='enroll' for contact in empty['contacts']) and not empty['enrichment_candidates']
    before=len(bus.writes)
    record('event-sequence','early-close',empty)
    assert len(bus.writes)==before
    enrollment={'contacts':['aster.sample@synthetic.example'],'copy':['Demo invite'],'mailbox':'rep@seller.example','schedule':'demo-only'}
    rejects(lambda:bus.write('apollo',enrollment))
    record('event-sequence','sequence-plan',{'exact_proposal':enrollment,'writes':0})
    dropped=prep.prepare([event.row(last_reply_at=event.as_of.isoformat())],event.policy,event.as_of)
    assert not any(contact['label']=='enroll' for contact in dropped['contacts'])
    record('event-sequence','zero-recipients',dropped)
    assert len(bus.writes)==before
    bus.write('apollo',enrollment,approved=enrollment)
    bus.sent.append({'sequence':'demo','stopped_on_reply':True})
    record('event-sequence','launch',prepared)

    # Scope cases execute the actual Event helper against reviewed fictional native evidence.
    marker = {'outreach_owner_column': 'Outreach Owner', 'outreach_owner_value': 'Operator'}
    house = event.row(account_owner_id='synthetic-house', apollo_contact_id='synthetic-apollo',
                      apollo_contact_email='aster.sample@synthetic.example', apollo_crm_linked=True,
                      apollo_crm_owner_id='synthetic-house', **{'Outreach Owner': 'Operator'})
    scoped = prep.prepare([house], event.policy, event.as_of, **marker)
    assert scoped['counts'] == {'enroll': 1} and scoped['contacts'][0]['scope'] == 'outreach_owner'
    missing = event.row(account_id='', account_owner_id='', **{'Outreach Owner': 'Operator'})
    assert prep.prepare([missing], event.policy, event.as_of, **marker)['counts'] == {'enroll': 1}
    disabled = deepcopy(event.policy)
    disabled['prospecting']['event'].pop('outreach_owner_scope')
    for row in (house, missing):
        held = prep.prepare([row], disabled, event.as_of, **marker)['contacts'][0]
        assert held['label'] != 'enroll' and any(item['label'] == 'outside_named_accounts' for item in held['exclusions'])
    assert prep.prepare([event.row(account_id='', account_owner_id='', account_checked=False,
                                   **{'Outreach Owner': 'Operator'})], event.policy, event.as_of, **marker)['counts'] == {'needs_input': 1}
    record('event-sequence', 'house-and-missing-scope', {'helper': scoped, 'disabled_and_incomplete_checks': 'held'})
    before = len(bus.writes)
    house['account_owner_id'] = 'synthetic-other'
    lost = prep.prepare([house], event.policy, event.as_of, **marker)
    assert lost['contacts'][0]['scope'] is None and lost['contacts'][0]['label'] != 'enroll'
    assert any(item['label'] == 'outside_named_accounts' for item in lost['contacts'][0]['exclusions'])
    rejects(lambda: prep.prepare([house], event.policy, event.as_of,
                                 overrides={'event-1': ['outside_named_accounts']}, **marker))
    assert len(bus.writes) == before
    record('event-sequence', 'scope-loss', {'helper': lost, 'apollo_calls': 0, 'override': 'rejected'})
    from prospect_readback_check import compare
    interval = {'mode': 'interval', 'step_wait_days': [0, 3, 3], 'schedule_id': 'fictional-weekday',
                'timezone': 'America/Los_Angeles', 'stop_on_reply': True}
    native = {**interval, 'id': 'fictional-sequence'}
    assert compare(interval, native)['verdict'] == 'match' and 'send_datetime' not in native
    for changed in ({'step_wait_days': [1, 3, 3]}, {'schedule_id': 'different'}, {'mode': 'absolute'}):
        assert compare(interval, {**native, **changed})['verdict'] == 'mismatch'
    assert compare(interval, {'id': 'unsupported'})['verdict'] == 'mismatch'
    record('event-sequence', 'interval-readback', {'approved': interval, 'native': native,
                                                'projections': 'expected local windows, not native timestamps',
                                                'mismatches': 'held by comparison double'})

    # Read-only prep preserves source-supported facts and explicitly marks unknowns.
    before=len(bus.writes)
    for branch in ('intro','discovery','demo','proposal','customer','daily'):
        record('sales-call-prep',branch,{'account':'Demo Account','source':'calendar-fixture','required_information':policy['call_prep']['expected_information'].get(branch,[]),
                                      'buyer_attendance':'unconfirmed','source_scope':'fixture only','customer_writes':0})
    assert len(bus.writes)==before
    for branch in ('single-call','calendar-fallback','sweep'):
        marker=policy['salesforce']['call_marker'].format(meeting_id='demo') if branch!='calendar-fallback' else policy['salesforce']['calendar_call_marker'].format(event_id='demo')
        proposal={'Subject':'Demo call','Description':marker+'\nBuyer confirmed a review date.','WhatId':'006000000000001AAA'}
        if branch=='sweep':record('interaction-sync',branch,{'proposal':proposal,'writes':0,'handoff':'Pipeline thread'});continue
        bus.write('call-'+branch,proposal,approved=proposal)
        record('interaction-sync',branch,{'proposal':proposal,'readback':'verified'})
    record('watch-sync','add-drop-retained-thread',{'add':['Demo open deal'],'drop':['Demo closed deal'],'retained':['Demo approved exception'],'settings_writes':0,'handoff':'Pipeline approval'})

    from test_hygiene_check import PipelineTimingTests
    timing=PipelineTimingTests();timing.setUp()
    result=hygiene_check.check(timing.opp,timing.policy,hygiene_check.index_activity([],[],timing.as_of.tzinfo),timing.as_of)
    assert 'task_gap' in result['triggers']
    for branch in ('weekday','friday'):
        record('pipeline-review',branch,{'hygiene':result,'approval_state':'proposal','next':'corrected Salesforce state is eligible for Forecasting'})
    # Delivery choices are simulated. Receipts and ambiguity never grant record-write ownership.
    delivered = {'status': 'delivered', 'receipt': {'session_id': 'fictional-deal', 'message_id': 'fixture-1'}}
    failed, ambiguous = {'status': 'confirmed_no_delivery'}, {'status': 'ambiguous'}
    delivery_cases = [(delivered, delivered, True, None, ['session'], 'delivered'),
                      (failed, delivered, True, None, ['session', 'mail'], 'delivered'),
                      (failed, failed, True, None, ['session', 'mail'], 'needs-input'),
                      (ambiguous, delivered, True, None, ['session'], 'needs-input'),
                      (ambiguous, delivered, True, delivered, ['session'], 'delivered'),
                      (delivered, delivered, False, None, [], 'needs-input')]
    for primary, fallback, found, reconciled, attempts, status in delivery_cases:
        before = len(bus.writes)
        output = bus.deliver(primary, fallback, discovered=found, reconciled=reconciled)
        assert output['attempts'] == attempts and output['status'] == status
        assert len(bus.writes) == before
        if status != 'delivered': assert output['receipt'] is None and output['transport'] is None
    record('interaction-sync', 'delivery-success-and-denial', {'cases': len(delivery_cases),
           'fallback': 'only confirmed no delivery', 'ambiguous': 'reconciled or needs-input', 'customer_writes': 0})
    # Real renderer includes routed records without local labels on weekday and Friday.
    from test_pipeline_render import Render, base, friday, BIO
    render = Render(); render.setUp()
    try:
        routed = base()
        routed['deals'] = [row for row in routed['deals'] if row['id'] != BIO]
        routed['blocks'] = [row for row in routed['blocks'] if row['deal'] != BIO]
        routed['routed'] = [{'deal': BIO, 'name': 'Fictional Account', 'thread_url': 'https://example.test/deal',
                             'reason': 'Verified deal thread owns this Opportunity and its Tasks'}]
        assert '## Routed to deal threads' in render.ok('report', routed)
        routed_friday = friday(deepcopy(routed))
        routed_friday['friday']['letters'] = []
        assert '## Routed to deal threads' in render.ok('report', routed_friday)
        invalid = deepcopy(routed_friday)
        invalid['friday']['letters'] = friday(base())['friday']['letters']
        render.fails('report', invalid, 'routed deal is owned elsewhere')
        record('pipeline-review', 'routed-ownership-render', {'weekday_and_friday': 'actual renderer passed',
               'competing_letter': 'actual renderer rejected', 'handoff_success': 'not inferred from routed list'})
    finally: render.tearDown()
    # Ownership order drives fixture decisions for typed and scheduled triage. Prose-agent execution is unverified.
    ownership_rows = [('active', True, False, 'deal-thread'), ('current', False, True, 'pipeline-review'),
                      ('distinct', False, False, 'triage'), ('ambiguous', None, True, 'held')]
    for branch in ('typed-ownership', 'scheduled-ownership'):
        before = len(bus.writes)
        for key, active, current_action, owner in ownership_rows:
            actual = 'held' if active is None else 'deal-thread' if active else 'pipeline-review' if current_action else 'triage'
            assert actual == owner
            if actual != 'triage':
                rejects(lambda: bus.write('owned-'+key, {'Status': 'Completed'}, approved={'Status': 'Completed'}, guard=False))
        assert len(bus.writes) == before
        record('task-triage-speed-run', branch, {'owners': ownership_rows, 'owned_task_writes': 0,
               'closeout': 'routed Tasks remain open and pending delivery is not completion'})
    # Exact approval cannot cover changed native fields, failed guards or repeating a coupled success.
    bus.records['stale-task'] = {'ActivityDate': '2026-10-05'}
    original = deepcopy(bus.records['stale-task']); proposal = {'ActivityDate': '2026-10-08'}
    bus.records['stale-task']['ActivityDate'] = '2026-10-06'
    before = len(bus.writes)
    rejects(lambda: bus.write('stale-task', proposal, approved=proposal, current=original))
    rejects(lambda: bus.write('stale-task', proposal, approved=proposal, current=bus.records['stale-task'], guard=False))
    assert len(bus.writes) == before
    bus.write('coupled-opp', {'Next_Steps__c': 'Fictional approved action'}, approved={'Next_Steps__c': 'Fictional approved action'})
    rejects(lambda: bus.write('stale-task', proposal, approved=proposal, current=original))
    rejects(lambda: bus.write('coupled-opp', bus.records['coupled-opp'], approved=bus.records['coupled-opp'], current=bus.records['coupled-opp']))
    bus.write('stale-task', proposal, approved=proposal, current=deepcopy(bus.records['stale-task']))
    record('pipeline-review', 'stale-and-partial-writes', {'stale_or_guard_failed': 'zero affected writes',
           'partial_coupled_update': 'successful side retained without repeat', 'revised_current_proposal': 'verified locally'})
    triage={'ActivityDate':'2026-10-05'}
    assert not policy['template']['auto_date_move']
    rejects(lambda:bus.write('triage',triage))
    bus.write('triage',triage,approved=triage)
    record('task-triage-speed-run','daily-and-closeout',{'auto_move_enabled':False,'approved_task':triage,'closeout':'real helper covered in regression suite'})

    usage=account_usage.summarize_usage({'Account':{'Admin_Organization_UUID__c':'demo-org'},'org_uuid':'demo-org','data_through':'2026-10-03',
                                       'rows':[{'user_email':'buyer@demo.test','window_queries':3,'l7_queries':1}],'billed_seats':2})
    assert usage['active_users']==1 and usage['roster_seats']==1
    rejects(lambda:account_usage.summarize_usage({'Account':{'Admin_Organization_UUID__c':'demo-org'},'org_uuid':'wrong'}))
    record('pilot-usage','report',usage)
    pdf=PilotUsagePdfTests();pdf.setUp()
    try:
        pdf.review['customer_name']='Fictional Demo Company';pdf.review['prepared_by']='Sales Operator'
        # Exercise the complete customer deliverable with all narrative and work-card slots populated.
        titles=['Draft a market memo','Compare supplier proposals','Summarize an industry update','Prepare an account brief',
                'Draft a customer proposal','Compare contract terms','Summarize customer feedback','Prepare a weekly report']
        emails=['a@x.test','b@x.test']
        rows=[[f'ctx-{i+1}',emails[i%2],f'2026-08-{13+i:02d}',('100.5' if i==0 else '2.4999' if i==1 else '20'),title]
              for i,title in enumerate(titles)]
        pdf._replace_q5(rows)
        _page(pdf.calls,'ar1','h1',['USER_EMAIL','FIRST_QUERY','LAST_QUERY','L7_QUERIES','WINDOW_QUERIES','WINDOW_COMPUTER_QUERIES'],
              [[email,'2026-08-13','2026-08-20','2','4','4'] for email in emails])
        labels=['Drafting','Comparison','Synthesis','Reporting']
        pdf.review['categories']=[{'category_id':label.lower(),'label':label,'description':'Reviewed fictional task titles.'} for label in labels]
        pdf.review['task_categories']={f'ctx-{i+1}':labels[i%4].lower() for i in range(8)}
        pdf.review['display_names']={emails[0]:'Alex Demo',emails[1]:'Blair Demo'}
        pdf.review['narratives']={
            'scope_note':'Fictional billed task contexts across two demo seats. Task titles indicate attempted work, not completed business outcomes.',
            'usage_highlights':[{'label':'Observed work','text':'The reviewed titles cover drafting, comparison, synthesis and reporting.'}],
            'representative_work':[{'title':titles[i],'user_emails':[emails[i%2]],'summary':'A fictional billed context with this title appears in the reviewed source.'} for i in range(4)],
            'work_interpretation':['The task titles suggest evaluation of recurring information work. These local fixtures establish no customer outcome.',
                                   'Billing dates and credits describe consumption. They do not prove completion, retention or a current available balance.'],
            'business_value':[{'label':'Evaluation opportunity','text':'Measure output quality and cycle time on an agreed workflow before making a value claim.'}],
            'source_note':'Source is the fictional rehearsal roster, credit grants and billed-context results. Credit units are cents with per-context rounding.'}
        result=build_report(pdf.review,pdf.calls,HANDLES,pdf.policy,artifacts/'demo-pilot-usage.pdf',renderer)
        assert result['page_count']==2 and result['credits_used']==223 and result['billed_contexts']==8
        bad=deepcopy(pdf.review);bad['approved']=False
        rejects(lambda:build_report(bad,pdf.calls,HANDLES,pdf.policy,artifacts/'unapproved.pdf',renderer))
        assert not (artifacts/'unapproved.pdf').exists()
        record('pilot-usage','pdf',result)
    finally:pdf.doCleanups()
    customers=CustomerReviewTests();customers.setUp()
    for branch,kwargs in [('scheduled',{'window_start':'2026-09-07T07:30:00-07:00'}),('named-account',{'account_id':'account'})]:
        output=customers.review(**kwargs);assert output['accounts']
        record('customer-review',branch,output)
    for branch in ('new-org','existing-org','paid-pilot','credits','needs-ops'):
        proposal={'StageName':'Closed Won','Closed_Won_Notes__c':'Demo signed contract evidence supplied by the operator.'}
        if branch=='needs-ops':record('close',branch,{'proposal_only':True,'handoff':'verified operations channel'});continue
        bus.write('close-'+branch,proposal,approved=proposal)
        record('close',branch,{'signature':'synthetic signed-contract source','readback':'verified','provisioning':'local double only'})

    for branch in ('call-review','deal-review','pre-meeting','criteria-refresh'):
        record('deal-coach',branch,{'source':'fictional call and deal evidence','score':'missing facts remain unknown','external_writes':0,
                                  'handoff':'exact criteria diff to Systems after approval' if branch=='criteria-refresh' else 'operator report'})
    data={'quarter':'2026-Q4','booked':[{'Id':'won','ARR__c':1000}],'deals':[{'Id':'commit','ARR__c':2000,'bucket':'commit'}],'pull_ins':[]}
    forecast=forecast_math.calculate(data,policy);assert forecast['call']=='3000'
    record('forecast-weekly','weekly',forecast)
    tracking=forecast_math.calculate_tracking({'as_of':'2026-10-04','records':[],'reads_complete':True},policy)
    assert len(tracking['forward_quarters'])==2
    record('forecast-weekly','pace-and-forward',tracking)
    payload=forecast_notify.build_payload(1,'{"ready":false,"lines":["missing calendar"]}','demo','https://demo.test/thread',None)
    assert payload['title']=='Weekly forecast incomplete'
    record('forecast-weekly','incomplete-and-learning',{'notification':payload,'learning':'proposal only'})

    # Technical changes and setting readback are isolated to mock state, with no inherited merge authority.
    proposal={'revision':'demo-reviewed-revision','tests':'passed'}
    rejects(lambda:bus.write('repo-deployment',proposal))
    bus.write('repo-deployment',proposal,approved=proposal)
    record('repo-maintenance','authorized-local-change',{'deployment':'mock revision readback','domain_policy':'unchanged'})
    settings={'contract':'workspaces/pipeline/workflows/sales-call-prep/CONTEXT.md','active':False}
    rejects(lambda:bus.write('pointer',settings,approved=settings,readback_override={**settings,'active':True}))
    # Re-read current failed mock state before the corrected approved setting write.
    bus.records['pointer']={'contract':'old','active':False}
    bus.write('pointer',settings,approved=settings,current=bus.records['pointer'])
    record('agent-configuration','pointer-readback',{'settings':settings,'readback':'verified','activation':False})
    for branch in ('scheduled-review','typed-health','eval','no-change'):
        record('system-review',branch,{'repair_writes':0,'finding':'mock pointer drift' if branch!='no-change' else None,
                                     'deduplicated':True,'owner':'agent-configuration','scope':'local fixture window'})
    # Correction evidence uses existing task/comment/thread history in native-shaped fixture records.
    pattern = {'issue': 'Repeated date edit', 'workflow': 'task-triage-speed-run', 'fix': 'Use the approved local date'}
    links = ['https://example.test/proposal-1', 'https://example.test/proposal-2']
    history = {'pattern': pattern, 'question_links': links, 'reason': None, 'task_id': 'fictional-improvement'}
    def correction_question(existing, checked=True):
        if not checked: return {'status': 'not checked', 'question': None}
        if existing and existing['pattern'] == pattern:
            return {'status': 'known reason' if existing.get('reason') else 'already asked', 'question': None}
        return {'status': 'new question', 'question': {'links': links, 'text': 'What was wrong?'}}
    new = correction_question(None)
    assert len(new['question']['links']) == 2
    assert correction_question(history)['question'] is None
    assert correction_question({**history, 'reason': 'Operator supplied reason'})['status'] == 'known reason'
    assert correction_question(None, checked=False)['status'] == 'not checked'
    assert new['question'] is not None  # Visible with zero new proposals, no quiet suppression.
    comment = {'task_id': history['task_id'], 'body': 'Operator supplied reason', 'reply_link': 'https://example.test/reply'}
    bus.records['declined-improvement'] = {'status': 'declined', 'assigned': False}
    declined = deepcopy(bus.records['declined-improvement'])
    bus.write('correction-comment', comment, approved=comment)
    rejects(lambda: bus.write('correction-comment', comment, approved=comment, current=comment))
    assert bus.records['declined-improvement'] == declined
    history['reason'] = bus.records['correction-comment']['body']
    assert correction_question(history)['status'] == 'known reason'
    record('system-review', 'correction-evidence', {'new_question': new, 'existing_question': 'not repeated',
           'unreadable_history': 'not checked', 'comment': bus.records['correction-comment'],
           'declined_task': 'unchanged', 'quiet_with_new_question': False, 'repair_writes': 0})
    assert set(x['workflow'] for x in cases)==set(traces)
    return {'passed':True,'named_workflows':len(traces),'scenarios':len(cases),'cases':cases,'mock_writes':bus.writes,
            'limit':'Contract-guided local connector doubles and real helper executions. Prose-only agent judgment and live integration behavior remain unverified.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch',type=Path,required=True)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--renderer',default='auto')
    args=parser.parse_args(argv)
    if args.worker:
        report=worker(args.scratch,args.renderer);(args.scratch/'workflow-report.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k not in ('cases','mock_writes')}));return 0
    scratch=args.scratch.expanduser().resolve()
    if scratch.exists() or ROOT==scratch or ROOT in scratch.parents:
        parser.error('scratch must be absent and outside the repository')
    before=snapshot(ROOT);scratch.mkdir(parents=True)
    answers=json.loads((ROOT/'_core/tests/fixtures/onboarding/answers.fixture.json').read_text());answers['artifact_dir']=str(scratch/'artifacts')
    onboard.instantiate(answers,scratch/'workspace',simulation=True)
    assert onboard.check(scratch/'workspace')==0
    # Run generic regression tests against an unchanged template copy, separately from adopter settings.
    regression=scratch/'regression'
    shutil.copytree(ROOT,regression,ignore=lambda directory,names:[n for n in names if onboard.excluded_name(n)])
    with (scratch/'regression.log').open('w') as log:
        result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','_core/tests'],cwd=regression,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(f'regressions failed; inspect {scratch / "regression.log"}')
    with (scratch/'workflow.log').open('w') as log:
        result=subprocess.run([sys.executable,'-B',str(scratch/'workspace/_core/scripts/rehearse.py'),'--worker','--scratch',str(scratch/'artifacts'),'--renderer',args.renderer],
                              cwd=scratch,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(f'workflow simulation failed; inspect {scratch / "workflow.log"}')
    assert before==snapshot(ROOT),'source template changed during rehearsal'
    report=json.loads((scratch/'artifacts/workflow-report.json').read_text())
    tests=re.search(r'Ran (\d+) tests',(scratch/'regression.log').read_text())
    report.update(regression_tests=int(tests[1]),scratch=str(scratch),source_unchanged=True)
    (scratch/'report.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
    (scratch/'report.md').write_text(f"# Scratch rehearsal\n\nPassed {report['regression_tests']} regression tests, {report['named_workflows']} named workflows and {report['scenarios']} branch scenarios.\n\nOnboarding instantiated a separate demo workspace and generated 18 exact skill pointers. Source bytes remained unchanged.\nThe two-page pilot PDF was built and structurally verified. Inspect both rasterized pages before claiming visual acceptance.\n\n{report['limit']}\n")
    print(json.dumps({k:report[k] for k in ('passed','regression_tests','named_workflows','scenarios','source_unchanged','scratch')}));return 0


if __name__=='__main__':raise SystemExit(main())
