import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from install import install, STATE, USER


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.skill = self.source / 'skills/beoma-test'
        self.skill.mkdir(parents=True)
        (self.skill / 'SKILL.md').write_text('---\nname: beoma-test\ndescription: Test installation\n---\nInstructions.\n')
        self.target = self.root / 'target'

    def test_all_agents_and_repeat_update(self):
        first = install(self.source, self.target, ['codex', 'cursor', 'antigravity', 'claude'], revision='one')
        self.assertEqual(len(first), 2)
        (self.skill / 'asset.txt').write_text('v2')
        install(self.source, self.target, ['codex', 'claude'], revision='two')
        self.assertEqual((self.target / '.agents/skills/beoma-test/asset.txt').read_text(), 'v2')
        state = json.loads((self.target / STATE).read_text())
        self.assertEqual(state['installed']['.agents/skills/beoma-test']['revision'], 'two')

    def test_foreign_conflict_prevents_all_writes(self):
        foreign = self.target / '.claude/skills/beoma-test'
        foreign.mkdir(parents=True)
        (foreign / 'local.txt').write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'Unmanaged'):
            install(self.source, self.target, ['codex', 'claude'])
        self.assertFalse((self.target / '.agents').exists())
        self.assertEqual((foreign / 'local.txt').read_text(), 'preserve')

    def test_local_modification_is_preserved(self):
        install(self.source, self.target, ['codex'])
        changed = self.target / '.agents/skills/beoma-test/SKILL.md'
        changed.write_text('local edit')
        with self.assertRaisesRegex(ValueError, 'Locally modified'):
            install(self.source, self.target, ['codex'])
        self.assertEqual(changed.read_text(), 'local edit')

    def test_user_locations_and_selected_skill(self):
        install(self.source, self.target, list(USER), user=True, selected=['beoma-test'])
        for folder in set(USER.values()):
            self.assertTrue((self.target / folder / 'beoma-test/SKILL.md').exists())

    def test_stale_state_temp_prevents_writes(self):
        self.target.mkdir()
        (self.target / (STATE + '.tmp')).write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'temporary file'):
            install(self.source, self.target, ['codex'])
        self.assertFalse((self.target / '.agents').exists())

    def test_unknown_skill_and_symlink_rejected(self):
        with self.assertRaises(ValueError):
            install(self.source, self.target, ['codex'], selected=['beoma-missing'])
        external = self.root / 'external'
        external.mkdir()
        self.target.mkdir()
        (self.target / '.agents').symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink destination'):
            install(self.source, self.target, ['codex'])
        self.assertEqual(list(external.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
