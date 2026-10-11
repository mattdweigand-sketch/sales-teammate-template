#!/usr/bin/env python3
"""Check fixed predicates and sum reviewed amounts; interpretation stays with review.

Usage: forecast_math.py --input reviewed.json [--tracking] [--policy ../policy.yaml]
Input: as_of (ISO date), quarter, booked[{Id,ARR__c}],
deals[{Id,ARR__c,StageName,CloseDate,last_activity_date,bucket,action,buyer_date,evidence,
       buyer_delay_date,buyer_delay_evidence,blockers[{description,owner,date,evidence}]}],
pull_ins[{Id,ARR__c,StageName,CloseDate,action,buyer_date,evidence}]. Amounts and targets use policy.forecast.
last_activity_date is the reviewed latest activity across allowed sources (ISO date or null).
For S3 commit, review establishes a buyer-named signature/decision date; code checks only non-null and in-quarter.
Review identifies buyer-side obstacles to signing and buyer delay evidence. Code checks their structure,
the quarter-end delay exclusion and Commit blocker owner/date gate. Pull-in evidence meaning remains reviewed.
A deal that fails one of those two reviewed eligibility predicates is held, not an error. The run completes with
status incomplete, the held row appears once under held with its original facts, failed_predicate and held_amount,
and it contributes to no bucket-dependent sum (commit, upside, call, path, buffer). Structural errors still raise.
Optional operator_call[{deal,bucket,predicate,reason,approved_turn}] carries Operator's typed per-deal override from the
Forecasting thread. It overrides only the named predicate on the named deal and bucket. The row then counts once
in its bucket and appears under operator_calls labeled "Operator's call" with the failed predicate and approval reference.
Every eligibility predicate is evaluated. A row that also fails another predicate stays held with the remaining
failures under failed_predicates, and the applied override recorded on the held row.
A missing or nonmatching override leaves the row held. Identity, amount, scope and structure checks still apply.
Only pull-ins have a CloseDate bucket predicate; they have no recent-activity predicate. This is not full bucket validation.
qualified_pipeline sums open deals at or above policy.forecast.open_min_stage with in-quarter CloseDate, excluding booked.
Held rows keep that original qualified_pipeline scope.
Optional preview[{Id,ARR__c or null}] contains every next-quarter row. Preview IDs are unique,
may overlap pull_ins, and cannot overlap booked or deals. Missing amounts are not zero.
Output monetary values are decimal strings. Pull-ins never enter call or buffer.
When supplied, preview returns quarter, count, sum, missing_amount_count, top_three, and target.
Tracking input is as_of (ISO date), records, and optional previous snapshot.
Records carry Id, CloseDate, IsClosed, IsWon, ForecastCategoryName, and the policy amount field.
Open records also require StageName; policy.forecast.open_min_stage gates open pipeline, coverage and qualified_pipeline.
Forward tracking also requires CreatedDate with an offset on every current record.
Tracking returns quarter and year metrics, forward coverage, created ARR, alerts, material_change, and a thread snapshot.
Snapshots retain the stage floor; a missing or different prior floor yields basis_change, not a comparable movement baseline.
A previously open Id missing from the current read is never inferred closed or moved. Reread it, or list it under
unavailable_prior as {Id, reason}. Listed Ids are returned, the comparison stays incomplete, material_change stays true,
and the snapshot carries those prior rows and baseline_as_of, the last complete baseline, into the next comparison.
"""
import argparse
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

import yaml


HOLD_PREDICATES = {
    'buyer_delay_past_quarter_end': 'buyer delay past quarter end rejects commit and upside',
    'commit_blocker_owner_date': 'commit blocker needs a named owner and date',
}
OPERATOR_CALL_KEYS = {'deal', 'bucket', 'predicate', 'reason', 'approved_turn'}
OPERATOR_CALL_LABEL = "Operator's call"


