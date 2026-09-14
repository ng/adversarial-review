import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from gitlab_discussions import GitLabDiscussions
from publication_batch import PublicationBatch
from summary_coordinator import LocalCoordinator


class GitLabDiscussionTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.mr = dict(id=81, project_id=17, iid=3, sha='a' * 40, state='opened')
        self.reader = GitLabDiscussions(self.request, 'https://gitlab.example', 17, 3)
        self.rows = [dict(id='diff-1', individual_note=False, notes=[
            self.note(9), self.note(10, author=99, kind='DiscussionNote')])]

    def note(self, nid, *, author=42, kind='DiffNote'):
        return dict(id=nid, author={'id': author}, body='Note ' + str(nid), type=kind,
                    project_id=17, noteable_id=81, noteable_type='MergeRequest',
                    system=False, resolved=False, position={'new_path': 'a.py', 'new_line': 8})

    def request(self, method, path, body):
        self.assertEqual((method, body), ('GET', None))
        self.calls.append(path)
        if path == '/user':
            return {'id': 42}
        if path == self.reader.root:
            return copy.deepcopy(self.mr)
        page = int(path.rsplit('=', 1)[1])
        return copy.deepcopy(self.rows[(page - 1) * 100:page * 100])

    def test_roots_not_replies_are_recovery_candidates(self):
        snapshot = self.reader.snapshot()
        self.assertEqual([r['comment_id'] for r in snapshot['comments']], [9])
        self.assertEqual(snapshot['threads'][0]['replies'][0]['author_id'], 99)
        self.assertFalse(snapshot['threads'][0]['managed'])
        self.assertEqual(snapshot['positions']['diff-1']['new_line'], 8)

    def test_summary_and_overview_threads_are_distinguished(self):
        self.rows.extend([
            dict(id='summary', individual_note=True, notes=[self.note(11, kind=None)]),
            dict(id='overview', individual_note=False, notes=[self.note(12, kind='DiscussionNote')])])
        snapshot = self.reader.snapshot()
        self.assertEqual([r['target_kind'] for r in snapshot['comments']], ['inline', 'summary'])
        self.assertEqual(len(snapshot['threads']), 3)

    def test_filtered_full_page_does_not_end_pagination(self):
        first = [dict(id='system-' + str(i), individual_note=True,
                      notes=[{**self.note(i + 100, kind=None), 'system': True}]) for i in range(100)]
        self.rows = first + self.rows
        self.assertEqual(len(self.reader.snapshot()['comments']), 1)
        self.assertTrue(any('page=2' in p for p in self.calls))

    def test_foreign_duplicate_or_missing_resolution_fails(self):
        original = copy.deepcopy(self.rows)
        for mutation in ({'project_id': 18}, {'noteable_id': 82}, {'resolved': None}):
            self.rows = copy.deepcopy(original)
            self.rows[0]['notes'][0].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.reader.snapshot()
        self.rows = original * 2
        with self.assertRaisesRegex(ValueError, 'Duplicate discussion'):
            self.reader.snapshot()

    def test_internal_root_does_not_promote_public_reply(self):
        self.rows[0]['notes'][0]['internal'] = True
        self.assertEqual(self.reader.snapshot()['comments'], [])

    def test_push_during_collection_rejects_snapshot(self):
        def request(method, path, body):
            result = self.request(method, path, body)
            if '/discussions?' in path:
                self.mr['sha'] = 'b' * 40
            return result
        self.reader.request = request
        with self.assertRaisesRegex(ValueError, 'changed during collection'):
            self.reader.snapshot()

    def test_closed_mr_read_only_recovery_uses_actual_discussion_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = LocalCoordinator(directory)
            plan = dict(action='update', target_kind='inline', thread_id='diff-1',
                        comment_id=9, body='Note 9', preconditions={
                            'publisher_id': 42, 'current_head': 'a' * 40})
            with coordinator.claim(self.reader.resource, 1) as tx:
                PublicationBatch(tx, [plan]).start_step()
            self.mr['state'] = 'merged'
            with self.assertRaisesRegex(ValueError, 'not open'):
                self.reader.snapshot()
            result = self.reader.recover_batch(coordinator)
            self.assertEqual(result['confirmed_writes'], 1)

    def test_provider_snapshot_and_history_plan_same_inline_root_update(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = LocalCoordinator(directory)
            context = dict(scope='full branch', channel='combined')
            with coordinator.claim(self.reader.resource, 1) as tx:
                batch = PublicationBatch(tx, [dict(action='create', target_kind='inline',
                    body='Note 9', preconditions={'publisher_id': 42, 'current_head': 'a' * 40}, **context)])
                batch.start_step()
                batch.finish_step(dict(comment_id=9, thread_id='diff-1', publisher_id=42, body='Note 9'))
                batch.finish()
            with coordinator.claim(self.reader.resource, 2) as tx:
                plan = self.reader.plan_findings(tx, reviewed_head='a' * 40, **context, findings=[dict(
                    id='later-run-id', body='Updated evidence', location={'path': 'a.py', 'line': 25},
                    disposition='existing', matched_thread_id='diff-1',
                    evidence='Same missing-record trigger and null dereference', verified_head='a' * 40)])
                self.assertEqual((plan['actions'][0]['action'], plan['actions'][0]['comment_id']), ('update', 9))
                self.assertIn('discussion_sha256', plan['actions'][0]['preconditions'])


if __name__ == '__main__':
    unittest.main()
