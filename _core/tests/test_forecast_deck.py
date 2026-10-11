import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / 'workspaces/forecasting/workflows/forecast-weekly'
sys.path.insert(0, str(WORKFLOW / 'scripts'))
import forecast_deck
from forecast_math import calculate

# Synthetic presentations.get JSON. Labels follow the live slide fields in references/deck.md.
# Names, amounts and objectIds are invented. The live deck is never read in tests.
PRESENTATION_ID = 'fictional-deck'


def text_body(value):
    lines = value.split('\n')
    return {'textElements': [element for line in lines
                             for element in ({'paragraphMarker': {}}, {'textRun': {'content': line + '\n'}})]}


def shape(identity, value):
    return {'objectId': identity, 'shape': {'shapeType': 'TEXT_BOX', 'text': text_body(value)}}


def table(identity, rows):
    return {'objectId': identity, 'table': {
        'rows': len(rows), 'columns': len(rows[0]),
        'tableRows': [{'tableCells': [{'location': {'rowIndex': r, 'columnIndex': c}, 'text': text_body(value)}
                                      for c, value in enumerate(row)]} for r, row in enumerate(rows)]}}


def seller_slide(prefix, seller, quarter='Q4', quota='$650K'):
    core = [['Deal', 'Amount', 'Stage', 'Risk']] + [['[Deal name]', '$0', '[S#]', '[Risk / buyer next step]']] * 5
    backup = ([['Deal', 'Amount', 'Required action']]
              + [['[Deal name]', '$0', f'[What has to happen to close in {quarter}]']] * 4 + [['Backup total', '$0', '']])
    return {'objectId': prefix, 'pageElements': [
        shape(prefix + '_t', f'{seller}  |  {quarter} New Business Bookings Plan'),
        shape(prefix + '_d', 'Updated: [date]   |   Start date: [date]'),
        shape(prefix + '_w', 'ENTERPRISE WEST'),
        {'objectId': prefix + '_g', 'elementGroup': {'children': [
            {'objectId': prefix + '_card', 'shape': {'shapeType': 'RECTANGLE'}},
            shape(prefix + '_ql', f'{quarter} QUOTA'), shape(prefix + '_qv', quota)]}},
        shape(prefix + '_cl', f'{quarter} CALL'), shape(prefix + '_cv', '$0'),
        shape(prefix + '_ul', 'UPSIDE CALL'), shape(prefix + '_uv', '$0'),
        shape(prefix + '_gl', 'GAP TO CALL'), shape(prefix + '_gv', '$0'),
        shape(prefix + '_al', 'ARR CLOSED QTD'), table(prefix + '_at', [['Closed total', '$0']]),
        shape(prefix + '_kl', 'CORE DEALS TO HIT FORECAST'), table(prefix + '_kt', core),
        shape(prefix + '_bl', 'BACKUP PIPELINE'), table(prefix + '_bt', backup),
        shape(prefix + '_sl', 'SUPPORT NEEDED'),
        shape(prefix + '_sv', '[Biggest support need]\n[Specific ask]\n[Specific ask]'),
        shape(prefix + '_n', f'Gap to call = {quarter} quota minus {quarter} call.'),
        shape(prefix + '_pl', 'CURRENT QUARTER QUALIFIED PIPELINE (S2+)'),
        table(prefix + '_pt', [['Qualified pipeline (S2+) ARR', '$0']])]}


def presentation(quarter='Q4', quota='$650K'):
    slides = [{'objectId': f'intro{n}', 'pageElements': [shape(f'intro{n}_t', f'Intro {n}')]} for n in (1, 2, 3)]
    slides += [seller_slide(f'other{n}', f'Seller {n}', quarter) for n in (4, 5, 6, 7)]
    slides.append(seller_slide('gx91', 'Sales Operator', quarter, quota))
    slides.append({'objectId': 'rollup', 'pageElements': [
        shape('rollup_t', 'Team rollup'), table('rollup_q', [['Seller', 'Quota'], ['Sales Operator', quota]])]})
    return {'presentationId': PRESENTATION_ID, 'revisionId': 'rev-1', 'slides': slides}


