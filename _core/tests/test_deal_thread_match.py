"""Synthetic exact-name matching and fail-closed pagination checks, without live calls."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "workspaces/pipeline/scripts/deal_thread_match.py"
spec = importlib.util.spec_from_file_location("deal_thread_match", SCRIPT)
matcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matcher)


def session(identifier="thread-1", title="Acme Systems deal", **changes):
    return {"context_uuid": identifier, "title": title, "url": f"https://example.test/{identifier}",
            "status": "idle", "project": {"uuid": "project-1"}, **changes}


def listing(sessions=None, name="Acme Systems, LLC"):
    return {"pages": [{"offset": 0, "sessions": sessions if sessions is not None else [session()]}],
            "limit": 10, "project_uuid": "project-1", "accounts": [{"account_id": "account-1", "account_name": name}],
            "account_searches": {"account-1": []}}


def sanitized_listing():
    sessions = json.loads((ROOT / "_core/tests/fixtures/sanitized_sessions_page.json").read_text())
    return {"pages": [{"offset": 0, "sessions": sessions}], "limit": 10, "project_uuid": sessions[0]["project"]["uuid"],
            "accounts": [{"account_id": "account-1", "account_name": "Example Corp"},
                         {"account_id": "account-2", "account_name": "Sample Industries"}],
            "account_searches": {"account-1": {"sessions": [sessions[0]]}, "account-2": {"sessions": [sessions[2]]}}}


class DealThreadMatchTests(unittest.TestCase):
    def tool_response_listing(self):
        data = sanitized_listing()
        data["accounts"].append({"account_id": "missing", "account_name": "Missing Corp"})
        fixture = ROOT / "_core/tests/fixtures/sanitized_account_session_tool_response.json"
        data["account_searches"]["missing"] = json.loads(fixture.read_text())
        return data

    def test_session_list_tool_response_routes_exact_same_project_owner_without_mutation(self):
        data = self.tool_response_listing()
        original = copy.deepcopy(data)
        result = matcher.match_threads(data)
        self.assertEqual(result["status"], "complete", result["reasons"])
        self.assertEqual([row["status"] for row in result["accounts"]], ["owner", "owner", "owner"])
        self.assertEqual(result["accounts"][-1]["context_uuid"],
                         data["account_searches"]["missing"]["sessions"][0]["context_uuid"])
        self.assertEqual(data, original)

    def test_session_list_tool_response_ignores_other_project_null_project_and_near_miss(self):
        for index in (1, 2, 3):
            data = self.tool_response_listing()
            response = data["account_searches"]["missing"]
            response["sessions"] = [response["sessions"][index]]
            with self.subTest(index=index):
                self.assertEqual(matcher.match_threads(data)["accounts"][-1]["status"], "local")

    def test_session_list_tool_response_empty_and_at_limit_keep_existing_bounds(self):
        for count in (0, 99, 100):
            data = self.tool_response_listing()
            response = data["account_searches"]["missing"]
            response["sessions"] = [copy.deepcopy(response["sessions"][0]) for _ in range(count)]
            with self.subTest(count=count):
                row = matcher.match_threads(data)["accounts"][-1]
                self.assertEqual(row["status"], "local" if count == 0 else "owner" if count < 100 else "needs_input")

    def test_unknown_session_list_response_shapes_hold_only_affected_account(self):
        for response in ({}, {"data": []}, {"sessions": None}, {"sessions": {}},
                         {"sessions": [], "error": "failed"}, "[]", 0):
            data = self.tool_response_listing()
            data["account_searches"]["missing"] = response
            with self.subTest(response=response):
                result = matcher.match_threads(data)
                self.assertEqual(result["status"], "complete")
                self.assertEqual([row["status"] for row in result["accounts"]], ["owner", "owner", "needs_input"])

    def test_malformed_candidate_in_session_list_tool_response_cannot_establish_local(self):
        data = self.tool_response_listing()
        data["account_searches"]["missing"]["sessions"][0]["project"] = {}
        self.assertEqual(matcher.match_threads(data)["accounts"][-1]["status"], "needs_input")

    def test_short_82_row_project_page_alone_cannot_establish_owner_or_local(self):
        data = listing([session()] + [session(f"other-{index}", f"Other Account {index} deal") for index in range(81)])
        data["limit"] = 100
        data["accounts"].append({"account_id": "missing", "account_name": "Missing Corp"})
        del data["account_searches"]
        result = matcher.match_threads(data)
        self.assertEqual(result["status"], "complete", result["reasons"])
        self.assertEqual([row["status"] for row in result["accounts"]], ["needs_input", "needs_input"])
        self.assertTrue(all(row["reason"] == "account search required before ownership" for row in result["accounts"]))
        self.assertTrue(all("context_uuid" not in row for row in result["accounts"]))

    def test_search_for_listed_owner_reveals_second_thread_omitted_from_short_page(self):
        data = listing([session()] + [session(f"other-{index}", f"Other Account {index} deal") for index in range(81)])
        data["limit"] = 100
        data["account_searches"]["account-1"] = {"sessions": [
            session(type="computer"), session("omitted-thread", "Acme Systems Inc deal", type="computer")]}
        original = copy.deepcopy(data)
        row = self.row(data)
        self.assertEqual(row["status"], "needs_input")
        self.assertEqual(row["reason"], "ambiguous deal threads")
        self.assertEqual([candidate["context_uuid"] for candidate in row["candidates"]], ["omitted-thread", "thread-1"])
        self.assertEqual(data, original)

    def test_search_gaps_hold_listed_owner_without_invalidating_other_verified_owner(self):
        for response in (None, {"error": "failed"}, {"sessions": None},
                         {"sessions": [session(type="computer")] * 100}):
            data = sanitized_listing()
            data["account_searches"]["account-1"] = response
            with self.subTest(response=response):
                result = matcher.match_threads(data)
                self.assertEqual([row["status"] for row in result["accounts"]], ["needs_input", "owner"])
                self.assertNotIn("context_uuid", result["accounts"][0])

    def test_missing_search_holds_listed_owner_without_invalidating_other_verified_owner(self):
        data = sanitized_listing()
        del data["account_searches"]["account-1"]
        result = matcher.match_threads(data)
        self.assertEqual([row["status"] for row in result["accounts"]], ["needs_input", "owner"])
        self.assertEqual(result["accounts"][0]["reason"], "account search required before ownership")

    def fallback_listing(self):
        data = sanitized_listing()
        data["accounts"].append({"account_id": "missing", "account_name": "Missing Corp"})
        data["account_searches"]["missing"] = json.loads((ROOT / "_core/tests/fixtures/sanitized_account_session_search.json").read_text())
        return data

    def test_saved_search_finds_thread_omitted_from_complete_project_listing(self):
        data = self.fallback_listing()
        original = copy.deepcopy(data)
        result = matcher.match_threads(data)
        self.assertEqual(result["status"], "complete", result["reasons"])
        self.assertEqual([row["status"] for row in result["accounts"]], ["owner", "owner", "owner"])
        found = result["accounts"][-1]
        self.assertEqual(found["context_uuid"], data["account_searches"]["missing"][0]["context_uuid"])
        self.assertEqual(found["url"], "https://www.perplexity.ai" + data["account_searches"]["missing"][0]["url"])
        self.assertEqual(data, original)

    def test_wrong_project_and_near_miss_search_titles_are_not_candidates(self):
        for index in (1, 2):
            data = self.fallback_listing()
            data["account_searches"]["missing"] = [data["account_searches"]["missing"][index]]
            with self.subTest(index=index):
                result = matcher.match_threads(data)
                self.assertEqual(result["status"], "complete")
                self.assertEqual(result["accounts"][-1]["status"], "local")
        data["account_searches"]["missing"] = []
        self.assertEqual(matcher.match_threads(data)["accounts"][-1]["status"], "local")

    def test_missing_failed_malformed_search_holds_only_affected_account(self):
        for search in ("missing", None, {"error": "failed"}):
            data = self.fallback_listing()
            if search == "missing":
                del data["account_searches"]["missing"]
            else:
                data["account_searches"]["missing"] = search
            with self.subTest(search=search):
                result = matcher.match_threads(data)
                self.assertEqual(result["status"], "complete")
                self.assertEqual(result["reasons"], [])
                self.assertEqual([row["status"] for row in result["accounts"]], ["owner", "owner", "needs_input"])
                self.assertNotIn("url", result["accounts"][-1])
        data = self.fallback_listing()
        del data["account_searches"]
        self.assertEqual([row["status"] for row in matcher.match_threads(data)["accounts"]], ["needs_input"] * 3)
        for searches in (None, []):
            data["account_searches"] = searches
            self.assertEqual([row["status"] for row in matcher.match_threads(data)["accounts"]], ["needs_input"] * 3)

    def test_malformed_search_rows_and_urls_cannot_establish_local(self):
        for field, value in (("context_uuid", None), ("title", "Missing\nCorp deal"), ("status", None),
                             ("type", "other"), ("project", {}), ("url", "/computer/tasks/id?query=1")):
            data = self.fallback_listing()
            data["account_searches"]["missing"][0][field] = value
            with self.subTest(field=field):
                result = matcher.match_threads(data)
                self.assertEqual(result["status"], "complete")
                self.assertEqual(result["accounts"][-1]["status"], "needs_input")

    def test_null_project_search_session_does_not_hold_same_project_owner(self):
        data = self.fallback_listing()
        data["account_searches"]["missing"] = [data["account_searches"]["missing"][3], data["account_searches"]["missing"][0]]
        result = matcher.match_threads(data)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["accounts"][-1]["status"], "owner")
        self.assertEqual(result["accounts"][-1]["context_uuid"], data["account_searches"]["missing"][1]["context_uuid"])

    def test_null_project_search_session_with_no_match_establishes_local(self):
        data = self.fallback_listing()
        data["account_searches"]["missing"] = [data["account_searches"]["missing"][3]]
        result = matcher.match_threads(data)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["accounts"][-1]["status"], "local")

    def test_unrelated_malformed_search_row_is_ignored(self):
        data = self.fallback_listing()
        data["account_searches"]["missing"] = [{"title": "Missing Corp deal follow-up notes", "project": [],
                                                "url": "/invalid", "status": None, "type": "other"},
                                               {"title": "Other Account deal\nnotes"}]
        result = matcher.match_threads(data)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["accounts"][-1]["status"], "local")

    def test_unknown_search_rows_hold_only_the_account(self):
        """A row with no readable title is unknown, not negative evidence for local ownership."""
        for row in (None, {}, {"title": 123}, {"title": None}, {"error": "failed"}, "Missing Corp deal", []):
            data = self.fallback_listing()
            data["account_searches"]["missing"] = [row]
            original = copy.deepcopy(data)
            with self.subTest(row=row):
                result = matcher.match_threads(data)
                self.assertEqual(result["status"], "complete")
                self.assertEqual([entry["status"] for entry in result["accounts"]], ["owner", "owner", "needs_input"])
                self.assertEqual(result["accounts"][-1]["reason"], "account search session 0 has an unknown title or row")
                self.assertNotIn("context_uuid", result["accounts"][-1])
                self.assertEqual(data, original)

    def test_malformed_candidate_search_title_is_held_not_matched(self):
        """A CR/LF title that would match after a global strip holds the Account instead of becoming its owner."""
        for title in ("Missing\nCorp deal", "Missing Corp deal\r\n", "Missing\r\nCorp\ndeal"):
            data = self.fallback_listing()
            data["account_searches"]["missing"] = [dict(data["account_searches"]["missing"][0], title=title)]
            original = copy.deepcopy(data)
            with self.subTest(title=title):
                result = matcher.match_threads(data)
                self.assertEqual(result["status"], "complete")
                self.assertEqual([entry["status"] for entry in result["accounts"]], ["owner", "owner", "needs_input"])
                self.assertEqual(result["accounts"][-1]["reason"], "account search session 0 has a malformed candidate title")
                self.assertNotIn("context_uuid", result["accounts"][-1])
                self.assertEqual(data, original)

    def test_malformed_candidate_title_search_rows_hold_only_the_account(self):
        for field, value in (("project", []), ("url", "/invalid"), ("context_uuid", None)):
            data = self.fallback_listing()
            data["account_searches"]["missing"][0][field] = value
            with self.subTest(field=field):
                result = matcher.match_threads(data)
                self.assertEqual(result["status"], "complete")
                self.assertEqual([row["status"] for row in result["accounts"]], ["owner", "owner", "needs_input"])

    def test_at_limit_search_holds_even_with_candidate_and_short_search_can_route(self):
        for count in (99, 100, 101):
            data = self.fallback_listing()
            data["account_searches"]["missing"] = [copy.deepcopy(data["account_searches"]["missing"][0]) for index in range(count)]
            with self.subTest(count=count):
                result = matcher.match_threads(data)
                self.assertEqual(result["status"], "complete")
                self.assertEqual(result["accounts"][-1]["status"], "owner" if count < 100 else "needs_input")

    def test_candidates_merge_and_dedupe_across_listing_and_search(self):
        data = self.fallback_listing()
        candidate = copy.deepcopy(data["account_searches"]["missing"][0])
        data["pages"][0]["sessions"].append(candidate)
        self.assertEqual(matcher.match_threads(data)["accounts"][-1]["status"], "owner")
        duplicate = copy.deepcopy(candidate)
        data["account_searches"]["missing"].append(duplicate)
        self.assertEqual(matcher.match_threads(data)["accounts"][-1]["status"], "owner")
        distinct = copy.deepcopy(candidate)
        distinct["context_uuid"] = "different-thread"
        distinct["url"] = "/computer/tasks/different-thread"
        data["account_searches"]["missing"].append(distinct)
        found = matcher.match_threads(data)["accounts"][-1]
        self.assertEqual(found["status"], "needs_input")
        self.assertEqual(found["reason"], "ambiguous deal threads")
        self.assertEqual(len(found["candidates"]), 2)

    def test_account_collision_from_search_holds_each_account(self):
        data = self.fallback_listing()
        data["accounts"].append({"account_id": "collision", "account_name": "Missing LLC"})
        data["account_searches"]["collision"] = {"sessions": []}
        result = matcher.match_threads(data)
        for row in result["accounts"][-2:]:
            self.assertEqual(row["status"], "needs_input")
            self.assertEqual(row["reason"], "multiple Accounts share this normalized name")
            self.assertEqual(len(row["candidates"]), 1)

    def test_callers_require_saved_bounded_search_for_every_account_before_ownership(self):
        interface = (ROOT / "_core/scripts/interfaces.md").read_text()
        self.assertIn("## Account session search", interface)
        self.assertIn("account_searches", interface)
        self.assertIn("at-limit (100+)", interface)
        self.assertIn('For every Account, call the `session_list` tool', interface)
        self.assertIn('with type `computer`, search `"<account_name> deal"` and limit `100`', interface)
        self.assertIn('The response is `{"sessions": [...]}`', interface)
        self.assertIn("Unknown response shapes hold that Account", interface)
        self.assertIn("Search even listed owners", interface)
        self.assertIn("A short project page proves neither absence nor uniqueness", interface)
        for workflow in ("pipeline-review", "task-triage-speed-run"):
            path = ROOT / "workspaces/pipeline/workflows" / workflow
            contract = (path / "CONTEXT.md").read_text()
            collect = (path / "references/collect.md").read_text()
            with self.subTest(workflow=workflow):
                self.assertIn('"Account session search"', contract)
                self.assertIn("Account session searches in the sandbox", contract)
                self.assertIn('call `session_list` with type `computer`, search `"<account_name> deal"` and limit `100`', collect)
                self.assertIn("For every Account, including listed matches", collect)
                self.assertIn("A listing alone never proves absence or uniqueness", collect)
                self.assertIn("null on failure", collect)
                self.assertIn("before routing or proposals", collect)
                self.assertLessEqual(len(contract.splitlines()), 80)

    def test_sanitized_cli_page_is_complete_with_absolute_links_and_unchanged_input(self):
        data = sanitized_listing()
        original = copy.deepcopy(data)
        result = matcher.match_threads(data)
        self.assertEqual(result["status"], "complete", result["reasons"])
        self.assertEqual(result["reasons"], [])
        self.assertEqual([row["status"] for row in result["accounts"]], ["owner", "owner"])
        for row, index in zip(result["accounts"], (0, 2)):
            self.assertEqual(row["url"], "https://www.perplexity.ai" + original["pages"][0]["sessions"][index]["url"])
            self.assertEqual(row["context_uuid"], original["pages"][0]["sessions"][index]["context_uuid"])
        self.assertEqual(data, original)

    def test_changed_cli_url_shapes_fail_closed_for_deal_and_non_deal_sessions(self):
        for index in (0, 1):
            for url in ("/computer/tasks", "/computer/tasks/", "/computer/tasks/id/extra", "/computer/tasks/id/",
                        "/computer/tasks/id?query=1", "/computer/tasks/id#fragment", "/computer/tasks/../id",
                        "/computer/tasks/%2Fid", "/other/tasks/id", "//example.test/computer/tasks/id",
                        "/computer/tasks/id with spaces", "/computer/tasks/id\n", "/computer/tasks/id\\extra",
                        "https://", "https:///computer/tasks/id", "https://example.test:bad/id", "http://example.test/id"):
                with self.subTest(index=index, url=url):
                    data = sanitized_listing()
                    data["pages"][0]["sessions"][index]["url"] = url
                    original = copy.deepcopy(data)
                    result = matcher.match_threads(data)
                    self.assertEqual(result["status"], "incomplete")
                    self.assertTrue(result["reasons"])
                    for row in result["accounts"]:
                        self.assertEqual(row["status"], "needs_input")
                        self.assertNotIn("url", row)
                        self.assertNotIn("context_uuid", row)
                    self.assertEqual(data, original)

    def test_relative_urls_are_absolute_in_ambiguous_candidates(self):
        data = sanitized_listing()
        data["accounts"][1]["account_name"] = "Example LLC"
        result = matcher.match_threads(data)
        self.assertEqual(result["status"], "complete")
        for row in result["accounts"]:
            self.assertEqual(row["status"], "needs_input")
            self.assertEqual(row["reason"], "multiple Accounts share this normalized name")
            self.assertEqual(row["candidates"][0]["url"], "https://www.perplexity.ai" + data["pages"][0]["sessions"][0]["url"])

    def row(self, data):
        result = matcher.match_threads(data)
        self.assertEqual(result["status"], "complete", result["reasons"])
        return result["accounts"][0]

    def incomplete(self, data):
        data["accounts"].append({"account_id": "account-2", "account_name": "Other Devices"})
        result = matcher.match_threads(data)
        self.assertEqual(result["status"], "incomplete")
        self.assertTrue(result["reasons"])
        self.assertEqual([row["status"] for row in result["accounts"]], ["needs_input", "needs_input"])
        for row in result["accounts"]:
            self.assertNotIn("context_uuid", row)
            self.assertNotIn("url", row)

    def test_legal_suffix_matches_for_systems_law_and_short_name(self):
        for name, title in (("Acme Systems, LLC", "Acme Systems deal"),
                            ("Finch & Wren LLP", "Finch & Wren deal"), ("ZX Inc.", "ZX deal")):
            with self.subTest(name=name):
                row = self.row(listing([session(title=title)], name))
                self.assertEqual(row["status"], "owner")
                self.assertEqual(row["context_uuid"], "thread-1")
                self.assertEqual(row["url"], "https://example.test/thread-1")

    def test_exact_food_service_name_matches(self):
        self.assertEqual(self.row(listing([session(title="Corvid Food Service deal")], "Corvid Food Service"))["status"], "owner")

    def test_all_fixed_suffixes_strip_repeatedly_on_both_sides(self):
        for suffix in matcher.LEGAL_SUFFIXES:
            with self.subTest(suffix=suffix):
                data = listing([session(title=f"Acme Systems {suffix.upper()}. Ltd DEAL")], f"Acme Systems, LLC {suffix}")
                self.assertEqual(self.row(data)["status"], "owner")

    def test_punctuation_casefold_and_whitespace(self):
        data = listing([session(title="  STRASSE–Systems, LLC dEaL  ")], "Straße  Systems")
        self.assertEqual(self.row(data)["status"], "owner")
        self.assertEqual(self.row(listing([session(title="Acme+Systems deal")]))["status"], "owner")

    def test_ampersand_is_preserved_not_equated_to_and_or_space(self):
        for name in ("Finch and Wren", "Finch Wren"):
            with self.subTest(name=name):
                self.assertEqual(self.row(listing([session(title="Finch & Wren deal")], name))["status"], "local")

    def test_legal_suffix_inside_name_is_not_stripped(self):
        self.assertEqual(self.row(listing([session(title="Acme Systems deal")], "Acme LLC Systems"))["status"], "local")

    def test_zero_matches_is_local_only_with_complete_listing_and_saved_negative_search(self):
        self.assertEqual(self.row(listing([]))["status"], "local")
        data = listing([])
        del data["account_searches"]
        self.assertEqual(self.row(data)["status"], "needs_input")

    def test_near_misses_do_not_match_prefix_substring_or_fuzzy_names(self):
        for title in ("Acme Health deal", "AcmeSystems deal", "The Acme deal", "Acne deal"):
            with self.subTest(title=title):
                self.assertEqual(self.row(listing([session(title=title)], "Acme"))["status"], "local")

    def test_only_trailing_space_deal_titles_are_candidates(self):
        for title in ("Acme Systems", "Acme Systems deals", "Acme Systems deal notes", "Acme Systems-deal"):
            with self.subTest(title=title):
                self.assertEqual(self.row(listing([session(title=title)]))["status"], "local")

    def test_ambiguous_matches_list_candidates_in_stable_order(self):
        data = listing([session("thread-2", "Acme Systems Inc deal"), session()])
        row = self.row(data)
        self.assertEqual(row["status"], "needs_input")
        self.assertEqual([candidate["context_uuid"] for candidate in row["candidates"]], ["thread-1", "thread-2"])
        self.assertNotIn("context_uuid", row)
        data["pages"][0]["sessions"].reverse()
        self.assertEqual(self.row(data), row)

    def test_full_pages_with_empty_or_short_final_page(self):
        for last in ([], [session("thread-3", "Other Devices deal")]):
            with self.subTest(last=last):
                data = listing()
                data["limit"] = 2
                data["pages"] = [{"offset": 0, "sessions": [session(), session("thread-2", "Other Name")]},
                                 {"offset": 2, "sessions": last}]
                self.assertEqual(self.row(data)["status"], "owner")

    def test_gap_nonzero_start_reordered_and_missing_offsets_are_incomplete(self):
        for offsets in ([0, 4], [2, 4], [2, 0], [0, 0], [0, None], [False, 2], [0.0, 2]):
            with self.subTest(offsets=offsets):
                data = listing()
                data["limit"] = 2
                data["pages"] = [{"offset": offsets[0], "sessions": [session(), session("thread-2", "Other Name")]},
                                 {"offset": offsets[1], "sessions": []}]
                self.incomplete(data)

    def test_non_short_final_page_is_incomplete(self):
        data = listing()
        data["limit"] = 1
        self.incomplete(data)

    def test_short_or_oversized_intermediate_page_is_incomplete(self):
        for count in (0, 1, 3):
            with self.subTest(count=count):
                data = listing()
                data["limit"] = 2
                data["pages"] = [{"offset": 0, "sessions": [session(f"thread-{index}") for index in range(count)]},
                                 {"offset": 2, "sessions": []}]
                self.incomplete(data)

    def test_project_mismatch_on_noncandidate_is_incomplete(self):
        self.incomplete(listing([session(), session("thread-2", "Unrelated", project={"uuid": "other-project"})]))

    def test_duplicates_across_pages_are_incomplete(self):
        data = listing()
        data["limit"] = 2
        data["pages"] = [{"offset": 0, "sessions": [session(), session("thread-2", "Other Name")]},
                         {"offset": 2, "sessions": [session()]}]
        self.incomplete(data)

    def test_missing_or_invalid_listing_fields_are_incomplete(self):
        for field, values in (("pages", (None, [], {}, [[]], [{"offset": 0, "sessions": {}}])),
                              ("limit", (None, 0, -1, True, 1.5)), ("project_uuid", (None, "", []))):
            for value in values:
                with self.subTest(field=field, value=value):
                    data = listing()
                    data[field] = value
                    self.incomplete(data)

    def test_missing_or_invalid_session_fields_hold_every_account(self):
        for field in ("context_uuid", "title", "url", "status", "project"):
            with self.subTest(field=field):
                row = session()
                del row[field]
                self.incomplete(listing([row]))
        for row in (None, [], session(url="http://example.test/thread"), session(context_uuid=[]), session(title=None)):
            with self.subTest(row=row):
                self.incomplete(listing([row]))

    def test_malformed_listing_title_holds_only_its_account(self):
        """A CR/LF listing title for one Account holds that Account. Other verified owners and the listing stay complete."""
        malformed = session("thread-2", "Other\nDevices deal")
        data = listing([session(), malformed])
        data["accounts"].append({"account_id": "account-2", "account_name": "Other Devices"})
        data["account_searches"]["account-2"] = []
        original = copy.deepcopy(data)
        result = matcher.match_threads(data)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["reasons"], [])
        self.assertEqual([row["status"] for row in result["accounts"]], ["owner", "needs_input"])
        self.assertEqual(result["accounts"][0]["context_uuid"], "thread-1")
        self.assertEqual(result["accounts"][1]["reason"], "malformed deal thread title in project listing")
        self.assertNotIn("context_uuid", result["accounts"][1])
        self.assertEqual(data, original)
        # Stripping the line break by hand would have made thread-2 the owner. The helper never does that.
        data["account_searches"]["account-2"] = [dict(malformed, type="computer")]
        result = matcher.match_threads(data)
        self.assertEqual(result["accounts"][1]["status"], "needs_input")
        self.assertNotIn("context_uuid", result["accounts"][1])

    def test_unrelated_malformed_listing_title_does_not_hold_anyone(self):
        data = listing([session(), session("thread-2", "Unrelated\nAccount deal"), session("thread-3", "Notes\nonly")])
        data["accounts"].append({"account_id": "account-2", "account_name": "Other Devices"})
        data["account_searches"]["account-2"] = []
        result = matcher.match_threads(data)
        self.assertEqual(result["status"], "complete")
        self.assertEqual([row["status"] for row in result["accounts"]], ["owner", "local"])

    def test_duplicate_uuid_and_project_mismatch_still_hold_every_account(self):
        self.incomplete(listing([session(), session(title="Other Devices deal")]))
        self.incomplete(listing([session(project={"uuid": "project-2"})]))

    def test_multiple_accounts_preserve_order_and_raw_inputs(self):
        data = listing()
        data["accounts"].append({"account_id": "account-2", "account_name": "Other Devices"})
        data["account_searches"]["account-2"] = []
        original = copy.deepcopy(data)
        result = matcher.match_threads(data)
        self.assertEqual([row["status"] for row in result["accounts"]], ["owner", "local"])
        self.assertEqual(data, original)

    def test_llc_inc_account_collision_holds_each_account_with_candidates(self):
        for sessions in ([session()], [session("thread-2", "Acme Systems Inc deal"), session()]):
            with self.subTest(sessions=sessions):
                data = listing(sessions)
                data["accounts"].append({"account_id": "account-2", "account_name": "Acme Systems Inc."})
                data["account_searches"]["account-2"] = []
                original = copy.deepcopy(data)
                result = matcher.match_threads(data)
                self.assertEqual(result["status"], "complete")
                self.assertEqual(result["reasons"], [])
                self.assertEqual([row["account_id"] for row in result["accounts"]], ["account-1", "account-2"])
                for row in result["accounts"]:
                    self.assertEqual(row["status"], "needs_input")
                    self.assertEqual(row["reason"], "multiple Accounts share this normalized name")
                    self.assertEqual([candidate["context_uuid"] for candidate in row["candidates"]],
                                     sorted(session["context_uuid"] for session in sessions))
                    self.assertNotIn("context_uuid", row)
                    self.assertNotIn("url", row)
                self.assertEqual(data, original)

    def test_account_collision_with_no_matching_thread_stays_local(self):
        for sessions in ([], [session(title="Other Devices deal")]):
            with self.subTest(sessions=sessions):
                data = listing(sessions)
                data["accounts"].append({"account_id": "account-2", "account_name": "Acme Systems Inc."})
                data["account_searches"]["account-2"] = []
                result = matcher.match_threads(data)
                self.assertEqual(result["status"], "complete")
                self.assertEqual([row["status"] for row in result["accounts"]], ["local", "local"])
                self.assertTrue(all("candidates" not in row for row in result["accounts"]))

    def test_single_account_still_gets_exact_owner_record(self):
        self.assertEqual(self.row(listing()), {"account_id": "account-1", "account_name": "Acme Systems, LLC",
                                              "status": "owner", "context_uuid": "thread-1",
                                              "url": "https://example.test/thread-1"})

    def test_empty_normalized_name_is_needs_input(self):
        self.assertEqual(self.row(listing(name=" LLC, Inc."))["status"], "needs_input")

    def test_bad_account_input_is_unusable_not_local(self):
        for data in ([], {}, listing(name=""), {**listing(), "accounts": [None]},
                     {**listing(), "accounts": [listing()["accounts"][0]] * 2}):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    matcher.match_threads(data)

    def test_cli_stdlib_only_complete_incomplete_and_bad_input(self):
        help_result = subprocess.run([sys.executable, "-S", str(SCRIPT), "--help"], text=True, capture_output=True)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            command = [sys.executable, "-S", str(SCRIPT), "--input", str(path)]
            for data, status in ((listing(), "complete"), ({**listing(), "pages": []}, "incomplete")):
                path.write_text(json.dumps(data))
                result = subprocess.run(command, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], status)
            for contents in ("{}", "{not json"):
                path.write_text(contents)
                result = subprocess.run(command, text=True, capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
            path.unlink()
            self.assertEqual(subprocess.run(command, text=True, capture_output=True).returncode, 2)

    def test_registry_catalog_and_bounded_contract_wiring(self):
        policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        self.assertEqual(policy["tooling"]["scripts"]["deal_thread_match"], str(SCRIPT.relative_to(ROOT)))
        self.assertIn("`deal_thread_match`", (ROOT / "_core/scripts/CONTEXT.md").read_text())
        for workflow in ("pipeline-review", "task-triage-speed-run"):
            path = ROOT / "workspaces/pipeline/workflows" / workflow
            self.assertIn("`deal_thread_match`", (path / "CONTEXT.md").read_text())
            collect = (path / "references/collect.md").read_text()
            self.assertIn("--limit <L> --offset <O>", collect)
            self.assertIn("`offset` and `sessions`", collect)
            self.assertIn("`needs_input` or `incomplete` holds proposals", collect)
            self.assertNotIn("sessions list --search", collect)


class TrademarkNormalizationTests(unittest.TestCase):
    def test_all_four_symbols_are_removed_from_account_and_thread_names(self):
        for symbol in "®™©℠":
            with self.subTest(symbol=symbol):
                data = listing([session(title=f"Acme{symbol} Systems deal")], name=f"Acme Systems{symbol}, LLC")
                self.assertEqual(matcher.match_threads(data)["accounts"][0]["status"], "owner")
                self.assertEqual(matcher.normalize(f"Ac{symbol}me Systems"), "acme systems")

    def test_symbols_are_removed_in_account_search_fallback_too(self):
        data = listing([], name="Acme Systems®")
        data["account_searches"]["account-1"] = [session(title="Acme™ Systems deal", type="computer")]
        self.assertEqual(matcher.match_threads(data)["accounts"][0]["status"], "owner")

    def test_symbol_stripping_preserves_account_collision_holds(self):
        data = listing()
        data["accounts"].append({"account_id": "account-2", "account_name": "Acme Systems®"})
        self.assertEqual([row["status"] for row in matcher.match_threads(data)["accounts"]], ["needs_input", "needs_input"])

    def test_symbols_do_not_enable_parent_or_partial_name_matching(self):
        data = listing([session(title="Acme Systems deal")], name="Acme Systems® - Product Security")
        self.assertEqual(matcher.match_threads(data)["accounts"][0]["status"], "local")


if __name__ == "__main__":
    unittest.main()
