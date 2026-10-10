import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/beoma-ui-review/scripts/checklist.py'
spec = importlib.util.spec_from_file_location('ui_checklist', SCRIPT)
checklist = importlib.util.module_from_spec(spec)
with patch.object(sys, 'dont_write_bytecode', True):
    spec.loader.exec_module(checklist)


def fixture():
    return {'run_id': 'synthetic-contract-test', 'title': 'Synthetic UI report — no live audit',
            'scope': ['Synthetic fixture; no application tested'],
            'coverage': [{'check': 'Keyboard', 'result': 'not_checked', 'evidence': 'No browser supplied'}],
            'issues': [{'id': 'UI-001', 'kind': 'defect', 'priority': 'P2', 'status': 'open',
                        'title': 'Synthetic clipping', 'location': 'Fixture at 390 CSS px',
                        'observation': 'Synthetic overflow', 'expected': 'Content fits container',
                        'basis': 'Fixture requirement', 'impact': 'Action hidden',
                        'before': ['Synthetic measurement'], 'fix': 'Adjust container',
                        'retest': 'Verify content fits'}]}


class ChecklistTests(unittest.TestCase):
    def test_full_fix_cycle_and_history(self):
        data = fixture()
        checklist.patch_issue(data, 'UI-001', {'status': 'in_progress'})
        checklist.patch_issue(data, 'UI-001', {'status': 'fixed_pending_verification', 'change': 'Adjusted synthetic CSS'})
        checklist.patch_issue(data, 'UI-001', {'status': 'verified', 'after': ['Synthetic retest result'],
            'verification': {'result': 'passed', 'method': 'Synthetic scenario',
                             'environment': 'Unit test fixture', 'evidence': ['Scenario repeated']}})
        self.assertEqual(len(data['issues'][0]['history']), 3)
        self.assertEqual(data['issues'][0]['status'], 'verified')

    def test_cannot_skip_verification_or_finish_without_evidence(self):
        with self.assertRaisesRegex(ValueError, 'Invalid status transition'):
            checklist.patch_issue(fixture(), 'UI-001', {'status': 'verified'})
        data = fixture()
        data['issues'][0].update(status='verified', change='Edited code')
        with self.assertRaisesRegex(ValueError, 'passed retest'):
            checklist.validate(data)

    def test_recommendations_are_not_auto_fixes(self):
        data = fixture()
        data['issues'][0]['kind'] = 'recommendation'
        with self.assertRaisesRegex(ValueError, 'confirm the defect'):
            checklist.patch_issue(data, 'UI-001', {'status': 'in_progress'})

    def test_duplicate_ids_and_unexplained_coverage_are_rejected(self):
        data = fixture()
        data['issues'].append(copy.deepcopy(data['issues'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            checklist.validate(data)
        data = fixture()
        data['coverage'][0]['evidence'] = ''
        with self.assertRaisesRegex(ValueError, 'Coverage needs'):
            checklist.validate(data)

    def test_no_findings_still_has_real_coverage(self):
        data = fixture()
        data['issues'] = []
        checklist.validate(data)

    def test_decisions_do_not_change_verification(self):
        data = fixture()
        checklist.import_decisions(data, {'run_id': data['run_id'], 'review_decisions': {
            'UI-001': {'selected': False, 'note': 'Later'}}})
        self.assertEqual(data['issues'][0]['status'], 'open')
        with self.assertRaisesRegex(ValueError, 'Only user decisions'):
            checklist.import_decisions(data, {'run_id': data['run_id'], 'issues': []})
        with self.assertRaisesRegex(ValueError, 'Wrong report run'):
            checklist.import_decisions(data, {'run_id': 'other'})

    def test_status_cannot_be_imported_as_user_decision(self):
        data = fixture()
        with self.assertRaisesRegex(ValueError, 'cannot change'):
            checklist.import_decisions(data, {'run_id': data['run_id'], 'review_decisions': {
                'UI-001': {'selected': True, 'status': 'verified'}}})

    def test_payload_cannot_break_out_of_script(self):
        data = fixture()
        data['issues'][0]['title'] = '</script><script>alert(1)</script>'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.html'
            checklist.render(data, path)
            html = path.read_text()
            self.assertNotIn(data['issues'][0]['title'], html)
            payload = html.split('<script id="report-data" type="application/json">')[1].split('</script>')[0]
            self.assertEqual(json.loads(payload)['issues'][0]['title'], data['issues'][0]['title'])


if __name__ == '__main__':
    unittest.main()
