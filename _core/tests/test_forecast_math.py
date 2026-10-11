import copy
import contextlib
import io
import json
import tempfile
import unittest
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspaces" / "forecasting" / "workflows" / "forecast-weekly" / "scripts"))
from forecast_math import calculate, calculate_tracking, main  # noqa: E402


class ForecastMathTests(unittest.TestCase):
    def setUp(self):
        self.policy={'forecast':{'amount_field':'Amount','open_min_stage':'S2','targets':{'2026-Q3':'1000.30'},'target_default':'2000', 'activity_days':14}}
        self.data={'as_of':'2026-09-25','quarter':'2026-Q3','booked':[{'Id':'won','Amount':'100.10'}],
                   'deals':[{'Id':'commit','Amount':'100.20','bucket':'commit','StageName':'S4 - Testing'},
                            {'Id':'small','Amount':'300','bucket':'upside','StageName':'S2 - Solutioning',
                             'action':'Ask for decision','buyer_date':None,'evidence':'email-1'},
                            {'Id':'large','Amount':'600','bucket':'upside','StageName':'S3 - Validation',
                             'action':'Finish legal','buyer_date':'2026-09-29','evidence':'email-2'},
                            {'Id':'excluded','Amount':None,'bucket':'excluded','StageName':'S0'}],
                   'pull_ins':[{'Id':'next-quarter','Amount':'9000','StageName':'S2','CloseDate':'2026-10-01','action':'Confirm rollout',
                                'buyer_date':'2026-10-01','evidence':'email-3'}]}
        for row in self.data['deals']:
            row.update(CloseDate='2026-09-01', last_activity_date='2026-09-25',
                       buyer_delay_date=None, buyer_delay_evidence=None, blockers=[])

    def test_commit_stage_and_buyer_date_fixed_predicates(self):
        for stage, buyer_date, predicate in (
                ('S0', '2026-09-25', 'commit requires'), ('S2', '2026-09-25', 'commit requires'),
                ('S3', None, 'buyer_date'), ('S3', '2026-06-30', 'inside the quarter'),
                ('S3', '2026-10-01', 'inside the quarter'), ('S3', '2026-02-30', 'buyer_date')):
            with self.subTest(stage=stage, buyer_date=buyer_date):
                self.data['deals'][0].update(StageName=stage, buyer_date=buyer_date)
                with self.assertRaisesRegex(ValueError, f'commit:.*{predicate}'):
                    calculate(self.data, self.policy)
        self.data['deals'][0].update(StageName='S3')
        del self.data['deals'][0]['buyer_date']
        with self.assertRaisesRegex(ValueError, 'commit:.*buyer_date'):
            calculate(self.data, self.policy)

    def test_valid_commit_stages_and_inclusive_quarter_boundaries_keep_totals(self):
        expected = calculate(self.data, self.policy)
        for stage, buyer_date in (('S4', None), ('S5 - Negotiation', None),
                                 ('S3', '2026-07-01'), ('S3 - Validation', '2026-09-30')):
            with self.subTest(stage=stage, buyer_date=buyer_date):
                self.data['deals'][0].update(StageName=stage, buyer_date=buyer_date)
                self.assertEqual(calculate(self.data, self.policy), expected)

    def test_recent_activity_for_commit_and_upside_is_inclusive_and_not_future(self):
        for row_index in (0, 1, 2):
            for activity in (None, '2026-09-10', '2026-09-26', '2026-02-30', 123):
                with self.subTest(row=row_index, activity=activity):
                    changed = copy.deepcopy(self.data)
                    row = changed['deals'][row_index]
                    row['last_activity_date'] = activity
                    with self.assertRaisesRegex(ValueError, f"{row['Id']}:.*last_activity_date"):
                        calculate(changed, self.policy)
            self.data['deals'][row_index]['last_activity_date'] = '2026-09-11'
        self.assertEqual(calculate(self.data, self.policy)['call'], '200.30')
        self.policy['forecast']['activity_days'] = 13
        with self.assertRaisesRegex(ValueError, 'commit:.*activity_days'):
            calculate(self.data, self.policy)

    def test_upside_stage_and_policy_amount_field(self):
        for stage in ('S0', 'S1'):
            changed = copy.deepcopy(self.data)
            changed['deals'][1]['StageName'] = stage
            with self.subTest(stage=stage), self.assertRaisesRegex(ValueError, 'small:.*S2 through S5'):
                calculate(changed, self.policy)
        for stage in ('S4', 'S5'):
            changed = copy.deepcopy(self.data)
            changed['deals'][1]['StageName'] = stage
            with self.subTest(stage=stage):
                calculate(changed, self.policy)
        self.policy['forecast']['amount_field'] = 'ARR__c'
        for group in ('booked', 'deals', 'pull_ins'):
            for row in self.data[group]:
                row['ARR__c'] = row['Amount']
        for group, row_index in (('deals', 1), ('pull_ins', 0)):
            for value in (None, ''):
                changed = copy.deepcopy(self.data)
                row = changed[group][row_index]
                row['ARR__c'] = value
                with self.subTest(group=group, value=value), self.assertRaisesRegex(ValueError, f"{row['Id']}:.*ARR__c"):
                    calculate(changed, self.policy)
            changed = copy.deepcopy(self.data)
            row = changed[group][row_index]
            del row['ARR__c']
            with self.assertRaisesRegex(ValueError, f"{row['Id']}:.*ARR__c"):
                calculate(changed, self.policy)
        self.assertEqual(calculate(self.data, self.policy)['call'], '200.30')

    def test_pullins_require_next_quarter_and_s2_to_s5_not_activity(self):
        for close_date in (None, '2026-09-30', '2027-01-01', '2026-02-30'):
            with self.subTest(close_date=close_date):
                self.data['pull_ins'][0]['CloseDate'] = close_date
                with self.assertRaisesRegex(ValueError, 'next-quarter:.*CloseDate'):
                    calculate(self.data, self.policy)
        for stage in ('S0', 'S1'):
            self.data['pull_ins'][0].update(StageName=stage, CloseDate='2026-10-01')
            with self.subTest(stage=stage), self.assertRaisesRegex(ValueError, 'next-quarter:.*S2..S5'):
                calculate(self.data, self.policy)
        for stage in ('S2', 'S3', 'S4', 'S5'):
            for close_date in ('2026-10-01', '2026-12-31'):
                self.data['pull_ins'][0].update(StageName=stage, CloseDate=close_date, last_activity_date=None)
                with self.subTest(stage=stage, close_date=close_date):
                    self.assertEqual(calculate(self.data, self.policy)['call'], '200.30')
        self.data['quarter'] = '2026-Q4'
        self.data['pull_ins'][0]['CloseDate'] = '2027-03-31'
        self.assertEqual(calculate(self.data, self.policy)['pull_ins'][0]['Amount'], '9000')
        self.data['pull_ins'][0]['CloseDate'] = '2027-04-01'
        with self.assertRaisesRegex(ValueError, 'next-quarter:.*next quarter'):
            calculate(self.data, self.policy)

    def test_unmappable_stages_fail_with_id(self):
        for group, row_index in (('deals', 0), ('deals', 3), ('pull_ins', 0)):
            for stage in (None, '', 'Closed Won', 'S6', 'S30', 'S3garbage', 3):
                changed = copy.deepcopy(self.data)
                row = changed[group][row_index]
                row['StageName'] = stage
                with self.subTest(group=group, stage=stage), self.assertRaisesRegex(ValueError, f"{row['Id']}:.*StageName"):
                    calculate(changed, self.policy)

    def test_as_of_requires_iso_date_and_excluded_has_no_bucket_predicates(self):
        for as_of in (None, '2026-02-30', '20260925', 123):
            self.data['as_of'] = as_of
            with self.subTest(as_of=as_of), self.assertRaisesRegex(ValueError, 'as_of'):
                calculate(self.data, self.policy)
        self.data['as_of'] = '2026-09-25'
        self.data['deals'][3].update(last_activity_date=None, CloseDate=None)
        self.assertEqual(calculate(self.data, self.policy)['call'], '200.30')

    def test_decimal_totals_ranking_and_pullin_exclusion(self):
        result=calculate(self.data,self.policy)
        self.assertEqual({k:result[k] for k in ('booked','call','upside','gap','buffer','path_shortfall')},
                         {'booked':'100.10','call':'200.30','upside':'900','gap':'800.00','buffer':'100.00','path_shortfall':'0'})
        self.assertEqual([r['Id'] for r in result['path_to_target']],['large','small'])
        self.assertEqual(result['pull_ins'][0]['Amount'],'9000')

    def test_qualified_pipeline_counts_all_open_current_quarter_s2_to_s5_buckets(self):
        for stage in ('S2', 'S3', 'S4', 'S5'):
            self.data['deals'].append({'Id': 'qualified-' + stage, 'StageName': stage, 'bucket': 'excluded',
                                       'Amount': '10.11', 'CloseDate': '2026-07-01',
                                       'buyer_delay_date': None, 'buyer_delay_evidence': None, 'blockers': []})
        for identity, stage, closed, close_date in [('early', 'S1', False, '2026-09-30'),
                                                    ('future', 'S2', False, '2026-10-01'),
                                                    ('past-quarter', 'S2', False, '2026-06-30'),
                                                    ('closed', 'S2', True, '2026-09-30')]:
            self.data['deals'].append({'Id': identity, 'StageName': stage, 'bucket': 'excluded',
                                       'Amount': '3000', 'IsClosed': closed, 'CloseDate': close_date,
                                       'buyer_delay_date': None, 'buyer_delay_evidence': None, 'blockers': []})
        result = calculate(self.data, self.policy)
        self.assertEqual(result['qualified_pipeline'], '1040.64')
        self.assertEqual(result['call'], '200.30')

    def test_qualified_pipeline_uses_configurable_floor_without_changing_buckets(self):
        self.data['deals'][-1]['Amount'] = '50'
        baseline = calculate(self.data, self.policy)
        expected = ('1050.20', '1000.20', '1000.20', '700.20', '100.20', '0')
        for floor, qualified in enumerate(expected):
            with self.subTest(floor=floor):
                self.policy['forecast']['open_min_stage'] = f'S{floor}'
                result = calculate(self.data, self.policy)
                self.assertEqual(result['qualified_pipeline'], qualified)
                for key in ('booked', 'commit', 'upside', 'call', 'pull_ins', 'path_to_target'):
                    self.assertEqual(result[key], baseline[key])

    def test_qualified_pipeline_rejects_missing_or_invalid_shared_floor(self):
        del self.policy['forecast']['open_min_stage']
        with self.assertRaisesRegex(ValueError, 'forecast.open_min_stage'):
            calculate(self.data, self.policy)
        for floor in (None, 2, 'S2ish', 'S6'):
            with self.subTest(floor=floor), self.assertRaisesRegex(ValueError, 'forecast.open_min_stage'):
                self.policy['forecast']['open_min_stage'] = floor
                calculate(self.data, self.policy)

    def test_qualified_pipeline_requires_date_and_amount_and_boolean_closed_flag(self):
        self.data['deals'].append({'Id': 'qualified-missing', 'StageName': 'S2', 'bucket': 'excluded',
                                   'Amount': None, 'CloseDate': '2026-09-30',
                                   'buyer_delay_date': None, 'buyer_delay_evidence': None, 'blockers': []})
        with self.assertRaisesRegex(ValueError, 'qualified-missing: qualified_pipeline needs Amount'):
            calculate(self.data, self.policy)
        self.data['deals'][-1]['Amount'] = '5'
        self.data['deals'][-1]['CloseDate'] = None
        with self.assertRaisesRegex(ValueError, 'qualified-missing: qualified_pipeline needs an ISO CloseDate'):
            calculate(self.data, self.policy)
        self.data['deals'][-1].update(CloseDate='2026-09-30', IsClosed='false')
        with self.assertRaisesRegex(ValueError, 'IsClosed must be Boolean'):
            calculate(self.data, self.policy)

    def test_repository_policy_counts_arr_with_approved_quarter_targets(self):
        policy = yaml.safe_load((Path(__file__).resolve().parents[1] / 'policy.yaml').read_text())
        data = {'as_of': '2026-10-06', 'quarter': '2026-Q4', 'booked': [{'Id': 'won', 'ARR__c': '100', 'Amount': '9000'}],
                'deals': [{'Id': 'commit', 'ARR__c': '200', 'Amount': '8000', 'bucket': 'commit',
                           'StageName': 'S4', 'CloseDate': '2026-10-01', 'last_activity_date': '2026-10-06',
                           'buyer_delay_date': None, 'buyer_delay_evidence': None, 'blockers': []}],
                'pull_ins': []}
        result = calculate(data, policy)
        self.assertEqual((result['booked'], result['call'], result['gap']), ('100', '300', '249700'))
        self.assertEqual(result['qualified_pipeline'], '200')
        for quarter, target in [('2026-Q1', '250000'), ('2026-Q2', '250000'), ('2026-Q3', '250000'),
                                ('2026-Q4', '250000'), ('2027-Q1', '250000')]:
            data['quarter'] = quarter
            self.assertEqual(calculate(data, policy)['target'], target)

    def test_path_stops_after_gap_covered(self):
        self.policy['forecast']['targets']['2026-Q3']='700'
        result=calculate(self.data,self.policy)
        self.assertEqual([r['Id'] for r in result['path_to_target']],['large'])

    def test_shortfall_and_default_target(self):
        self.data['quarter']='2027-Q1'
        self.data['pull_ins'][0]['CloseDate'] = '2027-04-01'
        self.assertEqual(calculate(self.data,self.policy)['path_shortfall'],'899.70')

    def test_target_already_covered_has_no_path(self):
        self.policy['forecast']['targets']['2026-Q3']='100'
        result=calculate(self.data,self.policy)
        self.assertEqual(result['path_to_target'],[])
        self.assertEqual(result['gap'],'-100.30')

    def test_duplicate_ids_and_nonfinite_amounts_fail(self):
        self.data['pull_ins'][0]['Id']='commit'
        with self.assertRaises(ValueError):calculate(self.data,self.policy)
        self.data['pull_ins'][0]['Id']='pull'
        for value in (None,True,'NaN','Infinity',-1):
            self.data['deals'][0]['Amount']=value
            with self.assertRaises(ValueError):calculate(self.data,self.policy)

    def test_path_needs_action_date_field_and_evidence(self):
        for key in ('action','buyer_date','evidence'):
            changed=copy.deepcopy(self.data)
            del changed['deals'][2][key]
            with self.assertRaises(ValueError):calculate(changed,self.policy)

    def test_all_upside_rows_need_fields_when_booked_covers_target(self):
        self.data['booked'][0]['Amount'] = '2000'
        for row_index in (1, 2):
            for key in ('action', 'buyer_date', 'evidence'):
                with self.subTest(row=row_index, key=key):
                    changed = copy.deepcopy(self.data)
                    row = changed['deals'][row_index]
                    del row[key]
                    with self.assertRaisesRegex(ValueError, f"{row['Id']}:.*{key}"):
                        calculate(changed, self.policy)

    def test_unselected_upside_row_needs_fields_after_gap_is_covered(self):
        self.policy['forecast']['targets']['2026-Q3'] = '700'
        for key in ('action', 'buyer_date', 'evidence'):
            changed = copy.deepcopy(self.data)
            del changed['deals'][1][key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, f'small:.*{key}'):
                calculate(changed, self.policy)

    def test_every_pullin_row_needs_action_date_field_and_evidence(self):
        self.data['pull_ins'].append({'Id': 'another-pull', 'Amount': '100', 'action': 'Confirm decision',
                                      'StageName': 'S3', 'CloseDate': '2026-12-31', 'buyer_date': None, 'evidence': 'email-4'})
        for row_index in (0, 1):
            for key in ('action', 'buyer_date', 'evidence'):
                with self.subTest(row=row_index, key=key):
                    changed = copy.deepcopy(self.data)
                    row = changed['pull_ins'][row_index]
                    del row[key]
                    with self.assertRaisesRegex(ValueError, f"{row['Id']}:.*{key}"):
                        calculate(changed, self.policy)

    def test_invalid_upside_and_pullin_field_values_name_the_row(self):
        for group, row_index in (('deals', 1), ('pull_ins', 0)):
            for key, value in (('action', ''), ('action', '  '), ('action', None),
                               ('buyer_date', '2026-02-30'), ('buyer_date', 123), ('evidence', None),
                               ('evidence', []), ('evidence', '')):
                with self.subTest(group=group, key=key, value=value):
                    changed = copy.deepcopy(self.data)
                    row = changed[group][row_index]
                    row[key] = value
                    with self.assertRaisesRegex(ValueError, f"{row['Id']}:.*{key}"):
                        calculate(changed, self.policy)

    def test_valid_rows_keep_totals_when_target_is_covered_and_null_date_is_explicit(self):
        self.data['booked'][0]['Amount'] = '2000'
        self.data['pull_ins'][0]['buyer_date'] = None
        result = calculate(self.data, self.policy)
        self.assertEqual(result['path_to_target'], [])
        self.assertEqual((result['call'], result['upside'], result['buffer']), ('2100.20', '900', '1999.90'))
        self.assertEqual(result['pull_ins'], self.data['pull_ins'])

    def test_cli_invalid_unselected_row_fails_without_calculation_output(self):
        self.data['booked'][0]['Amount'] = '2000'
        del self.data['deals'][1]['evidence']
        with tempfile.TemporaryDirectory() as directory:
            input_path, policy_path = Path(directory) / 'input.json', Path(directory) / 'policy.yaml'
            input_path.write_text(json.dumps(self.data))
            policy_path.write_text(yaml.safe_dump(self.policy))
            output, error = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                self.assertEqual(main(['--input', str(input_path), '--policy', str(policy_path)]), 1)
            self.assertEqual(output.getvalue(), '')
            self.assertIn('Forecast calculation failed: small: needs source evidence', error.getvalue())

    def test_preview_is_optional_and_does_not_change_forecast_totals(self):
        baseline = calculate(self.data, self.policy)
        self.assertNotIn('preview', baseline)
        self.data['preview'] = [{'Id': 'next-quarter', 'Amount': '9000'}]
        result = calculate(self.data, self.policy)
        self.assertEqual({key: value for key, value in result.items() if key != 'preview'}, baseline)
        self.assertEqual(result['preview']['top_three'], [{'Id': 'next-quarter', 'Amount': '9000'}])

    def test_preview_empty_list_is_a_checked_empty_quarter(self):
        self.data['preview'] = []
        self.policy['forecast']['targets']['2026-Q4'] = '1234.56'
        self.assertEqual(calculate(self.data, self.policy)['preview'],
                         {'quarter': '2026-Q4', 'count': 0, 'sum': '0', 'missing_amount_count': 0,
                          'top_three': [], 'target': '1234.56'})

    def test_preview_decimal_sum_missing_count_and_top_three_with_id_ties(self):
        self.data['preview'] = [{'Id': 'next-quarter', 'Amount': '600.10'},
                                {'Id': 'tie-b', 'Amount': '300.20'},
                                {'Id': 'tie-a', 'Amount': '300.20'},
                                {'Id': 'lower', 'Amount': '0.01'},
                                {'Id': 'missing', 'Amount': None}]
        preview = calculate(self.data, self.policy)['preview']
        self.assertEqual((preview['count'], preview['sum'], preview['missing_amount_count']), (5, '1200.51', 1))
        self.assertEqual(preview['top_three'], [{'Id': 'next-quarter', 'Amount': '600.10'},
                                               {'Id': 'tie-a', 'Amount': '300.20'},
                                               {'Id': 'tie-b', 'Amount': '300.20'}])

    def test_preview_missing_amounts_are_not_zero_amount_ranked_rows(self):
        self.data['preview'] = [{'Id': 'missing-a', 'Amount': None}, {'Id': 'missing-b', 'Amount': None}]
        preview = calculate(self.data, self.policy)['preview']
        self.assertEqual((preview['count'], preview['sum'], preview['missing_amount_count'], preview['top_three']),
                         (2, '0', 2, []))
        self.data['preview'].append({'Id': 'present-zero', 'Amount': 0})
        preview = calculate(self.data, self.policy)['preview']
        self.assertEqual(preview['top_three'], [{'Id': 'present-zero', 'Amount': '0'}])
        self.assertEqual((preview['count'], preview['sum'], preview['missing_amount_count']), (3, '0', 2))

    def test_preview_q4_rollover_policy_amount_field_and_next_quarter_target(self):
        policy = yaml.safe_load((Path(__file__).resolve().parents[1] / 'policy.yaml').read_text())
        data = {'as_of': '2026-10-06', 'quarter': '2026-Q4', 'booked': [], 'deals': [], 'pull_ins': [],
                'preview': [{'Id': 'present', 'ARR__c': '123.45', 'Amount': '999999'},
                            {'Id': 'missing', 'ARR__c': None, 'Amount': '999999'}]}
        preview = calculate(data, policy)['preview']
        self.assertEqual((preview['quarter'], preview['target'], preview['sum'], preview['missing_amount_count']),
                         ('2027-Q1', '250000', '123.45', 1))
        self.assertEqual(preview['top_three'], [{'Id': 'present', 'ARR__c': '123.45'}])
        self.data['quarter'] = '2027-Q4'
        self.data['pull_ins'][0]['CloseDate'] = '2028-01-01'
        self.data['preview'] = []
        self.assertEqual((calculate(self.data, self.policy)['preview']['quarter'],
                          calculate(self.data, self.policy)['preview']['target']), ('2028-Q1', '2000'))

    def test_preview_rejects_invalid_present_amounts(self):
        for amount in (True, False, 'NaN', 'Infinity', '-Infinity', -1, 'not-a-number'):
            with self.subTest(amount=amount):
                self.data['preview'] = [{'Id': 'preview', 'Amount': amount}]
                with self.assertRaises(ValueError):
                    calculate(self.data, self.policy)

    def test_preview_requires_list_object_id_and_explicit_amount_or_null(self):
        for preview in (None, {}, 'rows', [None], [[]], [{}], [{'Id': ''}], [{'Id': 1, 'Amount': None}],
                        [{'Id': 'preview'}]):
            with self.subTest(preview=preview):
                self.data['preview'] = preview
                with self.assertRaises(ValueError):
                    calculate(self.data, self.policy)

    def test_preview_rejects_duplicates_and_overlap_with_every_current_bucket(self):
        for identity in ('won', 'commit', 'small', 'large', 'excluded'):
            with self.subTest(identity=identity):
                self.data['preview'] = [{'Id': identity, 'Amount': None}]
                with self.assertRaisesRegex(ValueError, 'do not overlap booked or deals'):
                    calculate(self.data, self.policy)
        self.data['preview'] = [{'Id': 'duplicate', 'Amount': None}, {'Id': 'duplicate', 'Amount': '10'}]
        with self.assertRaisesRegex(ValueError, 'preview needs unique Ids'):
            calculate(self.data, self.policy)

    def test_cli_returns_preview_json_without_changing_pullins(self):
        self.data['preview'] = [{'Id': 'next-quarter', 'Amount': '9000'}, {'Id': 'missing', 'Amount': None}]
        with tempfile.TemporaryDirectory() as directory:
            input_path, policy_path = Path(directory) / 'input.json', Path(directory) / 'policy.yaml'
            input_path.write_text(json.dumps(self.data))
            policy_path.write_text(yaml.safe_dump(self.policy))
            output, error = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                self.assertEqual(main(['--input', str(input_path), '--policy', str(policy_path)]), 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result['preview'], calculate(self.data, self.policy)['preview'])
            self.assertEqual(result['pull_ins'], self.data['pull_ins'])
            self.assertEqual(error.getvalue(), '')