def money(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('amount must be a reviewed number, not Boolean/null')
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('invalid amount') from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError('amount must be finite and nonnegative')
    return amount


def calculate(data, policy):
    fp = policy['forecast']
    floor = forecast_stage_floor(fp)
    quarter = data.get('quarter', '')
    if not re.fullmatch(r'\d{4}-Q[1-4]', quarter):
        raise ValueError('quarter must be YYYY-Q1..Q4')
    try:
        as_of = tracking_date(data.get('as_of'))
    except (TypeError, ValueError) as exc:
        raise ValueError('as_of must be an ISO date') from exc
    year, quarter_number = map(int, quarter.split('-Q'))
    start = date(year, (quarter_number - 1) * 3 + 1, 1)
    next_start = date(year + (quarter_number == 4), quarter_number % 4 * 3 + 1, 1)
    after_next = date(next_start.year + 1, 1, 1) if next_start.month == 10 else date(next_start.year, next_start.month + 3, 1)
    target = money(fp.get('targets', {}).get(quarter, fp['target_default']))
    field = fp['amount_field']
    seen, amounts, holds = set(), {}, {}
    for group in ('booked', 'deals', 'pull_ins'):
        if not isinstance(data.get(group), list):
            raise ValueError(f'{group} must be a list (empty allowed)')
        for row in data[group]:
            identity = row.get('Id')
            if not isinstance(identity,str) or not identity or identity in seen:
                raise ValueError('each Opportunity needs a unique Id across all lists')
            seen.add(identity)
            if group == 'deals' and row.get('bucket') not in ('commit','upside','excluded'):
                raise ValueError(f'{identity}: unsupported reviewed bucket')
            if group == 'deals':
                failures = reviewed_bucket_predicates(row, next_start)
                if failures:
                    holds[identity] = failures
            if group in ('deals', 'pull_ins'):
                fixed_predicates(row, group, fp, as_of, start, next_start, after_next)
            if group == 'pull_ins' or (group == 'deals' and row['bucket'] == 'upside'):
                if not isinstance(row.get('action'), str) or not row['action'].strip():
                    raise ValueError(f'{identity}: needs a reviewed action')
                if 'buyer_date' not in row:
                    raise ValueError(f'{identity}: needs buyer_date (null if unknown)')
                if row['buyer_date'] is not None:
                    try:
                        date.fromisoformat(row['buyer_date'])
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f'{identity}: buyer_date must be an ISO date or null') from exc
                if not row.get('evidence'):
                    raise ValueError(f'{identity}: needs source evidence')
            value = row.get(field)
            try:
                amounts[identity] = Decimal(0) if group=='deals' and row['bucket']=='excluded' and value is None else money(value)
            except ValueError as exc:
                raise ValueError(f'{identity}: {field} {exc}') from exc
    held, operator_calls = apply_operator_calls(data, holds, amounts, field)
    held_ids = {row['Id'] for row in held}
    booked = sum((amounts[r['Id']] for r in data['booked']), Decimal(0))
    commit = sum((amounts[r['Id']] for r in data['deals'] if r['bucket']=='commit' and r['Id'] not in held_ids), Decimal(0))
    upsides = sorted((r for r in data['deals'] if r['bucket']=='upside' and r['Id'] not in held_ids),
                     key=lambda r:(-amounts[r['Id']],r['Id']))
    upside = sum((amounts[r['Id']] for r in upsides), Decimal(0))
    call, path, covered = booked + commit, [], Decimal(0)
    gap = target - call
    for row in upsides:
        if covered >= gap:
            break
        covered += amounts[row['Id']]
        path.append({**row, field:format(amounts[row['Id']], 'f'), 'cumulative_upside':format(covered,'f')})
    qualified = Decimal(0)
    for row in data['deals']:
        stage = opportunity_stage(row)
        closed = row.get('IsClosed', False)
        if not isinstance(closed, bool):
            raise ValueError(f"{row['Id']}: IsClosed must be Boolean when supplied")
        if stage < floor or closed:
            continue
        try:
            close_date = tracking_date(row.get('CloseDate'))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{row['Id']}: qualified_pipeline needs an ISO CloseDate") from exc
        if start <= close_date < next_start:
            try:
                qualified += money(row.get(field))
            except ValueError as exc:
                raise ValueError(f"{row['Id']}: qualified_pipeline needs {field}: {exc}") from exc
    totals = {'target':target,'booked':booked,'commit':commit,'call':call,'upside':upside,'gap':gap,
              'qualified_pipeline':qualified,
              'buffer':max(call+upside-target,Decimal(0)),'path_shortfall':max(gap-covered,Decimal(0))}
    result = {'quarter':quarter, 'status': 'incomplete' if held else 'complete',
              **{k:format(v,'f') for k,v in totals.items()},'path_to_target':path,
              'pull_ins':[{**r,field:format(amounts[r['Id']],'f')} for r in sorted(data['pull_ins'],key=lambda r:(-amounts[r['Id']],r['Id']))],
              'held': held, 'operator_calls': operator_calls}
    if 'preview' in data:
        current_ids = {row['Id'] for group in ('booked', 'deals') for row in data[group]}
        result['preview'] = calculate_preview(data['preview'], quarter, fp, current_ids)
    return result


