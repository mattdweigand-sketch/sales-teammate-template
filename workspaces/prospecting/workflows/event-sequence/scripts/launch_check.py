"""Compare a saved E snapshot, launch recheck and native Apollo responses.

Input JSON has approved, recheck (event_list_prep output), native_contacts
(bulk-create contacts), native_sequence (create/update response), and payload
(the exact add_contact_ids request). No network calls or approval validation.

The payload carries only the keys the add_contact_ids operation defines, listed
in APPROVED_PAYLOAD_KEYS. Its id and emailer_campaign_id must equal the verified
native campaign id, which every native step already belongs to. Any other key
fails. A saved wrapper or selected native response carrying a positive failure
marker (truncated, error, isError, or authenticated false) stops before it is
unwrapped or compared. isError false, error null and truncated false are not
failures by presence. Fields the comparison does not cover stay in not_checked.

Approved recipients have row_id and email. Approved steps have subject, body and
a required boolean include_signature, compared against every linked native touch.
Native sequence input is the confirmed sideloaded result, bare or in the saved
{tool, result, connector, structure} wrapper. Steps, touches and templates are
joined by native IDs without reshaping the saved response. Missing documented
fields or unrecognized structures STOP enrollment. Mailbox is checked only in
the payload. Approved emailer_schedule_id is required, not just a schedule name.
Copy may match after conservative HTML-to-text normalization, provided extracted
merge variables and URLs still match exactly, including count and order.
"""

import argparse
import copy
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path


APPROVED_PAYLOAD_KEYS = ("id", "emailer_campaign_id", "contact_ids", "send_email_from_email_account_id")
FAILURE_MARKERS = ("truncated", "error", "isError")

MERGE_VARIABLE = re.compile(r"\{\{[^{}]*\}\}")
URL = re.compile(r"(?:https?://|ftp://|mailto:)[^\s<>\"']+", re.IGNORECASE)
LINK_ATTRIBUTE = re.compile(
    r"\b(?:href|src|action|formaction|poster|cite|background)\s*=\s*"
    r"(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))", re.IGNORECASE)


class CopyText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("p", "div", "li"):
            self.parts.append("\n")


def normalize_copy(value):
    parser = CopyText()
    parser.feed(html.unescape(value).replace("\r\n", "\n").replace("\r", "\n"))
    parser.close()
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in "".join(parser.parts).split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def copy_signature(value):
    source = html.unescape(value)
    links = {}
    attribute_spans = []
    for match in LINK_ATTRIBUTE.finditer(source):
        group = next(position for position in (1, 2, 3) if match.group(position) is not None)
        span = match.span(group)
        attribute_spans.append(span)
        links[span] = match.group(group)
    for match in URL.finditer(source):
        if not any(start <= match.start() and match.end() <= end for start, end in attribute_spans):
            links[match.span()] = match.group()
    return MERGE_VARIABLE.findall(source), [links[span] for span in sorted(links)]


def text(value, path):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path} must be a nonempty string")
    return value


def records(value, path):
    if not isinstance(value, list) or any(not isinstance(record, dict) for record in value):
        raise ValueError(f"{path} must be a list of objects")
    return value


def indexed(value, key, path):
    result = {}
    for record in records(value, path):
        identity = text(record.get(key), f"{path}.{key}")
        if identity in result:
            raise ValueError(f"{path} has duplicate {key} {identity!r}")
        result[identity] = record
    return result


def failure_markers(record, path, structure_errors):
    """Record positive failure markers on one saved response object. Returns True when any was found."""
    found = False
    if not isinstance(record, dict):
        return found
    for marker in FAILURE_MARKERS:
        if record.get(marker):
            structure_errors.append({"field": f"{path}.{marker}", "reason": "Native response carries a failure marker"})
            found = True
    if record.get("authenticated") is False:
        structure_errors.append({"field": f"{path}.authenticated", "reason": "Native response is not authenticated"})
        found = True
    return found


