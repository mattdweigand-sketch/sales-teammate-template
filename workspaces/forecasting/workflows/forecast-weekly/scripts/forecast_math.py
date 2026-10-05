#!/usr/bin/env python3
"""Sum reviewed forecast amounts; bucket interpretation remains with the workflow.

Usage: forecast_math.py --input reviewed.json [--tracking] [--policy ../policy.yaml]
Input: quarter, booked[{Id,ARR__c}], deals[{Id,ARR__c,bucket,action,buyer_date,evidence}],
pull_ins[{Id,ARR__c,action,buyer_date,evidence}]. The amount field and targets come from policy.forecast.
Optional preview[{Id,ARR__c or null}] contains every next-quarter row. Preview IDs are unique,
may overlap pull_ins, and cannot overlap booked or deals. Missing amounts are not zero.
Output monetary values are decimal strings. Pull-ins never enter call or buffer.
When supplied, preview returns quarter, count, sum, missing_amount_count, top_three, and target.
Tracking input is as_of (ISO date), records, and optional previous snapshot.
Records carry Id, CloseDate, IsClosed, IsWon, ForecastCategoryName, and the policy amount field.
Forward tracking also requires CreatedDate with an offset on every current record.
Tracking returns quarter and year metrics, forward coverage, created ARR, alerts, material_change, and a thread snapshot.
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
    quarter = data.get('quarter', '')
    if not re.fullmatch(r'\d{4}-Q[1-4]', quarter):
        raise ValueError('quarter must be YYYY-Q1..Q4')
    target = money(fp.get('targets', {}).get(quarter, fp['target_default']))
    field = fp['amount_field']
    seen, amounts = set(), {}
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
            amounts[identity] = Decimal(0) if group=='deals' and row['bucket']=='excluded' and value is None else money(value)
    booked = sum((amounts[r['Id']] for r in data['booked']), Decimal(0))
    commit = sum((amounts[r['Id']] for r in data['deals'] if r['bucket']=='commit'), Decimal(0))
    upsides = sorted((r for r in data['deals'] if r['bucket']=='upside'),key=lambda r:(-amounts[r['Id']],r['Id']))
    upside = sum((amounts[r['Id']] for r in upsides), Decimal(0))
    call, path, covered = booked + commit, [], Decimal(0)
    gap = target - call
    for row in upsides:
        if covered >= gap:
            break
        covered += amounts[row['Id']]
        path.append({**row, field:format(amounts[row['Id']], 'f'), 'cumulative_upside':format(covered,'f')})
    totals = {'target':target,'booked':booked,'commit':commit,'call':call,'upside':upside,'gap':gap,
              'buffer':max(call+upside-target,Decimal(0)),'path_shortfall':max(gap-covered,Decimal(0))}
    result = {'quarter':quarter, **{k:format(v,'f') for k,v in totals.items()},'path_to_target':path,
              'pull_ins':[{**r,field:format(amounts[r['Id']],'f')} for r in sorted(data['pull_ins'],key=lambda r:(-amounts[r['Id']],r['Id']))]}
    if 'preview' in data:
        current_ids = {row['Id'] for group in ('booked', 'deals') for row in data[group]}
        result['preview'] = calculate_preview(data['preview'], quarter, fp, current_ids)
    return result


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


def tracking_snapshot(data, field):
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
        value = row.get(field)
        records.append({'Id': identity, 'CloseDate': close_date.isoformat(),
                        'IsClosed': row['IsClosed'], 'IsWon': row['IsWon'],
                        'ForecastCategoryName': row.get('ForecastCategoryName'),
                        field: None if value is None else format(money(value).normalize(), 'f')})
        if 'CreatedDate' in row:
            records[-1]['CreatedDate'] = row['CreatedDate']
    return {'as_of': as_of.isoformat(), 'records': sorted(records, key=lambda row: row['Id'])}


def tracking_period(records, field, as_of, start, end, target, settings, *, year=False, target_to_date=None):
    booked_rows = [r for r in records if r['IsWon'] and start <= tracking_date(r['CloseDate']) <= end]
    open_start = as_of if year else start
    open_rows = [r for r in records if not r['IsClosed'] and open_start <= tracking_date(r['CloseDate']) <= end]
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
    quarter_number = (as_of.month - 1) // 3 + 1
    quarter = f'{as_of.year}-Q{quarter_number}'
    start = date(as_of.year, (quarter_number - 1) * 3 + 1, 1)
    next_start = date(as_of.year + 1, 1, 1) if quarter_number == 4 else date(as_of.year, start.month + 3, 1)
    end = next_start - timedelta(days=1)

    def target(key):
        return money(forecast.get('targets', {}).get(key, forecast['target_default']))

    args = (snapshot['records'], forecast['amount_field'], as_of)
    settings = forecast['tracking']
    year_target_to_date = sum((target(f'{as_of.year}-Q{quarter_index}')
                               for quarter_index in range(1, quarter_number)), Decimal(0))
    year_target_to_date += target(quarter) * Decimal((as_of - start).days + 1) / Decimal((end - start).days + 1)
    return {
        'quarter': {'period': quarter, **tracking_period(*args, start, end, target(quarter), settings)},
        'year': {'period': str(as_of.year), **tracking_period(
            *args, date(as_of.year, 1, 1), date(as_of.year, 12, 31),
            sum((target(f'{as_of.year}-Q{q}') for q in range(1, 5)), Decimal(0)), settings,
            year=True, target_to_date=year_target_to_date)},
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
    for offset in range(1, count + 1):
        year, quarter_index_in_year = divmod(quarter_index + offset, 4)
        start = date(year, quarter_index_in_year * 3 + 1, 1)
        next_year, next_index = divmod(quarter_index + offset + 1, 4)
        end = date(next_year, next_index * 3 + 1, 1) - timedelta(days=1)
        quarter = f'{year}-Q{quarter_index_in_year + 1}'
        target = money(forecast.get('targets', {}).get(quarter, forecast['target_default']))
        rows = [row for row in snapshot['records'] if start.isoformat() <= row['CloseDate'] <= end.isoformat()]
        booked = sum((money(row[field]) for row in rows if row['IsWon']), Decimal(0))
        pipeline = sum((money(row[field]) for row in rows if not row['IsClosed']), Decimal(0))
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
                        'open_ids': [row['Id'] for row in rows if not row['IsClosed']]})
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


def calculate_tracking(data, policy):
    forecast = policy['forecast']
    snapshot = tracking_snapshot(data, forecast['amount_field'])
    totals = tracking_totals(snapshot, forecast)
    forward, created_arr = forward_tracking(snapshot, forecast)
    if forward:
        snapshot['forward_targets'] = {row['period']: row['target'] for row in forward}
    snapshot['targets'] = {scope: totals[scope]['target'] for scope in ('quarter', 'year')}
    previous = data.get('previous')
    previous_targets = previous.get('targets') if isinstance(previous, dict) else None
    previous_forward_targets = previous.get('forward_targets') if isinstance(previous, dict) else None
    alerts = []
    material_change = True
    if previous is not None:
        previous = tracking_snapshot(previous, forecast['amount_field'])
        if previous['as_of'] > snapshot['as_of']:
            raise ValueError('previous snapshot cannot be later than as_of')
        previous_totals = tracking_totals(previous, forecast)
        old = {row['Id']: row for row in previous['records']}
        current_ids = {row['Id'] for row in snapshot['records']}
        missing = [identity for identity, row in old.items() if not row['IsClosed'] and identity not in current_ids]
        if missing:
            raise ValueError('previously open Opportunities must be reread, including those outside the year')
        for row in snapshot['records']:
            prior = old.get(row['Id'])
            in_year = totals['year']['start'] <= row['CloseDate'] <= totals['year']['end']
            if in_year and row['IsClosed'] and (prior is None or not prior['IsClosed'] or prior['IsWon'] != row['IsWon']):
                alerts.append({'kind': 'closed_won' if row['IsWon'] else 'closed_lost',
                               'periods': [scope for scope in ('quarter', 'year')
                                           if totals[scope]['start'] <= row['CloseDate'] <= totals[scope]['end']],
                               'opportunity_ids': [row['Id']]})
            if prior and not prior['IsClosed'] and prior['ForecastCategoryName'] == 'Commit':
                old_quarter = previous_totals['quarter']
                if old_quarter['start'] <= prior['CloseDate'] <= old_quarter['end'] and not (
                        old_quarter['start'] <= row['CloseDate'] <= old_quarter['end']):
                    alerts.append({'kind': 'commit_left_quarter', 'periods': [old_quarter['period']],
                                   'opportunity_ids': [row['Id']], 'old_date': prior['CloseDate'],
                                   'new_date': row['CloseDate']})
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
            'baseline_available': previous is not None, 'material_change': material_change,
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
