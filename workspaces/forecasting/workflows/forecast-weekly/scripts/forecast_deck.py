#!/usr/bin/env python3
"""Plan and check Operator's slide update in the shared bookings deck; offline, no network.

Usage: forecast_deck.py plan --presentation get.json --forecast result.json --reviewed reviewed.json
                             --input deck.json --coverage coverage.json [--approved preview.json] [--policy policy.yaml]
       forecast_deck.py verify --plan plan.json --before get.json --after readback.json [--policy policy.yaml]
`plan` prints the D preview and the batchUpdate body. With --approved it also stops when the fresh
read or the values differ from the approved D preview. `verify` compares the post-write read.
Mapping, text limits, rounding and overflow belong to references/deck.md. gws calls stay in the contract.
"""
import argparse
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path
import re
import sys

import yaml

from forecast_math import OPERATOR_CALL_LABEL, calculate, forecast_stage_floor, money, opportunity_stage, tracking_date


ROOT = Path(__file__).resolve().parents[5]
MONEY = re.compile(r'^-?\$\d[\d,]*(\.\d+)?([KM])?$')
DATES = re.compile(r'^(Updated:\s*)(.*?)(\s*\|\s*Start date:\s*)(.*)$')
CORE_HEADER = ['Deal', 'Amount', 'Stage', 'Risk']
BACKUP_HEADER = ['Deal', 'Amount', 'Required action']


def text(container):
    """Plain text of a shape or cell `text` object, without the final paragraph newline."""
    elements = (container or {}).get('textElements', [])
    value = ''.join((element.get('textRun') or element.get('autoText') or {}).get('content', '')
                    for element in elements)
    return value.rstrip('\n')


def flatten(elements):
    for element in elements or []:
        if 'elementGroup' in element:
            yield from flatten(element['elementGroup'].get('children'))
        else:
            yield element


def cells(table):
    return [[text(cell.get('text')) for cell in row.get('tableCells', [])] for row in table.get('tableRows', [])]


def page_text(page):
    """Every shape and cell text on a page, keyed by objectId and cell."""
    values = {}
    for element in flatten(page.get('pageElements')):
        if 'shape' in element:
            values[(element['objectId'], None)] = text(element['shape'].get('text'))
        elif 'table' in element:
            for row, columns in enumerate(cells(element['table'])):
                for column, value in enumerate(columns):
                    values[(element['objectId'], (row, column))] = value
    return values


def short_text(value, label, cap):
    if not isinstance(value, str) or not value.strip() or any(ord(character) < 32 for character in value):
        raise ValueError(f'{label}: needs nonempty single-line text')
    if len(value) > cap:
        raise ValueError(f'{label}: exceeds character cap ({cap}); shorten the text')
    return value


def _deck_character_caps(policy: dict) -> dict[str, int]:
    settings = policy['forecast']['deck']
    keys = ('cell_character_cap', 'name_character_cap', 'core_risk_character_cap')
    for key in keys:
        value = settings.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f'{key} must be a positive integer')
    return {key: settings[key] for key in keys}


def _deck_column_character_cap(group: str, column: int, caps: dict[str, int]) -> int:
    if column == 0:
        return caps['name_character_cap']
    if group == 'CORE' and column == 3:
        return caps['core_risk_character_cap']
    return caps['cell_character_cap']