def read_native(saved, missing, structure_errors, compare):
    def problem(path, reason):
        structure_errors.append({"field": path, "reason": reason})

    def required(record, field, path):
        if field not in record or record[field] is None:
            missing.append(f"{path}.{field}")
            return None
        return record[field]

    def array(record, field, path):
        value = required(record, field, path)
        if value is None:
            return []
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            problem(f"{path}.{field}", "Expected a list of native objects")
            return []
        return value

    def by_id(values, fields, path):
        result = {}
        for position, record in enumerate(values):
            location = f"{path}.{position}"
            for field in fields:
                required(record, field, location)
            identity = record.get("id")
            if not isinstance(identity, str) or not identity:
                if identity is not None:
                    problem(f"{location}.id", "Expected a nonempty native ID")
            elif identity in result:
                problem(f"{location}.id", "Duplicate native ID")
            else:
                result[identity] = (location, record)
        return result

    if not isinstance(saved, dict):
        problem("native_sequence", "Unrecognized saved response structure")
        return {}, [], {}
    if failure_markers(saved, "native_sequence", structure_errors):
        return {}, [], {}
    if "result" in saved:
        for field in ("tool", "result", "connector", "structure"):
            if field not in saved:
                missing.append(f"native_sequence.wrapper.{field}")
        saved = saved["result"]
        if failure_markers(saved, "native_sequence.result", structure_errors):
            return {}, [], {}
    if not isinstance(saved, dict):
        problem("native_sequence.result", "Expected the confirmed sideloaded result object")
        return {}, [], {}
    for field in ("sharing_accesses", "attachments", "team", "sequence_url"):
        if field not in saved:
            missing.append(f"native_sequence.{field}")
    campaign = required(saved, "emailer_campaign", "native_sequence")
    if not isinstance(campaign, dict):
        if campaign is not None:
            problem("native_sequence.emailer_campaign", "Expected a native campaign object")
        campaign = {}
    for field in ("id", "mark_finished_if_reply", "emailer_schedule_id", "sequence_by_exact_daytime"):
        required(campaign, field, "native_sequence.emailer_campaign")
    steps = by_id(array(saved, "emailer_steps", "native_sequence"),
                  ("id", "emailer_campaign_id", "position", "type", "wait_time", "wait_mode"),
                  "native_sequence.emailer_steps")
    touches = by_id(array(saved, "emailer_touches", "native_sequence"),
                    ("id", "emailer_step_id", "emailer_template_id", "type", "include_signature"),
                    "native_sequence.emailer_touches")
    templates = by_id(array(saved, "emailer_templates", "native_sequence"),
                      ("id", "subject", "body_html"), "native_sequence.emailer_templates")
    if not isinstance(campaign.get("id"), str) or not campaign.get("id"):
        if campaign.get("id") is not None:
            problem("native_sequence.emailer_campaign.id", "Expected a nonempty native ID")
    positions = set()
    for location, step in steps.values():
        position = step.get("position")
        if type(position) is not int or position in positions:
            problem(f"{location}.position", "Expected a unique integer position")
        else:
            positions.add(position)
        if step.get("emailer_campaign_id") is not None and step["emailer_campaign_id"] != campaign.get("id"):
            problem(f"{location}.emailer_campaign_id", "Step does not belong to the native campaign")
    copies = {identity: [] for identity in steps}
    for location, touch in touches.values():
        step_id = touch.get("emailer_step_id")
        template_id = touch.get("emailer_template_id")
        if not isinstance(step_id, str) or step_id not in steps:
            problem(f"{location}.emailer_step_id", "Dangling step ID")
        if not isinstance(template_id, str) or template_id not in templates:
            problem(f"{location}.emailer_template_id", "Dangling template ID")
        if isinstance(step_id, str) and step_id in copies and isinstance(template_id, str) and template_id in templates:
            copies[step_id].append((location, touch, *templates[template_id]))
    if "emailer_steps" in campaign:
        campaign_steps = by_id(array(campaign, "emailer_steps", "native_sequence.emailer_campaign"),
                               ("id", "wait_time", "wait_mode"), "native_sequence.emailer_campaign.emailer_steps")
        compare("native_sequence.emailer_campaign.emailer_steps.ids", sorted(steps), sorted(campaign_steps))
        for identity in sorted(set(steps) & set(campaign_steps)):
            location, embedded = campaign_steps[identity]
            for field in ("wait_time", "wait_mode"):
                compare(f"{location}.{field}", steps[identity][1].get(field), embedded.get(field))
    ordered = [] if missing or structure_errors else sorted(steps.values(), key=lambda item: item[1]["position"])
    return campaign, ordered, copies


