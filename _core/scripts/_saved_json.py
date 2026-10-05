"""Read saved connector JSON without confusing failed/malformed input with empty data."""
import json
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from pathlib import Path


def resolve_calls_dir(explicit_path=None):
    """Prefer an explicit directory, then one live session, then legacy cwd; reject ambiguity."""
    if explicit_path is not None:
        return Path(explicit_path).expanduser()
    sessions = Path.home() / '.perplexity' / 'sessions'
    candidates = sorted(path for path in sessions.glob('*/tool_calls/call_external_tool') if path.is_dir())
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise ValueError('Multiple saved tool-call session directories found; provide an explicit --calls-dir, --sources or --tool-calls path')
    return Path.cwd() / 'current_session_context/tool_calls/call_external_tool'


def unwrap_saved(data):
    while isinstance(data, dict):
        if data.get('truncated') or data.get('is_truncated'):
            raise ValueError('truncated source result; fetch a complete result')
        status = str(data.get('status') or data.get('state') or '').lower()
        if data.get('error') or data.get('authenticated') is False or status in {'error', 'failed', 'failure', 'aborted'}:
            raise ValueError(f"failed source result: {data.get('error') or status or 'unauthenticated'}")
        if 'result' not in data:
            break
        outer = data
        data = data['result']
        if isinstance(data, str):
            data = json.loads(data)
        flags = {k: outer[k] for k in ('hasMore','has_more','done','nextRecordsUrl','next_cursor','totalSize') if k in outer}
        if flags and isinstance(data, dict):
            data = {**data, **flags}
        elif flags:
            raise ValueError('pagination metadata requires a result object')
    if not isinstance(data, (dict, list)):
        raise ValueError('saved result must be an object or list')
    return data


def load_saved(path):
    with open(path) as handle:
        return unwrap_saved(json.load(handle))


def records_of(data, *, complete=True):
    data = unwrap_saved(data)
    if isinstance(data, list):
        rows = data
    elif isinstance(data.get('records'), list):
        rows = data['records']
        if complete and (data.get('hasMore') or data.get('has_more') or data.get('next_cursor') or data.get('nextRecordsUrl') or data.get('done') is False
                         or data.get('truncated') or int(data.get('totalSize', len(rows))) != len(rows)):
            raise ValueError('incomplete Salesforce result: fetch every page before using this file')
    elif isinstance(data.get('results'), list) and len(data['results']) == 1:
        return records_of(data['results'][0], complete=complete)
    else:
        raise ValueError('missing Salesforce records list')
    if any(not isinstance(row, dict) or not row.get('Id') for row in rows):
        raise ValueError('Salesforce records must be objects with Id')
    return rows


def load_records(path):
    return records_of(load_saved(path)) if path else []


def parse_email_date(value):
    """Normalize ISO/RFC timestamps to aware UTC; reject unknown dates for review."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError('email date missing; review required')
    for parser in (lambda v: datetime.fromisoformat(v.replace('Z', '+00:00')), parsedate_to_datetime):
        try:
            parsed = parser(value)
            if parsed.tzinfo is None:
                raise ValueError('email date needs a timezone')
            return parsed.astimezone(timezone.utc)
        except (ValueError, TypeError, IndexError):
            continue
    raise ValueError(f'unparseable email date; review required: {value!r}')


def load_email_records(paths):
    """Read complete saved Gmail pages, using paired call inputs for returned cursors."""
    from pathlib import Path
    groups, emails = {}, []
    for path in sorted(map(Path, paths), key=lambda p: (p.stat().st_mtime, p.name)):
        result = load_saved(path)
        page = result.get('email_results') if isinstance(result, dict) else None
        if not isinstance(page, dict) or not isinstance(page.get('emails'), list) or page.get('error') or page.get('truncated'):
            raise ValueError('missing, failed, or truncated email results; source was not checked')
        paired = path.with_name(path.name.replace('output_', 'input_', 1))
        args = {}
        if paired != path and paired.is_file():
            args = (load_saved(paired).get('arguments') or {})
        queries = tuple(args.get('queries') or ([args['query']] if args.get('query') else []))
        issued, used = groups.setdefault(queries, (set(), set()))
        cursor = args.get('cursor')
        next_cursor = page.get('next_cursor') or result.get('next_cursor')
        if cursor:
            if cursor not in issued or cursor in used:
                raise ValueError('email cursor was not returned for this query or was reused')
            used.add(cursor)
        if next_cursor:
            if next_cursor in used:
                raise ValueError('repeated email cursor')
            issued.add(next_cursor)
        if any(item.get('hasMore') or item.get('has_more') for item in (result, page)) and not next_cursor:
            raise ValueError('incomplete email results without a cursor')
        emails.extend(page['emails'])
    if any(issued - used for issued, used in groups.values()):
        raise ValueError('incomplete email pagination; supply every saved page and its paired call input')
    return emails