def reviewed_operator_calls(data, deal_ids):
    """Structure of Operator's typed overrides. Approval authority stays in the Forecasting thread, not here."""
    entries = data.get('operator_call', [])
    if not isinstance(entries, list):
        raise ValueError('operator_call must be a list of reviewed per-deal overrides (empty allowed)')
    calls = {}
    for index, entry in enumerate(entries):
        label = f'operator_call[{index}]'
        if not isinstance(entry, dict) or set(entry) != OPERATOR_CALL_KEYS:
            raise ValueError(f'{label} needs exactly deal, bucket, predicate, reason and approved_turn')
        for key in sorted(OPERATOR_CALL_KEYS):
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise ValueError(f'{label}.{key} must be a nonempty string')
        if entry['deal'] not in deal_ids:
            raise ValueError(f'{label}.deal is not a current-quarter deal in this input')
        if entry['deal'] in calls:
            raise ValueError(f'{label}.deal duplicates an earlier override')
        if entry['bucket'] not in ('commit', 'upside'):
            raise ValueError(f'{label}.bucket must be commit or upside')
        if entry['predicate'] not in HOLD_PREDICATES:
            raise ValueError(f'{label}.predicate must be one of ' + ', '.join(sorted(HOLD_PREDICATES)))
        calls[entry['deal']] = entry
    return calls


def apply_operator_calls(data, holds, amounts, field):
    """Each held deal appears once, either held or overridden by the matching reviewed operator_call."""
    calls = reviewed_operator_calls(data, {row['Id'] for row in data['deals']})
    held, operator_calls = [], []
    for row in data['deals']:
        failures = holds.get(row['Id'])
        if not failures:
            continue
        call = calls.get(row['Id'])
        matched = call is not None and call['bucket'] == row['bucket'] and call['predicate'] in failures
        remaining = [key for key in failures if not (matched and key == call['predicate'])]
        shown = {**row, field: format(amounts[row['Id']], 'f')}
        if matched and not remaining:
            operator_calls.append({**shown, 'failed_predicate': call['predicate'], 'label': OPERATOR_CALL_LABEL, 'operator_call': call})
            continue
        held.append({**shown, 'failed_predicate': remaining[0], 'failed_predicates': remaining,
                     'held_amount': format(amounts[row['Id']], 'f'), 'hold': HOLD_PREDICATES[remaining[0]],
                     **({'operator_call': call} if matched else {'unmatched_operator_call': call} if call is not None else {})})
    return held, operator_calls


def opportunity_stage(row):
    stage_name = row.get('StageName')
    match = re.match(r'S([0-5])(?:\b|\s|-)', stage_name) if isinstance(stage_name, str) else None
    if not match:
        raise ValueError(f"{row['Id']}: StageName must map to S0..S5")
    return int(match.group(1))


def reviewed_bucket_predicates(row: dict, next_start: date) -> list[str]:
    """Missing review is needs-input, not evidence that no signing obstacle exists.

    Evaluates every eligibility predicate and returns each failed key that holds the row, in HOLD_PREDICATES order."""
    identity = row['Id']
    for key in ('buyer_delay_date', 'buyer_delay_evidence', 'blockers'):
        if key not in row:
            raise ValueError(f'{identity}: needs-input: missing reviewed {key}')
    delay = row['buyer_delay_date']
    evidence = row['buyer_delay_evidence']
    if evidence is not None and (not isinstance(evidence, str) or not evidence.strip()):
        raise ValueError(f'{identity}: needs-input: buyer_delay_evidence must be a source reference or null')
    if delay is not None:
        try:
            delay = tracking_date(delay)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{identity}: needs-input: buyer_delay_date must be an ISO date or null') from exc
        if evidence is None:
            raise ValueError(f'{identity}: needs-input: buyer_delay_date needs source evidence')
    blockers = row['blockers']
    if not isinstance(blockers, list):
        raise ValueError(f'{identity}: needs-input: blockers must be a reviewed list')
    unowned = False
    for index, blocker in enumerate(blockers):
        label = f'{identity}: needs-input: blockers[{index}]'
        if not isinstance(blocker, dict) or not {'description', 'owner', 'date', 'evidence'} <= blocker.keys():
            raise ValueError(f'{label} needs description, owner, date and evidence')
        for key in ('description', 'evidence'):
            if not isinstance(blocker[key], str) or not blocker[key].strip():
                raise ValueError(f'{label}.{key} must be a nonempty reviewed source value')
        owner = blocker['owner']
        if owner is not None and (not isinstance(owner, str) or not owner.strip()):
            raise ValueError(f'{label}.owner must be a reviewed name or null')
        deadline = blocker['date']
        if deadline is not None:
            try:
                tracking_date(deadline)
            except (TypeError, ValueError) as exc:
                raise ValueError(f'{label}.date must be an ISO date or null') from exc
        unowned |= owner is None or deadline is None
    failures = []
    if row['bucket'] in ('commit', 'upside') and delay is not None and delay >= next_start:
        failures.append('buyer_delay_past_quarter_end')
    if row['bucket'] == 'commit' and unowned:
        failures.append('commit_blocker_owner_date')
    return failures


