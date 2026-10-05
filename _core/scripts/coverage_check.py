#!/usr/bin/env python3
"""Verify current-run source pages and the narrow queries used by sales workflows.

Run from the sandbox root: coverage_check.py --scope pipeline|pipeline-daily|forecast
--since <ISO datetime with local offset> [--hygiene FILE] [--json] [--policy FILE] [--calls-dir DIR].
--json adds `affected`, the in-scope Opportunity Ids whose proposals must be withheld, or null when unknown.
"""
import argparse
import contextlib
import datetime as dt
import io
import json
import re
import sys
from email.utils import parseaddr
from pathlib import Path

import yaml
from _saved_json import load_saved, resolve_calls_dir

AFFECTED_PREFIX = 'Affected deals: '
DEAL_GAP_PREFIXES = ('Thread read missing: ', 'Gmail missing: ', 'Calendar missing: ',
                     'Contact domain unavailable: ', 'No Contact domain in evidence: ')
SOQL_OBJECTS = re.compile(r'\bFROM\s+(Opportunity|Task|Event|Contact)\b', re.I)
QUOTED_LITERAL = re.compile(r"'([^']+)'")


def normalized(text):
    return ' '.join(re.findall(r'[a-z0-9]+', (text or '').lower()))


def saved_calls(root, since_ts):
    for path in sorted(root.glob('input_*.json'), key=lambda p: (p.stat().st_mtime, p.name)):
        if path.stat().st_mtime < since_ts:
            continue
        try:
            inp = json.loads(path.read_text())
        except (ValueError, OSError):
            yield path, {'invalid_input': True}, path.with_name(path.name.replace('input_', 'output_', 1))
            continue
        yield path, inp, path.with_name(path.name.replace('input_', 'output_', 1))


def read_output(path, since_ts):
    if not path.is_file() or path.stat().st_mtime < since_ts:
        return None, 'missing current-run output'
    try:
        result = load_saved(path)
    except (ValueError, OSError) as exc:
        return None, str(exc)
    if not isinstance(result, dict) or result.get('ready') is False:
        return None, 'failed source result'
    return result, None


def source_page(tool, result):
    key, rows = ('email_results', 'emails') if tool == 'search_email' else ('calendar_event_list', 'events')
    page = result.get(key)
    if result.get('status') not in (None, 'success') or not isinstance(page, dict) or not isinstance(page.get(rows), list):
        return None
    if any(container.get('hasMore') or container.get('has_more') for container in (result,page)) and not (page.get('next_cursor') or result.get('next_cursor')):
        return None
    if page.get('error') or page.get('truncated') or 'invalid' in str(page.get('snippet', '')).lower():
        return None
    return page