def apply(document, body):
    """Minimal Slides batchUpdate simulator for deleteText ALL and insertText at 0."""
    document = copy.deepcopy(document)
    if body['writeControl']['requiredRevisionId'] != document['revisionId']:
        raise AssertionError('stale revision')
    index = {}
    for page in document['slides']:
        for element in forecast_deck.flatten(page['pageElements']):
            index[element['objectId']] = element
    for request in body['requests']:
        kind, spec = next(iter(request.items()))
        element = index[spec['objectId']]
        if 'cellLocation' in spec:
            location = spec['cellLocation']
            holder = element['table']['tableRows'][location['rowIndex']]['tableCells'][location['columnIndex']]
        else:
            holder = element['shape']
        if kind == 'deleteText':
            assert forecast_deck.text(holder.get('text')), 'deleteText on empty text fails in Slides'
            holder['text'] = {'textElements': []}
        else:
            assert spec['insertionIndex'] == 0 and not forecast_deck.text(holder.get('text'))
            holder['text'] = text_body(spec['text'])
    document['revisionId'] = 'rev-2'
    return document


def fixture_inputs(core_count=7, upside_count=3, pull_in_count=3):
    reviewed = {'as_of': '2026-10-08', 'quarter': '2026-Q4',
                'booked': [{'Id': 'fixture-won', 'ARR__c': '50000.50', 'Amount': '999999'}],
                'deals': [], 'pull_ins': []}
    deck = {'as_of': reviewed['as_of'], 'quarter_start': '2026-10-01', 'rows': {},
            'support': ['Confirm decision timing.', 'Review commercial flexibility.', 'Align security review.']}
    for group, count, bucket, stage, amount in [('deals', core_count, 'commit', 'S4', 50000),
                                               ('deals', upside_count, 'upside', 'S2', 30000),
                                               ('pull_ins', pull_in_count, 'pull', 'S2', 20000)]:
        for index in range(count):
            identity = f'fixture-{bucket}-{index:02d}'
            row = {'Id': identity, 'Name': f'{bucket.title()} {index + 1}',
                   'ARR__c': str(amount + index * 1000), 'Amount': '999999', 'StageName': stage,
                   'CloseDate': '2027-01-15' if group == 'pull_ins' else '2026-12-15',
                   'last_activity_date': reviewed['as_of'], 'action': 'Confirm buyer decision.',
                   'buyer_date': None, 'evidence': 'synthetic-reviewed-source'}
            if group == 'deals':
                row['bucket'] = bucket
                row.update(buyer_delay_date=None, buyer_delay_evidence=None, blockers=[])
            reviewed[group].append(row)
            deck['rows'][identity] = 'Buyer review scheduled.' if bucket == 'commit' else 'Confirm buyer decision.'
    return reviewed, deck


