"""Copy portable skills into native discovery paths without overwriting local work."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from check import ROOT, validate

PROJECT = {'codex': '.agents/skills', 'cursor': '.agents/skills',
           'antigravity': '.agents/skills', 'claude': '.claude/skills'}
USER = {'codex': '.agents/skills', 'cursor': '.agents/skills',
        'antigravity': '.gemini/config/skills', 'claude': '.claude/skills'}
STATE = '.beoma-skills-state.json'
SOURCE = 'https://github.com/elementary1997/beoma-skills'


def digest(folder):
    files = {}
    for path in sorted(folder.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Symlink in skill tree: {path}')
        if path.is_file():
            files[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def safe_target(base, relative):
    path = base / relative
    for parent in [path, *path.parents]:
        if parent == base:
            break
        if parent.is_symlink():
            raise ValueError(f'Refusing symlink destination: {parent}')
    return path


def install(source, base, agents, user=False, selected=None, revision='unknown'):
    source = source.resolve()
    base = base.resolve()
    available = {s.name: s for s in validate(source)}
    names = sorted(available) if selected is None else sorted(set(selected))
    if not names or set(names) - available.keys():
        raise ValueError('Empty or unknown skill selection')
    targets = sorted({(USER if user else PROJECT)[a] for a in agents})
    if not targets:
        raise ValueError('No agents selected')
    state_path = safe_target(base, STATE)
    state = json.loads(state_path.read_text()) if state_path.exists() else {'version': 1, 'installed': {}}
    if state.get('version') != 1 or not isinstance(state.get('installed'), dict):
        raise ValueError('Unsupported installation state')
    temp = safe_target(base, STATE + '.tmp')
    if temp.exists():
        raise ValueError(f'State temporary file already exists: {temp}')
    pending = []
    # Check every destination before the first write; never overwrite foreign/local edits.
    for target in targets:
        for name in names:
            key = f'{target}/{name}'
            dst = safe_target(base, key)
            entry = state['installed'].get(key)
            if dst.exists():
                if not dst.is_dir() or entry is None or entry.get('source') != SOURCE:
                    raise ValueError(f'Unmanaged destination: {dst}')
                if digest(dst) != entry['files']:
                    raise ValueError(f'Locally modified destination: {dst}')
            pending.append((key, available[name], dst, digest(available[name])))
    for key, src, dst, hashes in pending:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        state['installed'][key] = {'source': SOURCE, 'revision': revision, 'files': hashes}
    base.mkdir(parents=True, exist_ok=True)
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    temp.replace(state_path)
    return [key for key, _, _, _ in pending]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--project', type=Path)
    scope.add_argument('--user', action='store_true')
    parser.add_argument('--agents', nargs='+', choices=list(PROJECT), default=list(PROJECT))
    parser.add_argument('--skills', nargs='+')
    parser.add_argument('--allow-dirty', action='store_true', help='Install a local development snapshot')
    args = parser.parse_args()
    if args.project:
        project = args.project.resolve()
        if not project.is_dir():
            parser.error('Project directory must exist')
        top = subprocess.check_output(['git', '-C', str(project), 'rev-parse', '--show-toplevel'], text=True).strip()
        if Path(top).resolve() != project:
            parser.error('--project must point to a Git repository root (including worktrees)')
    dirty = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=all'], text=True)
    if dirty and not args.allow_dirty:
        parser.error('Source has local changes; use a clean revision or explicit --allow-dirty for development')
    sha = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    revision = sha + ('+dirty' if dirty else '')
    for target in install(ROOT, Path.home() if args.user else args.project, args.agents,
                          args.user, args.skills, revision):
        print(f'Installed {target} from {revision}')
    print('Verify skill discovery in a new agent session.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'Installation failed: {error}')
