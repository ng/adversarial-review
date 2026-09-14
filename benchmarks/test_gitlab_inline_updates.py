import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from gitlab_discussions import GitLabDiscussions
from gitlab_inline_updates import GitLabInlineUpdates, snapshot_digest
from publication_batch import PublicationBatch
from summary_coordinator import LocalCoordinator


class GitLabInlineUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.coordinator = LocalCoordinator(self.temp.name)
        self.head, self.writes, self.after_write = 'a' * 40, [], None
        self.rows = [dict(id='thread-' + str(i), individual_note=False, notes=[dict(
            id=i, author={'id': 42}, body='Old ' + str(i), system=False,
            type='DiffNote', resolved=False, project_id=17, noteable_id=81,
            noteable_type='MergeRequest', position={'new_path': 'a.py', 'new_line': i})]) for i in (9, 19)]
        self.rows[0]['notes'].append(dict(self.rows[0]['notes'][0], id=10,
                                        author={'id': 99}, body='Human reply', type='DiscussionNote'))
        self.reader = GitLabDiscussions(self.request, 'https://gitlab.example', 17, 3)
        self.publisher = GitLabInlineUpdates(self.reader)
        self.context = dict(scope='full branch', channel='combined')
        with self.coordinator.claim(self.reader.resource, 1) as tx:
            batch = PublicationBatch(tx, [dict(action='create', target_kind='inline', body='Old ' + str(i),
                preconditions={'publisher_id': 42, 'current_head': self.head}, **self.context) for i in (9, 19)])
            for i in (9, 19):
                plan = batch.start_step()
                batch.finish_step(dict(comment_id=i, publisher_id=42, body=plan['body'], thread_id='thread-' + str(i)))
            batch.finish()
        self.args = dict(reviewed_head=self.head, **self.context, run_version=2,
                         coordinator=self.coordinator,
                         adjudicated_snapshot_sha256=snapshot_digest(self.reader.snapshot()), findings=[dict(
                             id='finding-' + str(i), body='Updated ' + str(i), disposition='existing',
                             matched_thread_id='thread-' + str(i), location={'path': 'a.py', 'line': i + 50},
                             evidence='Same trigger and failure', verified_head=self.head) for i in (9, 19)])

    def request(self, method, path, body):
        if method == 'GET':
            if path == '/user':
                return {'id': 42}
            if path == self.reader.root:
                return dict(id=81, project_id=17, iid=3, state='opened', sha=self.head)
            return copy.deepcopy(self.rows)
        self.assertEqual(method, 'PUT')
        self.assertEqual(set(body), {'body'})
        self.writes.append(path)
        row = next(d for d in self.rows if '/discussions/' + d['id'] + '/notes/' in path)['notes'][0]
        self.assertTrue(path.endswith('/' + str(row['id'])))
        row['body'] = body['body']
        if self.after_write:
            self.after_write()
        return copy.deepcopy(row)

    def test_two_root_updates_then_noop_preserve_human_reply(self):
        result = self.publisher.publish_updates(**self.args)
        self.assertEqual(result['writes'], 2)
        self.assertEqual(self.rows[0]['notes'][1]['body'], 'Human reply')
        self.assertEqual([p.rsplit('/', 1)[1] for p in self.writes], ['9', '19'])
        self.args.update(run_version=3, adjudicated_snapshot_sha256=snapshot_digest(self.reader.snapshot()))
        self.assertEqual(self.publisher.publish_updates(**self.args)['action'], 'noop')
        self.assertEqual(len(self.writes), 2)

    def test_reply_after_adjudication_prevents_any_write(self):
        self.rows[0]['notes'][1]['body'] = 'New objection'
        with self.assertRaisesRegex(ValueError, 'since adjudication'):
            self.publisher.publish_updates(**self.args)
        self.assertEqual(self.writes, [])

    def test_reply_between_writes_stops_tail_and_recovery_does_not_replay(self):
        self.after_write = lambda: self.rows[0]['notes'][1].update(body='New objection')
        with self.assertRaisesRegex(ValueError, 'during batch'):
            self.publisher.publish_updates(**self.args)
        self.assertEqual(len(self.writes), 1)
        result = self.reader.recover_batch(self.coordinator)
        self.assertEqual((result['confirmed_writes'], result['not_attempted']), (1, 1))
        self.assertEqual(len(self.writes), 1)

    def test_timeout_after_remote_success_recovers_without_duplicate(self):
        def timeout():
            raise TimeoutError('Response lost')
        self.after_write = timeout
        with self.assertRaises(TimeoutError):
            self.publisher.publish_updates(**self.args)
        self.args['run_version'] = 3
        with self.assertRaisesRegex(ValueError, 'Uncertain'):
            self.publisher.publish_updates(**self.args)
        self.assertEqual(self.reader.recover_batch(self.coordinator)['confirmed_writes'], 1)
        self.assertEqual(len(self.writes), 1)

    def test_new_issue_rejected_before_any_update(self):
        self.args['findings'][1].update(disposition='new', matched_thread_id=None)
        with self.assertRaisesRegex(ValueError, 'separate diff-position'):
            self.publisher.publish_updates(**self.args)
        self.assertEqual(self.writes, [])

    def test_foreign_write_response_stays_uncertain_even_after_remote_success(self):
        def request(method, path, body):
            result = self.request(method, path, body)
            if method == 'PUT':
                result['noteable_id'] = 999
            return result
        self.reader.request = request
        with self.assertRaisesRegex(ValueError, 'expected public MR diff root'):
            self.publisher.publish_updates(**self.args)
        self.assertEqual(len(self.writes), 1)
        self.args['run_version'] = 3
        with self.assertRaisesRegex(ValueError, 'Uncertain'):
            self.publisher.publish_updates(**self.args)

    def test_reply_during_prewrite_recheck_prevents_batch(self):
        changed = False
        def request(method, path, body):
            nonlocal changed
            result = self.request(method, path, body)
            if '/discussions?' in path and not changed:
                changed = True
                self.rows[0]['notes'][1]['body'] = 'New objection'
            return result
        self.reader.request = request
        with self.assertRaisesRegex(ValueError, 'before batch'):
            self.publisher.publish_updates(**self.args)
        self.assertEqual(self.writes, [])

    def test_stale_commit_skips_without_write(self):
        self.head = 'b' * 40
        self.assertEqual(self.publisher.publish_updates(**self.args)['action'], 'skip_stale')
        self.assertEqual(self.writes, [])


if __name__ == '__main__':
    unittest.main()