def fixed_predicates(row, group, forecast, as_of, start, next_start, after_next):
    identity = row['Id']
    stage = opportunity_stage(row)
    if group == 'deals' and row['bucket'] == 'excluded':
        return
    if group == 'pull_ins':
        if stage < 2:
            raise ValueError(f'{identity}: pull-in requires stage S2..S5')
        try:
            close_date = tracking_date(row.get('CloseDate'))
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{identity}: pull-in CloseDate must be an ISO date') from exc
        if not next_start <= close_date < after_next:
            raise ValueError(f'{identity}: pull-in CloseDate must be in the next quarter')
    else:
        if row['bucket'] == 'commit':
            if stage not in (3, 4, 5):
                raise ValueError(f'{identity}: commit requires S4/S5 or S3 with an in-quarter buyer_date')
            if stage == 3:
                try:
                    buyer_date = tracking_date(row.get('buyer_date'))
                except (TypeError, ValueError) as exc:
                    raise ValueError(f'{identity}: S3 commit requires a non-null ISO buyer_date') from exc
                if not start <= buyer_date < next_start:
                    raise ValueError(f'{identity}: S3 commit buyer_date must be inside the quarter')
        elif stage not in (2, 3, 4, 5):
            raise ValueError(f'{identity}: upside requires stage S2 through S5')
        try:
            activity = tracking_date(row.get('last_activity_date'))
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{identity}: last_activity_date must be a non-null ISO date') from exc
        if not 0 <= (as_of - activity).days <= forecast['activity_days']:
            raise ValueError(f'{identity}: last_activity_date must be within forecast.activity_days of as_of')
    if row.get(forecast['amount_field']) is None:
        raise ValueError(f"{identity}: {forecast['amount_field']} must be present")


def calculate_preview(rows, quarter, forecast, current_ids):
    if not isinstance(rows, list):
        raise ValueError('preview must be a list (empty allowed)')
    field = forecast['amount_field']
    seen, present, missing = set(), [], 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('each preview row must be an object')
        identity = row.get('Id')
        if not isinstance(identity, str) or not identity or identity in seen or identity in current_ids:
            raise ValueError('preview needs unique Ids that do not overlap booked or deals')
        seen.add(identity)
        if field not in row:
            raise ValueError(f'{identity}: preview needs {field} (null if missing)')
        if row[field] is None:
            missing += 1
        else:
            present.append((identity, money(row[field])))
    year, quarter_number = map(int, quarter.split('-Q'))
    next_quarter = f'{year + (quarter_number == 4)}-Q{quarter_number % 4 + 1}'
    target = money(forecast.get('targets', {}).get(next_quarter, forecast['target_default']))
    ranked = sorted(present, key=lambda item: (-item[1], item[0]))
    return {'quarter': next_quarter, 'count': len(rows),
            'sum': format(sum((amount for _, amount in present), Decimal(0)), 'f'),
            'missing_amount_count': missing,
            'top_three': [{'Id': identity, field: format(amount, 'f')} for identity, amount in ranked[:3]],
            'target': format(target, 'f')}


def tracking_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('tracking dates must be YYYY-MM-DD')
    return date.fromisoformat(value)


