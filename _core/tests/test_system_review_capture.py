"""Check invoking-thread capture and the Friday review's bounded handoff."""
import re
import unittest
from datetime import date

import yaml

from test_icm_contracts import headings, sections, table_rows
from test_skill_contracts import CONTRACT_PATHS, ROOT, WORKSPACES, frontmatter, inputs_rows, loaded_contract_text

REVIEW = CONTRACT_PATHS["system-review"].parent
CAPTURE = CONTRACT_PATHS["process-capture"].parent
CAPTURES = WORKSPACES / "systems" / "captures"
CAPTURE_LABELS = ("Task", "Owner", "Status", "Reasons", "Decisions", "Second case", "Open questions", "Evidence")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


THREAD_LINK = re.compile(
    r"https://www\.perplexity\.ai/(?:computer/tasks/[^/?#\s]+|teammate/[^/?#\s]+/[^/?#\s]+)"
)


def capture_applied_location_exists(line):
    """Resolve named files and sections in the checkout, not historical intent."""
    match = re.fullmatch(r"\s*Applied in:\s*`([^`]+)`(.*)", line)
    if not match:
        return False
    reference, tail = match.groups()
    if reference.startswith("rules#"):
        reference = "_core/rules.md#" + reference.split("#", 1)[1]
    path, separator, fragment = reference.partition("#")
    target = (ROOT / path).resolve()
    if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
        return False
    if separator:
        if not fragment:
            return False
        source = target.read_text()
        if target.suffix in {".yaml", ".yml"}:
            value = yaml.safe_load(source)
            for key in fragment.split("."):
                if not isinstance(value, dict) or key not in value:
                    return False
                value = value[key]
        else:
            named_headings = headings(target)
            anchors = set(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)["\']', source))
            heading_anchors = {re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-") for heading in named_headings}
            if fragment not in anchors | named_headings | heading_anchors:
                return False
    quoted_heading = re.match(r'\s*"([^"\n]+)"', tail)
    if quoted_heading and quoted_heading.group(1) not in headings(target):
        return False
    return True


def capture_evidence_links_valid(lines):
    """Check approved thread-link shapes only, never authenticity or faithfulness."""
    if not lines:
        return False
    for line in lines:
        links = re.findall(r"https?://[^\s<>()]+", line)
        if not links or any(not THREAD_LINK.fullmatch(link) for link in links):
            return False
    return True


def capture_file_problems(name, text):
    """Return format problems only. Rule fidelity stays with Systems review."""
    problems = []
    if not re.fullmatch(r"[a-z0-9-]+\.md", name):
        problems.append("name")
    lines = text.splitlines()
    starts = [next((i for i, line in enumerate(lines) if re.match(r"`?" + label + r"`?:", line)), None) for label in CAPTURE_LABELS]
    if None in starts or starts != sorted(starts):
        return problems + ["labels"]
    status = lines[starts[2]].split(":", 1)[1].strip().strip("`")
    status_word = status.split()[0].strip("`,") if status else ""
    if status_word not in {"confirmed", "applied", "retired"}:
        problems.append("status")
    status_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", status)
    try:
        date.fromisoformat(status_date.group() if status_date else "")
    except ValueError:
        problems.append("ISO date")
    if status_word == "applied":
        if "/pull/" not in status and "/commit/" not in status:
            problems.append("applied PR link")
        applied_locations = [line for line in lines if re.match(r"\s*Applied in:", line)]
        if not applied_locations or not all(capture_applied_location_exists(line) for line in applied_locations):
            problems.append("applied location")
    evidence = [line for line in lines[starts[7] + 1:] if line.strip()]
    if not capture_evidence_links_valid(evidence):
        problems.append("evidence links")
    if EMAIL.search(text):
        problems.append("email address")
    return problems


class SystemReviewCaptureTests(unittest.TestCase):
    def test_capture_conversation_and_evidence_stay_in_the_invoking_thread(self):
        contract = (CAPTURE / "CONTEXT.md").read_text()
        reference = (CAPTURE / "references/capture.md").read_text()
        location = "the thread where Operator invokes capture"
        self.assertIn(location, frontmatter(contract)["reads"])
        request = next(row for row in inputs_rows(contract) if row[0] == "Operator's request")
        self.assertEqual(request[1], location)
        _, outputs = table_rows(sections(contract)["Outputs"])
        guide = next(row for row in outputs if row[0] == "Proposed process guide")
        evidence = next(row for row in outputs if row[0] == "Walkthrough and trial evidence")
        self.assertEqual(guide[1], location)
        self.assertEqual(evidence[1], location + ", supporting artifacts in sandbox")
        self.assertIn("Keep the conversation in " + location + ".", "\n".join(sections(reference)["Select a task"]))
        self.assertNotIn("Systems capture thread", contract + reference)

    def test_approved_wording_routes_to_systems_from_any_capture_thread(self):
        contract = (CAPTURE / "CONTEXT.md").read_text()
        _, outputs = table_rows(sections(contract)["Outputs"])
        handoff = next(row for row in outputs if row[0] == "Approved wording handoff")
        self.assertEqual(handoff[1], 'Systems thread per `_core/CONVENTIONS.md` "Handoffs and state"')
        for expected in ("Repo-maintenance request", "exact sanitized diff", "Operator's native approval link", "only when approved"):
            self.assertIn(expected, handoff[2])
        review = "\n".join(sections((CAPTURE / "references/capture.md").read_text())["Review and handoff"])
        for expected in ("After approval, send the repo-maintenance request to the Systems thread",
                         '`_core/CONVENTIONS.md` "Handoffs and state" for destination and transport', "exact approved diff",
                         "Operator's native approval link", "whichever thread ran the capture", "Capture itself makes no repo writes."):
            self.assertIn(expected, review)
        self.assertEqual(frontmatter(contract)["writes"], "nothing")

    def test_systems_destination_is_configured_and_send_once(self):
        handoffs = '\n'.join(sections((ROOT / '_core/CONVENTIONS.md').read_text())['Handoffs and state'])
        self.assertIn('configured Systems destination', handoffs)
        self.assertIn('_core/thread-locators.md', handoffs)
        self.assertIn('Send once with `pplx tm mail send', handoffs)
        self.assertNotRegex(handoffs, r'session [0-9a-f]{8}-')


    def test_friday_only_capture_step_precedes_report_without_changing_cadence(self):
        contract = (REVIEW / "CONTEXT.md").read_text()
        process = sections(contract)["Process"]
        capture_step = next(line for line in process if "Capture nomination" in line)
        report_step = next(line for line in process if "Report and routing" in line)
        self.assertTrue(capture_step.startswith("6. Friday only, prepare at most one capture step"))
        self.assertLess(process.index(capture_step), process.index(report_step))
        self.assertEqual(frontmatter(contract)["cadence"], "Friday")
        nomination = sections((REVIEW / "references/eval.md").read_text())["Capture nomination"]
        self.assertIn("On-demand Eval adds no capture step.", "\n".join(nomination))
        self.assertIn("not a new automation or schedule", "\n".join(nomination))

    def test_capture_inputs_read_only_two_required_method_sections(self):
        contract = (REVIEW / "CONTEXT.md").read_text()
        rows = [row for row in inputs_rows(contract) if "process-capture" in row[1]]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "`workspaces/systems/workflows/process-capture/references/capture.md`")
        self.assertEqual(rows[0][2], '"Select a task", "Walk through decisions"')
        loaded = loaded_contract_text(REVIEW)
        for heading in ("Select a task", "Walk through decisions", "Capture nomination"):
            self.assertIn("## " + heading + "\n", loaded)
        for heading in ("Try another case", "Working guide", "Review and handoff", "Method source"):
            self.assertNotIn("## " + heading + "\n", loaded)
        self.assertNotIn("# Process Capture\n", loaded)

    def test_report_caps_nomination_or_continuation_at_one_step(self):
        contract = sections((REVIEW / "CONTEXT.md").read_text())
        audit = next(line for line in contract["Audit"] if line.startswith("| Capture,"))
        self.assertIn("At most one capture step.", audit)
        _, outputs = table_rows(contract["Outputs"])
        capture_outputs = [row for row in outputs if row[0] == "Friday capture step"]
        self.assertEqual(len(capture_outputs), 1)
        self.assertEqual(capture_outputs[0][1], "Systems thread, supporting evidence in sandbox")
        self.assertIn("At most one nomination", capture_outputs[0][2])
        self.assertIn("or one status line for an open capture", capture_outputs[0][2])
        self.assertNotIn("trial", capture_outputs[0][2])

    def test_capture_dedupe_includes_all_statuses_prior_declines_and_missing_reads(self):
        nomination = "\n".join(sections((REVIEW / "references/eval.md").read_text())["Capture nomination"])
        for expected in ("capture files in `workspaces/systems/captures/`", "Operator's prior declines in the Systems thread",
                         "by recurring task and owning workflow across confirmed, applied, retired and declined captures, not title alone",
                         "Incomplete capture-file or decline reads are not checked and block a new nomination",
                         "with no existing capture file or prior Operator decline"):
            self.assertIn(expected, nomination)

    def test_nominee_requires_actual_weekly_signals_owner_links_and_bounded_questions(self):
        nomination = "\n".join(sections((REVIEW / "references/eval.md").read_text())["Capture nomination"])
        for expected in ("from this week's \"Signals\"", "same edit or rejection twice or repeated manual work",
                         "Post its owning workflow, two real example links and the first one or two questions",
                         '"Select a task" and "Walk through decisions"',
                         "A nomination is only a suggestion until Operator selects the task."):
            self.assertIn(expected, nomination)
        selection = "\n".join(sections((CAPTURE / "references/capture.md").read_text())["Select a task"])
        self.assertIn("An unselected nomination is a suggestion until Operator selects the task.", selection)

    def test_open_capture_takes_priority_with_status_only_never_a_trial(self):
        nomination = "\n".join(sections((REVIEW / "references/eval.md").read_text())["Capture nomination"])
        for expected in ("If a capture is open, meaning a `confirmed` file or an unfinished capture in the Systems thread",
                         "post one status line instead of nominating another task",
                         "State what it waits on, such as a second case or wording approval",
                         "Never prepare a trial during system-review"):
            self.assertIn(expected, nomination)
        self.assertLess(nomination.index("If a capture is open"), nomination.index("Otherwise choose"))
        self.assertNotIn('"Try another case"', nomination)
        self.assertNotIn("Prepare a read-only second-case trial", nomination)

    def test_same_edit_capture_question_replaces_not_duplicates_correction_question(self):
        nomination = "\n".join(sections((REVIEW / "references/eval.md").read_text())["Capture nomination"])
        self.assertIn("its capture question replaces that pattern's repeated-correction question", nomination)
        self.assertIn("Ask once per pattern, never both questions.", nomination)
        audit = "\n".join(sections((REVIEW / "CONTEXT.md").read_text())["Audit"])
        self.assertIn("A same-edit capture question replaces that pattern's repeated-correction question.", audit)

    def test_questions_do_not_pause_and_capture_does_not_authorize_writes_or_git_history(self):
        contract = (REVIEW / "CONTEXT.md").read_text()
        nomination = "\n".join(sections((REVIEW / "references/eval.md").read_text())["Capture nomination"])
        for expected in ("Questions wait for no reply.", "under the process-capture contract, not as a repair or wording approval",
                         "No repo or customer-system writes.", "Do not write capture files here",
                         "customer examples in Git", "Existing improvement task recording is unchanged."):
            self.assertIn(expected, nomination)
        self.assertEqual(frontmatter(contract)["writes"], "Teammate improvement tasks and evidence comments only")
        self.assertTrue("\n".join(sections(contract)["Checkpoints"]).strip().startswith("None."))
        self.assertIn("no capture file writes and no customer examples in Git", "\n".join(sections(contract)["Audit"]))
        self.assertEqual(frontmatter((CAPTURE / "CONTEXT.md").read_text())["writes"], "nothing")

    def test_only_process_capture_and_system_review_read_capture_files_as_input(self):
        allowed = {CAPTURE, REVIEW}
        for path in sorted(WORKSPACES.glob("*/workflows/**/*.md")):
            if any(path.is_relative_to(folder) for folder in allowed):
                continue
            self.assertNotIn("captures/", path.read_text(), str(path.relative_to(ROOT)))
        for path in sorted(WORKSPACES.glob("*/references/*.md")) + [ROOT / "_core/rules.md", ROOT / "_core/policy.yaml"]:
            self.assertNotIn("captures/", path.read_text(), str(path.relative_to(ROOT)))
        for folder in allowed:
            rows = [row for row in inputs_rows((folder / "CONTEXT.md").read_text()) if "captures/" in row[1]]
            self.assertEqual([row[1] for row in rows], ["`workspaces/systems/captures/`"], folder.name)

    def test_capture_folder_holds_only_generalized_capture_files(self):
        self.assertTrue(CAPTURES.is_dir())
        for path in CAPTURES.iterdir():
            if path.name in {".gitkeep", ".DS_Store"}:
                continue
            self.assertEqual(capture_file_problems(path.name, path.read_text()), [], path.name)

    def test_capture_file_check_rejects_bad_format(self):
        good = ("Task: Opening line for cold drafts\nOwner: prospecting signal-outreach\n"
                "Status: applied 2026-10-09 https://github.com/o/r/pull/7\nReasons:\n- Lead with the buyer initiative\n"
                "Decisions:\n- Signal initiative named, action open with it\n  Applied in: `_core/rules.md#email_body`\nSecond case: Accepted\n"
                "Open questions:\n- None\nEvidence:\n- https://www.perplexity.ai/computer/tasks/x\n")
        self.assertEqual(capture_file_problems("prospecting-opening-line.md", good), [])
        for status_word in ("open", "tested", "merged"):
            with self.subTest(status_word=status_word):
                self.assertIn("status", capture_file_problems("a.md", good.replace("Status: applied", "Status: " + status_word)))
        self.assertIn("applied PR link", capture_file_problems("a.md", good.replace("https://github.com/o/r/pull/7", "")))
        self.assertIn("evidence links", capture_file_problems("a.md", good + "Quoted buyer text\n"))
        self.assertIn("email address", capture_file_problems("a.md", good.replace("None", "jane@acme.com")))
        self.assertEqual(capture_file_problems("a.md", good.replace("Owner:", "Who:")), ["labels"])
        self.assertIn("name", capture_file_problems("Acme Capture.md", good))

    def test_capture_status_requires_iso_date_for_each_allowed_status(self):
        for status_word in ("confirmed", "applied", "retired"):
            good = ("Task: Drafting\nOwner: Pipeline\nStatus: " + status_word + " 2026-10-08 https://github.com/o/r/pull/7\n"
                    "Reasons:\n- Clear ask\nDecisions:\n- Keep it short\n  Applied in: `_core/rules.md`\n"
                    "Second case: untested, awaiting review\nOpen questions:\n- Trial\nEvidence:\n- https://www.perplexity.ai/computer/tasks/synthetic-thread\n")
            with self.subTest(status_word=status_word):
                self.assertEqual(capture_file_problems("a.md", good), [])
                for invalid_date in ("", "10/8/26", "2026-1-08", "2026-02-30"):
                    self.assertIn("ISO date", capture_file_problems("a.md", good.replace("2026-10-08", invalid_date)))

    def test_applied_capture_requires_existing_backticked_repo_file(self):
        good = ("Task: Drafting\nOwner: Pipeline\nStatus: applied 2026-10-08 https://github.com/o/r/pull/7\n"
                "Reasons:\n- Clear ask\nDecisions:\n- Keep it short\n  Applied in: `_core/rules.md#email_body`\n"
                "Second case: Reviewed\nOpen questions:\n- None\nEvidence:\n- https://www.perplexity.ai/computer/tasks/synthetic-thread\n")
        for replacement in ("", "  Applied in: _core/rules.md#email_body", "  Applied in: `_core/missing.md`",
                            "  Applied in: `_core/`", "  Applied in: `../outside.md`"):
            with self.subTest(replacement=replacement):
                self.assertIn("applied location", capture_file_problems("a.md", good.replace("  Applied in: `_core/rules.md#email_body`", replacement)))
        self.assertEqual(capture_file_problems("a.md", good), [])
        self.assertEqual(capture_file_problems("a.md", good.replace("#email_body", "")), [])

    def test_capture_evidence_accepts_only_approved_thread_link_shapes(self):
        good = ("Task: Drafting\nOwner: Pipeline\nStatus: confirmed 2026-10-08\n"
                "Reasons:\n- Clear ask\nDecisions:\n- Keep it short\n"
                "Second case: untested\nOpen questions:\n- None\nEvidence:\n- {link}\n")
        for link in ("https://www.perplexity.ai/computer/tasks/synthetic-thread",
                     "https://www.perplexity.ai/teammate/synthetic-project/synthetic-thread"):
            with self.subTest(link=link):
                self.assertEqual(capture_file_problems("a.md", good.format(link=link)), [])
                self.assertEqual(capture_file_problems("a.md", good.format(link="[Thread](" + link + ")")), [])
        for link in ("https://example.org/unrelated", "https://www.perplexity.ai/unrelated",
                     "https://www.perplexity.ai/computer/tasks/", "https://www.perplexity.ai/teammate/project",
                     "https://www.perplexity.ai/computer/tasks/thread/extra",
                     "https://www.perplexity.ai/teammate/project/thread/extra",
                     "https://www.perplexity.ai/computer/tasks/thread?query=extra",
                     "https://www.perplexity.ai/computer/tasks/thread#extra",
                     "https://www.perplexity.ai.evil.example/computer/tasks/thread",
                     "http://www.perplexity.ai/computer/tasks/thread",
                     "https://github.com/ppl-ai/sales-teammate/pull/1",
                     "https://github.com/ppl-ai/sales-teammate/commit/abc"):
            with self.subTest(link=link):
                self.assertIn("evidence links", capture_file_problems("a.md", good.format(link=link)))
        mixed = good.format(link="https://www.perplexity.ai/computer/tasks/thread") + "- https://example.org/unrelated\n"
        self.assertIn("evidence links", capture_file_problems("a.md", mixed))

    def test_applied_capture_checks_each_named_section_in_the_checked_files(self):
        good = ("Task: Drafting\nOwner: Pipeline\nStatus: applied 2026-10-08 https://github.com/o/r/pull/7\n"
                "Reasons:\n- Clear ask\nDecisions:\n- Keep it short\n  Applied in: {location}\n"
                "Second case: Reviewed\nOpen questions:\n- None\nEvidence:\n"
                "- https://www.perplexity.ai/computer/tasks/synthetic-thread\n")
        grouping = "workspaces/pipeline/workflows/task-triage-speed-run/references/grouping.md"
        for location in ("`_core/rules.md#email_body`", "`rules#email_body`", "`_core/policy.yaml#followup`",
                         "`_core/policy.yaml#followup.cooldown_days`", "`" + grouping + '` "Other Tasks" item 5.',
                         "`" + grouping + "#other-tasks`", "`" + grouping + "#Other Tasks`"):
            with self.subTest(location=location):
                self.assertEqual(capture_file_problems("a.md", good.format(location=location)), [])
        for location in ("`_core/rules.md#missing_section`", "`rules#missing_section`", "`_core/rules.md#`",
                         "`_core/policy.yaml#missing_section`", "`_core/policy.yaml#followup.missing_section`",
                         "`" + grouping + '` "Missing heading"', "`" + grouping + "#missing-heading`"):
            with self.subTest(location=location):
                self.assertIn("applied location", capture_file_problems("a.md", good.format(location=location)))
                mixed = good.format(location="`_core/rules.md#email_body`").replace(
                    "Second case:", "  Applied in: " + location + "\nSecond case:")
                self.assertIn("applied location", capture_file_problems("a.md", mixed))

    def test_capture_file_contract_records_reviewed_changes_without_fixed_commit_count(self):
        contract = (CAPTURE / "CONTEXT.md").read_text()
        section = "\n".join(sections((CAPTURE / "references/capture.md").read_text())["Capture file"])
        for expected in ("Systems repo-maintenance commits it. Capture itself makes no repo writes.",
                         "Repo-maintenance commits each change Operator has reviewed", "batched per session", "There is no fixed number of commits",
                         "Unconfirmed material stays in the thread", "`confirmed`, `applied` and `retired`", "YYYY-MM-DD",
                         "It may be untested", "Its Status line carries the PR link", "an `Applied in:` sub-line",
                         "any difference between captured wording and applied wording", "Thread links only",
                         "or `untested` with the missing check", "history, never authority", "never overrides or substitutes for the owning file",
                         "They do not block access",
                         "Retire a file only through repo-maintenance after Operator agrees."):
            self.assertIn(expected, section)
        for label in CAPTURE_LABELS:
            self.assertIn("| `" + label + "` |", section)
        _, outputs = table_rows(sections(contract)["Outputs"])
        row = next(row for row in outputs if row[0] == "Capture file")
        self.assertIn("through Systems repo-maintenance", row[1])
        self.assertIn('per `references/capture.md` "Capture file"', row[2])
        self.assertNotIn("committed at tested", row[2])
        self.assertIn("confirmed capture file and its reviewed updates", frontmatter(contract)["next"])
        _, checkpoints = table_rows(sections(contract)["Checkpoints"])
        confirmation = next(row for row in checkpoints if row[0] == "3")
        self.assertIn("states his reasoning faithfully or corrects it", confirmation[2])
        trial = "\n".join(sections((CAPTURE / "references/capture.md").read_text())["Try another case"])
        self.assertIn("Operator's confirmation shows faithful capture", trial)
        self.assertIn("Only reviewed trial results show usefulness", trial)
        self.assertIn("Do not claim saved time or better performance without them", trial)

    def test_monthly_capture_review_runs_first_friday_inside_existing_review(self):
        monthly = "\n".join(sections((REVIEW / "references/eval.md").read_text())["Monthly capture review"])
        for expected in ("On the first Friday of each month", "not a new schedule", "On-demand Eval skips it.",
                         "same edit or rejection again", "Never edit capture files.", "an `applied` capture", "since its applied date"):
            self.assertIn(expected, monthly)
        process = "\n".join(sections((REVIEW / "CONTEXT.md").read_text())["Process"])
        self.assertIn('First Friday of the month, also add the summary per `references/eval.md` "Monthly capture review".', process)
        self.assertEqual(frontmatter((REVIEW / "CONTEXT.md").read_text())["cadence"], "Friday")

    def test_agent_configuration_reads_platform_limits_without_copying_them(self):
        contract = CONTRACT_PATHS["agent-configuration"].read_text()
        approval = next(row for row in inputs_rows(contract) if row[0] == "Approval")
        self.assertIn('"Platform limits"', approval[2])
        self.assertNotIn("RUN_AUTOMATION_SCOPE_VIOLATION", contract)

    def test_factory_captures_exclude_source_history_and_applied_records_name_each_decision(self):
        self.assertEqual({p.name for p in CAPTURES.iterdir() if p.name != '.DS_Store'}, {'.gitkeep'})
        record = ("Task: Follow-up wording\nOwner: Pipeline\nStatus: applied 2026-10-09 https://github.com/o/r/pull/7\n"
                  "Reasons:\n- Clear short ask\nDecisions:\n- Captured limit was three sentences. Applied limit is two.\n"
                  "  Applied in: `_core/rules.md#email_body`\nSecond case: Reviewed and accepted\n"
                  "Open questions:\n- None\nEvidence:\n- https://www.perplexity.ai/computer/tasks/synthetic-thread\n")
        self.assertEqual(capture_file_problems('pipeline-wording.md', record), [])
        decisions = record.split('Decisions:\n', 1)[1].split('Second case:', 1)[0]
        for decision in decisions.split('\n- '):
            self.assertIn('Applied in:', decision)


if __name__ == "__main__":
    unittest.main()
