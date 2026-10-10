"""Render a portable review checklist and update evidence-backed issue states."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

SKILL = Path(__file__).resolve().parents[1]
STATUSES = {'open', 'in_progress', 'fixed_pending_verification', 'verified', 'blocked', 'deferred'}
TRANSITIONS = {
    'open': {'in_progress', 'blocked', 'deferred'},
    'in_progress': {'fixed_pending_verification', 'blocked', 'deferred'},
    'fixed_pending_verification': {'verified', 'in_progress', 'blocked'},
    'verified': {'in_progress'},
    'blocked': {'in_progress', 'deferred'},
    'deferred': {'open', 'in_progress'},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def evidence(value):
    return isinstance(value, list) and bool(value) and all(nonempty(item) for item in value)


def validate(data):
    require(isinstance(data, dict), 'Report must be an object')
    for key in ('run_id', 'title'):
        require(nonempty(data.get(key)), f'Missing {key}')
    require(isinstance(data.get('scope'), list) and bool(data['scope']), 'scope must describe actual coverage')
    require(all(nonempty(s) for s in data['scope']), 'Invalid scope')
    require(isinstance(data.get('coverage'), list) and bool(data['coverage']), 'coverage must not be empty')
    for item in data['coverage']:
        require(isinstance(item, dict) and nonempty(item.get('check')), 'Invalid coverage check')
        require(item.get('result') in {'pass', 'fail', 'not_checked', 'not_applicable'}, 'Invalid coverage result')
        require(nonempty(item.get('evidence')), 'Coverage needs evidence or a reason it was not checked')
    require(isinstance(data.get('issues'), list), 'issues must be a list (empty is allowed)')
    ids = set()
    for item in data['issues']:
        require(isinstance(item, dict), 'Invalid issue')
        ident = item.get('id', '')
        require(isinstance(ident, str) and re.fullmatch(r'UI-\d{3,}', ident), 'Use stable UI-001 IDs')
        require(ident not in ids, f'Duplicate issue {ident}')
        ids.add(ident)
        require(item.get('kind') in {'defect', 'hypothesis', 'recommendation'}, f'{ident}: invalid kind')
        require(item.get('priority') in {'P0', 'P1', 'P2', 'P3'}, f'{ident}: invalid priority')
        require(item.get('status') in STATUSES, f'{ident}: invalid status')
        for key in ('title', 'location', 'observation', 'expected', 'basis', 'impact', 'fix', 'retest'):
            require(nonempty(item.get(key)), f'{ident}: missing {key}')
        require(evidence(item.get('before')), f'{ident}: missing initial evidence')
        if item['status'] in {'in_progress', 'fixed_pending_verification', 'verified'}:
            require(item['kind'] == 'defect', f'{ident}: confirm the defect before fixing')
        if item['status'] in {'fixed_pending_verification', 'verified'}:
            require(nonempty(item.get('change')), f'{ident}: missing implemented change')
        if item['status'] in {'blocked', 'deferred'}:
            require(nonempty(item.get('reason')), f'{ident}: missing blocked/deferred reason')
        if item['status'] == 'verified':
            v = item.get('verification', {})
            require(isinstance(v, dict) and v.get('result') == 'passed', f'{ident}: no passed retest')
            require(nonempty(v.get('method')) and nonempty(v.get('environment')),
                    f'{ident}: retest method and environment required')
            require(evidence(v.get('evidence')) and evidence(item.get('after')),
                    f'{ident}: retest and after evidence required')
    decisions = data.get('review_decisions', {})
    require(isinstance(decisions, dict), 'review_decisions must be an object')
    for ident, decision in decisions.items():
        require(ident in ids and isinstance(decision, dict), 'Unknown decision ID')
        require(set(decision) <= {'selected', 'note'}, 'Decision cannot change verification status')
        require(isinstance(decision.get('selected'), bool) and isinstance(decision.get('note', ''), str),
                'Invalid review decision')
    return data


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    require(not tmp.exists() and not tmp.is_symlink(), f'Temporary file already exists: {tmp}')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def render(data, output):
    validate(data)
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = (SKILL / 'assets/checklist.html').read_text(encoding='utf-8')
    require(template.count('__REPORT_DATA__') == 1, 'Invalid HTML template')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template.replace('__REPORT_DATA__', payload), encoding='utf-8')


def patch_issue(data, ident, patch):
    validate(data)
    require(isinstance(patch, dict) and 'id' not in patch, 'Patch must not replace identity')
    item = next((i for i in data['issues'] if i['id'] == ident), None)
    require(item is not None, f'Unknown issue: {ident}')
    old = item['status']
    new = patch.get('status', old)
    require(new == old or new in TRANSITIONS[old], f'Invalid status transition: {old} -> {new}')
    item.update(patch)
    if new != old:
        item.setdefault('history', []).append({'from': old, 'to': new,
            'at': datetime.now(timezone.utc).isoformat(timespec='seconds')})
    return validate(data)


def import_decisions(data, exported):
    validate(data)
    require(isinstance(exported, dict) and exported.get('run_id') == data['run_id'], 'Wrong report run')
    require(set(exported) <= {'run_id', 'review_decisions'}, 'Only user decisions may be imported')
    data['review_decisions'] = exported.get('review_decisions', {})
    return validate(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('render', 'patch', 'import-decisions'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--state', required=True, type=Path)
        if name == 'render':
            cmd.add_argument('--output', required=True, type=Path)
        if name == 'patch':
            cmd.add_argument('--id', required=True)
            cmd.add_argument('--patch', required=True, type=Path)
        if name == 'import-decisions':
            cmd.add_argument('--decisions', required=True, type=Path)
    args = parser.parse_args()
    data = read(args.state)
    if args.command == 'render':
        require(args.state.resolve() != args.output.resolve(), 'Output cannot overwrite state')
        render(data, args.output)
        print(f'Rendered {args.output}')
    elif args.command == 'patch':
        write(args.state, patch_issue(data, args.id, read(args.patch)))
        print(f'Updated {args.id}; render HTML again')
    else:
        write(args.state, import_decisions(data, read(args.decisions)))
        print('Imported selection and notes; technical verification is unchanged')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as error:
        raise SystemExit(f'Checklist failed: {error}')
