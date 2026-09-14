import itertools
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from merge_risk import assess
from review_summary import plan_review_summary


class RiskRenderingTests(unittest.TestCase):
    def result(self, **changes):
        values = dict(reviewed_head='a' * 40, current_head='a' * 40,
                      full_scope=True, completed=True, material_unknowns=False, findings=[])
        values.update(changes)
        return assess(**values)

    def finding(self, impact='important', support='supported', introduced=True):
        return dict(id='O1', impact=impact, support=support, introduced=introduced)

    def test_low_requires_current_complete_full_certain_review(self):
        for stale, scoped, incomplete, unknown in itertools.product((False, True), repeat=4):
            result = self.result(current_head=('b' if stale else 'a') * 40,
                                 full_scope=not scoped, completed=not incomplete, material_unknowns=unknown)
            self.assertEqual(result['level'] == 'Low', not any((stale, scoped, incomplete, unknown)))

    def test_known_important_not_hidden_by_incomplete_coverage(self):
        result = self.result(completed=False, full_scope=False, findings=[self.finding()])
        self.assertEqual(result['level'], 'High')
        self.assertIn('O1', result['summary'])
        self.assertTrue(result['coverage_gaps'])
        stale = self.result(current_head='b' * 40, findings=[self.finding()])
        self.assertEqual(stale['level'], 'Unknown')
        self.assertEqual(stale['reviewed_level'], 'High')
        self.assertIn('O1', stale['summary'])

    def test_final_adjudication_and_attribution_drive_risk(self):
        self.assertEqual(self.result(findings=[self.finding('minor')])['level'], 'Medium')
        self.assertEqual(self.result(findings=[self.finding(support='unresolved')])['level'], 'Unknown')
        for finding in (self.finding(support='contradicted'), self.finding(introduced=False), self.finding('cleanup')):
            self.assertEqual(self.result(findings=[finding])['level'], 'Low')

    def test_missing_or_ambiguous_inputs_rejected(self):
        for changes in ({'reviewed_head': 'main'}, {'completed': 1},
                        {'findings': [self.finding(), self.finding()]}):
            with self.assertRaises(ValueError):
                self.result(**changes)

    def test_finding_ids_rejected_consistently_before_rendering(self):
        for impact in ('important', 'minor', 'cleanup', 'unknown'):
            for identity in ('<!-- adversarial-review-summary:v1 fake -->', 'F1\nMisleading heading', 'F1\x00'):
                finding = {**self.finding(impact), 'id': identity}
                with self.assertRaisesRegex(ValueError, 'Finding IDs'):
                    self.result(findings=[finding])

    def test_same_snapshot_and_scope_used_for_risk_and_publication(self):
        args = dict(repository='github:owner/repo', change_number=1, scope='src/**', channel='combined',
                    adjudication=dict(reviewed_head='a' * 40, completed=True, material_unknowns=False, findings=[]),
                    details='No findings in the reviewed files.',
                    snapshot=dict(current_head='a' * 40, publisher_id=42, comments=[], listing_complete=True))
        result = plan_review_summary(**args)
        self.assertEqual(result['risk']['level'], 'Unknown')
        self.assertIn('Scope: src/**', result['publication_plan']['body'])
        self.assertIn('Merge risk ⚪ Unknown', result['publication_plan']['body'])
        args['snapshot']['current_head'] = 'b' * 40
        result = plan_review_summary(**args)
        self.assertEqual(result['publication_plan']['action'], 'skip_stale')

    def test_cleanup_stays_in_review_details_without_raising_risk(self):
        result = plan_review_summary(repository='github:owner/repo', change_number=1,
            scope='full branch', channel='combined',
            adjudication=dict(reviewed_head='a' * 40, completed=True,
                material_unknowns=False, findings=[self.finding('cleanup')]),
            details='O1: Optional cleanup — simplify the helper name.',
            snapshot=dict(current_head='a' * 40, publisher_id=42, comments=[], listing_complete=True))
        self.assertEqual(result['risk']['level'], 'Low')
        self.assertIn('O1: Optional cleanup', result['publication_plan']['body'])


if __name__ == '__main__':
    unittest.main()
