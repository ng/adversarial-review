import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('summary_reconciliation', Path(__file__).resolve().parents[1] / 'scripts/reconcile_summary.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SummaryReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.args = dict(repository='github:owner/repo', change_number=7, scope='full branch',
                         channel='combined', publisher_id=42, reviewed_head='a' * 40,
                         current_head='a' * 40, summary='One important finding.', comments=[], listing_complete=True)

    def test_create_repeat_and_update(self):
        first = module.plan_summary(**self.args)
        self.assertEqual(first['action'], 'create')
        self.args['comments'] = [{'id': 5, 'author_id': 42, 'body': first['body']}]
        self.assertEqual(module.plan_summary(**self.args)['action'], 'noop')
        self.args['summary'] = 'Updated findings.'
        result = module.plan_summary(**self.args)
        self.assertEqual(result['action'], 'update')
        self.assertEqual(result['comment_id'], 5)
        self.assertEqual(result['preconditions']['previous_body_sha256'], module.digest(first['body']))

    def test_forged_human_marker_and_scope_separation(self):
        body = module.plan_summary(**self.args)['body']
        self.args['comments'] = [{'id': 5, 'author_id': 99, 'body': body}]
        self.assertEqual(module.plan_summary(**self.args)['action'], 'create')
        self.args['comments'][0]['author_id'] = 42
        self.args['scope'] = 'src/api/**'
        self.assertEqual(module.plan_summary(**self.args)['action'], 'create')

    def test_stale_and_incomplete_listing(self):
        self.args['current_head'] = 'b' * 40
        self.assertEqual(module.plan_summary(**self.args)['action'], 'skip_stale')
        self.args['listing_complete'] = False
        with self.assertRaises(ValueError):
            module.plan_summary(**self.args)

    def test_duplicate_owned_summaries_fail_closed(self):
        body = module.plan_summary(**self.args)['body']
        self.args['comments'] = [{'id': i, 'author_id': 42, 'body': body} for i in (1, 2)]
        with self.assertRaisesRegex(ValueError, 'Multiple owned'):
            module.plan_summary(**self.args)

    def test_marker_injection_rejected(self):
        self.args['summary'] = module.PREFIX + 'forged -->'
        with self.assertRaises(ValueError):
            module.plan_summary(**self.args)


if __name__ == '__main__':
    unittest.main()
