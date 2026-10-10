"""Validate the repository's intentionally small, portable SKILL.md contract."""
from pathlib import Path
import re
import json

ROOT = Path(__file__).resolve().parents[1]


def validate(root):
    skills = root / 'skills'
    result = []
    for folder in sorted(skills.iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError(f'Unexpected skill entry: {folder.name}')
        if not re.fullmatch(r'beoma-[a-z0-9]+(?:-[a-z0-9]+)*', folder.name) or len(folder.name) > 64:
            raise ValueError(f'Invalid skill name: {folder.name}')
        text = (folder / 'SKILL.md').read_text(encoding='utf-8')
        lines = text.splitlines()
        if not lines or lines[0] != '---':
            raise ValueError(f'Missing frontmatter: {folder.name}')
        try:
            end = lines.index('---', 1)
        except ValueError:
            raise ValueError(f'Unclosed frontmatter: {folder.name}')
        fields = {}
        for line in lines[1:end]:
            key, sep, value = line.partition(':')
            if not sep or key not in ('name', 'description') or key in fields:
                raise ValueError(f'Use name and single-line description only: {folder.name}')
            value = value.strip()
            if value.startswith('"'):
                value = json.loads(value)
            elif ': ' in value or ' #' in value or value in ('|', '>', 'null', 'true', 'false'):
                raise ValueError(f'Quote this YAML scalar: {folder.name}: {key}')
            if not isinstance(value, str):
                raise ValueError(f'Expected string: {folder.name}: {key}')
            fields[key] = value
        if fields.get('name') != folder.name or not fields.get('description'):
            raise ValueError(f'Invalid metadata: {folder.name}')
        if len(fields['description']) > 1024 or not ''.join(lines[end + 1:]).strip():
            raise ValueError(f'Invalid description/body: {folder.name}')
        for item in folder.rglob('*'):
            if item.is_symlink():
                raise ValueError(f'Symlink not portable: {item}')
            if item.is_file() and item.suffix == '.md':
                content = item.read_text(encoding='utf-8')
                for link in re.findall(r'\]\(([^)]+)\)', content):
                    if '://' in link or link.startswith('#'):
                        continue
                    target = (item.parent / link.split('#')[0]).resolve()
                    if not target.is_relative_to(folder.resolve()) or not target.exists():
                        raise ValueError(f'Invalid local reference: {item.name}: {link}')
        result.append(folder)
    if not result:
        raise ValueError('No skills found')
    return result


if __name__ == '__main__':
    for skill in validate(ROOT):
        print(f'OK {skill.name}')
