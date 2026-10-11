"""Native-snapshot regressions and offline two-writer Task reschedule flows."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Literal
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "workspaces/pipeline/scripts/task_reschedule_check.py"
SPEC = importlib.util.spec_from_file_location("task_reschedule_check", SCRIPT)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)
TASK_ID = "00T000000000001"
OTHER_TASK_ID = "00T000000000002"
ACCOUNT_ID = "001000000000001"
OPPORTUNITY_ID = "006000000000001"
AS_OF = "2026-10-07T09:00:00-07:00"
PREFIX = "M/D/YY SR - "


def native_related_task_soql(link_id: str) -> str:
    return "SELECT " + ", ".join(CHECK.TASK_BASELINE_FIELDS) + f" FROM Task WHERE WhatId = '{link_id}' AND IsClosed = false"


def native_task_fixture() -> CHECK.NativeTaskSnapshot:
    return {
        "attributes": {"type": "Task"}, "Id": TASK_ID, "OwnerId": "005000000000001",
        "Subject": "Confirm pilot review", "Status": "Not Started", "IsClosed": False,
        "ActivityDate": "2026-10-06", "LastModifiedDate": "2026-10-07T02:06:31.000+0000",
        "WhatId": OPPORTUNITY_ID, "WhoId": "003000000000001",
        "Description": "10/6/26 SR - Buyer proposed review\r\nOriginal history unchanged\n",
    }


def reschedule_request_fixture() -> CHECK.TaskRescheduleRequest:
    task = native_task_fixture()
    return {
        "writer": "triage", "task": task,
        "account": {"attributes": {"type": "Account"}, "Id": ACCOUNT_ID},
        "opportunity": {"attributes": {"type": "Opportunity"}, "Id": OPPORTUNITY_ID, "AccountId": ACCOUNT_ID},
        "related_account": {"records": [], "totalSize": 0, "hasMore": False},
        "related_opportunity": {"records": [deepcopy(task)], "totalSize": 1, "hasMore": False},
        "related_account_soql": native_related_task_soql(ACCOUNT_ID),
        "related_opportunity_soql": native_related_task_soql(OPPORTUNITY_ID),
        "current_action_task_ids": [TASK_ID], "desired_date": "2026-10-09",
        "note_line": "10/7/26 SR - Buyer requested Friday review, deal thread owns next step",
    }


def sync_related_task_fixture(request: CHECK.TaskRescheduleRequest) -> None:
    task = request["task"]
    for envelope in (request["related_account"], request["related_opportunity"]):
        if envelope is not None:
            envelope["records"] = [record for record in envelope["records"] if record["Id"] != task["Id"]]
    if not task["IsClosed"]:
        target = request["related_account"] if task["WhatId"] == request["account"]["Id"] else request["related_opportunity"]
        target["records"].append(deepcopy(task))
    for envelope in (request["related_account"], request["related_opportunity"]):
        if envelope is not None:
            envelope["totalSize"] = len(envelope["records"])


def evaluate_task_reschedule(request: CHECK.TaskRescheduleRequest, phase: Literal["proposal", "prewrite"] = "proposal") -> CHECK.TaskRescheduleResult:
    return CHECK.check_task_reschedule(request, phase=phase, as_of=AS_OF, note_prefix=PREFIX)


def run_task_reschedule_cli(request: CHECK.TaskRescheduleRequest, phase: Literal["proposal", "prewrite"]) -> CHECK.TaskRescheduleResult:
    with tempfile.TemporaryDirectory() as directory:
        saved_input = Path(directory) / "native-request.json"
        saved_input.write_text(json.dumps(request))
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "--input", str(saved_input), "--phase", phase,
             "--as-of", AS_OF, "--note-prefix", PREFIX], capture_output=True, text=True, check=False,
        )
    if process.returncode not in (0, 1):
        raise AssertionError(process.stderr)
    result = json.loads(process.stdout)
    if process.returncode != (0 if result["status"] == "ready" else 1):
        raise AssertionError("CLI outcome and exit disagree")
    return result


class TaskRescheduleCheckTests(unittest.TestCase):
    def test_owner_change_stops_prewrite_even_without_a_changed_version(self):
        request = self.prewrite_request()
        request["task"]["OwnerId"] = "005000000000002"
        sync_related_task_fixture(request)
        result = evaluate_task_reschedule(request, "prewrite")
        self.assert_held(result, "stale")
        self.assertIn("OwnerId", " ".join(result["reasons"]))

    def test_missing_or_unreadable_native_owner_holds_proposal(self):
        for owner in (None, "", "owner", 5, "001000000000001"):
            with self.subTest(owner=owner):
                request = reschedule_request_fixture()
                request["task"]["OwnerId"] = owner
                sync_related_task_fixture(request)
                self.assert_held(evaluate_task_reschedule(request), "needs-input")
        request = reschedule_request_fixture()
        del request["task"]["OwnerId"]
        sync_related_task_fixture(request)
        self.assert_held(evaluate_task_reschedule(request), "needs-input")

    def test_owner_is_saved_but_never_added_to_the_write_payload(self):
        request = reschedule_request_fixture()
        result = evaluate_task_reschedule(request)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["baseline"]["OwnerId"], request["task"]["OwnerId"])
        self.assertNotIn("OwnerId", result["payload"])

    def test_related_queries_must_read_owner_and_groups_remain_native_owners(self):
        request = reschedule_request_fixture()
        request["related_opportunity_soql"] = request["related_opportunity_soql"].replace("OwnerId, ", "")
        self.assert_held(evaluate_task_reschedule(request), "needs-input")
        request = reschedule_request_fixture()
        request["task"]["OwnerId"] = "00G000000000001"
        sync_related_task_fixture(request)
        self.assertEqual(evaluate_task_reschedule(request)["status"], "ready")

    def test_unreviewed_future_related_task_does_not_hold_triage_date_preflight(self):
        request = reschedule_request_fixture()
        future_task = deepcopy(request["task"])
        future_task.update(Id=OTHER_TASK_ID, ActivityDate="2026-10-21", Subject="Later readout")
        request["related_opportunity"]["records"].append(future_task)
        request["related_opportunity"]["totalSize"] = 2
        proposal = run_task_reschedule_cli(request, "proposal")
        self.assertEqual(proposal["status"], "ready")
        request.update(baseline=proposal["baseline"], baseline_links=proposal["baseline_links"],
                       displayed_payload=proposal["payload"])
        future_task.update(ActivityDate="2026-10-28", LastModifiedDate="2026-10-07T17:00:00.000+0000")
        prewrite = run_task_reschedule_cli(request, "prewrite")
        self.assertEqual(prewrite["status"], "ready")
        self.assertEqual(prewrite["payload"], proposal["payload"])

    def prewrite_request(self) -> CHECK.TaskRescheduleRequest:
        request = reschedule_request_fixture()
        result = evaluate_task_reschedule(request)
        self.assertEqual(result["status"], "ready")
        request["baseline"] = result["baseline"]
        request["baseline_links"] = result["baseline_links"]
        request["displayed_payload"] = result["payload"]
        return request

    def assert_held(self, result: CHECK.TaskRescheduleResult, status: str) -> None:
        self.assertEqual(result["status"], status, result)
        self.assertNotIn("payload", result)

    def test_unchanged_native_prewrite_limits_fields_and_preserves_history(self):
        request = self.prewrite_request()
        result = evaluate_task_reschedule(request, "prewrite")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(set(result["payload"]), {"Id", "ActivityDate", "Description"})
        self.assertEqual(result["payload"]["Description"], request["note_line"] + "\n" + request["task"]["Description"])
        self.assertEqual(result["payload"], request["displayed_payload"])

    def test_null_and_empty_native_description_are_valid_distinct_baselines(self):
        for description in (None, ""):
            with self.subTest(description=description):
                request = reschedule_request_fixture()
                request["task"]["Description"] = description
                sync_related_task_fixture(request)
                result = evaluate_task_reschedule(request)
                self.assertEqual(result["status"], "ready")
                self.assertIs(result["baseline"]["Description"], description)
                self.assertEqual(result["payload"]["Description"], request["note_line"])
        request = reschedule_request_fixture()
        request["task"]["Description"] = None
        sync_related_task_fixture(request)
        proposal = evaluate_task_reschedule(request)
        request.update(baseline=proposal["baseline"], baseline_links=proposal["baseline_links"], displayed_payload=proposal["payload"])
        request["task"]["Description"] = ""
        sync_related_task_fixture(request)
        self.assert_held(evaluate_task_reschedule(request, "prewrite"), "stale")

    def test_completed_task_is_noop_with_empty_open_action_review(self):
        request = reschedule_request_fixture()
        request["task"].update(Status="Completed", IsClosed=True)
        request["current_action_task_ids"] = []
        sync_related_task_fixture(request)
        self.assert_held(evaluate_task_reschedule(request), "no-op")

    def test_verified_account_linked_replacement_is_noop(self):
        request = reschedule_request_fixture()
        replacement = native_task_fixture()
        replacement.update(Id=OTHER_TASK_ID, WhatId=ACCOUNT_ID)
        request["related_account"].update(records=[replacement], totalSize=1)
        request["current_action_task_ids"] = [OTHER_TASK_ID]
        self.assert_held(evaluate_task_reschedule(request), "no-op")

    def test_multiple_current_actions_are_ambiguous_not_same_date_equivalence(self):
        request = reschedule_request_fixture()
        other = native_task_fixture()
        other.update(Id=OTHER_TASK_ID, WhatId=ACCOUNT_ID)
        request["related_account"].update(records=[other], totalSize=1)
        request["current_action_task_ids"] = [TASK_ID, OTHER_TASK_ID]
        self.assert_held(evaluate_task_reschedule(request), "needs-input")
        request["current_action_task_ids"] = [TASK_ID]
        self.assertEqual(evaluate_task_reschedule(request)["status"], "ready")

    def test_already_desired_date_suppresses_note_even_after_version_change(self):
        request = self.prewrite_request()
        request["task"].update(ActivityDate=request["desired_date"], LastModifiedDate="2026-10-07T17:00:00+00:00")
        sync_related_task_fixture(request)
        self.assert_held(evaluate_task_reschedule(request, "prewrite"), "no-op")

    def test_each_native_baseline_change_is_stale(self):
        mutations = {
            "Status": "In Progress", "ActivityDate": "2026-10-08",
            "LastModifiedDate": "2026-10-07T17:00:00+00:00", "Description": "Another writer's note",
            "WhoId": "003000000000002", "WhatId": ACCOUNT_ID, "Subject": "Changed action",
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                request = self.prewrite_request()
                request["task"][field] = value
                sync_related_task_fixture(request)
                self.assert_held(evaluate_task_reschedule(request, "prewrite"), "stale")

    def test_missing_native_task_fields_fail_closed_even_with_model_flags(self):
        for field in CHECK.TASK_BASELINE_FIELDS + ("attributes",):
            with self.subTest(field=field):
                request = reschedule_request_fixture()
                del request["task"][field]
                request.update(fresh=True, approved=True)
                self.assert_held(evaluate_task_reschedule(request), "needs-input")

    def test_missing_baseline_or_displayed_payload_never_passes_prewrite(self):
        for field in ("baseline", "baseline_links", "displayed_payload"):
            request = self.prewrite_request()
            del request[field]
            self.assert_held(evaluate_task_reschedule(request, "prewrite"), "needs-input")

    def test_changed_verified_opportunity_account_linkage_is_stale(self):
        request = self.prewrite_request()
        request["account"]["Id"] = "001000000000002"
        request["opportunity"]["AccountId"] = request["account"]["Id"]
        request["related_account_soql"] = native_related_task_soql(request["account"]["Id"])
        self.assert_held(evaluate_task_reschedule(request, "prewrite"), "stale")

    def test_incomplete_or_unread_related_evidence_fails_closed(self):
        for scope in ("related_account", "related_opportunity"):
            for mutation in ("missing", "has_more", "count", "cursor", "version", "type"):
                with self.subTest(scope=scope, mutation=mutation):
                    request = reschedule_request_fixture()
                    if mutation == "missing":
                        del request[scope]
                    elif mutation == "has_more":
                        request[scope]["hasMore"] = True
                    elif mutation == "count":
                        request[scope]["totalSize"] += 1
                    elif mutation == "cursor":
                        request[scope]["nextRecordsUrl"] = "/more"
                    else:
                        record = native_task_fixture()
                        record.update(Id=OTHER_TASK_ID, WhatId=ACCOUNT_ID if scope == "related_account" else OPPORTUNITY_ID)
                        if mutation == "version":
                            del record["LastModifiedDate"]
                        else:
                            record["attributes"]["type"] = "Contact"
                        request[scope]["records"].append(record)
                        request[scope]["totalSize"] += 1
                    self.assert_held(evaluate_task_reschedule(request), "needs-input")

    def test_review_ids_must_bind_to_native_open_records(self):
        for ids in ([], [OTHER_TASK_ID], [TASK_ID, TASK_ID], ["00Tinvalid"]):
            request = reschedule_request_fixture()
            request["current_action_task_ids"] = ids
            self.assert_held(evaluate_task_reschedule(request), "needs-input")

    def test_native_linkage_and_exact_read_consistency_are_required(self):
        for mutation in ("account", "opportunity", "task_link", "task_copy", "duplicate", "wrong_type"):
            with self.subTest(mutation=mutation):
                request = reschedule_request_fixture()
                if mutation == "account":
                    request["account"]["Id"] = "001000000000002"
                elif mutation == "opportunity":
                    request["opportunity"]["AccountId"] = "001000000000002"
                elif mutation == "task_link":
                    request["task"]["WhatId"] = "006000000000002"
                elif mutation == "task_copy":
                    request["related_opportunity"]["records"][0]["Description"] = "Inconsistent reread"
                elif mutation == "duplicate":
                    request["related_opportunity"]["records"].append(deepcopy(request["task"]))
                    request["related_opportunity"]["totalSize"] = 2
                else:
                    request["account"]["attributes"]["type"] = "Contact"
                self.assert_held(evaluate_task_reschedule(request), "needs-input")

    def test_account_only_task_requires_explicit_opportunity_absence(self):
        request = reschedule_request_fixture()
        request["task"]["WhatId"] = ACCOUNT_ID
        request.update(opportunity=None, related_opportunity=None, related_opportunity_soql=None)
        sync_related_task_fixture(request)
        self.assertEqual(evaluate_task_reschedule(request)["status"], "ready")
        del request["related_opportunity"]
        self.assert_held(evaluate_task_reschedule(request), "needs-input")

    def test_native_hasmore_structure_retained_without_invented_done(self):
        request = reschedule_request_fixture()
        original = deepcopy(request)
        self.assertEqual(evaluate_task_reschedule(request)["status"], "ready")
        self.assertEqual(request, original)
        for scope in ("related_account", "related_opportunity"):
            self.assertEqual(set(request[scope]), {"totalSize", "records", "hasMore"})

    def test_missing_true_and_malformed_native_hasmore_fail_closed(self):
        for scope in ("related_account", "related_opportunity"):
            for value in ("missing", True, None, 0, "false", [], {}):
                with self.subTest(scope=scope, value=value):
                    request = reschedule_request_fixture()
                    if value == "missing":
                        del request[scope]["hasMore"]
                    else:
                        request[scope]["hasMore"] = value
                    request.update(reads_complete=True)
                    self.assert_held(evaluate_task_reschedule(request), "needs-input")

    def test_native_hasmore_false_cannot_override_paging_errors_or_done(self):
        for marker, value in (("nextRecordsUrl", "/more"), ("nextPageToken", "more"),
                              ("error", "query failed"), ("errors", []), ("done", True),
                              ("status", "failed"), ("has_more", True)):
            request = reschedule_request_fixture()
            request["related_account"][marker] = value
            self.assert_held(evaluate_task_reschedule(request), "needs-input")

    def test_related_task_query_input_must_be_uncapped_and_scope_bound(self):
        for scope in ("related_account_soql", "related_opportunity_soql"):
            for mutation in ("missing", "limit", "offset", "filter", "other_link", "fields"):
                with self.subTest(scope=scope, mutation=mutation):
                    request = reschedule_request_fixture()
                    if mutation == "missing":
                        del request[scope]
                    elif mutation == "limit":
                        request[scope] += " LIMIT 1"
                    elif mutation == "offset":
                        request[scope] += " OFFSET 1"
                    elif mutation == "filter":
                        request[scope] += " AND ActivityDate <= TODAY"
                    elif mutation == "other_link":
                        request[scope] = request[scope].replace("000000000001", "000000000002")
                    else:
                        request[scope] = request[scope].replace("LastModifiedDate, ", "")
                    self.assert_held(evaluate_task_reschedule(request), "needs-input")

    def test_related_query_supports_native_whitespace_predicate_order_and_orderby(self):
        request = reschedule_request_fixture()
        request["related_account_soql"] = native_related_task_soql(ACCOUNT_ID).replace(
            f"WhatId = '{ACCOUNT_ID}' AND IsClosed = false", f"IsClosed = false AND WhatId = '{ACCOUNT_ID}'") + " ORDER BY ActivityDate ASC NULLS FIRST"
        request["related_opportunity_soql"] = request["related_opportunity_soql"].replace(", ", ",\n")
        self.assertEqual(evaluate_task_reschedule(request)["status"], "ready")

    def test_related_query_native_id_case_must_match_even_when_keywords_do_not(self):
        request = reschedule_request_fixture()
        request["account"]["Id"] = "001000000000AbC"
        request["opportunity"]["AccountId"] = request["account"]["Id"]
        request["related_account_soql"] = native_related_task_soql(request["account"]["Id"])
        self.assertEqual(evaluate_task_reschedule(request)["status"], "ready")
        request["related_account_soql"] = request["related_account_soql"].replace("001000000000AbC", "001000000000abc")
        self.assert_held(evaluate_task_reschedule(request), "needs-input")

    def test_future_task_excluded_for_triage_but_not_deal_thread(self):
        request = reschedule_request_fixture()
        request["task"]["ActivityDate"] = "2026-10-08"
        sync_related_task_fixture(request)
        self.assert_held(evaluate_task_reschedule(request), "no-op")
        request["writer"] = "deal_thread"
        self.assertEqual(evaluate_task_reschedule(request)["status"], "ready")

    def test_undated_task_is_eligible(self):
        request = reschedule_request_fixture()
        request["task"]["ActivityDate"] = None
        sync_related_task_fixture(request)
        self.assertEqual(evaluate_task_reschedule(request)["status"], "ready")

    def test_bad_dates_timestamps_or_notes_fail_closed(self):
        for field, value in (("desired_date", "2026-02-30"), ("desired_date", "20261009"),
                             ("note_line", "10/6/26 SR - Wrong day"), ("note_line", "10/7/26 SR - first\nsecond"),
                             ("note_line", "10/7/26 SR - ")):
            request = reschedule_request_fixture()
            request[field] = value
            self.assert_held(evaluate_task_reschedule(request), "needs-input")
        request = reschedule_request_fixture()
        request["task"]["LastModifiedDate"] = "2026-10-07T02:00:00"
        self.assert_held(evaluate_task_reschedule(request), "needs-input")

    def test_altered_displayed_date_note_or_extra_field_requires_new_proposal(self):
        for mutation in ("date", "note", "history", "field", "id"):
            request = self.prewrite_request()
            if mutation == "date":
                request["desired_date"] = "2026-10-12"
            elif mutation == "note":
                request["note_line"] += " changed"
            elif mutation == "history":
                request["displayed_payload"]["Description"] = request["note_line"]
            elif mutation == "field":
                request["displayed_payload"]["Status"] = "Completed"
            else:
                request["baseline"]["Id"] = OTHER_TASK_ID
            self.assert_held(evaluate_task_reschedule(request, "prewrite"), "needs-input")

    def test_cli_reports_holds_and_rejects_unusable_json(self):
        request = reschedule_request_fixture()
        self.assertEqual(run_task_reschedule_cli(request, "proposal")["status"], "ready")
        del request["task"]["LastModifiedDate"]
        self.assert_held(run_task_reschedule_cli(request, "proposal"), "needs-input")
        with tempfile.TemporaryDirectory() as directory:
            saved = Path(directory) / "broken.json"
            saved.write_text("{")
            process = subprocess.run([sys.executable, str(SCRIPT), "--input", str(saved), "--phase", "proposal",
                                      "--as-of", AS_OF, "--note-prefix", PREFIX], capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)

    def test_documented_native_example_runs_with_null_description(self):
        interface = (ROOT / "_core/scripts/interfaces.md").read_text().split("## Task reschedule input", 1)[1]
        example = json.loads(interface.split("```json\n", 1)[1].split("```", 1)[0])
        proposal = run_task_reschedule_cli(example, "proposal")
        self.assertEqual(proposal["status"], "ready")
        self.assertIsNone(proposal["baseline"]["Description"])
        example.update(baseline=proposal["baseline"], baseline_links=proposal["baseline_links"], displayed_payload=proposal["payload"])
        self.assertEqual(run_task_reschedule_cli(example, "prewrite")["status"], "ready")


class SyntheticTaskStore:
    """Offline native reads and counted writes, deliberately without a lock."""

    def __init__(self) -> None:
        self.tasks = {TASK_ID: native_task_fixture()}
        self.account = reschedule_request_fixture()["account"]
        self.opportunity = reschedule_request_fixture()["opportunity"]
        self.opportunity.update(Next_Steps__c="Buyer confirms pilot review", StageName="Pilot")
        self.current_action_task_ids = [TASK_ID]
        self.write_calls: list[CHECK.TaskReschedulePayload] = []
        self.readback_corrupt = False
        self.delivery_calls: list[str] = []
        self.delivery_succeeds = True

    def deliver_evidence(self, command: str) -> bool:
        self.delivery_calls.append(command)
        return self.delivery_succeeds

    def collect_task_ids(self, writer: str) -> list[str]:
        return [task_id for task_id, task in self.tasks.items() if not task["IsClosed"] and
                (writer != "triage" or task["ActivityDate"] is None or task["ActivityDate"] <= AS_OF[:10])]

    def read_request(self, writer: str, desired_date: str) -> CHECK.TaskRescheduleRequest:
        request = reschedule_request_fixture()
        request.update(writer=writer, task=deepcopy(self.tasks[TASK_ID]), account=deepcopy(self.account),
                       opportunity=deepcopy(self.opportunity), desired_date=desired_date,
                       current_action_task_ids=list(self.current_action_task_ids))
        for scope, link_id in (("related_account", ACCOUNT_ID), ("related_opportunity", OPPORTUNITY_ID)):
            records = [deepcopy(task) for task in self.tasks.values() if not task["IsClosed"] and task["WhatId"] == link_id]
            request[scope] = {"records": records, "totalSize": len(records), "hasMore": False}
        return request

    def write_task(self, payload: CHECK.TaskReschedulePayload) -> None:
        if set(payload) != {"Id", "ActivityDate", "Description"}:
            raise AssertionError("unexpected substantive field")
        self.write_calls.append(deepcopy(payload))
        self.tasks[payload["Id"]].update(payload)
        self.tasks[payload["Id"]]["LastModifiedDate"] = f"2026-10-07T18:00:{len(self.write_calls):02d}+00:00"

    def readback_task(self, task_id: str) -> CHECK.NativeTaskSnapshot:
        task = deepcopy(self.tasks[task_id])
        if self.readback_corrupt:
            task["Description"] = "Unverified native result"
        return task


class SyntheticTaskWriter:
    """Drive the real CLI, with approval and readback outside its boundary."""

    def __init__(self, store: SyntheticTaskStore, writer: str) -> None:
        self.store = store
        self.writer = writer
        self.proposal: CHECK.TaskRescheduleRequest | None = None
        self.delivery_status = "delivered"

    def route_evidence(self) -> str:
        self.delivery_status = "failed"
        for command in ("mail_send",):
            if self.store.deliver_evidence(command):
                self.delivery_status = "delivered"
                break
        return self.delivery_status

    def propose(self, desired_date: str = "2026-10-09", note_line: str | None = None) -> CHECK.TaskRescheduleResult:
        request = self.store.read_request(self.writer, desired_date)
        if note_line is not None:
            request["note_line"] = note_line
        result = run_task_reschedule_cli(request, "proposal")
        if result["status"] == "ready":
            request.update(baseline=result["baseline"], baseline_links=result["baseline_links"], displayed_payload=result["payload"])
            self.proposal = deepcopy(request)
        return result

    def execute(self, approved_payload: CHECK.TaskReschedulePayload | None) -> str:
        if self.proposal is None or approved_payload != self.proposal["displayed_payload"]:
            return "not-approved"
        request = self.store.read_request(self.writer, self.proposal["desired_date"])
        for field in ("baseline", "baseline_links", "displayed_payload", "note_line"):
            request[field] = deepcopy(self.proposal[field])
        result = run_task_reschedule_cli(request, "prewrite")
        if result["status"] != "ready":
            return result["status"]
        self.store.write_task(result["payload"])
        readback = self.store.readback_task(TASK_ID)
        return "verified" if all(readback[field] == value for field, value in result["payload"].items()) else "pending"


class TaskRescheduleTwoWriterIntegrationTests(unittest.TestCase):
    def test_triage_first_then_deal_thread_same_date_second_writer_noop(self):
        self.assert_two_writer_order("triage", "deal_thread", "2026-10-09", "no-op")

    def test_deal_thread_first_then_triage_same_date_second_writer_noop(self):
        self.assert_two_writer_order("deal_thread", "triage", "2026-10-09", "no-op")

    def test_triage_first_then_deal_thread_different_date_second_writer_stale(self):
        self.assert_two_writer_order("triage", "deal_thread", "2026-10-12", "stale")

    def test_deal_thread_first_then_triage_different_date_second_writer_stale(self):
        self.assert_two_writer_order("deal_thread", "triage", "2026-10-12", "stale")

    def assert_two_writer_order(self, first_name: str, second_name: str, second_date: str, outcome: str) -> None:
        store = SyntheticTaskStore()
        original_history = store.tasks[TASK_ID]["Description"]
        original_deal = deepcopy(store.opportunity)
        self.assertIn(TASK_ID, store.collect_task_ids(first_name))
        self.assertIn(TASK_ID, store.collect_task_ids(second_name))
        first, second = SyntheticTaskWriter(store, first_name), SyntheticTaskWriter(store, second_name)
        first_proposal, second_proposal = first.propose(), second.propose(second_date)
        self.assertEqual(first.execute(first_proposal["payload"]), "verified")
        after_first = deepcopy(store.tasks[TASK_ID])
        calls_before_second = len(store.write_calls)
        self.assertEqual(second.execute(second_proposal["payload"]), outcome)
        self.assertEqual(len(store.write_calls) - calls_before_second, 0)
        self.assertEqual(len(store.write_calls), 1)
        self.assertEqual(store.tasks[TASK_ID], after_first)
        self.assertEqual(after_first["Description"], first.proposal["note_line"] + "\n" + original_history)
        self.assertEqual(store.opportunity, original_deal)
        self.assertNotIn(TASK_ID, store.collect_task_ids("triage"))

    def test_unchanged_approved_move_one_actual_date_note_write_for_each_writer(self):
        for writer_name in ("triage", "deal_thread"):
            with self.subTest(writer=writer_name):
                store = SyntheticTaskStore()
                writer = SyntheticTaskWriter(store, writer_name)
                proposal = writer.propose()
                self.assertEqual(writer.execute(proposal["payload"]), "verified")
                self.assertEqual(len(store.write_calls), 1)
                self.assertEqual(store.write_calls[0], proposal["payload"])
                self.assertEqual(store.readback_task(TASK_ID)["Description"], proposal["payload"]["Description"])

    def test_closed_replaced_already_desired_and_stale_make_zero_actual_calls(self):
        for writer_name in ("triage", "deal_thread"):
            for mutation, expected in (("completed", "no-op"), ("replaced", "no-op"), ("satisfied", "no-op"), ("stale", "stale")):
                with self.subTest(writer=writer_name, mutation=mutation):
                    store = SyntheticTaskStore()
                    writer = SyntheticTaskWriter(store, writer_name)
                    proposal = writer.propose()
                    if mutation == "completed":
                        store.tasks[TASK_ID].update(Status="Completed", IsClosed=True)
                        store.current_action_task_ids = []
                    elif mutation == "replaced":
                        replacement = native_task_fixture()
                        replacement.update(Id=OTHER_TASK_ID, WhatId=ACCOUNT_ID)
                        store.tasks[OTHER_TASK_ID] = replacement
                        store.current_action_task_ids = [OTHER_TASK_ID]
                    elif mutation == "satisfied":
                        store.tasks[TASK_ID]["ActivityDate"] = proposal["payload"]["ActivityDate"]
                    else:
                        store.tasks[TASK_ID]["Description"] = "Another writer preserved an action note"
                    self.assertEqual(writer.execute(proposal["payload"]), expected)
                    self.assertEqual(store.write_calls, [])

    def test_failed_handoff_leaves_deal_substance_unchanged_and_no_unapproved_write(self):
        store = SyntheticTaskStore()
        original_deal = deepcopy(store.opportunity)
        original_task = deepcopy(store.tasks[TASK_ID])
        writer = SyntheticTaskWriter(store, "triage")
        store.delivery_succeeds = False
        self.assertEqual(writer.route_evidence(), "failed")
        self.assertEqual(store.delivery_calls, ["mail_send"])
        proposal = writer.propose(note_line="10/7/26 SR - Buyer requested Friday review, routing failed, deal thread still owns next step")
        self.assertEqual(writer.execute(None), "not-approved")
        self.assertEqual(store.write_calls, [])
        self.assertEqual(store.tasks[TASK_ID], original_task)
        self.assertEqual(writer.delivery_status, "failed")
        self.assertEqual(writer.execute(proposal["payload"]), "verified")
        self.assertEqual(len(store.write_calls), 1)
        self.assertEqual(store.opportunity, original_deal)
        for field in ("Subject", "Status", "WhatId", "WhoId"):
            self.assertEqual(store.tasks[TASK_ID][field], original_task[field])

    def test_later_new_buyer_evidence_requires_new_proposal_not_same_day_freeze(self):
        store = SyntheticTaskStore()
        first = SyntheticTaskWriter(store, "triage")
        first_proposal = first.propose()
        self.assertEqual(first.execute(first_proposal["payload"]), "verified")
        later = SyntheticTaskWriter(store, "deal_thread")
        proposal = later.propose("2026-10-12", "10/7/26 SR - New buyer reply moved review to Monday")
        self.assertEqual(proposal["status"], "ready")
        self.assertEqual(later.execute(first_proposal["payload"]), "not-approved")
        self.assertEqual(len(store.write_calls), 1)
        self.assertEqual(later.execute(proposal["payload"]), "verified")
        self.assertEqual(len(store.write_calls), 2)
        self.assertTrue(store.tasks[TASK_ID]["Description"].endswith(first_proposal["payload"]["Description"]))

    def test_unverified_native_readback_stays_pending(self):
        store = SyntheticTaskStore()
        writer = SyntheticTaskWriter(store, "deal_thread")
        proposal = writer.propose()
        store.readback_corrupt = True
        self.assertEqual(writer.execute(proposal["payload"]), "pending")
        self.assertEqual(len(store.write_calls), 1)

    def test_two_final_reads_before_either_write_are_not_atomic_protection(self):
        store = SyntheticTaskStore()
        first = SyntheticTaskWriter(store, "triage")
        second = SyntheticTaskWriter(store, "deal_thread")
        first.propose()
        second.propose("2026-10-12")
        first_ready = run_task_reschedule_cli(first.proposal, "prewrite")
        second_ready = run_task_reschedule_cli(second.proposal, "prewrite")
        self.assertEqual(first_ready["status"], "ready")
        self.assertEqual(second_ready["status"], "ready")
        store.write_task(first_ready["payload"])
        store.write_task(second_ready["payload"])
        self.assertEqual(len(store.write_calls), 2)
        self.assertEqual(store.tasks[TASK_ID]["ActivityDate"], "2026-10-12")


if __name__ == "__main__":
    unittest.main()