def dollars(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('invalid monetary value') from exc
    if not amount.is_finite():
        raise ValueError('monetary value must be finite')
    rounded = amount.quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return f'{"-" if rounded < 0 else ""}${abs(rounded):,.0f}'


def parse_dollars(value):
    match = MONEY.match(value.strip())
    if not match:
        raise ValueError(f'not a dollar value: {value!r}')
    scale = {'K': 1000, 'M': 1000000}.get(match.group(2), 1)
    return Decimal(value.strip().rstrip('KM').replace('$', '').replace(',', '')) * scale


def short_date(value):
    return f'{value.month}/{value.day}'


def rank(rows, field):
    return sorted(rows, key=lambda row: (-money(row[field]), row['Id']))


def display_rows(rows, capacity, field):
    if len(rows) <= capacity:
        return rows
    ordered = rank(rows, field)
    hidden = ordered[capacity - 1:]
    return ordered[:capacity - 1] + [{'Name': f'+{len(hidden)} more',
                                    field: sum((money(row[field]) for row in hidden), Decimal(0))}]


def resolve_slide(presentation, title):
    matches = [slide for slide in presentation.get('slides', [])
               if any(value.strip() == title for (_, cell), value in page_text(slide).items() if cell is None)]
    if len(matches) != 1:
        raise ValueError(f'expected exactly one slide titled {title!r}, found {len(matches)}')
    return matches[0]


class Slide:
    """Label-based lookup on one live slide. Never uses positions or stored objectIds."""

    def __init__(self, slide):
        self.elements = list(flatten(slide.get('pageElements')))
        self.shapes = [(element['objectId'], text(element['shape'].get('text')))
                       for element in self.elements if 'shape' in element]
        self.shape_types = {element['objectId']: element['shape'].get('shapeType')
                            for element in self.elements if 'shape' in element}
        self.tables = [(element['objectId'], cells(element['table']))
                       for element in self.elements if 'table' in element]

    def labelled_value(self, label, money_value=True):
        """Money labels take the first nonempty following shape. A text label takes the shape directly after it,
        selected as empty when blank, so an emptied value box never resolves to a later note."""
        indexes = [index for index, (_, value) in enumerate(self.shapes) if value.strip() == label]
        if len(indexes) != 1:
            raise ValueError(f'{label}: expected one label on the slide, found {len(indexes)}')
        following = self.shapes[indexes[0] + 1:]
        if not money_value:
            if not following:
                raise ValueError(f'{label}: no value shape follows the label')
            identity, value = following[0]
            if not value.strip() and self.shape_types.get(identity) != 'TEXT_BOX':
                raise ValueError(f'{label}: the shape after the label is empty and not a text box, value target ambiguous')
            return identity, value
        following = [(identity, value) for identity, value in following if value.strip()]
        if not following or not MONEY.match(following[0][1].strip()):
            raise ValueError(f'{label}: no value shape follows the label')
        return following[0]

    def shape_starting(self, prefix):
        found = [(identity, value) for identity, value in self.shapes if value.startswith(prefix)]
        if len(found) != 1:
            raise ValueError(f'{prefix!r}: expected one shape, found {len(found)}')
        return found[0]

    def table(self, label, test):
        found = [(identity, rows) for identity, rows in self.tables if rows and test(rows)]
        if len(found) != 1:
            raise ValueError(f'{label}: expected one table, found {len(found)}')
        return found[0]


def validated_inputs(result, reviewed, deck_input, policy):
    caps = _deck_character_caps(policy)
    cap = caps['cell_character_cap']
    if result != calculate(reviewed, policy):
        raise ValueError('forecast output does not match the reviewed calculation and current policy')
    if result['status'] != 'complete' or result['held']:
        raise ValueError('held: D is not proposed while any row is held: '
                         + ', '.join(sorted(row['Id'] for row in result['held'])))
    as_of = tracking_date(deck_input['as_of'])
    year, quarter_number = map(int, result['quarter'].split('-Q'))
    start = date(year, (quarter_number - 1) * 3 + 1, 1)
    if tracking_date(deck_input['quarter_start']) != start or deck_input['as_of'] != reviewed['as_of']:
        raise ValueError('deck dates must match reviewed as_of and quarter start')
    if (as_of.year, (as_of.month - 1) // 3 + 1) != (year, quarter_number):
        raise ValueError('as_of must be in the reviewed quarter')
    field = policy['forecast']['amount_field']
    core = rank([row for row in reviewed['deals'] if row['bucket'] == 'commit'], field)
    backup = rank([row for row in reviewed['deals'] if row['bucket'] == 'upside'], field)
    backup += rank(reviewed['pull_ins'], field)
    row_text = deck_input['rows']
    if not isinstance(row_text, dict) or set(row_text) != {row['Id'] for row in core + backup}:
        raise ValueError('rows must provide short text for exactly the core and backup Ids')
    for rows, text_cap in ((core, caps['core_risk_character_cap']), (backup, cap)):
        for row in rows:
            short_text(row.get('Name'), f"{row['Id']}.Deal", caps['name_character_cap'])
            short_text(row_text[row['Id']], f"{row['Id']}.Risk / Required action", text_cap)
    support = deck_input.get('support', [])
    if not isinstance(support, list) or len(support) > 3:
        raise ValueError('SUPPORT NEEDED: provide at most 3 Asks lines')
    for index, value in enumerate(support):
        short_text(value, f'SUPPORT NEEDED[{index + 1}]', cap)
    return cap, as_of, start, f'Q{quarter_number}', field, core, backup, row_text, support


def _require_deck_coverage(coverage: dict | None, reviewed: dict, result: dict, policy: dict) -> None:
    """Aggregate D cannot bypass failed coverage or conceal affected contributors."""
    if not isinstance(coverage, dict) or coverage.get('ready') is not True or coverage.get('process_status') != 'complete':
        raise ValueError('coverage: D is not proposed without ready saved coverage')
    affected = coverage.get('affected')
    if not isinstance(affected, list) or any(not isinstance(identity, str) or not identity for identity in affected):
        raise ValueError('coverage: D is not proposed when affected is unknown or malformed')
    contributors = {row['Id'] for group in ('booked', 'pull_ins') for row in reviewed[group]}
    year, number = map(int, result['quarter'].split('-Q'))
    start = date(year, (number - 1) * 3 + 1, 1)
    end = date(year + (number == 4), number % 4 * 3 + 1, 1)
    floor = forecast_stage_floor(policy['forecast'])
    for row in reviewed['deals']:
        if row['bucket'] in ('commit', 'upside') or (
                opportunity_stage(row) >= floor and not row.get('IsClosed', False)
                and start <= tracking_date(row['CloseDate']) < end):
            contributors.add(row['Id'])
    blocked = sorted(contributors.intersection(affected))
    if blocked:
        raise ValueError('coverage: D contains affected contributing Opportunities: ' + ', '.join(blocked))


def plan(presentation, result, reviewed, deck_input, policy, coverage=None):
    settings = policy['forecast']['deck']
    cap, as_of, start, quarter, field, core, backup, row_text, support = validated_inputs(
        result, reviewed, deck_input, policy)
    _require_deck_coverage(coverage, reviewed, result, policy)
    caps = _deck_character_caps(policy)
    if presentation.get('presentationId') != settings['presentation_id']:
        raise ValueError('presentation id does not match policy.forecast.deck.presentation_id')
    if not presentation.get('revisionId'):
        raise ValueError('presentation read has no revisionId')
    title = settings['slide_title'].format(quarter=quarter)
    page = resolve_slide(presentation, title)
    slide = Slide(page)
    fields = []

    def put(label, identity, current, new, cell=None, capped=True, limit=None):
        limit = cap if limit is None else limit
        if capped and len(new) > limit:
            raise ValueError(f'{label}: exceeds character cap ({limit})')
        fields.append({'label': label, 'object_id': identity, 'cell': list(cell) if cell else None,
                       'current': current, 'new': new})

    identity, current = slide.shape_starting('Updated:')
    match = DATES.match(current)
    if not match:
        raise ValueError('Updated / Start date: unexpected label format')
    put('Updated / Start date', identity, current,
        f'{match.group(1)}{short_date(as_of)}{match.group(3)}{short_date(start)}', capped=False)
    quota_id, quota_text = slide.labelled_value(f'{quarter} QUOTA')
    if parse_dollars(quota_text) != Decimal(result['target']):
        raise ValueError(f'{quarter} QUOTA: slide shows {quota_text}, policy target is {dollars(result["target"])}')
    for label, value in [(f'{quarter} CALL', result['call']),
                         ('UPSIDE CALL', Decimal(result['call']) + Decimal(result['upside'])),
                         ('GAP TO CALL', result['gap'])]:
        put(label, *slide.labelled_value(label), dollars(value))
    identity, rows = slide.table('Closed total', lambda rows: rows[0][:1] == ['Closed total'])
    put('Closed total', identity, rows[0][1], dollars(result['booked']), (0, 1))
    for group, header, rows_in, capacity, extra in [('CORE', CORE_HEADER, core, settings['core_rows'], 0),
                                                    ('BACKUP', BACKUP_HEADER, backup, settings['backup_rows'], 1)]:
        identity, rows = slide.table(group, lambda rows, header=header: rows[0] == header)
        if len(rows) != 1 + capacity + extra:
            raise ValueError(f'{group}: live table has {len(rows) - 1 - extra} deal rows, policy expects {capacity}')
        shown = display_rows(rows_in, capacity, field)
        for index in range(capacity):
            values = [''] * len(header)
            if index < len(shown):
                row = shown[index]
                values = [row['Name'], dollars(row[field])]
                if group == 'CORE':
                    values.append(re.match(r'S[0-5]', row['StageName']).group(0) if row.get('Id') else '')
                values.append(row_text[row['Id']] if row.get('Id') else '')
            for column, value in enumerate(values):
                limit = _deck_column_character_cap(group, column, caps)
                put(f'{group}[{index + 1}][{column + 1}]', identity, rows[index + 1][column], value,
                    (index + 1, column), limit=limit)
        if group == 'BACKUP':
            if rows[-1][0] != 'Backup total':
                raise ValueError('BACKUP: last row must be Backup total')
            put('Backup total', identity, rows[-1][1],
                dollars(sum((money(row[field]) for row in rows_in), Decimal(0))), (len(rows) - 1, 1))
    identity, rows = slide.table('Qualified pipeline', lambda rows: rows[0][0].startswith('Qualified pipeline'))
    put('Qualified pipeline', identity, rows[0][1], dollars(result['qualified_pipeline']), (0, 1))
    identity, current = slide.labelled_value('SUPPORT NEEDED', money_value=False)
    put('SUPPORT NEEDED', identity, current, '\n'.join(support) or 'None.', capped=False)
    requests = []
    for entry in fields:
        if entry['current'] == entry['new']:
            continue
        target = {'objectId': entry['object_id']}
        if entry['cell']:
            target['cellLocation'] = {'rowIndex': entry['cell'][0], 'columnIndex': entry['cell'][1]}
        if entry['current']:
            requests.append({'deleteText': {**target, 'textRange': {'type': 'ALL'}}})
        if entry['new']:
            requests.append({'insertText': {**target, 'insertionIndex': 0, 'text': entry['new']}})
    operator_calls = [{'Id': row['Id'], 'Name': row.get('Name'), 'bucket': row['bucket'], 'label': OPERATOR_CALL_LABEL,
                   'failed_predicate': row['failed_predicate'], 'approved_turn': row['operator_call']['approved_turn']}
                  for row in result['operator_calls']]
    return {'presentation_id': presentation['presentationId'], 'revision_id': presentation['revisionId'],
            'slide_object_id': page['objectId'], 'slide_title': title, 'quarter': quarter,
            'quota': quota_text, 'fields': fields, 'changed': sum(entry['current'] != entry['new'] for entry in fields),
            'operator_calls': operator_calls,
            'batch_update': {'requests': requests,
                             'writeControl': {'requiredRevisionId': presentation['revisionId']}}}


def check_approved(fresh, approved):
    """Stop when the fresh read or values differ from the approved D preview."""
    if fresh['slide_object_id'] != approved['slide_object_id'] or len(fresh['fields']) != len(approved['fields']):
        raise ValueError('slide changed since the D preview; re-propose D')
    for now, then in zip(fresh['fields'], approved['fields']):
        if (now['label'], now['object_id'], now['cell']) != (then['label'], then['object_id'], then['cell']):
            raise ValueError('slide changed since the D preview; re-propose D')
        if now['current'] != then['current']:
            raise ValueError(f"{now['label']}: slide text changed since the D preview; re-propose D")
        if now['new'] != then['new']:
            raise ValueError(f"{now['label']}: value changed since the D preview; re-propose D")
    if fresh.get('operator_calls') != approved.get('operator_calls'):
        raise ValueError(f"{OPERATOR_CALL_LABEL} labels changed since the D preview; re-propose D")
    return fresh


def _verify_readback_character_caps(plan_result: dict, after: dict, policy: dict) -> None:
    """Use current policy and actual table columns, not caller-supplied plan limits."""
    caps = _deck_character_caps(policy)
    pages = [page for page in after['slides'] if page['objectId'] == plan_result['slide_object_id']]
    if len(pages) != 1:
        raise ValueError('readback: expected one target slide')
    slide = Slide(pages[0])
    settings = policy['forecast']['deck']
    for group, header, capacity, extra in [('CORE', CORE_HEADER, settings['core_rows'], 0),
                                           ('BACKUP', BACKUP_HEADER, settings['backup_rows'], 1)]:
        _, rows = slide.table(group, lambda rows, header=header: rows[0] == header)
        if len(rows) != 1 + capacity + extra:
            raise ValueError(f'readback: {group} table capacity differs from policy')
        for index, row in enumerate(rows[1:1 + capacity], 1):
            for column, value in enumerate(row):
                cap = _deck_column_character_cap(group, column, caps)
                if value:
                    short_text(value, f'readback: {group}[{index}][{column + 1}]', cap)
    _, support = slide.labelled_value('SUPPORT NEEDED', money_value=False)
    lines = support.split('\n')
    if len(lines) > 3:
        raise ValueError('readback: SUPPORT NEEDED has more than 3 lines')
    for index, value in enumerate(lines, 1):
        short_text(value, f'readback: SUPPORT NEEDED[{index}]', caps['cell_character_cap'])


def verify(plan_result, before, after, policy=None):
    """Readback: every field shows its new value and nothing else changed on any slide."""
    if after.get('presentationId') != plan_result['presentation_id']:
        raise ValueError('readback: different presentation')
    if [slide['objectId'] for slide in after.get('slides', [])] != [slide['objectId'] for slide in before.get('slides', [])]:
        raise ValueError('readback: slides added, removed or reordered')
    targets = {(entry['object_id'], tuple(entry['cell']) if entry['cell'] else None): entry
               for entry in plan_result['fields']}
    for old_page, new_page in zip(before['slides'], after['slides']):
        old, new = page_text(old_page), page_text(new_page)
        if set(old) != set(new):
            raise ValueError(f"readback: elements changed on slide {new_page['objectId']}")
        for key, value in new.items():
            if new_page['objectId'] == plan_result['slide_object_id'] and key in targets:
                if value != targets[key]['new']:
                    raise ValueError(f"readback: {targets[key]['label']} mismatch")
            elif value != old[key]:
                raise ValueError(f"readback: text outside the planned fields changed on slide {new_page['objectId']}")
    if policy is None:
        policy = yaml.safe_load((ROOT / '_core/policy.yaml').read_text())
    _verify_readback_character_caps(plan_result, after, policy)
    return {'readback': 'passed', 'slide_object_id': plan_result['slide_object_id'],
            'fields': len(plan_result['fields'])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    planner = commands.add_parser('plan')
    for option in ('presentation', 'forecast', 'reviewed', 'input', 'coverage'):
        planner.add_argument('--' + option, required=True)
    planner.add_argument('--approved')
    planner.add_argument('--policy', default=ROOT / '_core/policy.yaml')
    checker = commands.add_parser('verify')
    for option in ('plan', 'before', 'after'):
        checker.add_argument('--' + option, required=True)
    checker.add_argument('--policy', default=ROOT / '_core/policy.yaml')
    args = parser.parse_args(argv)
    load = lambda path: json.loads(Path(path).read_text())
    try:
        with open(args.policy) as stream:
            policy = yaml.safe_load(stream)
        if args.command == 'plan':
            output = plan(load(args.presentation), load(args.forecast), load(args.reviewed), load(args.input), policy,
                          coverage=load(args.coverage))
            if args.approved:
                output = check_approved(output, load(args.approved))
        else:
            output = verify(load(args.plan), load(args.before), load(args.after), policy)
    except (ValueError, OSError, KeyError, TypeError, IndexError, AttributeError) as exc:
        print(f'forecast_deck: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