class ForecastTrackingTests(unittest.TestCase):
    def setUp(self):
        self.policy = {'forecast': {'amount_field': 'ARR__c', 'targets': {}, 'target_default': 1000, 'open_min_stage': 'S2',
                                   'tracking': { 'coverage_min': 3, 'pace_behind_alert_percent': 15}}}

    def row(self, identity, amount, close='2026-03-31', *, won=False, lost=False, category='Pipeline'):
        return {'Id': identity, 'ARR__c': amount, 'Amount': 999999, 'CloseDate': close,
                'IsClosed': won or lost, 'IsWon': won, 'ForecastCategoryName': category, 'StageName': 'S2 - Qualified'}

    def result(self, rows, as_of='2026-02-15', previous=None):
        data = {'as_of': as_of, 'records': rows}
        if previous is not None:
            data['previous'] = previous
        return calculate_tracking(data, self.policy)

    def test_tracking_stage_floor_excludes_early_deals_from_all_current_coverage(self):
        rows = [{**self.row('early-s1', 10000, '2026-12-31'), 'StageName': 'S1 - Discovery'},
                {**self.row('early-s0', 90000, '2026-12-31'), 'StageName': 'S0'},
                self.row('qualified-s2', 300, '2026-12-31'),
                {**self.row('qualified-s3', 400, '2026-12-31'), 'StageName': 'S3 - Validation'},
                {**self.row('qualified-s4', 200, '2026-12-31'), 'StageName': 'S4'},
                {**self.row('booked-s1', 100, '2026-12-31', won=True), 'StageName': 'S1'}]
        result = self.result(rows, '2026-10-12')
        expected_ids = ['qualified-s2', 'qualified-s3', 'qualified-s4']
        for scope in ('quarter', 'year'):
            self.assertEqual(result[scope]['open_pipeline'], '900.00')
            self.assertEqual(result[scope]['open_ids'], expected_ids)
            self.assertEqual(result[scope]['booked'], '100.00')
            self.assertEqual(result[scope]['booked_ids'], ['booked-s1'])
            self.assertEqual(result[scope]['largest_two_ids'], ['qualified-s3', 'qualified-s2'])
        self.assertEqual(result['quarter']['coverage'], '1.0000')
        self.assertEqual(result['quarter']['coverage_without_largest_two'], '0.2222')
        self.assertEqual(result['year']['coverage'], '0.2308')
        self.assertEqual(result['year']['coverage_without_largest_two'], '0.0513')
        for alert in result['alerts']:
            self.assertEqual(alert['opportunity_ids'], expected_ids)
        self.assertEqual(result['snapshot']['open_min_stage'], 'S2')
        self.assertEqual(next(row for row in result['snapshot']['records'] if row['Id'] == 'early-s1')['StageName'],
                         'S1 - Discovery')

    def test_tracking_floor_reads_policy_and_stage_prefixes(self):
        rows = [{**self.row(f'stage-{stage}', 100), 'StageName': f'S{stage} - Synthetic'} for stage in range(6)]
        for floor in range(6):
            with self.subTest(floor=floor):
                self.policy['forecast']['open_min_stage'] = f'S{floor}'
                result = self.result(rows)
                self.assertEqual(result['quarter']['open_ids'], [f'stage-{stage}' for stage in range(floor, 6)])
                self.assertEqual(result['quarter']['open_pipeline'], f'{(6 - floor) * 100}.00')

    def test_tracking_existing_s2_snapshot_survives_policy_key_move(self):
        row = self.row('qualified', 100)
        previous = {'as_of': '2026-02-15', 'records': [row], 'open_min_stage': 'S2',
                    'targets': {'quarter': '1000.00', 'year': '4000.00'}}
        self.assertNotIn('open_min_stage', self.policy['forecast']['tracking'])
        result = self.result([row], previous=previous)
        self.assertEqual(result['snapshot']['open_min_stage'], 'S2')
        self.assertEqual(result['quarter']['open_pipeline'], '100.00')
        self.assertIsNone(result['basis_change'])
        self.assertTrue(result['comparison_available'])
        self.assertFalse(result['material_change'])
        self.assertFalse(any(alert['kind'] in ('coverage_drop', 'pipeline_drop') for alert in result['alerts']))

    def test_tracking_invalid_policy_floor_is_an_error(self):
        for floor in (None, 2, 'S2ish', 'S6'):
            with self.subTest(floor=floor), self.assertRaisesRegex(ValueError, 'forecast.open_min_stage'):
                self.policy['forecast']['open_min_stage'] = floor
                self.result([])

    def test_tracking_open_stage_is_required_and_must_parse(self):
        row = self.row('open', 100)
        del row['StageName']
        with self.assertRaisesRegex(ValueError, 'open: StageName'):
            self.result([row])
        for stage in (None, 2, {}, 'S2ish', 'S6', 'S20'):
            with self.subTest(stage=stage), self.assertRaisesRegex(ValueError, 'open: StageName'):
                self.result([{**row, 'StageName': stage}])
        booked = self.row('booked', 100, won=True)
        del booked['StageName']
        self.assertEqual(self.result([booked])['quarter']['booked'], '100.00')

    def test_legacy_stage_basis_change_is_reported_once_without_movement_comparison(self):
        rows = [{**self.row('early', 10000, '2026-12-31'), 'StageName': 'S1'}]
        self.policy['forecast']['open_min_stage'] = 'S0'
        previous = self.result(rows, '2026-10-05')['snapshot']
        del previous['open_min_stage']
        for row in previous['records']:
            row.pop('StageName', None)
        self.policy['forecast']['open_min_stage'] = 'S2'
        result = self.result(rows, '2026-10-12', previous)
        self.assertEqual(result['basis_change'], {'previous_open_min_stage': None, 'open_min_stage': 'S2'})
        self.assertTrue(result['baseline_available'])
        self.assertFalse(result['comparison_available'])
        self.assertTrue(result['material_change'])
        self.assertEqual(result['quarter']['open_pipeline'], '0.00')
        self.assertEqual(result['quarter']['open_ids'], [])
        repeated = self.result(rows, '2026-10-19', result['snapshot'])
        self.assertIsNone(repeated['basis_change'])
        self.assertTrue(repeated['comparison_available'])
        self.assertFalse(repeated['material_change'])
        invalid = [{**rows[0], 'StageName': None}]
        with self.assertRaisesRegex(ValueError, 'early: StageName'):
            self.result(invalid, '2026-10-12', previous)

    def test_different_stage_basis_preserves_actual_closed_and_commit_date_alerts(self):
        rows = [{**self.row('early', 10000, '2026-12-31'), 'StageName': 'S1'},
                {**self.row('win', 100, '2026-12-31'), 'StageName': 'S1'},
                self.row('push', 300, '2026-12-31', category='Commit')]
        self.policy['forecast']['open_min_stage'] = 'S0'
        previous = self.result(rows, '2026-10-05')['snapshot']
        self.policy['forecast']['open_min_stage'] = 'S2'
        current = [rows[0], {**rows[1], 'IsClosed': True, 'IsWon': True},
                   {**rows[2], 'CloseDate': '2027-03-31'}]
        result = self.result(current, '2026-10-12', previous)
        self.assertEqual(result['basis_change'], {'previous_open_min_stage': 'S0', 'open_min_stage': 'S2'})
        self.assertFalse(result['comparison_available'])
        self.assertEqual(result['quarter']['booked'], '100.00')
        alerts = {row['kind']: row for row in result['alerts']}
        self.assertEqual(alerts['closed_won']['opportunity_ids'], ['win'])
        self.assertEqual(alerts['commit_left_quarter']['opportunity_ids'], ['push'])

    def test_tracking_cli_missing_open_stage_blocks_output(self):
        data = {'as_of': '2026-10-12', 'records': [self.row('missing-stage', 100, '2026-12-31')]}
        del data['records'][0]['StageName']
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / 'input.json'
            policy_path = Path(directory) / 'policy.yaml'
            input_path.write_text(json.dumps(data))
            policy_path.write_text(yaml.safe_dump(self.policy))
            output, error = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                self.assertEqual(main(['--tracking', '--input', str(input_path), '--policy', str(policy_path)]), 1)
            self.assertEqual(output.getvalue(), '')
            self.assertIn('missing-stage: StageName', error.getvalue())

    def test_period_scope_uses_arr_and_rest_of_year_open_pipeline(self):
        rows = [self.row('won', '100.10', '2026-01-01', won=True),
                self.row('year-win', '200.20', '2026-12-31', won=True),
                self.row('old-win', 9999, '2025-12-31', won=True),
                self.row('lost', None, lost=True), self.row('overdue', 50, '2026-02-01'),
                self.row('open', 300), self.row('future', 400, '2026-12-31'),
                self.row('next-year', 9999, '2027-01-01')]
        result = self.result(rows)
        quarter, year = result['quarter'], result['year']
        self.assertEqual((quarter['booked'], quarter['gap'], quarter['open_pipeline']),
                         ('100.10', '899.90', '350.00'))
        self.assertEqual((year['booked'], year['gap'], year['open_pipeline']),
                         ('300.30', '3699.70', '700.00'))
        self.assertEqual(year['open_ids'], ['future', 'open'])

    def test_concentration_ranking_and_coverage_without_largest_two(self):
        quarter = self.result([self.row('b', 400), self.row('c', 200), self.row('a', 400)])['quarter']
        self.assertEqual(quarter['largest_two_ids'], ['a', 'b'])
        self.assertEqual((quarter['largest_two_share_percent'], quarter['coverage'],
                          quarter['coverage_without_largest_two']), ('80.00', '1.0000', '0.2000'))

    def test_actual_policy_annual_targets_and_zero_quarter(self):
        self.policy = yaml.safe_load((Path(__file__).resolve().parents[1] / 'policy.yaml').read_text())
        result = self.result([])
        self.assertEqual(result['year']['target'], '1000000.00')
        self.assertEqual(result['quarter']['target'], '250000.00')
        self.assertIsNotNone(result['quarter']['pace_behind_percent'])
        self.assertTrue(result['quarter']['pace_alert'])
        self.assertEqual(self.result([], '2027-01-01')['year']['target'], '1000000.00')

    def test_calendar_days_linear_pace_and_required_per_week(self):
        result = self.result([], '2024-02-15')
        quarter = result['quarter']
        self.assertEqual((quarter['elapsed_days'], quarter['total_days'], quarter['remaining_days']), (46, 91, 45))
        self.assertEqual((quarter['linear_pace'], quarter['required_per_week']), ('505.49', '155.56'))
        self.assertEqual(result['year']['total_days'], 366)

    def test_ramp_year_pace_includes_completed_targets_and_current_quarter_days(self):
        self.policy['forecast']['targets'] = {'2026-Q1': 0, '2026-Q2': 0,
                                            '2026-Q3': 333333, '2026-Q4': 666667}
        rows = [self.row('won', 300000, '2026-09-30', won=True)]
        result = self.result(rows, '2026-10-01')
        year = result['year']
        self.assertEqual((year['target'], year['linear_pace'], year['pace_behind_percent']),
                         ('1000000.00', '340579.38', '11.91'))
        self.assertFalse(year['pace_alert'])
        self.assertEqual((year['elapsed_days'], year['total_days'], year['remaining_days']), (274, 365, 91))
        quarter = result['quarter']
        self.assertEqual((quarter['linear_pace'], quarter['gap'], quarter['required_per_week']),
                         ('7246.38', '666667.00', '51282.08'))
        self.assertEqual((quarter['coverage'], quarter['coverage_without_largest_two']), ('0.0000', '0.0000'))
        self.assertIsNone(quarter['largest_two_share_percent'])
        rows[0]['ARR__c'] = 400000
        year = self.result(rows, '2026-10-01')['year']
        self.assertEqual(year['pace_behind_percent'], '0.00')
        self.assertFalse(year['pace_alert'])

    def test_ramp_year_zero_pace_and_quarter_boundaries(self):
        self.policy['forecast']['targets'] = {'2026-Q1': 0, '2026-Q2': 0,
                                            '2026-Q3': 333333, '2026-Q4': 666667}
        for as_of in ('2026-01-01', '2026-03-31', '2026-04-01', '2026-06-30'):
            with self.subTest(as_of=as_of):
                year = self.result([], as_of)['year']
                self.assertEqual(year['linear_pace'], '0.00')
                self.assertIsNone(year['pace_behind_percent'])
                self.assertFalse(year['pace_alert'])
        for as_of, expected in (('2026-07-01', '3623.18'), ('2026-09-30', '333333.00'),
                                ('2026-12-31', '1000000.00')):
            with self.subTest(as_of=as_of):
                self.assertEqual(self.result([], as_of)['year']['linear_pace'], expected)

    def test_default_target_year_pace_and_year_end(self):
        for as_of, expected in (('2026-01-01', '11.11'), ('2026-03-31', '1000.00'),
                                ('2026-04-01', '1010.99'), ('2026-06-30', '2000.00'),
                                ('2026-10-01', '3010.87'), ('2026-12-31', '4000.00'),
                                ('2024-02-15', '505.49')):
            with self.subTest(as_of=as_of):
                year = self.result([], as_of)['year']
                self.assertEqual((year['target'], year['linear_pace']), ('4000.00', expected))
                self.assertEqual(year['pace_behind_percent'], '100.00')
        year = self.result([self.row('won', 4000, '2026-12-31', won=True)], '2026-12-31')['year']
        self.assertEqual((year['linear_pace'], year['gap'], year['pace_behind_percent']),
                         ('4000.00', '0.00', '0.00'))
        self.assertEqual(year['required_per_week'], '0.00')
        self.assertIsNone(year['coverage'])

    def test_year_pace_uses_default_for_unlisted_completed_and_current_quarters(self):
        self.policy['forecast']['targets'] = {'2026-Q1': 0, '2026-Q3': 3000}
        year = self.result([], '2026-10-01')['year']
        self.assertEqual((year['target'], year['linear_pace']), ('5000.00', '4010.87'))

    def test_period_end_and_covered_gap_have_explicit_nulls(self):
        quarter = self.result([], '2026-03-31')['quarter']
        self.assertEqual(quarter['linear_pace'], '1000.00')
        self.assertIsNone(quarter['required_per_week'])
        self.assertEqual(quarter['coverage'], '0.0000')
        self.assertIsNone(quarter['largest_two_share_percent'])
        quarter = self.result([self.row('won', 1200, won=True)], '2026-03-31')['quarter']
        self.assertEqual((quarter['gap'], quarter['required_per_week']), ('0.00', '0.00'))
        self.assertIsNone(quarter['coverage'])
        self.assertIsNone(quarter['coverage_without_largest_two'])
        self.assertFalse(quarter['coverage_alert'])

    def test_thresholds_are_strict_and_use_unrounded_values(self):
        rows = [self.row('won', 850, won=True), self.row('open', 450)]
        quarter = self.result(rows, '2026-03-31')['quarter']
        self.assertFalse(quarter['coverage_alert'])
        self.assertFalse(quarter['pace_alert'])
        rows[0]['ARR__c'] = '849.999'
        quarter = self.result(rows, '2026-03-31')['quarter']
        self.assertEqual(quarter['pace_behind_percent'], '15.00')
        self.assertEqual(quarter['coverage'], '3.0000')
        self.assertTrue(quarter['coverage_alert'])
        self.assertTrue(quarter['pace_alert'])

    def test_missing_or_invalid_contributing_amount_is_not_zero(self):
        for value in (None, True, 'NaN', 'Infinity', -1):
            for won in (False, True):
                with self.subTest(value=value, won=won), self.assertRaises(ValueError):
                    self.result([self.row('bad', value, won=won)])

    def test_malformed_records_fail_before_reporting(self):
        row = self.row('deal', 100)
        for key, value in [('IsWon', 'false'), ('IsClosed', None), ('CloseDate', '2026-02-30'),
                           ('CloseDate', '20260215'), ('Id', '')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.result([{**row, key: value}])
        with self.assertRaises(ValueError):
            self.result([row, row])
        with self.assertRaises(ValueError):
            self.result([{**row, 'IsWon': True, 'IsClosed': False}])

    def test_no_baseline_requires_initial_report(self):
        result = self.result([])
        self.assertFalse(result['baseline_available'])
        self.assertTrue(result['material_change'])

    def test_identical_records_and_decimal_format_do_not_trigger_report(self):
        previous = self.result([self.row('deal', '100.00')], '2026-02-15')['snapshot']
        result = self.result([self.row('deal', 100)], '2026-02-22', previous)
        self.assertTrue(result['baseline_available'])
        self.assertFalse(result['material_change'])

    def test_pace_threshold_crossing_is_material_without_record_changes(self):
        rows = [self.row('won', 500, won=True)]
        previous = self.result(rows, '2026-02-15')['snapshot']
        result = self.result(rows, '2026-03-01', previous)
        self.assertTrue(result['material_change'])
        self.assertTrue(result['quarter']['pace_alert'])

    def test_period_and_target_changes_are_material(self):
        previous = self.result([], '2026-03-31')['snapshot']
        self.assertTrue(self.result([], '2026-04-01', previous)['material_change'])
        previous = self.result([])['snapshot']
        self.policy['forecast']['target_default'] = 2000
        self.assertTrue(self.result([], previous=previous)['material_change'])

    def test_closed_outcomes_and_commit_push_have_opportunity_ids(self):
        rows = [self.row('won', 100), self.row('lost', 200), self.row('push', 300, category='Commit')]
        previous = self.result(rows)['snapshot']
        current = [self.row('won', 100, won=True), self.row('lost', 200, lost=True),
                   self.row('push', 300, '2027-01-01')]
        alerts = self.result(current, previous=previous)['alerts']
        by_kind = {r['kind']: r for r in alerts}
        self.assertEqual(by_kind['closed_won']['opportunity_ids'], ['won'])
        self.assertEqual(by_kind['closed_lost']['opportunity_ids'], ['lost'])
        self.assertEqual(by_kind['commit_left_quarter']['opportunity_ids'], ['push'])
        self.assertEqual(by_kind['commit_left_quarter']['new_date'], '2027-01-01')
        self.assertEqual(by_kind['closed_won']['periods'], ['quarter', 'year'])

    def test_calendar_rollover_is_not_a_commit_date_move(self):
        rows = [self.row('commit', 300, category='Commit')]
        previous = self.result(rows, '2026-03-31')['snapshot']
        result = self.result(rows, '2026-04-01', previous)
        self.assertNotIn('commit_left_quarter', [r['kind'] for r in result['alerts']])

    def test_missing_previous_open_record_and_future_snapshot_fail(self):
        previous = self.result([self.row('deal', 100)])['snapshot']
        with self.assertRaisesRegex(ValueError, 'must be reread.*unavailable_prior with a reviewed reason: deal'):
            self.result([], previous=previous)
        with self.assertRaisesRegex(ValueError, 'cannot be later'):
            self.result([], '2026-02-01', previous)

    def unavailable(self, rows, as_of, previous, *entries):
        data = {'as_of': as_of, 'records': rows, 'previous': previous, 'unavailable_prior': list(entries)}
        return calculate_tracking(data, self.policy)

    def test_unavailable_prior_keeps_comparison_incomplete_and_the_last_complete_baseline(self):
        """V4. A deleted, merged or reassigned prior open Id is listed with a reason, never inferred closed or moved."""
        rows = [self.row('kept', 100), self.row('gone', 300, category='Commit')]
        previous = self.result(rows, '2026-02-08')['snapshot']
        entry = {'Id': 'gone', 'reason': 'Record not returned by owner query, merge suspected, reviewed 2/15'}
        result = self.unavailable([self.row('kept', 100)], '2026-02-15', previous, entry)
        self.assertEqual(result['unavailable_prior'], [{**previous['records'][0], 'reason': entry['reason']}])
        self.assertEqual(result['unavailable_prior'][0]['Id'], 'gone')
        self.assertTrue(result['baseline_available'])
        self.assertFalse(result['comparison_available'])
        self.assertTrue(result['material_change'])
        self.assertIsNone(result['basis_change'])
        self.assertEqual(result['baseline_as_of'], '2026-02-08')
        self.assertEqual([alert['kind'] for alert in result['alerts'] if 'gone' in alert['opportunity_ids']], [])
        self.assertNotIn('commit_left_quarter', [alert['kind'] for alert in result['alerts']])
        self.assertEqual(result['quarter']['open_pipeline'], '100.00')
        snapshot = result['snapshot']
        self.assertEqual(snapshot['baseline_as_of'], '2026-02-08')
        self.assertEqual([row['Id'] for row in snapshot['records']], ['kept'])
        self.assertEqual(snapshot['unavailable_prior'], result['unavailable_prior'])
        with self.assertRaisesRegex(ValueError, 'must be reread.*gone'):
            self.result([self.row('kept', 100)], '2026-02-22', snapshot)
        again = self.unavailable([self.row('kept', 100)], '2026-02-22', snapshot, {'Id': 'gone', 'reason': 'still unavailable'})
        self.assertEqual(again['baseline_as_of'], '2026-02-08')
        self.assertFalse(again['comparison_available'])
        self.assertTrue(again['material_change'])
        self.assertEqual(again['unavailable_prior'][0]['reason'], 'still unavailable')
        back = self.result([self.row('kept', 100), self.row('gone', 300, '2027-01-01')], '2026-03-01', snapshot)
        self.assertTrue(back['comparison_available'])
        self.assertEqual(back['baseline_as_of'], '2026-02-08')
        self.assertEqual(back['unavailable_prior'], [])
        self.assertNotIn('unavailable_prior', back['snapshot'])
        self.assertNotIn('baseline_as_of', back['snapshot'])
        moved = next(alert for alert in back['alerts'] if alert['kind'] == 'commit_left_quarter')
        self.assertEqual((moved['opportunity_ids'], moved['old_date']), (['gone'], '2026-03-31'))
        self.assertTrue(self.result([self.row('kept', 100), self.row('gone', 300, lost=True)], '2026-03-01', snapshot)['alerts'])

    def test_unavailable_prior_entries_are_reviewed_and_scoped(self):
        previous = self.result([self.row('kept', 100), self.row('gone', 300)], '2026-02-08')['snapshot']
        current = [self.row('kept', 100)]
        good = {'Id': 'gone', 'reason': 'reviewed'}
        for case in ('not-a-list', [None], [{'Id': 'gone'}], [{**good, 'extra': 1}], [{'Id': '', 'reason': 'x'}],
                     [{'Id': 'gone', 'reason': ' '}], [{'Id': 'gone', 'reason': None}], [good, good],
                     [{'Id': 'kept', 'reason': 'present'}], [{'Id': 'unknown', 'reason': 'never open'}], []):
            data = {'as_of': '2026-02-15', 'records': current, 'previous': previous, 'unavailable_prior': case}
            with self.subTest(case=case), self.assertRaises(ValueError):
                calculate_tracking(data, self.policy)
        complete = {'as_of': '2026-02-15', 'records': [self.row('kept', 100), self.row('gone', 300)],
                    'previous': previous, 'unavailable_prior': [good]}
        with self.assertRaisesRegex(ValueError, 'not a missing previously open record'):
            calculate_tracking(complete, self.policy)
        self.assertTrue(self.result([self.row('kept', 100)], '2026-02-15', self.result([self.row('kept', 100)])['snapshot'])['comparison_available'])

    def test_cli_tracking_emits_json_and_rejects_invalid_amount(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path, policy_path = Path(directory) / 'input.json', Path(directory) / 'policy.yaml'
            policy_path.write_text(yaml.safe_dump(self.policy))
            input_path.write_text(json.dumps({'as_of': '2026-02-15', 'records': []}))
            output = io.StringIO()
            args = ['--tracking', '--input', str(input_path), '--policy', str(policy_path)]
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(args), 0)
            self.assertEqual(json.loads(output.getvalue())['year']['target'], '4000.00')
            input_path.write_text(json.dumps({'as_of': '2026-02-15', 'records': [self.row('bad', None)]}))
            error = io.StringIO()
            with contextlib.redirect_stderr(error):
                self.assertEqual(main(args), 1)
            self.assertIn('Forecast calculation failed', error.getvalue())
