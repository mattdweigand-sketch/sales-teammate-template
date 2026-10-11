from copy import deepcopy
import unittest

import test_task_reschedule_check as fixtures


def manual_request():
    request = fixtures.reschedule_request_fixture()
    request['task']['ActivityDate'] = '2026-10-08'
    request['note_line'] = '10/7/26 SR - Operator typed the current-action date move'
    fixtures.sync_related_task_fixture(request)
    request['manual_one_deal'] = {
        'task_id': fixtures.TASK_ID,
        'opportunity_id': fixtures.OPPORTUNITY_ID,
        'command_text': 'next step Example review the form by 2026-10-09',
        'command_url': 'https://example.test/source-turn',
        'source_kind': 'operator_typed_command',
    }
    return request


def prewrite_request(request, proposal):
    current = deepcopy(request)
    current['baseline'] = deepcopy(proposal['baseline'])
    current['baseline_links'] = deepcopy(proposal['baseline_links'])
    current['displayed_payload'] = deepcopy(proposal['payload'])
    current['baseline_manual_one_deal'] = deepcopy(proposal['manual_one_deal'])
    return current


class ManualCurrentAction(unittest.TestCase):
    def test_future_current_task_manual_ready_but_scheduled_excluded(self):
        request = manual_request()
        result = fixtures.evaluate_task_reschedule(request)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(request['writer'], 'triage')
        self.assertEqual(result['manual_one_deal']['source_kind'], 'operator_typed_command')
        request.pop('manual_one_deal')
        result = fixtures.evaluate_task_reschedule(request)
        self.assertEqual(result['status'], 'no-op')
        self.assertNotIn('payload', result)

    def test_existing_exact_task_is_reused_and_milestone_untouched(self):
        request = manual_request()
        milestone = deepcopy(request['task'])
        milestone.update(Id=fixtures.OTHER_TASK_ID, Subject='Later unrelated milestone', ActivityDate='2026-10-28')
        request['related_opportunity']['records'].append(milestone)
        request['related_opportunity']['totalSize'] = 2
        saved = deepcopy(request)
        result = fixtures.evaluate_task_reschedule(request)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['payload']['Id'], fixtures.TASK_ID)
        self.assertEqual(set(result['payload']), {'Id', 'ActivityDate', 'Description'})
        self.assertEqual(request, saved)
        self.assertEqual(request['related_opportunity']['records'][1], milestone)

    def test_manual_identity_missing_opportunity_and_nontriage_are_held(self):
        for field, value in (('task_id', fixtures.OTHER_TASK_ID), ('opportunity_id', '006000000000099'),
                             ('source_kind', 'buyer_evidence'), ('command_text', ''), ('command_url', '/relative')):
            with self.subTest(field=field):
                request = manual_request()
                request['manual_one_deal'][field] = value
                result = fixtures.evaluate_task_reschedule(request)
                self.assertEqual(result['status'], 'needs-input')
                self.assertNotIn('payload', result)
        request = manual_request()
        request['writer'] = 'deal_thread'
        self.assertEqual(fixtures.evaluate_task_reschedule(request)['status'], 'needs-input')
        request = manual_request()
        request['opportunity'] = None
        request['related_opportunity'] = None
        request['related_opportunity_soql'] = None
        self.assertEqual(fixtures.evaluate_task_reschedule(request)['status'], 'needs-input')

    def test_manual_multiple_current_tasks_or_incomplete_reads_hold(self):
        request = manual_request()
        other = deepcopy(request['task'])
        other['Id'] = fixtures.OTHER_TASK_ID
        request['related_opportunity']['records'].append(other)
        request['related_opportunity']['totalSize'] = 2
        request['current_action_task_ids'].append(fixtures.OTHER_TASK_ID)
        self.assertEqual(fixtures.evaluate_task_reschedule(request)['status'], 'needs-input')
        request = manual_request()
        request['related_opportunity']['hasMore'] = True
        self.assertEqual(fixtures.evaluate_task_reschedule(request)['status'], 'needs-input')

    def test_manual_prewrite_keeps_exact_payload_and_provenance(self):
        request = manual_request()
        proposal = fixtures.evaluate_task_reschedule(request)
        current = prewrite_request(request, proposal)
        result = fixtures.evaluate_task_reschedule(current, phase='prewrite')
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['payload'], proposal['payload'])
        for mutate in ('remove', 'change', 'missing_baseline'):
            current = prewrite_request(request, proposal)
            if mutate == 'remove':
                current.pop('manual_one_deal')
            elif mutate == 'change':
                current['manual_one_deal']['command_text'] = 'changed source'
            else:
                current.pop('baseline_manual_one_deal')
            self.assertEqual(fixtures.evaluate_task_reschedule(current, phase='prewrite')['status'], 'needs-input')

    def test_native_change_and_changed_displayed_payload_stop_manual_write(self):
        request = manual_request()
        proposal = fixtures.evaluate_task_reschedule(request)
        current = prewrite_request(request, proposal)
        current['task']['LastModifiedDate'] = '2026-10-07T03:06:31.000+0000'
        fixtures.sync_related_task_fixture(current)
        result = fixtures.evaluate_task_reschedule(current, phase='prewrite')
        self.assertEqual(result['status'], 'stale')
        self.assertNotIn('payload', result)
        current = prewrite_request(request, proposal)
        current['displayed_payload']['ActivityDate'] = '2026-10-12'
        result = fixtures.evaluate_task_reschedule(current, phase='prewrite')
        self.assertEqual(result['status'], 'needs-input')
        self.assertNotIn('payload', result)


if __name__ == '__main__':
    unittest.main()