def walk_records(obj):
    if isinstance(obj, dict):
        if isinstance(obj.get('records'), list):
            yield from obj['records']
        for value in obj.values():
            yield from walk_records(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_records(value)


def record_type(row):
    return (row.get('attributes') or {}).get('type') if isinstance(row, dict) else None


def stage_num(stage):
    match = re.match(r'S(\d+)(?:\b|\s|-)', stage or '')
    return int(match.group(1)) if match else None


def contact_domains(opp, contacts, internal, generic=frozenset()):
    """Buyer addresses for one Account. Internal and generic (policy.tooling.generic_email_domains) domains never become Account domains."""
    addresses = {str(c['Email']).lower() for c in contacts if c.get('Email') and c.get('AccountId') == opp.get('AccountId')}
    addresses = {a for a in addresses if '@' in a and a.rsplit('@', 1)[1] not in internal and a.rsplit('@', 1)[1] not in generic}
    return addresses, {a.rsplit('@', 1)[1] for a in addresses}


def parse_instant(text):
    try:
        value = dt.datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None
    return value if value.tzinfo else None


def event_cross_check(scope, sf_events, calendars, domains_by_opp, window_start, window_end, owner=None):
    """Corroborate Salesforce Events against retrieved Calendar events. Matching every Event proves nothing about Calendar completeness."""
    matched, uncertain, unmatched, eligible, unmatched_ids = [], [], [], 0, set()
    for opp in scope:
        domains = domains_by_opp[opp['Id']]
        for row in sf_events:
            if owner and row.get('OwnerId') and str(row['OwnerId'])[:15] != str(owner)[:15]:
                continue
            if row.get('WhatId') != opp['Id'] and row.get('AccountId') != opp.get('AccountId'):
                continue
            start = parse_instant(row.get('StartDateTime'))
            if start is None or not window_start <= start <= window_end:
                continue
            eligible += 1
            label = f"{account_name(opp)} · {row.get('Subject') or row['Id']} · {start.date().isoformat()}"
            same_start = [e for e in calendars if (s := parse_instant(e.get('start'))) and abs((s - start).total_seconds()) <= 60]
            if any(any((a.get('email') or '').lower().rsplit('@', 1)[-1] in domains for a in e.get('attendees') or []) for e in same_start):
                matched.append(label)
            elif same_start:
                uncertain.append(label)
                unmatched_ids.add(opp['Id'])
            else:
                unmatched.append(label)
                unmatched_ids.add(opp['Id'])
    return matched, uncertain, unmatched, eligible, unmatched_ids


def calendar_range(args, tz):
    """Tz-aware (start, end) of one search_calendar call, or None when missing or naive."""
    try:
        start = dt.datetime.fromisoformat(args['start_date'].replace('Z', '+00:00'))
        end = dt.datetime.fromisoformat(args['end_date'].replace('Z', '+00:00'))
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    if start.tzinfo is None or end.tzinfo is None or end < start:
        return None
    return start.astimezone(tz), end.astimezone(tz)


def union_gap(ranges, lo, hi):
    """First uncovered instant in [lo, hi] after merging ranges, or None when the union covers it (rules#calendar_search)."""
    cursor = lo
    for start, end in sorted(ranges):
        if start > cursor:
            return cursor
        cursor = max(cursor, end)
        if cursor >= hi:
            return None
    return None if cursor >= hi else cursor


def calendar_covered(account, addresses, queries):
    return any(q.lower() in addresses or normalized(q) == normalized(account) for q in queries)


def account_name(opp):
    return (opp.get('Account') or {}).get('Name') or opp.get('AccountId') or '?'


def activity_scope(groups, obj):
    """IDs quoted in complete Task or Event queries, or None when one such query had no literal and so covered everything.

    The repository's Task and Event templates scope only by quoted Opportunity and Account Ids, so a quoted
    literal is a scope Id. This is a bounded check of those templates, not a SOQL parser."""
    ids, unbounded = set(), False
    for group in groups:
        if group['meta']['tool'] != 'salesforce' or not group['complete'] or obj not in group['meta']['objects']:
            continue
        found = QUOTED_LITERAL.findall(group['meta']['query'])
        if found:
            ids.update(found)
        else:
            unbounded = True
    return None if unbounded else ids


def unscoped_accounts(scope, groups, obj):
    """In-scope Accounts whose Opportunity Id and Account Id both miss every complete query for obj."""
    ids = activity_scope(groups, obj)
    if ids is None:
        return []
    return sorted(account_name(opp) for opp in scope if opp['Id'] not in ids and opp.get('AccountId') not in ids)


def quarter_bounds(today):
    start = dt.date(today.year, 3 * ((today.month - 1) // 3) + 1, 1)
    def shift(months):
        month = start.month + months
        return dt.date(start.year + (month - 1) // 12, (month - 1) % 12 + 1, 1)
    return start, shift(3), shift(6)


def previous_scheduled_date(today, policy):
    schedule = policy['pipeline'].get('schedule', {})
    days = set(schedule.get('daily', {}).get('days', ['MO', 'TU', 'WE', 'TH'])) | set(schedule.get('friday', {}).get('days', ['FR']))
    names = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
    if not days & set(names):
        raise ValueError('pipeline schedule has no valid days')
    for distance in range(1, 8):
        previous = today - dt.timedelta(days=distance)
        if names[previous.weekday()] in days:
            return previous


def email_query(query):
    """Parse only the two canonical account query forms, never substring-match domains."""
    query = query.lower().strip()
    match = re.fullmatch(r'from:@([\w.-]+)\s+after:(\d{4}[-/]\d{2}[-/]\d{2})', query)
    both = False
    if not match:
        match = re.fullmatch(r'\(\s*from:@([\w.-]+)\s+or\s+to:@\1\s*\)\s+after:(\d{4}[-/]\d{2}[-/]\d{2})', query)
        both = True
    if not match:
        return None
    try:
        return match[1], dt.date.fromisoformat(match[2].replace('/', '-')), both
    except ValueError:
        return None

def forecast_retry_window(mail, failures, domains, mail_start, retry_date):
    """Start date of the one successful shortened Gmail retry that followed the one timed-out full-window search, else None."""
    shortened = [(parsed, g) for parsed, g in mail if parsed[0] in domains and parsed[1] == retry_date]

    def timed_out_for_domains(meta, error, full_window_only):
        if meta['tool'] != 'search_email' or not ('timeout' in error.lower() or 'timed out' in error.lower()):
            return False
        for query in meta['queries']:
            parsed = email_query(query)
            if parsed and parsed[0] in domains and (not full_window_only or parsed[1] <= mail_start):
                return True
        return False

    timeouts = [meta for _, _, meta, error in failures if timed_out_for_domains(meta, error, True)]
    domain_timeouts = [meta for _, _, meta, error in failures if timed_out_for_domains(meta, error, False)]
    if shortened and len(timeouts) == 1 and len(domain_timeouts) == 1 and timeouts[0]['sequence'] < shortened[0][1]['sequence']:
        return shortened[0][0][1]
    return None



def _cursor(args):
    return args.get('cursor') or args.get('nextRecordsUrl') or args.get('next_records_url')


def opportunity_collection(query):
    """Recognize only the collection templates documented by pipeline/forecast."""
    tail = re.split(r"\bFROM\s+Opportunity\b", query, maxsplit=1, flags=re.I)[-1].strip()
    match = re.fullmatch(r"WHERE\s+OwnerId\s*=\s*'([^']+)'\s+AND\s+(.*?)(?:\s+ORDER\s+BY\s+CloseDate(?:\s+(?:ASC|DESC))?)?",tail,re.I)
    if not match:
        return None
    condition = re.sub(r"\s+", " ",match[2].lower()).strip()
    condition = re.sub(r"\s*=\s*", "=",condition)
    forms = {"isclosed=false":"open", "isclosed=false and closedate=this_quarter":"current_open",
             "isclosed=false and closedate=next_quarter":"next_open", "stagename='closed won' and closedate=this_quarter":"booked"}
    return (match[1],forms[condition]) if condition in forms else None


def collect(root, since, cap=50):
    """Collect exact query/page chains once for every report scope. A Calendar page at the connector cap is never complete."""
    errors, groups, failures, pending_sf, tool_of = [], {}, [], {}, {}
    for sequence, (path, inp, output_path) in enumerate(saved_calls(root, since.timestamp())):
        if inp.get('invalid_input'):
            errors.append(f'{path.name}: invalid saved input')
            continue
        tool, args = inp.get('tool_name'), inp.get('arguments') or {}
        tool_of[path.name] = tool
        query = args.get('query') or ''
        objects = {o.lower() for o in SOQL_OBJECTS.findall(query)}
        cursor = _cursor(args)
        if not objects and tool not in ('search_email', 'search_calendar') and cursor not in pending_sf:
            continue
        if objects and re.search(r'\b(?:LIMIT|OFFSET)\s+\d+',query,re.I):
            print(f'{path.name}: ignored restrictive Salesforce LIMIT/OFFSET lookup')
            continue
        if 'opportunity' in objects and not opportunity_collection(query):
            print(f'{path.name}: ignored non-collection Opportunity scope')
            continue
        if objects:
            key = ('salesforce', ' '.join(query.lower().split()))
            meta = {'tool':'salesforce', 'query':query, 'objects':objects, 'args':args, 'sequence':sequence}
        elif cursor in pending_sf:
            key = pending_sf[cursor]
            meta = groups[key]['meta']
        else:
            queries = tuple(args.get('queries') or ([query] if query else []))
            key = (tool, queries, args.get('start_date'), args.get('end_date'))
            meta = {'tool':tool, 'queries':queries, 'args':args, 'sequence':sequence}
        result, error = read_output(output_path, since.timestamp())
        if error:
            failures.append((path.name, key, meta, error))
            continue
        group = groups.setdefault(key, {'meta':meta, 'rows':{}, 'pages':[], 'issued':set(), 'used':set(), 'terminal':False, 'expected':None, 'sequence':sequence})
        if meta['tool'] == 'salesforce':
            rows = result.get('records')
            if not isinstance(rows, list):
                errors.append(f'{path.name}: missing Salesforce records')
                continue
            if 'event' in meta['objects'] and not all(f.lower() in meta['query'].lower() for f in ('StartDateTime','EndDateTime')):
                errors.append(f'{path.name}: Event query missing start/end timestamps')
            try:
                if 'totalSize' in result:
                    group['expected'] = max(group['expected'] or 0, int(result['totalSize']))
            except (ValueError, TypeError):
                errors.append(f'{path.name}: invalid Salesforce totalSize')
            for row in rows:
                if not isinstance(row, dict) or not row.get('Id'):
                    errors.append(f'{path.name}: Salesforce record missing Id')
                else:
                    group['rows'][row['Id']] = row
            next_cursor = result.get('nextRecordsUrl')
            more = result.get('hasMore') or result.get('done') is False or result.get('truncated')
            if more and not next_cursor:
                errors.append(f'{path.name}: Salesforce pagination cursor missing')
            if next_cursor:
                pending_sf[next_cursor] = key
        else:
            page = source_page(meta['tool'], result)
            if page is None:
                errors.append(f'{path.name}: missing or failed source result')
                continue
            group['pages'].append(page)
            if meta['tool'] == 'search_calendar' and len(page['events']) >= cap:
                group['capped'] = True
                group['deferred'] = [f"{path.name}: Calendar result cap reached ({len(page['events'])} events) for {list(meta['queries'])} {args.get('start_date')} to {args.get('end_date')}; chunk the window and rerun"]
            next_cursor = page.get('next_cursor') or result.get('next_cursor')
            more = bool(next_cursor)
        if cursor:
            if cursor not in group['issued'] or cursor in group['used']:
                errors.append(f'{path.name}: cursor was not returned for this query or was reused')
            group['used'].add(cursor)
        elif group['issued']:
            errors.append(f'{path.name}: paginated query restarted before consuming its cursor')
        if next_cursor:
            if next_cursor in group['used']:
                errors.append(f'{path.name}: repeated pagination cursor')
            group['issued'].add(next_cursor)
        if not next_cursor and not more:
            group['terminal'] = True
    for group in groups.values():
        group['complete'] = group['terminal'] and group['issued'] <= group['used'] and not group.get('capped')
        if group['meta']['tool'] == 'salesforce' and group['expected'] is not None:
            group['complete'] &= len(group['rows']) == group['expected']
        if not group['complete']:
            tool = group['meta']['tool']
            label = 'Email' if tool == 'search_email' else 'Calendar' if tool == 'search_calendar' else 'Salesforce'
            if tool == 'search_calendar':
                # Decided in check_coverage: complete split windows for the same term may supersede this call (rules#calendar_search).
                group.setdefault('deferred', []).append('Calendar pagination incomplete')
            else:
                errors.append(f'{label} pagination incomplete')
    # A successful retry of the same query recovers its transport error; it never repairs another scope.
    for name, key, meta, error in failures:
        if key in groups and groups[key]['complete']:
            print(f"Recovered {'Salesforce' if meta['tool']=='salesforce' else 'source'} call error: {name}; same source query succeeded.")
        elif meta['tool'] == 'salesforce':
            # Deduplicating a SELECT list is a safe correction with otherwise identical scope.
            tail = re.split(r'\bfrom\b', meta['query'], maxsplit=1, flags=re.I)[-1].lower().strip()
            recovered = any(g['complete'] and g['meta']['tool']=='salesforce' and re.split(r'\bfrom\b',g['meta']['query'],maxsplit=1,flags=re.I)[-1].lower().strip()==tail for g in groups.values())
            if recovered:
                print(f'Recovered Salesforce call error: {name}; corrected source query succeeded.')
            else:
                errors.append(f'{name}: unresolved Salesforce call error: {error}')
    return list(groups.values()), failures, errors, tool_of


def check_coverage(scope_kind, since, policy, root, stage_min=2, list_accounts=False, hygiene=None):
    groups, failures, errors, tool_of = collect(root, since, int(policy['tooling'].get('calendar_result_cap', 50)))
    unmatched_ids, thread_missing_ids = set(), set()
    internal = set(policy['tooling']['internal_domains'])
    generic = set(policy['tooling'].get('generic_email_domains', []))
    daily = scope_kind == 'pipeline-daily'
    required_collections = {'current_open','next_open','booked'} if scope_kind == 'forecast' else {'open'}
    opps, contacts, objects, collections, owners, sf_events = {}, [], set(), set(), set(), []
    for group in groups:
        if group['meta']['tool'] != 'salesforce' or not group['complete']:
            continue
        objects |= group['meta']['objects']
        if 'opportunity' in group['meta']['objects']:
            owner, kind = opportunity_collection(group['meta']['query'])
            collections.add(kind)
            owners.add(owner)
        for row in group['rows'].values():
            if record_type(row) == 'Opportunity' and opportunity_collection(group['meta']['query'])[1] in required_collections:
                opps.setdefault(row['Id'], {}).update(row)
            elif record_type(row) == 'Contact':
                contacts.append(row)
            elif record_type(row) == 'Event' or ('event' in group['meta']['objects'] and record_type(row) is None and row.get('StartDateTime')):
                sf_events.append(row)
    if required_collections - collections:
        errors.append('Missing complete Opportunity collections: ' + ', '.join(sorted(required_collections - collections)))
    if len(owners) > 1:
        errors.append('Opportunity collection owners disagree')
    if not opps and 'opportunity' not in objects:
        errors.append('No opportunity snapshot found. Run from the sandbox root after complete Salesforce queries. Report not ready.')
    if not opps and any(g['meta']['tool']=='salesforce' and 'opportunity' in g['meta']['objects'] and opportunity_collection(g['meta']['query'])[1] in required_collections and g['rows'] for g in groups):
        errors.append('No opportunity snapshot found with recognized Opportunity records')
    if scope_kind == 'forecast' and policy.get('forecast', {}).get('quarters') != 'calendar':
        raise ValueError('Only policy.forecast.quarters: calendar is supported')
    q_start, q_next, q_end = quarter_bounds(since.date())
    scope = []
    for opp in opps.values():
        stage = stage_num(opp.get('StageName'))
        if stage is None or stage < stage_min or opp.get('IsClosed') is True:
            continue
        if scope_kind == 'forecast':
            try:
                close = dt.date.fromisoformat(opp.get('CloseDate') or '')
            except ValueError:
                errors.append(f"{account_name(opp)}: CloseDate missing or invalid")
                continue
            if not q_start <= close < q_end or (close >= q_next and opp.get('Amount') in (None, 0)):
                continue
        scope.append(opp)
    missing_objects = {'opportunity','task','event','contact'} - objects
    if missing_objects:
        errors.append('Missing Salesforce source queries: ' + ', '.join(sorted(missing_objects)))
    for obj, label in (('task', 'Task'), ('event', 'Event')):
        if obj in objects:
            unscoped = unscoped_accounts(scope, groups, obj)
            if unscoped:
                errors.append(f'{label} query scope missing: ' + ', '.join(unscoped))
    if scope and 'contact' not in objects:
        errors.append(f"No Contact records saved since {since.isoformat(timespec='minutes')}. Run the Contact query, then rerun. Report not ready.")
    scan_start = previous_scheduled_date(since.date(), policy) if daily else since.date()-dt.timedelta(days=policy['tooling'].get('calendar_lookback_days',30))
    calendar_end = since.date()+dt.timedelta(days=policy['tooling'].get('calendar_lookahead_days',30))
    cal_queries, calendars, mail, inbox, seen_events, domains_by_opp = [], [], [], [], set(), {}
    for group in groups:
        if not group['complete']:
            continue
        meta = group['meta']
        if meta['tool']=='search_email':
            for query in meta['queries']:
                parsed = email_query(query)
                if parsed:
                    mail.append((parsed, group))
                tokens = query.lower().split()
                after = [t for t in tokens if t.startswith('after:')]
                expected_tokens = {f'-from:{d}' for d in internal}
                if len(meta['queries'])==1 and len(after)==1 and set(tokens)==expected_tokens|set(after):
                    try:
                        if dt.date.fromisoformat(after[0][6:].replace('/','-')) <= scan_start:
                            inbox.extend(group['pages'])
                    except ValueError:
                        pass
    # Calendar: per defined term, complete uncapped windows count together. Their union must cover the
    # required window with no gap; a capped or incomplete call is superseded when they do (rules#calendar_search).
    cal_lo = dt.datetime.combine(scan_start, dt.time.min, since.tzinfo)
    cal_hi = dt.datetime.combine(calendar_end, dt.time(23,59,59), since.tzinfo)
    cal_recovered, cal_unrecovered = False, False
    by_term = {}
    for group in groups:
        if group['meta']['tool']=='search_calendar':
            by_term.setdefault(group['meta']['queries'], []).append(group)
    for term, term_groups in by_term.items():
        complete_ranges = []
        for group in term_groups:
            rng = calendar_range(group['meta']['args'], since.tzinfo)
            if group['complete'] and rng is None:
                errors.append(f'calendar range missing or insufficient for {list(term)}: start_date/end_date missing or naive')
            elif group['complete']:
                complete_ranges.append(rng)
        gap = union_gap(complete_ranges, cal_lo, cal_hi) if complete_ranges else cal_lo
        if gap is None:
            cal_queries.extend(term)
            for group in term_groups:
                if not group['complete']:
                    cal_recovered = True
                    print(f"Superseded Calendar call for {list(term)}: complete split windows cover {cal_lo.date()} to {cal_hi.date()}.")
                    continue
                for event in (event for page in group['pages'] for event in page['events']):
                    key = event.get('event_id') or json.dumps(event, sort_keys=True)
                    if key not in seen_events:
                        seen_events.add(key)
                        calendars.append(event)
        else:
            if complete_ranges:
                errors.append(f"calendar range missing or insufficient for {list(term)}: uncovered from {gap.isoformat(timespec='minutes')}")
            for group in term_groups:
                errors.extend(group.get('deferred', []))
                cal_unrecovered |= bool(group.get('capped'))
    if daily:
        print(f'Daily scan window: {scan_start} through {since.date()} (previous scheduled run).')
        if not inbox:
            errors.append('Missing successful weekday inbox search')
    missing_calendar, missing_mail, no_domain, matched_mail, matched_events, covered_threads = [], [], [], [], [], set()
    mail_start = q_start if scope_kind=='forecast' else since.date()-dt.timedelta(days=policy['pipeline'].get('activity_query_days',30))
    for opp in scope:
        account = account_name(opp)
        addresses, domains = contact_domains(opp,contacts,internal,generic)
        domains_by_opp[opp['Id']] = domains
        if not domains:
            no_domain.append(account)
        if not calendar_covered(account,addresses,cal_queries):
            missing_calendar.append(account)
        full = [(parsed, g) for parsed, g in mail
                if parsed[0] in domains and parsed[1] <= mail_start and (scope_kind == 'forecast' or parsed[2])]
        if full:
            covered_threads.add(opp['Id'])
        elif scope_kind == 'forecast':
            retry_date = since.date() - dt.timedelta(days=policy.get('forecast', {}).get('activity_days', 14))
            retried_from = forecast_retry_window(mail, failures, domains, mail_start, retry_date)
            if retried_from is not None:
                covered_threads.add(opp['Id'])
                print(f'Not checked: {account}; Gmail retry succeeded, earlier window {mail_start} to {retried_from} unread.')
        if not daily and opp['Id'] not in covered_threads:
            missing_mail.append(account)
        for page in inbox:
            for email in page['emails']:
                domain=parseaddr(email.get('from_') or '')[1].lower().rsplit('@',1)[-1]
                if domain in domains:
                    matched_mail.append({'opportunity':opp['Id'],'account':account,'email_id':email.get('email_id'),'date':email.get('date'),'subject':email.get('subject')})
        for event in calendars:
            if any((a.get('email') or '').lower().rsplit('@',1)[-1] in domains for a in event.get('attendees') or []):
                matched_events.append({'opportunity':opp['Id'],'account':account,'event_id':event.get('event_id'),'start':event.get('start'),'end':event.get('end'),'title':event.get('title')})
    event_summary = None
    if 'event' in objects:
        matched, uncertain, unmatched, eligible, unmatched_ids = event_cross_check(
            scope, sf_events, calendars, domains_by_opp, cal_lo, cal_hi,
            owner=next(iter(owners)) if len(owners) == 1 else None)
        # A title search can succeed with no relevant events. Salesforce evidence of a
        # missed meeting must fail readiness, not just appear beneath a passing count.
        for opp in scope:
            if opp['Id'] in unmatched_ids and account_name(opp) not in missing_calendar:
                missing_calendar.append(account_name(opp))
        event_summary = f'Salesforce Events matched {len(matched)}/{eligible} eligible'
        if uncertain:
            event_summary += '; uncertain (attendee domain unverified): ' + ' | '.join(uncertain)
        if unmatched:
            event_summary += '; unmatched (reconcile before proposing on these Accounts): ' + ' | '.join(unmatched)
    n=len(scope)
    if daily:
        print(f"Coverage (pipeline-daily): {n} in scope. Inbox {'complete' if inbox else 'incomplete'}. Calendar {n-len(missing_calendar)}/{n}. Contact domains {n-len(no_domain)}/{n}.")
        print('Domain-matched email receipts: '+json.dumps(matched_mail))
        print('Domain-matched calendar receipts: '+json.dumps(matched_events))
        if hygiene is not None:
            flagged=[d for d in hygiene if d.get('triggers')]
            missing=[d.get('Account') or d['Id'] for d in flagged if d['Id'] not in covered_threads]
            thread_missing_ids={d['Id'] for d in flagged if d['Id'] not in covered_threads}
            print(f'Thread reads {len(flagged)-len(missing)}/{len(flagged)}.')
            if missing:
                errors.append('Thread read missing: '+', '.join(missing))
    else:
        desc=f'open S{stage_min}+' if scope_kind=='pipeline' else f'S{stage_min}+ CloseDate this quarter, or next quarter with Amount'
        print(f"Coverage ({scope_kind}, calls since {since.isoformat(timespec='minutes')}): {n} deals in scope ({desc}). Gmail {n-len(missing_mail)}/{n}. Calendar {n-len(missing_calendar)}/{n}.")
    if cal_unrecovered:
        print('Calendar: result cap reached; retrieval incomplete.')
    elif cal_recovered:
        print('Calendar: result cap reached, recovered by split windows; no cap on the split searches.')
    else:
        print('Calendar: defined searches completed, no cap detected.')
    if event_summary is not None:
        print(event_summary + '.')
    if list_accounts:
        for opp in sorted(scope,key=account_name):
            print('  '+account_name(opp))
    if no_domain and 'contact' in objects:
        errors.append(('Contact domain unavailable: ' if daily else 'No Contact domain in evidence: ')+', '.join(sorted(no_domain)))
    if missing_mail:
        errors.append('Gmail missing: '+', '.join(sorted(missing_mail)))
    if missing_calendar:
        errors.append('Calendar missing: '+', '.join(sorted(missing_calendar)))
    # Deals whose proposals must be withheld. A gap tied to named deals affects those deals. Email paging errors
    # surface per deal through thread reads and Gmail coverage. Any other gap affects every deal in scope.
    names = {}
    for opp in scope:
        names.setdefault(account_name(opp), set()).add(opp['Id'])
    affected = set(unmatched_ids) | thread_missing_ids
    for name in missing_calendar + missing_mail + (no_domain if 'contact' in objects else []):
        affected |= names.get(name, set())
    mail_files = {name for name, tool in tool_of.items() if tool == 'search_email'}
    if any(not e.startswith(DEAL_GAP_PREFIXES) and e != 'Email pagination incomplete' and e.split(': ', 1)[0] not in mail_files
           for e in errors):
        affected = {opp['Id'] for opp in scope}
    print(AFFECTED_PREFIX + json.dumps(sorted(affected)))
    for error in errors:
        print(error)
    print('Report not ready: resolve gaps or publish an explicitly incomplete report with affected proposals withheld.' if errors else 'Coverage ready.')
    return int(bool(errors))



def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope',choices=['pipeline','pipeline-daily','forecast'],required=True)
    parser.add_argument('--since',required=True)
    parser.add_argument('--policy',default=str(Path(__file__).resolve().parents[1]/'policy.yaml'))
    parser.add_argument('--calls-dir',type=Path,help='Explicit saved connector result directory; required when multiple sessions exist')
    parser.add_argument('--stage-min',type=int)
    parser.add_argument('--list',action='store_true')
    parser.add_argument('--hygiene')
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args(argv)
    try:
        since=dt.datetime.fromisoformat(args.since.replace('Z','+00:00'))
        if since.tzinfo is None:
            raise ValueError('--since needs a timezone offset')
        policy=yaml.safe_load(Path(args.policy).read_text())
        hygiene=json.loads(Path(args.hygiene).read_text()) if args.hygiene else None
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            code=check_coverage(args.scope,since,policy,resolve_calls_dir(args.calls_dir),args.stage_min if args.stage_min is not None else stage_num(policy['pipeline']['stages'][0]),args.list,hygiene)
        lines=output.getvalue().splitlines()
        affected=next((json.loads(l[len(AFFECTED_PREFIX):]) for l in lines if l.startswith(AFFECTED_PREFIX)),None)
    except (ValueError, OSError, TypeError) as exc:
        if not args.json:
            parser.error(str(exc))
        code,lines,affected=1,[str(exc)],None
    if args.json:
        lines=[l for l in lines if not l.startswith(AFFECTED_PREFIX)]
        print(json.dumps({'ready':code==0,'process_status':'complete' if code==0 else 'incomplete','lines':lines,'affected':affected}))
    else:
        print('\n'.join(lines))
    return code


if __name__=='__main__':
    sys.exit(main())