def check(bundle):
    approved = bundle["approved"]
    payload = bundle["payload"]
    if not all(isinstance(value, dict) for value in (approved, payload)):
        raise ValueError("approved and payload must be objects")
    steps = records(approved["steps"], "approved.steps")
    for position, step in enumerate(steps):
        if type(step.get("include_signature")) is not bool:
            raise ValueError(f"approved.steps.{position}.include_signature must be a bool")
    mismatches = []
    missing = []
    structure_errors = []
    not_checked = []
    copy_matches = []
    supported = {"recipients", "steps", "send_email_from_email_account_id", "stop_on_reply", "emailer_schedule_id", "schedule_settings"}
    not_checked.extend(f"approved.{field}" for field in sorted(set(approved) - supported))

    def compare(path, expected, actual):
        if type(expected) is not type(actual) or expected != actual:
            mismatches.append({"field": path, "expected": expected, "actual": actual})

    def result():
        status = "STOP" if missing or structure_errors else "FAIL" if mismatches else "PASS"
        return {"status": status, "mismatches": mismatches, "missing": list(dict.fromkeys(missing)),
                "structure_errors": structure_errors, "not_checked": not_checked, "copy_matches": copy_matches,
                "payload": copy.deepcopy(payload) if status == "PASS" else None}

    campaign, native_steps, copies = read_native(bundle.get("native_sequence"), missing, structure_errors, compare)
    failure_markers(bundle.get("native_contacts"), "native_contacts", structure_errors)
    if not approved.get("emailer_schedule_id"):
        missing.append("approved.emailer_schedule_id")
    if missing or structure_errors:
        return result()

    unknown_keys = sorted(set(payload) - set(APPROVED_PAYLOAD_KEYS))
    if unknown_keys:
        compare("payload.keys", list(APPROVED_PAYLOAD_KEYS), unknown_keys)
    for field in ("id", "emailer_campaign_id"):
        compare(f"payload.{field}", campaign["id"], payload.get(field))

    recipients = indexed(approved["recipients"], "row_id", "approved.recipients")
    rechecked = indexed(bundle["recheck"]["contacts"], "row_id", "recheck.contacts")
    contacts = indexed(bundle["native_contacts"]["contacts"], "id", "native_contacts.contacts")
    by_email = {}
    for contact_id, contact in contacts.items():
        email = text(contact.get("email"), "native_contacts.email")
        by_email.setdefault(email, []).append(contact_id)
    expected_ids = []
    seen_emails = set()
    for row_id, recipient in recipients.items():
        email = text(recipient.get("email"), f"approved.recipients.{row_id}.email")
        if email in seen_emails:
            raise ValueError("approved.recipients has duplicate email")
        seen_emails.add(email)
        current = rechecked.get(row_id)
        if current is None:
            compare(f"recheck.{row_id}", "present", None)
            continue
        compare(f"recheck.{row_id}.email", email, current.get("email"))
        label = current.get("label")
        if label in ("recent_reply", "needs_input"):
            continue
        if label != "enroll":
            compare(f"recheck.{row_id}.label", "enroll, recent_reply or needs_input", label)
            continue
        matches = by_email.get(email, [])
        if len(matches) != 1:
            compare(f"contacts.{row_id}", "one native contact with approved email", matches)
            continue
        contact_id = matches[0]
        if current.get("apollo_contact_id"):
            compare(f"contacts.{row_id}.id", current["apollo_contact_id"], contact_id)
        expected_ids.append(contact_id)
    planned_ids = payload.get("contact_ids")
    if not isinstance(planned_ids, list) or any(not isinstance(value, str) or not value for value in planned_ids):
        raise ValueError("payload.contact_ids must be a list of nonempty strings")
    if len(set(planned_ids)) != len(planned_ids):
        compare("payload.contact_ids.duplicates", [], planned_ids)
    compare("payload.contact_ids", sorted(expected_ids), sorted(planned_ids))
    if not expected_ids:
        compare("recipients", "at least one remaining approved recipient", [])

    mailbox = text(approved["send_email_from_email_account_id"], "approved.send_email_from_email_account_id")
    compare("payload.send_email_from_email_account_id", mailbox, payload.get("send_email_from_email_account_id"))
    if approved["stop_on_reply"] is not True:
        compare("approved.stop_on_reply", True, approved["stop_on_reply"])
    text(approved["emailer_schedule_id"], "approved.emailer_schedule_id")
    compare("native_sequence.emailer_campaign.mark_finished_if_reply", approved["stop_on_reply"], campaign["mark_finished_if_reply"])
    compare("native_sequence.emailer_campaign.emailer_schedule_id", approved["emailer_schedule_id"], campaign["emailer_schedule_id"])
    compare("native_sequence.emailer_campaign.sequence_by_exact_daytime", False, campaign["sequence_by_exact_daytime"])
    schedule_settings = approved["schedule_settings"]
    if not isinstance(schedule_settings, dict) or schedule_settings.get("mode") != "interval":
        raise ValueError("approved.schedule_settings must include mode interval")
    if not isinstance(schedule_settings.get("step_waits"), list):
        raise ValueError("approved.schedule_settings.step_waits is required")
    if any(type(wait) is not int or wait < 0 for wait in schedule_settings["step_waits"]):
        raise ValueError("approved step waits must be nonnegative integer days")
    not_checked.extend(f"schedule_settings.{field}" for field in sorted(set(schedule_settings) - {"mode", "step_waits"}))

    if not steps:
        raise ValueError("approved.steps must not be empty")
    if len(schedule_settings["step_waits"]) != len(steps):
        raise ValueError("approved step waits must cover every step")
    compare("native_sequence.emailer_steps.count", len(steps), len(native_steps))
    for position, step in enumerate(steps):
        not_checked.extend(f"steps.{position}.{field}" for field in sorted(set(step) - {"subject", "body", "type", "include_signature"}))
        for field in ("subject", "body"):
            if not isinstance(step.get(field), str):
                raise ValueError(f"approved.steps.{position}.{field} must be a string")
        if position >= len(native_steps):
            continue
        location, native_step = native_steps[position]
        compare(f"{location}.wait_time", schedule_settings["step_waits"][position], native_step["wait_time"])
        compare(f"{location}.wait_mode", "day", native_step["wait_mode"])
        if "type" in step:
            compare(f"{location}.type", step["type"], native_step["type"])
        if not copies[native_step["id"]]:
            structure_errors.append({"field": f"{location}.id", "reason": "Step has no touch with required native copy"})
        for touch_path, touch, template_path, template in copies[native_step["id"]]:
            compare(f"{touch_path}.include_signature", step["include_signature"], touch["include_signature"])
            for approved_field, native_field in (("subject", "subject"), ("body", "body_html")):
                path = f"{template_path}.{native_field}"
                expected, actual = step[approved_field], template[native_field]
                if expected == actual:
                    continue
                if (isinstance(actual, str) and normalize_copy(expected) == normalize_copy(actual)
                        and copy_signature(expected) == copy_signature(actual)):
                    copy_matches.append({"field": path, "note": "matched after HTML normalization"})
                else:
                    compare(path, expected, actual)
    return result()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Saved comparison bundle JSON in the sandbox")
    parser.add_argument("--output", type=Path, help="Save the result JSON outside Git")
    args = parser.parse_args(argv)
    try:
        result = check(json.loads(args.input.read_text()))
    except (ValueError, KeyError, TypeError, OSError) as error:
        result = {"status": "FAIL", "mismatches": [{"field": "input", "error": str(error)}],
                  "missing": [], "structure_errors": [], "not_checked": [], "copy_matches": [], "payload": None}
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n")
    print(rendered)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
