import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'reconcile_findings', Path(__file__).resolve().parents[1] / 'scripts/reconcile_findings.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FindingReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.thread = dict(id='thread-7', root_comment_id=9, author_id=42,
                           body='Original issue and evidence', managed=True, resolved=False,
                           replies=[])
        self.finding = dict(id='run-local-99', body='Same defect, updated evidence',
                            location=dict(path='src/service.py', line=91),
                            disposition='existing', matched_thread_id='thread-7',
                            evidence='Same unchecked null on the missing-record path',
                            verified_head='a' * 40)
        self.args = dict(reviewed_head='a' * 40, current_head='a' * 40,
                         publisher_id=42, threads=[self.thread], findings=[self.finding],
                         listing_complete=True)

    def test_moved_line_updates_same_root_and_repeat_is_noop(self):
        plan = module.plan_findings(**self.args)
        action = plan['actions'][0]
        self.assertEqual((action['action'], action['thread_id'], action['comment_id']),
                         ('update', 'thread-7', 9))
        self.assertNotIn('location', action)  # Never relocate the provider thread.
        self.assertIn('src/service.py:91', action['body'])
        self.thread['body'] = action['body']
        self.finding['id'] = 'different-run-id'
        self.assertEqual(module.plan_findings(**self.args)['actions'][0]['action'], 'noop')

    def test_omission_preserves_prior_issue(self):
        self.args['findings'] = []
        plan = module.plan_findings(**self.args)
        self.assertEqual(plan['actions'], [])
        self.assertEqual(plan['preserved_thread_ids'], ['thread-7'])

    def test_new_issue_does_not_reuse_same_line_thread(self):
        self.finding.update(disposition='new', matched_thread_id=None,
                            evidence='Different trigger and failure from thread 7')
        plan = module.plan_findings(**self.args)
        self.assertEqual(plan['actions'][0]['action'], 'create')
        self.assertEqual(plan['preserved_thread_ids'], ['thread-7'])

    def test_human_unmanaged_resolved_threads_rejected(self):
        for mutation in ({'author_id': 99}, {'managed': False}, {'resolved': True}):
            with self.subTest(mutation=mutation):
                args = copy.deepcopy(self.args)
                args['threads'][0].update(mutation)
                with self.assertRaises(ValueError):
                    module.plan_findings(**args)

    def test_ambiguous_or_unknown_matches_rejected(self):
        duplicate = {**self.finding, 'id': 'other'}
        self.args['findings'].append(duplicate)
        with self.assertRaises(ValueError):
            module.plan_findings(**self.args)
        self.args['findings'] = [{**self.finding, 'matched_thread_id': 'thread-8'}]
        with self.assertRaises(ValueError):
            module.plan_findings(**self.args)

    def test_incomplete_stale_and_wrong_evidence(self):
        self.args['listing_complete'] = False
        with self.assertRaises(ValueError):
            module.plan_findings(**self.args)
        self.args['listing_complete'] = True
        self.args['current_head'] = 'b' * 40
        self.assertEqual(module.plan_findings(**self.args)['action'], 'skip_stale')
        self.args['current_head'] = 'a' * 40
        self.finding['verified_head'] = 'b' * 40
        with self.assertRaises(ValueError):
            module.plan_findings(**self.args)

    def test_planning_does_not_mutate_inputs(self):
        original = copy.deepcopy(self.args)
        module.plan_findings(**self.args)
        self.assertEqual(self.args, original)

    def test_new_human_reply_changes_plan_without_becoming_edit_target(self):
        before = module.plan_findings(**self.args)
        self.thread['replies'].append(dict(id=11, author_id=99, body='This trigger is impossible.'))
        after = module.plan_findings(**self.args)
        self.assertNotEqual(before['discussion_sha256'], after['discussion_sha256'])
        self.assertNotEqual(before, after)
        self.assertEqual(after['actions'][0]['comment_id'], 9)
        self.assertNotIn('This trigger is impossible.', after['actions'][0]['body'])

    def test_unmatched_discussion_changes_invalidate_new_issue_plan(self):
        self.finding.update(disposition='new', matched_thread_id=None)
        before = module.plan_findings(**self.args)
        self.thread['replies'].append(dict(id=11, author_id=99, body='Already reported here.'))
        after = module.plan_findings(**self.args)
        self.assertNotEqual(before['actions'][0]['preconditions'],
                            after['actions'][0]['preconditions'])

    def test_missing_or_duplicate_reply_listing_rejected(self):
        for replies in (None, [dict(id=9, author_id=99, body='Duplicate root ID')],
                        [dict(id=11, author_id=99, body='One'),
                         dict(id=11, author_id=99, body='Duplicate')]):
            with self.subTest(replies=replies):
                self.thread['replies'] = replies
                with self.assertRaises(ValueError):
                    module.plan_findings(**self.args)

    def test_provider_thread_order_does_not_change_snapshot(self):
        self.args['threads'].append(dict(id='thread-8', root_comment_id=12, author_id=99,
                                       body='Other discussion', managed=False, resolved=False,
                                       replies=[]))
        before = module.plan_findings(**self.args)
        self.args['threads'].reverse()
        self.assertEqual(before, module.plan_findings(**self.args))


if __name__ == '__main__':
    unittest.main()
