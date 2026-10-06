#!/usr/bin/env python3
"""Validate one-pass answers and instantiate a separate sales workspace. No external writes."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import yaml

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = {'.git', '.venv', '__pycache__', '.DS_Store', '.pplx', '.perplexity',
            '.env', 'answers.json', 'tool_calls', 'outputs', 'tmp', 'status.json', 'skill-pointers'}


def excluded_name(name):
    return name in EXCLUDED or name.endswith(('.pyc','.local.json')) or name.startswith('.env.')


def read_schema(root=ROOT):
    return json.loads((root / '_core/onboarding/questions.json').read_text())


def read_integrations(root=ROOT):
    return json.loads((root / '_core/onboarding/integrations.json').read_text())


def nested_get(document, key):
    for part in key.split('.'):
        document = document[part]
    return document


def reject_credentials(value):
    """Answers contain configuration metadata only, never credential values."""
    if isinstance(value, dict):
        for key, item in value.items():
            if re.search(r'(?:^|_)(?:password|secret|token|api_key|private_key|credential_handle)(?:$|_)', key, re.I):
                raise ValueError('credentials belong directly in the runtime secret store, not answers')
            reject_credentials(item)
    elif isinstance(value, list):
        for item in value:
            reject_credentials(item)
    elif isinstance(value, str):
        if '\x00' in value or '{{' in value:
            raise ValueError('answers contain a placeholder or invalid byte')
        if re.search(r'-----BEGIN .*PRIVATE KEY-----|\bBearer\s+\S+|\b(?:sk-|xox[baprs]-)[A-Za-z0-9-]{12,}', value):
            raise ValueError('credentials belong directly in the runtime secret store, not answers')
        if value.startswith(('https://', 'http://')):
            parsed = urlparse(value)
            if parsed.username or parsed.password or any(
                    re.search(r'token|secret|password|api.?key|signature', key, re.I) for key in parse_qs(parsed.query)):
                raise ValueError('connection URLs must not contain credentials')


def matches_type(value, spec):
    kind = spec['type']
    return {'string': isinstance(value, str) and bool(value.strip()),
            'list': isinstance(value, list) and (bool(value) or spec.get('allow_empty', False)) and
                    all(isinstance(x, str) and x.strip() for x in value),
            'object': isinstance(value, dict),
            'boolean': type(value) is bool,
            'number': type(value) in (int, float) and math.isfinite(value) and value >= 0}.get(kind, False)


def validate_event_scope(scope, operator_id, *, simulation=False):
    """Legacy absence disables scope. Actual setup checks configured Salesforce User IDs."""
    if not isinstance(scope, dict) or set(scope) - {'house_owner_ids', 'include_missing_account'}:
        raise ValueError('outreach_owner_scope must contain only house_owner_ids and include_missing_account')
    owners = scope.get('house_owner_ids', [])
    if not isinstance(owners, list) or any(not isinstance(item, str) for item in owners):
        raise ValueError('event_house_owner_ids must be a list of Salesforce User IDs')
    if type(scope.get('include_missing_account', False)) is not bool:
        raise ValueError('event_include_missing_account must be boolean')
    if len(owners) != len(set(owners)):
        raise ValueError('event_house_owner_ids must be distinct')
    if operator_id in owners:
        raise ValueError('event_house_owner_ids must exclude the operator')
    if any(not re.fullmatch(r'005[A-Za-z0-9]{15}', item) or
           (not simulation and item.startswith('005000000000')) for item in owners):
        raise ValueError('event_house_owner_ids need actual 18-character Salesforce User IDs')


def validate_policy_shape(value, sample, label):
    if isinstance(sample, dict):
        if not isinstance(value, dict) or set(value) != set(sample):
            raise ValueError(f'{label} must map every compatible policy key, or defer and adapt the contract')
        for key, expected in sample.items():
            validate_policy_shape(value[key], expected, f'{label}.{key}')
    elif sample is None:
        if value is not None:
            raise ValueError(f'{label} requires null for the no-error success condition')
    elif type(sample) in (int, float):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError(f'{label} must be a finite nonnegative number')
    elif isinstance(sample, str) and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f'{label} must be a nonempty string')
    elif isinstance(sample, bool) and not isinstance(value, bool):
        raise ValueError(f'{label} must be boolean')


def validate_integrations(selected, root=ROOT, *, simulation=False):
    registry = read_integrations(root)
    if not isinstance(selected, dict) or set(selected) != set(registry):
        raise ValueError('integration_setup must explicitly cover every system in integrations.json')
    reject_credentials(selected)
    policy = yaml.safe_load((root / '_core/policy.yaml').read_text())
    for name, entry in selected.items():
        if not isinstance(entry, dict) or entry.get('choice') not in ('configure', 'defer', 'not_used'):
            raise ValueError(f'{name} needs configure, defer or not_used')
        if entry['choice'] != 'configure':
            if set(entry) != {'choice', 'reason'} or not isinstance(entry['reason'], str) or not entry['reason'].strip():
                raise ValueError(f'{name} needs a reason and no connection settings when deferred or unused')
            continue
        if set(entry) != {'choice', 'transport', 'connection', 'auth', 'settings'}:
            raise ValueError(f'{name} needs transport, connection, auth and settings only, with no credentials')
        if entry['transport'] not in ('native', 'mcp', 'api', 'cli', 'manual', 'local'):
            raise ValueError(f'{name} has an unsupported transport')
        if entry['auth'] not in ('oauth', 'api_key', 'service_account', 'runtime', 'none'):
            raise ValueError(f'{name} needs an authentication method, never a credential value')
        if not isinstance(entry['connection'], str) or not entry['connection'].strip():
            raise ValueError(f'{name} needs the actual connector, server, API, CLI or evidence route name')
        settings = entry['settings']
        if not isinstance(settings, dict) or set(settings) != set(registry[name]['settings']):
            raise ValueError(f'{name} settings must match integrations.json')
        for key, spec in registry[name]['settings'].items():
            value = settings[key]
            label = f'{name}.{key}'
            if not matches_type(value, spec):
                raise ValueError(f'{label} must be a {spec["type"]}')
            if spec.get('keys') and (set(value) != set(spec['keys']) or
                                    any(not isinstance(v, str) or not v.strip() for v in value.values())):
                raise ValueError(f'{label} must name every workspace destination')
            if spec.get('policy_shape'):
                validate_policy_shape(value, nested_get(policy, spec['target']), label)
            if spec.get('format') == 'tool' and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', value):
                raise ValueError(f'{label} must be a tool or flow API name')
            if spec.get('format') == 'email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
                raise ValueError(f'{label} must be an email address')
            if spec.get('format') == 'salesforce_user_list' and any(
                    not re.fullmatch(r'005[A-Za-z0-9]{15}', item) or
                    (not simulation and item.startswith('005000000000')) for item in value):
                raise ValueError(f'{label} needs actual 18-character Salesforce integration User IDs')
    return selected


def nested_set(document, key, value):
    parts = key.split('.')
    current = document
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def validate(answers, root=ROOT, *, simulation=False):
    schema = read_schema(root)
    if not isinstance(answers, dict):
        raise ValueError('answers must be a JSON object')
    unknown = sorted(set(answers) - set(schema))
    missing = [key for key, spec in schema.items() if spec['required'] and key not in answers]
    if unknown or missing:
        raise ValueError(f'unknown answers {unknown}; missing answers {missing}')
    reject_credentials(answers)
    validate_integrations(answers['integration_setup'], root, simulation=simulation)
    values = {}
    for key, spec in schema.items():
        if key not in answers and 'default' not in spec:
            integration = spec.get('required_when')
            if integration and answers['integration_setup'][integration]['choice'] == 'configure':
                raise ValueError(f'{key} is required when {integration} is selected')
            continue
        value = answers.get(key, deepcopy(spec.get('default')))
        if not matches_type(value, spec):
            raise ValueError(f'{key} must be a nonempty {spec["type"]}')
        if isinstance(value, str) and ('{{' in value or '\x00' in value):
            raise ValueError(f'{key} contains a placeholder or invalid byte')
        values[key] = deepcopy(value)
    validate_event_scope({'house_owner_ids': values['event_house_owner_ids'],
                          'include_missing_account': values['event_include_missing_account']},
                         values['owner_id'], simulation=simulation)
    # The rehearsal opts into fictional fixtures. Mode is never an onboarding answer.
    values['mode'] = 'demo' if simulation else 'configured'
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', values['owner_email']):
        raise ValueError('owner_email must be an email address')
    if not re.fullmatch(r'005[A-Za-z0-9]{15}', values['owner_id']):
        raise ValueError('owner_id must be an 18-character Salesforce User ID')
    try:
        ZoneInfo(values['timezone'])
        ZoneInfo(values.get('warehouse_timezone', values['timezone']))
    except ZoneInfoNotFoundError as exc:
        raise ValueError('timezone must be an installed IANA timezone') from exc
    url = urlparse(values['crm_url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise ValueError('crm_url must be an HTTPS origin without credentials, path, query or fragment')
    for domain in values['internal_domains']:
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*\.[a-z]{2,}', domain):
            raise ValueError('internal_domains must be lowercase email domains')
    if values['owner_email'].split('@')[1].lower() not in values['internal_domains']:
        raise ValueError('owner_email domain must be in internal_domains')
    if not re.fullmatch(r'[A-Z]{1,5}',values['note_initials']):
        raise ValueError('note_initials must be 1 to 5 uppercase letters')
    date.fromisoformat(values['product_review_date'])
    for key in ('owner_name','product_name','company_name'):
        if any(char in values[key] for char in '\r\n'):
            raise ValueError(f'{key} must fit on one line')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',values['amount_field']):
        raise ValueError('amount_field must be a CRM API name')
    for quarter, amount in values['quarter_targets'].items():
        if not re.fullmatch(r'\d{4}-Q[1-4]',quarter) or type(amount) not in (int,float) or not math.isfinite(amount) or amount < 0:
            raise ValueError('quarter_targets maps YYYY-Q1..Q4 to nonnegative numbers')
    mapping = json.loads((root / '_core/onboarding/adapter-schema.json').read_text())
    if values['crm_field_map'].get('ARR__c', values['amount_field']) != values['amount_field']:
        raise ValueError('amount_field conflicts with the ARR__c mapping')
    if values['amount_field'] != 'ARR__c':
        values['crm_field_map']['ARR__c'] = values['amount_field']
    for key, pattern in (('crm_field_map',r'[A-Za-z][A-Za-z0-9_]*'),
                         ('warehouse_table_map',r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){1,2}')):
        selected = values[key]
        if set(selected) - set(mapping[key]) or len(set(selected.values())) != len(selected):
            raise ValueError(f'{key} has unknown or duplicate mappings')
        if any(not isinstance(v,str) or not re.fullmatch(pattern,v) for v in selected.values()):
            raise ValueError(f'{key} contains an invalid API name')
        effective = {old:selected.get(old,old) for old in mapping[key]}
        if len(set(effective.values())) != len(effective):
            raise ValueError(f'{key} collides with an unmapped field or table')
    reserved_examples = ('example.com','example.net','example.org')
    domains = (url.hostname,values['owner_email'].split('@')[1].lower())
    if not simulation and any(domain.endswith(('.invalid','.example','.test')) or domain in reserved_examples or
                              any(domain.endswith('.'+example) for example in reserved_examples) for domain in domains):
        raise ValueError('setup requires your company email and Salesforce origin, not reserved example domains')
    if not simulation:
        if values['owner_id'].startswith('005000000000'):
            raise ValueError('owner_id must be your actual Salesforce User ID, not the fictional fixture')
        for key in ('ops_channel', 'deal_desk_channel'):
            if key in values and (not re.fullmatch(r'C[A-Z0-9]{8,}', values[key]) or values[key].startswith('C000000')):
                raise ValueError(f'{key} must be an actual Slack channel ID')
        if 'ops_owners' in values and any(not re.fullmatch(r'U[A-Z0-9]{8,}', item) or item.startswith('U000000') for item in values['ops_owners']):
            raise ValueError('ops_owners must be actual Slack user IDs')
        if 'warehouse' in values and values['warehouse'].startswith('EXAMPLE_'):
            raise ValueError('warehouse must be the actual selected warehouse')
        gmail = values['integration_setup']['gmail']
        if gmail['choice'] == 'configure' and gmail['settings']['assistant_email'].split('@')[1].lower() not in values['internal_domains']:
            raise ValueError('the assistant sender must use a configured internal domain')
    output = Path(values['artifact_dir']).expanduser()
    if not output.is_absolute():
        raise ValueError('artifact_dir must be an absolute path outside the workspace')
    return values


def collect_questionnaire(root=ROOT):
    answers = {}
    for key, spec in read_schema(root).items():
        if key == 'integration_setup':
            answers[key] = collect_integrations(root)
            continue
        default = spec.get('default')
        hint = f" [{json.dumps(default)}]" if default is not None else ''
        value = input(f"{spec['question']}{hint} ").strip()
        if not value:
            if default is not None:
                answers[key] = default
            continue
        answers[key] = value if spec['type'] == 'string' else json.loads(value)
    return answers


def collect_integrations(root=ROOT):
    selected = {}
    for name, spec in read_integrations(root).items():
        print(f"\n{spec['label']}\nUse: {spec['scope']}\nSetup: {spec['setup']}\nAuthentication: {spec['authentication']}\nVerify: {spec['verify']}")
        choice = input('Choose configure, defer or not_used: ').strip()
        if choice != 'configure':
            selected[name] = {'choice': choice, 'reason': input('Reason and affected work to hold: ').strip()}
            continue
        entry = {'choice': choice,
                 'transport': input('Transport (native, mcp, api, cli, manual, local): ').strip(),
                 'connection': input('Actual connection or evidence route name, without secrets: ').strip(),
                 'auth': input('Auth method (oauth, api_key, service_account, runtime, none), never the value: ').strip(),
                 'settings': {}}
        for key, field in spec['settings'].items():
            value = input(field['question'] + ' ').strip()
            entry['settings'][key] = value if field['type'] == 'string' else json.loads(value)
        selected[name] = entry
    return selected


def routes(root):
    return re.findall(r'^\| `([a-z-]+)` \| `(workspaces/[^`]+/CONTEXT.md)` \| ([^|]+) \|',
                      (root/'AGENTS.md').read_text(),re.M)


def instantiate(answers, destination, root=ROOT, *, simulation=False):
    values = validate(answers,root,simulation=simulation)
    registry = read_integrations(root)
    destination = Path(destination).expanduser()
    # Reject symlink ancestors, overlaps and any existing destination before creating anything.
    if any(p.is_symlink() for p in (destination,*destination.parents)):
        raise ValueError('destination must not have symlink ancestors')
    destination = destination.resolve()
    source = root.resolve()
    if yaml.safe_load((source / '_core/policy.yaml').read_text())['template']['mode'] != 'unconfigured':
        raise ValueError('setup must start from an unconfigured template, not an existing company workspace')
    if any(path.is_symlink() for path in source.rglob('*') if '.git' not in path.relative_to(source).parts):
        raise ValueError('source contains a symlink; resolve its eligibility before copying')
    if destination.exists() or source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('destination must be absent and separate from the source')
    artifacts = Path(values['artifact_dir']).expanduser().resolve()
    if artifacts == destination or destination in artifacts.parents or source == artifacts or source in artifacts.parents:
        raise ValueError('artifact_dir must be outside both source and configured workspace')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.sales-setup-',dir=destination.parent) as staging:
        stage = Path(staging)/'workspace'
        if (source / '.git').exists():
            # A repository may contain ignored customer material. Copy tracked factory files only.
            names = subprocess.check_output(['git', '-C', str(source), 'ls-files', '-z']).decode().split('\0')
            stage.mkdir()
            for name in filter(None, names):
                relative = Path(name)
                if any(excluded_name(part) for part in relative.parts):
                    continue
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / relative, target)
        else:
            shutil.copytree(source,stage,ignore=lambda directory,names:[n for n in names if excluded_name(n)])
        policy_file = stage/'_core/policy.yaml'
        policy = yaml.safe_load(policy_file.read_text())
        for key,spec in read_schema(root).items():
            for target in spec.get('targets',[]):
                if key in values:
                    nested_set(policy,target,deepcopy(values[key]))
        def timezones(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key in ('tz','timezone','display_tz'):
                        value[key] = values['timezone']
                    else:
                        timezones(item)
            elif isinstance(value,list):
                for item in value:
                    timezones(item)
        timezones(policy)
        for name, entry in values['integration_setup'].items():
            if entry['choice'] == 'configure':
                for key, spec in registry[name]['settings'].items():
                    if spec.get('target'):
                        nested_set(policy, spec['target'], deepcopy(entry['settings'][key]))
                        # Operational values keep one canonical policy home.
                        del policy['template']['integrations'][name]['settings'][key]
        policy['template']['mode'] = values['mode']
        policy['template']['external_ready'] = False
        policy['salesforce']['note_prefix'] = f"M/D/YY {values['note_initials']} - "
        policy['salesforce']['cooldown_marker'] = f"M/D/YY {values['note_initials']} - Recycled. Cooldown until M/D/YY."
        policy['pipeline']['note_next_line'] = f"M/D/YY {values['note_initials']} - <next action in one sentence, due on or by M/D[/YY]>"
        policy['pipeline']['note_history_line'] = f"M/D/YY {values['note_initials']} - <what happened since the last note, two sentences at most>"
        policy['email_voice']['closing'] = f"Best,\n{values['owner_name']}"
        policy['pilot_usage']['pdf']['metadata_author'] = values['company_name']
        policy['pilot_usage']['pdf']['metadata_title'] = values['product_name']+' Pilot Usage Report'
        policy['prospecting']['user_scan']['statements'] = {
            'org_adopted':f"{values['product_name']} is already adopted at the organization.",
            'individuals_only':f"People at the organization already pay for {values['product_name']} individually."}
        policy_file.write_text(yaml.safe_dump(policy,sort_keys=False,allow_unicode=True))
        # Profile values are data, not shell or regular-expression replacement strings.
        talk = stage/'workspaces/prospecting/workflows/signal-prospecting/02-outreach/references/talk-track.md'
        text = re.sub(r"review_by: '[0-9-]+'",f"review_by: '{values['product_review_date']}'",talk.read_text())
        talk.write_text(text)
        replacements = {'Example Product': values['product_name'], 'Example Seller': values['company_name'],
                        **values['crm_field_map'], **values['warehouse_table_map']}
        if replacements:
            # One pass avoids cascades when a destination name is also a source name.
            pattern = re.compile(r'(?<![A-Za-z0-9_])('+ '|'.join(re.escape(k) for k in sorted(replacements,key=len,reverse=True))+r')(?![A-Za-z0-9_])')
            for file in stage.rglob('*'):
                if file.is_file() and file.suffix in ('.md','.py','.yaml','.sql') and 'tests' not in file.parts and 'onboarding' not in file.parts:
                    file.write_text(pattern.sub(lambda match:replacements[match.group()],file.read_text()))
        # Warehouse event dates must use one declared timezone in query adapters and parsers.
        for file in (stage/'workspaces').rglob('*'):
            if file.is_file() and file.suffix in ('.md','.py','.sql'):
                adapter_timezone = values['timezone'] if file.name == 'resolve_pilot.py' else values.get('warehouse_timezone', values['timezone'])
                text = file.read_text().replace('America/Los_Angeles', adapter_timezone)
                text = text.replace('Pacific date','configured warehouse date').replace('Pacific send','configured local send')
                file.write_text(text)
        pointers = stage/'_core/onboarding/skill-pointers'
        pointers.mkdir(exist_ok=True)
        for name,contract,branch in routes(stage):
            branch_line = '' if branch.strip() == 'None' else f"Select branch {branch.strip()}.\n"
            dependencies = ', '.join(key for key, spec in registry.items() if name in spec['workflows'])
            (pointers/f'{name}.md').write_text(f"---\nname: {name}\ndescription: Run {name} through its scoped contract.\n---\n\nRead `{contract}` explicitly, then only its applicable Inputs.\n{branch_line}Integration choices under `policy.template.integrations`: {dependencies}.\nRequire current live verification for the surfaces used by this branch. Deferred or unused dependencies hold only their affected operations.\nStop if the contract or required adapter is unavailable. Apply onboarding and external-write gates from root AGENTS.md.\n")
        status = {'mode':values['mode'],'external_ready':False,
                  'integrations': {key: {'choice': entry['choice'], 'live_verified': False,
                                       'workflows': registry[key]['workflows']} for key, entry in values['integration_setup'].items()},
                  'pending': list(registry),
                  'answer_sha256':hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()}
        (stage/'_core/onboarding/status.json').write_text(json.dumps(status,indent=2)+'\n')
        if destination.exists():
            raise ValueError('destination appeared during setup; refusing overwrite')
        stage.rename(destination)
    return status


def check(workspace,allow_template=False):
    workspace = Path(workspace)
    policy = yaml.safe_load((workspace/'_core/policy.yaml').read_text())
    mode = policy['template']['mode']
    errors = []
    if mode == 'unconfigured' and not allow_template:
        errors.append('run onboarding before a sales workflow')
    if mode not in ('unconfigured','demo','configured'):
        errors.append('invalid template mode')
    try:
        validate_event_scope(policy['prospecting']['event'].get('outreach_owner_scope', {}),
                             policy['prospecting']['identity']['sfdc_user_id'], simulation=mode == 'demo')
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    route_list = routes(workspace)
    if len(route_list) != 18 or any(not (workspace/path).is_file() for _,path,_ in route_list):
        errors.append('missing workflow routes')
    for path in policy['tooling']['scripts'].values():
        if not (workspace/path).is_file():
            errors.append(f'missing helper {path}')
    if policy['template']['auto_date_move'] or policy['prospecting']['approval']['unattended_writes']:
        errors.append('unattended writes enabled without template release review')
    registry = read_integrations(workspace)
    selected = policy['template'].get('integrations', {})
    if mode != 'unconfigured':
        try:
            expanded = deepcopy(selected)
            for name, entry in expanded.items():
                if name in registry and isinstance(entry, dict) and entry.get('choice') == 'configure':
                    fields = registry[name]['settings']
                    metadata_keys = {key for key, spec in fields.items() if not spec.get('target')}
                    if not isinstance(entry.get('settings'), dict) or set(entry['settings']) != metadata_keys:
                        raise ValueError(f'{name} must keep operational settings in their canonical policy targets')
                    for key, spec in fields.items():
                        if spec.get('target'):
                            entry['settings'][key] = nested_get(policy, spec['target'])
            validate_integrations(expanded, workspace, simulation=mode == 'demo')
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(str(exc))
        for name, contract, branch in route_list:
            pointer = workspace / '_core/onboarding/skill-pointers' / f'{name}.md'
            if not pointer.is_file() or f'Read `{contract}` explicitly' not in pointer.read_text():
                errors.append(f'missing or mismatched skill pointer {name}')
    if policy['template'].get('external_ready') is not False:
        errors.append('local setup cannot claim external readiness')
    print(json.dumps({'mode':mode,'external_ready':False,'routes':len(route_list),
                      'integrations':len(registry),'pending_live_verification':list(registry),
                      'deferred_or_unused': [key for key, entry in selected.items() if not isinstance(entry, dict) or entry.get('choice') != 'configure'],
                      'errors':errors},indent=2))
    return 1 if errors else 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    setup=sub.add_parser('setup')
    setup.add_argument('--answers',type=Path)
    setup.add_argument('--destination',type=Path,required=True)
    checker=sub.add_parser('check')
    checker.add_argument('--workspace',type=Path,default=ROOT)
    checker.add_argument('--allow-template',action='store_true')
    sub.add_parser('questions')
    sub.add_parser('integrations')
    args=parser.parse_args(argv)
    try:
        if args.command=='questions':
            print(json.dumps(read_schema(),indent=2)); return 0
        if args.command=='integrations':
            print(json.dumps(read_integrations(),indent=2)); return 0
        if args.command=='check':
            return check(args.workspace,args.allow_template)
        if args.answers:
            answer_path = args.answers.expanduser().resolve()
            destination = args.destination.expanduser().resolve()
            if ROOT in answer_path.parents or destination in answer_path.parents:
                raise ValueError('save answers outside the template and destination workspace')
            answers = json.loads(answer_path.read_text())
        else:
            answers = collect_questionnaire()
        print(json.dumps(instantiate(answers,args.destination),indent=2)); return 0
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print(f'onboarding failed: {exc}',file=sys.stderr); return 1


if __name__=='__main__':
    raise SystemExit(main())