def tracking_snapshot(data, field, *, require_stage=True):
    if not isinstance(data, dict):
        raise ValueError('tracking input must be an object')
    as_of = tracking_date(data.get('as_of'))
    if not isinstance(data.get('records'), list):
        raise ValueError('tracking records must be a complete list (empty allowed)')
    records, seen = [], set()
    for row in data['records']:
        if not isinstance(row, dict):
            raise ValueError('tracking records must be objects')
        identity = row.get('Id')
        if not isinstance(identity, str) or not identity.strip() or identity in seen:
            raise ValueError('tracking records need unique Opportunity Ids')
        seen.add(identity)
        close_date = tracking_date(row.get('CloseDate'))
        if any(type(row.get(key)) is not bool for key in ('IsClosed', 'IsWon')):
            raise ValueError(f'{identity}: IsClosed and IsWon must be Boolean')
        if row['IsWon'] and not row['IsClosed']:
            raise ValueError(f'{identity}: a won Opportunity must be closed')
        if not row['IsClosed'] and require_stage:
            opportunity_stage(row)
        value = row.get(field)
        records.append({'Id': identity, 'CloseDate': close_date.isoformat(),
                        'IsClosed': row['IsClosed'], 'IsWon': row['IsWon'],
                        'ForecastCategoryName': row.get('ForecastCategoryName'),
                        field: None if value is None else format(money(value).normalize(), 'f')})
        if not row['IsClosed'] and 'StageName' in row:
            records[-1]['StageName'] = row['StageName']
        if 'CreatedDate' in row:
            records[-1]['CreatedDate'] = row['CreatedDate']
    return {'as_of': as_of.isoformat(), 'records': sorted(records, key=lambda row: row['Id'])}


def forecast_stage_floor(forecast):
    value = forecast.get('open_min_stage')
    match = re.fullmatch(r'S([0-5])', value) if isinstance(value, str) else None
    if not match:
        raise ValueError('policy.forecast.open_min_stage must be S0..S5')
    return int(match.group(1))


def tracking_open_rows(records, floor):
    return [row for row in records if not row['IsClosed'] and opportunity_stage(row) >= floor]


def tracking_quarter(as_of):
    quarter_number = (as_of.month - 1) // 3 + 1
    quarter = f'{as_of.year}-Q{quarter_number}'
    start = date(as_of.year, (quarter_number - 1) * 3 + 1, 1)
    next_start = date(as_of.year + 1, 1, 1) if quarter_number == 4 else date(as_of.year, start.month + 3, 1)
    return quarter, start, next_start - timedelta(days=1)


def tracking_period(records, field, as_of, start, end, target, settings, *, open_floor, year=False, target_to_date=None):
    booked_rows = [r for r in records if r['IsWon'] and start <= tracking_date(r['CloseDate']) <= end]
    open_start = as_of if year else start
    open_rows = [row for row in tracking_open_rows(records, open_floor)
                 if open_start <= tracking_date(row['CloseDate']) <= end]
    # Missing ARR must not turn an unknown amount into zero coverage or bookings.
    booked = sum((money(r[field]) for r in booked_rows), Decimal(0))
    pipeline = sum((money(r[field]) for r in open_rows), Decimal(0))
    largest = sorted(open_rows, key=lambda row: (-money(row[field]), row['Id']))[:2]
    largest_amount = sum((money(r[field]) for r in largest), Decimal(0))
    total_days = (end - start).days + 1
    elapsed_days = (as_of - start).days + 1
    remaining_days = (end - as_of).days
    expected = target * Decimal(elapsed_days) / Decimal(total_days) if target_to_date is None else target_to_date
    gap = max(target - booked, Decimal(0))
    behind = max((expected - booked) / expected * 100, Decimal(0)) if expected else None
    coverage = pipeline / gap if gap else None
    without_largest = (pipeline - largest_amount) / gap if gap else None
    required = gap * 7 / remaining_days if remaining_days else (Decimal(0) if not gap else None)

    def number(value, places='0.01'):
        return None if value is None else format(value.quantize(Decimal(places)), 'f')

    return {'start': start.isoformat(), 'end': end.isoformat(),
            'target': number(target), 'booked': number(booked), 'gap': number(gap),
            'elapsed_days': elapsed_days, 'total_days': total_days, 'remaining_days': remaining_days,
            'linear_pace': number(expected), 'pace_behind_percent': number(behind),
            'required_per_week': number(required), 'open_pipeline': number(pipeline),
            'coverage': number(coverage, '0.0001'),
            'largest_two_ids': [r['Id'] for r in largest], 'largest_two_amount': number(largest_amount),
            'largest_two_share_percent': number(largest_amount / pipeline * 100 if pipeline else None),
            'coverage_without_largest_two': number(without_largest, '0.0001'),
            'coverage_alert': coverage is not None and coverage < money(settings['coverage_min']),
            'pace_alert': behind is not None and behind > money(settings['pace_behind_alert_percent']),
            'booked_ids': [r['Id'] for r in booked_rows], 'open_ids': [r['Id'] for r in open_rows]}