class ForecastDeckTests(unittest.TestCase):
    def setUp(self):
        self.policy = yaml.safe_load((ROOT / '_core/policy.yaml').read_text())
        self.policy['forecast']['deck'].update(presentation_id=PRESENTATION_ID, name_character_cap=14, core_risk_character_cap=24)
        self.policy['forecast']['targets'] = {'2026-Q4': 650000}
        self.reviewed, self.deck = fixture_inputs()
        self.result = calculate(self.reviewed, self.policy)
        self.presentation = presentation()
        self.coverage = {'ready': True, 'process_status': 'complete', 'affected': []}

    def plan(self, document=None):
        return forecast_deck.plan(document or self.presentation, self.result, self.reviewed, self.deck, self.policy,
                                  coverage=self.coverage)

    def field(self, planned, label):
        return next(entry['new'] for entry in planned['fields'] if entry['label'] == label)

    def test_policy_names_the_shared_deck_and_drops_the_pptx_template(self):
        settings = self.policy['forecast']['deck']
        self.assertEqual(settings['presentation_id'], PRESENTATION_ID)
        self.assertEqual(settings['slide_title'].format(quarter='Q4'), 'Sales Operator  |  Q4 New Business Bookings Plan')
        deployed = yaml.safe_load((ROOT / '_core/policy.yaml').read_text())['forecast']['deck']
        self.assertEqual(deployed.get('name_character_cap'), 14)
        self.assertEqual(deployed.get('core_risk_character_cap'), 24)
        self.assertEqual(deployed['cell_character_cap'], 32)
        for key in ('template', 'slide_number', 'output_name'):
            self.assertNotIn(key, settings)
        self.assertFalse((WORKFLOW / 'assets/bookings-plan-template.pptx').exists())

    def test_mapping_uses_whole_dollars_and_quarter_start(self):
        planned = self.plan()
        self.assertEqual(planned['slide_object_id'], 'gx91')
        for label, expected in [('Q4 CALL', '$421,001'), ('UPSIDE CALL', '$514,001'), ('GAP TO CALL', '$229,000'),
                                ('Closed total', '$50,001'), ('Qualified pipeline', '$464,000'),
                                ('Updated / Start date', 'Updated: 10/8   |   Start date: 10/1'),
                                ('CORE[1][3]', 'S4'),
                                ('SUPPORT NEEDED', '\n'.join(self.deck['support']))]:
            self.assertEqual(self.field(planned, label), expected, label)
        entry = next(entry for entry in planned['fields'] if entry['label'] == 'Q4 CALL')
        self.assertEqual((entry['object_id'], entry['current']), ('gx91_cv', '$0'))

    def test_batch_update_targets_only_matts_slide_with_required_revision(self):
        planned = self.plan()
        body = planned['batch_update']
        self.assertEqual(body['writeControl'], {'requiredRevisionId': 'rev-1'})
        targets = {next(iter(request.values()))['objectId'] for request in body['requests']}
        self.assertTrue(targets)
        self.assertTrue(all(identity.startswith('gx91_') for identity in targets), targets)
        self.assertNotIn('gx91_qv', targets)
        self.assertNotIn('gx91_t', targets)

    def test_slide_resolves_by_title_not_position_or_stored_id(self):
        document = self.presentation
        matt = document['slides'].pop(7)
        document['slides'].insert(1, matt)
        self.assertEqual(self.plan(document)['slide_object_id'], 'gx91')
        for count in (0, 2):
            document = presentation()
            if count == 0:
                document['slides'].pop(7)
            else:
                document['slides'].append(seller_slide('dup', 'Sales Operator'))
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, f'exactly one slide.*found {count}'):
                self.plan(document)

    def test_title_and_labels_follow_the_run_quarter(self):
        self.reviewed, self.deck = fixture_inputs(1, 1, 1)
        self.reviewed.update(as_of='2026-07-08', quarter='2026-Q3')
        self.deck.update(as_of='2026-07-08', quarter_start='2026-07-01')
        for row in self.reviewed['deals']:
            row.update(CloseDate='2026-09-15', last_activity_date='2026-07-08')
        self.reviewed['pull_ins'][0]['CloseDate'] = '2026-10-15'
        self.result = calculate(self.reviewed, self.policy)
        with self.assertRaisesRegex(ValueError, 'Q3 New Business'):
            self.plan()
        planned = self.plan(presentation('Q3', '$250,000'))
        self.assertEqual(planned['slide_title'], 'Sales Operator  |  Q3 New Business Bookings Plan')
        self.assertEqual(self.field(planned, 'Updated / Start date'), 'Updated: 7/8   |   Start date: 7/1')

    def test_quota_is_checked_against_policy_and_never_written(self):
        for quota in ('$650K', '$650,000'):
            with self.subTest(quota=quota):
                planned = self.plan(presentation(quota=quota))
                self.assertEqual(planned['quota'], quota)
                self.assertNotIn('Q4 QUOTA', [entry['label'] for entry in planned['fields']])
        with self.assertRaisesRegex(ValueError, 'Q4 QUOTA: slide shows \\$600K'):
            self.plan(presentation(quota='$600K'))

    def test_live_table_shape_must_match_policy_capacity(self):
        rows = self.presentation['slides'][7]['pageElements'][13]['table']['tableRows']
        rows.pop()
        with self.assertRaisesRegex(ValueError, 'CORE: live table has 4 deal rows, policy expects 5'):
            self.plan()

    def test_overflow_sums_hidden_rows_and_every_backup_row(self):
        planned = self.plan()
        for label, expected in [('CORE[1][1]', 'Commit 7'), ('CORE[5][1]', '+3 more'), ('CORE[5][2]', '$153,000'),
                                ('CORE[5][3]', ''), ('CORE[5][4]', ''), ('BACKUP[4][1]', '+3 more'),
                                ('BACKUP[4][2]', '$63,000'), ('Backup total', '$156,000')]:
            self.assertEqual(self.field(planned, label), expected, label)

    def test_ties_sort_by_id_and_nonoverflow_backup_upside_precedes_pullins(self):
        self.reviewed, self.deck = fixture_inputs(2, 1, 1)
        for row in self.reviewed['deals'][:2]:
            row['ARR__c'] = '50000'
        self.reviewed['deals'].reverse()
        self.reviewed['pull_ins'][0]['ARR__c'] = '90000'
        self.result = calculate(self.reviewed, self.policy)
        planned = self.plan()
        self.assertEqual(self.field(planned, 'CORE[1][1]'), 'Commit 1')
        self.assertEqual(self.field(planned, 'BACKUP[1][1]'), 'Upside 1')
        self.assertEqual(self.field(planned, 'BACKUP[2][1]'), 'Pull 1')
        self.assertEqual(self.field(planned, 'CORE[3][1]'), '')

    def test_empty_support_and_empty_tables(self):
        self.reviewed, self.deck = fixture_inputs(0, 0, 0)
        self.reviewed['booked'] = []
        self.deck['support'] = []
        self.result = calculate(self.reviewed, self.policy)
        planned = self.plan()
        self.assertEqual(self.field(planned, 'SUPPORT NEEDED'), 'None.')
        self.assertEqual(self.field(planned, 'CORE[1][1]'), '')
        self.assertEqual(self.field(planned, 'Backup total'), '$0')

    def test_empty_support_value_is_selected_as_empty_never_the_following_gap_note(self):
        """V3 paired case. The same slide with a blank and a filled SUPPORT NEEDED box targets the same shape id."""
        note = 'Gap to call = Q4 quota minus Q4 call.'
        outcomes = {}
        for case, current in (('empty', ''), ('nonempty', '[Biggest support need]\n[Specific ask]\n[Specific ask]')):
            document = presentation()
            document['slides'][7]['pageElements'][17] = shape('gx91_sv', current)
            planned = self.plan(document)
            entry = next(entry for entry in planned['fields'] if entry['label'] == 'SUPPORT NEEDED')
            self.assertEqual((entry['object_id'], entry['current'], entry['new']),
                             ('gx91_sv', current, '\n'.join(self.deck['support'])), case)
            targets = {next(iter(request.values()))['objectId'] for request in planned['batch_update']['requests']}
            self.assertNotIn('gx91_n', targets, case)
            after = apply(document, planned['batch_update'])
            self.assertEqual(forecast_deck.page_text(after['slides'][7])[('gx91_n', None)], note, case)
            self.assertEqual(forecast_deck.verify(planned, document, after)['readback'], 'passed', case)
            outcomes[case] = planned['slide_object_id'], entry['object_id']
        self.assertEqual(outcomes['empty'], outcomes['nonempty'])
        kinds = [next(iter(request)) for request in self.plan(document)['batch_update']['requests']
                 if next(iter(request.values()))['objectId'] == 'gx91_sv']
        self.assertIn('deleteText', kinds)

    def test_empty_non_text_shape_after_support_label_is_held_as_ambiguous(self):
        document = presentation()
        self.assertEqual(document['slides'][7]['pageElements'][17]['objectId'], 'gx91_sv')
        document['slides'][7]['pageElements'][17] = {'objectId': 'gx91_sv', 'shape': {'shapeType': 'RECTANGLE'}}
        with self.assertRaisesRegex(ValueError, 'SUPPORT NEEDED: .*ambiguous'):
            self.plan(document)

    def test_target_shape_ids_come_from_the_current_read_and_the_approved_preview(self):
        approved = self.plan()
        renamed = presentation()
        for element in forecast_deck.flatten(renamed['slides'][7]['pageElements']):
            if element['objectId'] == 'gx91_sv':
                element['objectId'] = 'gx91_sv_new'
        fresh = self.plan(renamed)
        entry = next(entry for entry in fresh['fields'] if entry['label'] == 'SUPPORT NEEDED')
        self.assertEqual(entry['object_id'], 'gx91_sv_new')
        with self.assertRaisesRegex(ValueError, 'slide changed since the D preview; re-propose D'):
            forecast_deck.check_approved(fresh, approved)
        self.assertNotIn('gx91_sv', json.dumps(self.policy['forecast']['deck']))

    def test_whole_dollars_round_half_up_and_negative_gap(self):
        self.assertEqual(forecast_deck.dollars('1817650'), '$1,817,650')
        self.assertEqual(forecast_deck.dollars('1000.50'), '$1,001')
        self.assertEqual(forecast_deck.dollars('-1000.50'), '-$1,001')
        self.assertEqual(forecast_deck.dollars('1000.49'), '$1,000')

    def test_plan_enforces_each_column_independently_without_truncation(self):
        cases = [('core_name', 14, 'CORE[1][1]'), ('upside_name', 14, 'BACKUP[1][1]'),
                 ('pull_name', 14, 'BACKUP[2][1]'), ('core_risk', 24, 'CORE[1][4]'),
                 ('backup_action', 32, 'BACKUP[1][3]'), ('support', 32, 'SUPPORT NEEDED')]
        for location, cap, label in cases:
            for length in (cap, cap + 1):
                reviewed, deck = fixture_inputs(1, 1, 1)
                value = 'A' * length
                if location.endswith('_name'):
                    row = reviewed['pull_ins'][0] if location == 'pull_name' else reviewed['deals'][location == 'upside_name']
                    row['Name'] = value
                elif location == 'support':
                    deck['support'] = [value]
                else:
                    identity = reviewed['deals'][location == 'backup_action']['Id']
                    deck['rows'][identity] = value
                with self.subTest(location=location, length=length):
                    if length > cap:
                        with self.assertRaisesRegex(ValueError, 'exceeds'):
                            forecast_deck.plan(self.presentation, calculate(reviewed, self.policy), reviewed, deck, self.policy,
                                              coverage=self.coverage)
                    else:
                        planned = forecast_deck.plan(self.presentation, calculate(reviewed, self.policy), reviewed, deck, self.policy,
                                                    coverage=self.coverage)
                        self.assertEqual(self.field(planned, label), value)

    def test_verify_rejects_long_cells_even_when_the_saved_plan_matches(self):
        for label, cap in [('CORE[1][1]', 14), ('BACKUP[1][1]', 14), ('CORE[1][4]', 24),
                           ('BACKUP[1][3]', 32), ('SUPPORT NEEDED', 32)]:
            planned = self.plan()
            after = apply(self.presentation, planned['batch_update'])
            entry = next(row for row in planned['fields'] if row['label'] == label)
            entry['new'] = 'A' * (cap + 1)
            element = next(row for row in forecast_deck.flatten(after['slides'][7]['pageElements'])
                           if row['objectId'] == entry['object_id'])
            holder = element['table']['tableRows'][entry['cell'][0]]['tableCells'][entry['cell'][1]] if entry['cell'] else element['shape']
            holder['text'] = text_body(entry['new'])
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, 'exceeds'):
                forecast_deck.verify(planned, self.presentation, after)

    def test_column_caps_require_positive_integer_policy_values(self):
        for key in ('cell_character_cap', 'name_character_cap', 'core_risk_character_cap'):
            for value in (None, True, 0, -1, '14'):
                policy = copy.deepcopy(self.policy)
                policy['forecast']['deck'][key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, key):
                    forecast_deck.plan(self.presentation, self.result, self.reviewed, self.deck, policy, coverage=self.coverage)

    def test_missing_or_multiline_metadata_and_too_many_support_lines_fail(self):
        identity = self.reviewed['deals'][0]['Id']
        for value in (None, '', 'two\nlines'):
            self.deck['rows'][identity] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, identity):
                self.plan()
        self.reviewed, self.deck = fixture_inputs()
        self.deck['support'].append('Extra ask.')
        with self.assertRaisesRegex(ValueError, 'at most 3'):
            self.plan()

    def test_stale_arithmetic_wrong_dates_missing_ids_and_wrong_presentation_fail(self):
        self.result['call'] = '0'
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.plan()
        self.result = calculate(self.reviewed, self.policy)
        self.deck['quarter_start'] = '2026-10-02'
        with self.assertRaisesRegex(ValueError, 'dates must match'):
            self.plan()
        self.deck['quarter_start'] = '2026-10-01'
        document = presentation()
        document['presentationId'] = 'other'
        with self.assertRaisesRegex(ValueError, 'presentation id'):
            self.plan(document)
        self.deck['rows'].clear()
        with self.assertRaisesRegex(ValueError, 'exactly'):
            self.plan()

    def test_unchanged_fields_send_no_request_and_empty_text_is_not_deleted(self):
        written = apply(self.presentation, self.plan()['batch_update'])
        again = self.plan(written)
        self.assertEqual(again['changed'], 0)
        self.assertEqual(again['batch_update']['requests'], [])
        kinds = [next(iter(request)) for request in self.plan()['batch_update']['requests']]
        self.assertIn('deleteText', kinds)
        self.assertIn('insertText', kinds)

    def test_approved_preview_stops_on_slide_or_value_drift(self):
        approved = self.plan()
        fresh = presentation()
        fresh['revisionId'] = 'rev-9'
        checked = forecast_deck.check_approved(self.plan(fresh), approved)
        self.assertEqual(checked['batch_update']['writeControl'], {'requiredRevisionId': 'rev-9'})
        edited = presentation()
        edited['slides'][7]['pageElements'][5] = shape('gx91_cv', '$1')
        with self.assertRaisesRegex(ValueError, 'Q4 CALL: slide text changed.*re-propose D'):
            forecast_deck.check_approved(self.plan(edited), approved)
        self.reviewed['deals'][0]['bucket'] = 'upside'
        self.result = calculate(self.reviewed, self.policy)
        self.deck['rows'][self.reviewed['deals'][0]['Id']] = 'Confirm buyer decision.'
        with self.assertRaisesRegex(ValueError, 'value changed since the D preview; re-propose D'):
            forecast_deck.check_approved(self.plan(), approved)

    def test_readback_passes_and_detects_field_and_outside_changes(self):
        planned = self.plan()
        after = apply(self.presentation, planned['batch_update'])
        self.assertEqual(forecast_deck.verify(planned, self.presentation, after)['readback'], 'passed')
        wrong = copy.deepcopy(after)
        wrong['slides'][7]['pageElements'][5] = shape('gx91_cv', '$0')
        with self.assertRaisesRegex(ValueError, 'readback: Q4 CALL mismatch'):
            forecast_deck.verify(planned, self.presentation, wrong)
        for slide, index in ((4, 4), (8, 0), (7, 2)):
            outside = copy.deepcopy(after)
            element = outside['slides'][slide]['pageElements'][index]
            outside['slides'][slide]['pageElements'][index] = shape(element['objectId'], 'edited')
            with self.subTest(slide=slide), self.assertRaisesRegex(ValueError, 'outside the planned fields'):
                forecast_deck.verify(planned, self.presentation, outside)

    def test_cli_plan_verify_and_no_silent_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            paths = {}
            for label, value in [('presentation', self.presentation), ('forecast', self.result),
                                 ('reviewed', self.reviewed), ('input', self.deck), ('coverage', self.coverage)]:
                paths[label] = directory / f'{label}.json'
                paths[label].write_text(json.dumps(value))
            policy_path = directory / 'policy.yaml'
            policy_path.write_text(yaml.safe_dump(self.policy))
            arguments = ['plan', '--policy', str(policy_path)] + [item for label, path in paths.items() for item in ('--' + label, str(path))]
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(forecast_deck.main(arguments), 0)
            planned = json.loads(stdout.getvalue())
            (directory / 'plan.json').write_text(stdout.getvalue())
            (directory / 'after.json').write_text(json.dumps(apply(self.presentation, planned['batch_update'])))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(forecast_deck.main(['verify', '--plan', str(directory / 'plan.json'),
                                                     '--before', str(paths['presentation']),
                                                     '--after', str(directory / 'after.json'), '--policy', str(policy_path)]), 0)
            self.deck['support'][0] = 'A' * 33
            paths['input'].write_text(json.dumps(self.deck))
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(forecast_deck.main(arguments), 1)
            self.assertIn('SUPPORT NEEDED[1]', stderr.getvalue())

    def test_contract_gates_the_slide_write_on_d_after_close(self):
        contract = (WORKFLOW / 'CONTEXT.md').read_text()
        self.assertLess(contract.index('10. Close'), contract.index('11. After closing counts'))
        self.assertIn("forecast branch writes only Opportunity ForecastCategoryName and Contact Email on approval, "
                      "and Operator's slide in the shared bookings deck on D", contract)
        for expected in ('`references/deck.md`', 'Deck values come only from forecast_math', 'Bookings deck slide', '| 6 | D in the same report'):
            self.assertIn(expected, contract)
        for stale in ('.pptx', 'bookings-plan-template'):
            self.assertNotIn(stale, contract)
        self.assertLessEqual(len(contract.splitlines()), 80)
        report = (WORKFLOW / 'references/report-format.md').read_text()
        self.assertIn('D. Operator\'s slide', report)
        self.assertIn('Reply with letters to apply, or `skip`.', report)


if __name__ == '__main__':
    unittest.main()
