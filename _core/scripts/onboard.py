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
import sys
import tempfile
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import yaml

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = {'.git', '.venv', '__pycache__', '.DS_Store', '.pplx', '.env', 'answers.json'}


def excluded_name(name):
    return name in EXCLUDED or name.endswith(('.pyc','.local.json')) or name.startswith('.env.')


def read_schema(root=ROOT):
    return json.loads((root / '_core/onboarding/questions.json').read_text())


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
    values = {}
    for key, spec in schema.items():
        value = answers.get(key, deepcopy(spec.get('default')))
        kind = spec['type']
        valid = {'string': isinstance(value, str) and bool(value.strip()),
                 'list': isinstance(value, list) and bool(value) and all(isinstance(x,str) and x.strip() for x in value),
                 'object': isinstance(value, dict),
                 'number': type(value) in (int,float) and math.isfinite(value) and value >= 0}.get(kind, False)
        if not valid:
            raise ValueError(f'{key} must be a nonempty {kind}')
        if isinstance(value, str) and ('{{' in value or '\x00' in value):
            raise ValueError(f'{key} contains a placeholder or invalid byte')
        values[key] = value
    # The rehearsal opts into fictional fixtures. Mode is never an onboarding answer.
    values['mode'] = 'demo' if simulation else 'configured'
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', values['owner_email']):
        raise ValueError('owner_email must be an email address')
    if not re.fullmatch(r'005[A-Za-z0-9]{15}', values['owner_id']):
        raise ValueError('owner_id must be an 18-character Salesforce User ID')
    try:
        ZoneInfo(values['timezone'])
        ZoneInfo(values['warehouse_timezone'])
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
    output = Path(values['artifact_dir']).expanduser()
    if not output.is_absolute():
        raise ValueError('artifact_dir must be an absolute path outside the workspace')
    return values


def collect_questionnaire(root=ROOT):
    answers = {}
    for key, spec in read_schema(root).items():
        default = spec.get('default')
        hint = f" [{json.dumps(default)}]" if default is not None else ''
        value = input(f"{spec['question']}{hint} ").strip()
        if not value:
            if default is not None:
                answers[key] = default
            continue
        answers[key] = value if spec['type'] == 'string' else json.loads(value)
    return answers


def routes(root):
    return re.findall(r'^\| `([a-z-]+)` \| `(workspaces/[^`]+/CONTEXT.md)` \| ([^|]+) \|',
                      (root/'AGENTS.md').read_text(),re.M)


def instantiate(answers, destination, root=ROOT, *, simulation=False):
    values = validate(answers,root,simulation=simulation)
    destination = Path(destination).expanduser()
    # Reject symlink ancestors, overlaps and any existing destination before creating anything.
    if any(p.is_symlink() for p in (destination,*destination.parents)):
        raise ValueError('destination must not have symlink ancestors')
    destination = destination.resolve()
    source = root.resolve()
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
        shutil.copytree(source,stage,ignore=lambda directory,names:[n for n in names if excluded_name(n)])
        policy_file = stage/'_core/policy.yaml'
        policy = yaml.safe_load(policy_file.read_text())
        for key,spec in read_schema(root).items():
            for target in spec.get('targets',[]):
                nested_set(policy,target,values[key])
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
        talk = stage/'workspaces/prospecting/workflows/outreach/references/talk-track.md'
        text = re.sub(r"review_by: '[0-9-]+'",f"review_by: '{values['product_review_date']}'",talk.read_text())
        talk.write_text(text)
        replacements = {**values['crm_field_map'],**values['warehouse_table_map']}
        if replacements:
            # One pass avoids cascades when a destination name is also a source name.
            pattern = re.compile(r'(?<![A-Za-z0-9_])('+ '|'.join(re.escape(k) for k in sorted(replacements,key=len,reverse=True))+r')(?![A-Za-z0-9_])')
            for file in stage.rglob('*'):
                if file.is_file() and file.suffix in ('.md','.py','.yaml','.sql') and 'tests' not in file.parts and 'onboarding' not in file.parts:
                    file.write_text(pattern.sub(lambda match:replacements[match.group()],file.read_text()))
        # Warehouse event dates must use one declared timezone in query adapters and parsers.
        for file in (stage/'workspaces').rglob('*'):
            if file.is_file() and file.suffix in ('.md','.py','.sql'):
                text = file.read_text().replace('America/Los_Angeles',values['warehouse_timezone'])
                text = text.replace('Pacific date','configured warehouse date').replace('Pacific send','configured local send')
                file.write_text(text)
        pointers = stage/'_core/onboarding/skill-pointers'
        pointers.mkdir(exist_ok=True)
        for name,contract,branch in routes(stage):
            branch_line = '' if branch.strip() == 'None' else f"Select branch {branch.strip()}.\n"
            (pointers/f'{name}.md').write_text(f"---\nname: {name}\ndescription: Run {name} through its scoped contract.\n---\n\nRead `{contract}` explicitly, then only its applicable Inputs.\n{branch_line}Stop if the contract or required adapter is unavailable. Apply onboarding and external-write gates from root AGENTS.md.\n")
        status = {'mode':values['mode'],'external_ready':False,'pending':['Salesforce identity and field describe','Gmail and Calendar scope','Transcript adapter','Warehouse schema and read-only grants','Apollo sender and stop-on-reply','Slack routing','Runtime skill pointers and permissions','Schedule review and activation'],'answer_sha256':hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()}
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
    route_list = routes(workspace)
    if len(route_list) != 18 or any(not (workspace/path).is_file() for _,path,_ in route_list):
        errors.append('missing workflow routes')
    for path in policy['tooling']['scripts'].values():
        if not (workspace/path).is_file():
            errors.append(f'missing helper {path}')
    if policy['template']['auto_date_move'] or policy['prospecting']['approval']['unattended_writes']:
        errors.append('unattended writes enabled without template release review')
    print(json.dumps({'mode':mode,'external_ready':False,'routes':len(route_list),'errors':errors},indent=2))
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
    args=parser.parse_args(argv)
    try:
        if args.command=='questions':
            print(json.dumps(read_schema(),indent=2)); return 0
        if args.command=='check':
            return check(args.workspace,args.allow_template)
        answers=json.loads(args.answers.read_text()) if args.answers else collect_questionnaire()
        print(json.dumps(instantiate(answers,args.destination),indent=2)); return 0
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print(f'onboarding failed: {exc}',file=sys.stderr); return 1


if __name__=='__main__':
    raise SystemExit(main())