def tracking_totals(snapshot, forecast):
    as_of = tracking_date(snapshot['as_of'])
    quarter, start, end = tracking_quarter(as_of)
    quarter_number = (as_of.month - 1) // 3 + 1

    def target(key):
        return money(forecast.get('targets', {}).get(key, forecast['target_default']))

    args = (snapshot['records'], forecast['amount_field'], as_of)
    settings = forecast['tracking']
    floor = forecast_stage_floor(forecast)
    year_target_to_date = sum((target(f'{as_of.year}-Q{quarter_index}')
                               for quarter_index in range(1, quarter_number)), Decimal(0))
    year_target_to_date += target(quarter) * Decimal((as_of - start).days + 1) / Decimal((end - start).days + 1)
    return {
        'quarter': {'period': quarter, **tracking_period(*args, start, end, target(quarter), settings, open_floor=floor)},
        'year': {'period': str(as_of.year), **tracking_period(
            *args, date(as_of.year, 1, 1), date(as_of.year, 12, 31),
            sum((target(f'{as_of.year}-Q{q}') for q in range(1, 5)), Decimal(0)), settings,
            open_floor=floor, year=True, target_to_date=year_target_to_date)},
    }


def forward_tracking(snapshot, forecast):
    settings = forecast['tracking']
    if 'forward_quarters' not in settings:
        return [], None
    count, window = settings['forward_quarters'], settings['created_arr_window_days']
    if type(count) is not int or count <= 0 or type(window) is not int or window <= 0:
        raise ValueError('forward quarter count and created ARR window must be positive integers')
    as_of = tracking_date(snapshot['as_of'])
    field = forecast['amount_field']
    quarter_index = as_of.year * 4 + (as_of.month - 1) // 3
    forward = []
    required_total = Decimal(0)
    open_records = tracking_open_rows(snapshot['records'], forecast_stage_floor(forecast))
    for offset in range(1, count + 1):
        year, quarter_index_in_year = divmod(quarter_index + offset, 4)
        start = date(year, quarter_index_in_year * 3 + 1, 1)
        next_year, next_index = divmod(quarter_index + offset + 1, 4)
        end = date(next_year, next_index * 3 + 1, 1) - timedelta(days=1)
        quarter = f'{year}-Q{quarter_index_in_year + 1}'
        target = money(forecast.get('targets', {}).get(quarter, forecast['target_default']))
        rows = [row for row in snapshot['records'] if start.isoformat() <= row['CloseDate'] <= end.isoformat()]
        booked = sum((money(row[field]) for row in rows if row['IsWon']), Decimal(0))
        open_rows = [row for row in open_records if start.isoformat() <= row['CloseDate'] <= end.isoformat()]
        pipeline = sum((money(row[field]) for row in open_rows), Decimal(0))
        gap = max(target - booked, Decimal(0))
        coverage = pipeline / gap if gap else None
        shortfall = max(money(settings['coverage_min']) * gap - pipeline, Decimal(0))
        days = (start - as_of).days
        required = shortfall * 7 / days
        required_total += required
        forward.append({'period': quarter, 'start': start.isoformat(), 'end': end.isoformat(),
                        'target': format(target.quantize(Decimal('0.01')), 'f'),
                        'booked': format(booked.quantize(Decimal('0.01')), 'f'),
                        'open_pipeline': format(pipeline.quantize(Decimal('0.01')), 'f'),
                        'coverage': None if coverage is None else format(coverage.quantize(Decimal('0.0001')), 'f'),
                        'coverage_alert': coverage is not None and coverage < money(settings['coverage_min']),
                        'coverage_shortfall': format(shortfall.quantize(Decimal('0.01')), 'f'),
                        'days_until_start': days, 'required_created_arr_per_week': format(required.quantize(Decimal('0.01')), 'f'),
                        'open_ids': [row['Id'] for row in open_rows]})
    timezone = ZoneInfo(settings['pace_report']['tz'])
    cutoff = as_of - timedelta(days=window - 1)
    created_rows = []
    for row in snapshot['records']:
        value = row.get('CreatedDate')
        if not isinstance(value, str):
            raise ValueError(f"{row['Id']}: CreatedDate must be an ISO timestamp with offset")
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if instant.tzinfo is None:
            raise ValueError(f"{row['Id']}: CreatedDate must include an offset")
        created_date = instant.astimezone(timezone).date()
        if created_date > as_of:
            raise ValueError(f"{row['Id']}: CreatedDate cannot be after as_of")
        if created_date >= cutoff:
            created_rows.append(row)
    created = sum((money(row[field]) for row in created_rows), Decimal(0))
    return forward, {'start': cutoff.isoformat(), 'end': as_of.isoformat(), 'window_days': window,
                     'amount': format(created.quantize(Decimal('0.01')), 'f'),
                     'opportunity_ids': [row['Id'] for row in created_rows],
                     'required_per_week': format(required_total.quantize(Decimal('0.01')), 'f'),
                     'below_required': created < required_total}


def reviewed_unavailable_prior(data, old, current_ids):
    """Previously open rows missing from the current read stay unavailable, never closed or moved.

    Each must be reread or listed under `unavailable_prior` with a reviewed reason. Returns the carried prior rows.
    """
    missing = {identity: row for identity, row in old.items() if not row['IsClosed'] and identity not in current_ids}
    entries = data.get('unavailable_prior', [])
    if not isinstance(entries, list):
        raise ValueError('unavailable_prior must be a list of {Id, reason} objects')
    carried = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'Id', 'reason'}:
            raise ValueError('unavailable_prior entries need exactly Id and reason')
        identity, reason = entry['Id'], entry['reason']
        if not isinstance(identity, str) or not identity.strip() or identity in carried:
            raise ValueError('unavailable_prior needs unique Opportunity Ids')
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f'{identity}: unavailable_prior needs a reviewed reason')
        if identity not in missing:
            raise ValueError(f'{identity}: unavailable_prior names an Opportunity that is not a missing previously open record')
        carried[identity] = {key: value for key, value in missing[identity].items() if key != 'reason'}
        carried[identity]['reason'] = reason.strip()
    unlisted = sorted(set(missing) - set(carried))
    if unlisted:
        raise ValueError('previously open Opportunities must be reread, including those outside the year, '
                         'or listed under unavailable_prior with a reviewed reason: ' + ', '.join(unlisted))
    return [carried[identity] for identity in sorted(carried)]


def carried_prior_rows(previous):
    rows = previous.get('unavailable_prior', []) if isinstance(previous, dict) else []
    if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get('Id'), str)
                                         or type(row.get('IsClosed')) is not bool for row in rows):
        raise ValueError('previous unavailable_prior must carry the prior open rows')
    return rows


def calculate_tracking(data, policy):
    forecast = policy['forecast']
    forecast_stage_floor(forecast)
    floor = forecast['open_min_stage']
    snapshot = tracking_snapshot(data, forecast['amount_field'])
    snapshot['open_min_stage'] = floor
    totals = tracking_totals(snapshot, forecast)
    forward, created_arr = forward_tracking(snapshot, forecast)
    if forward:
        snapshot['forward_targets'] = {row['period']: row['target'] for row in forward}
    snapshot['targets'] = {scope: totals[scope]['target'] for scope in ('quarter', 'year')}
    previous = data.get('previous')
    previous_targets = previous.get('targets') if isinstance(previous, dict) else None
    previous_forward_targets = previous.get('forward_targets') if isinstance(previous, dict) else None
    alerts = []
    basis_change = None
    material_change = True
    unavailable = []
    baseline_as_of = None
    if previous is not None:
        carried = carried_prior_rows(previous)
        baseline_as_of = previous.get('baseline_as_of') if carried else None
        previous_floor = previous.get('open_min_stage') if isinstance(previous, dict) else None
        if previous_floor is not None:
            forecast_stage_floor({'open_min_stage': previous_floor})
        if previous_floor != floor:
            basis_change = {'previous_open_min_stage': previous_floor, 'open_min_stage': floor}
        previous = tracking_snapshot(previous, forecast['amount_field'], require_stage=previous_floor is not None)
        if previous['as_of'] > snapshot['as_of']:
            raise ValueError('previous snapshot cannot be later than as_of')
        old_quarter, old_start, old_end = tracking_quarter(tracking_date(previous['as_of']))
        if baseline_as_of is None:
            baseline_as_of = previous['as_of']
        old = {row['Id']: row for row in carried}
        old.update({row['Id']: row for row in previous['records']})
        current_ids = {row['Id'] for row in snapshot['records']}
        unavailable = reviewed_unavailable_prior(data, old, current_ids)
        if unavailable:
            snapshot['unavailable_prior'] = unavailable
            snapshot['baseline_as_of'] = baseline_as_of
        for row in snapshot['records']:
            prior = old.get(row['Id'])
            in_year = totals['year']['start'] <= row['CloseDate'] <= totals['year']['end']
            if in_year and row['IsClosed'] and (prior is None or not prior['IsClosed'] or prior['IsWon'] != row['IsWon']):
                alerts.append({'kind': 'closed_won' if row['IsWon'] else 'closed_lost',
                               'periods': [scope for scope in ('quarter', 'year')
                                           if totals[scope]['start'] <= row['CloseDate'] <= totals[scope]['end']],
                               'opportunity_ids': [row['Id']]})
            if prior and not prior['IsClosed'] and prior['ForecastCategoryName'] == 'Commit':
                if old_start.isoformat() <= prior['CloseDate'] <= old_end.isoformat() and not (
                        old_start.isoformat() <= row['CloseDate'] <= old_end.isoformat()):
                    alerts.append({'kind': 'commit_left_quarter', 'periods': [old_quarter],
                                   'opportunity_ids': [row['Id']], 'old_date': prior['CloseDate'],
                                   'new_date': row['CloseDate']})
        if basis_change is None and not unavailable:
            previous_totals = tracking_totals(previous, forecast)
            fields = ('period', 'target', 'booked', 'open_pipeline', 'coverage_alert', 'pace_alert')
            material_change = snapshot['records'] != previous['records'] or any(
                totals[scope][key] != previous_totals[scope][key] for scope in ('quarter', 'year') for key in fields)
            if previous_targets is not None and previous_targets != snapshot['targets']:
                material_change = True
            if forward:
                if previous_forward_targets != snapshot['forward_targets'] or any('CreatedDate' not in row for row in previous['records']):
                    material_change = True
                else:
                    old_forward, old_created = forward_tracking(previous, forecast)
                    keys = ('period', 'target', 'booked', 'open_pipeline', 'coverage_alert')
                    material_change |= [[row[key] for key in keys] for row in forward] != [[row[key] for key in keys] for row in old_forward]
                    material_change |= any(created_arr[key] != old_created[key] for key in ('amount', 'opportunity_ids', 'below_required'))
    for scope in ('quarter', 'year'):
        for key in ('coverage', 'pace'):
            if totals[scope][key + '_alert']:
                alerts.append({'kind': key + '_below_target', 'periods': [scope],
                               'opportunity_ids': totals[scope]['open_ids']})
    for row in forward:
        if row['coverage_alert']:
            alerts.append({'kind': 'forward_coverage_below_target', 'periods': [row['period']], 'opportunity_ids': row['open_ids']})
    if created_arr and created_arr['below_required']:
        alerts.append({'kind': 'created_arr_below_required', 'periods': [row['period'] for row in forward],
                       'opportunity_ids': created_arr['opportunity_ids']})
    return {'as_of': snapshot['as_of'], 'amount_field': forecast['amount_field'], **totals,
            'baseline_available': previous is not None, 'baseline_as_of': baseline_as_of, 'material_change': material_change,
            'comparison_available': previous is not None and basis_change is None and not unavailable,
            'basis_change': basis_change, 'unavailable_prior': unavailable,
            'forward_quarters': forward, 'created_arr': created_arr, 'alerts': alerts, 'snapshot': snapshot}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--tracking', action='store_true', help='Read-only quarter and year pace tracking')
    parser.add_argument('--policy',type=Path,default=Path(__file__).resolve().parents[5]/'_core'/'policy.yaml')
    args=parser.parse_args(argv)
    try:
        calculation = calculate_tracking if args.tracking else calculate
        result=calculation(json.loads(args.input.read_text()),yaml.safe_load(args.policy.read_text()))
    except (OSError, ValueError, TypeError, KeyError, InvalidOperation) as exc:
        print(f'Forecast calculation failed: {exc}',file=sys.stderr)
        return 1
    print(json.dumps(result,indent=2))
    return 0


if __name__=='__main__':
    sys.exit(main())
