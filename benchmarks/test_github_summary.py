from contextlib import contextmanager
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from github_summary import GitHubSummary


class Coordinator:
    def __init__(self):
        self.state = 'new'
    @contextmanager
    def claim(self, resource, version):
        if self.state == 'uncertain':
            raise ValueError('Uncertain prior write')
        yield self
    def pending(self, plan):
        self.state = 'pending'
    def uncertain(self):
        self.state = 'uncertain'
    def complete(self, result):
        self.state = 'complete'


class GitHubSummaryTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.writes = [], []
        self.head = 'a' * 40
        self.coordinator = Coordinator()
        self.adapter = GitHubSummary(self.request, 'Owner/Repo', 1)
        self.args = dict(reviewed_head=self.head, scope='full branch', channel='combined',
                         summary='Findings', run_version=1, coordinator=self.coordinator)

    def request(self, method, path, body):
        if method != 'GET':
            self.assert_pending()
            self.writes.append((method, path, body))
            if method == 'POST':
                self.rows.append({'id': 7, 'body': body['body'], 'user': {'id': 42}})
            else:
                self.rows[0]['body'] = body['body']
            return self.rows[0].copy()
        if path == '/user':
            return {'id': 42}
        if '/pulls/' in path:
            return {'state': 'open', 'head': {'sha': self.head}}
        page = int(path.rsplit('=', 1)[1])
        return self.rows[(page - 1) * 100:page * 100]

    def assert_pending(self):
        self.assertEqual(self.coordinator.state, 'pending')

    def test_create_noop_then_update(self):
        self.assertEqual(self.adapter.publish(**self.args)['action'], 'create')
        result = self.adapter.publish(**self.args)
        self.assertEqual(result, {'action': 'noop', 'comment_id': 7, 'reviewed_head': self.head})
        self.args['summary'] = 'Changed findings'
        self.assertEqual(self.adapter.publish(**self.args)['action'], 'update')
        self.assertEqual([w[0] for w in self.writes], ['POST', 'PATCH'])

    def test_pagination_and_head_recheck(self):
        self.rows = [{'id': i + 1, 'body': 'human', 'user': {'id': 99}} for i in range(101)]
        self.assertEqual(len(self.adapter.snapshot()['comments']), 101)
        request = self.request
        reads = 0
        def changed(method, path, body):
            nonlocal reads
            if '/pulls/' in path:
                reads += 1
                if reads == 2:
                    self.head = 'b' * 40
            return request(method, path, body)
        self.adapter.request = changed
        with self.assertRaisesRegex(ValueError, 'state changed'):
            self.adapter.publish(**self.args)
        self.assertEqual(self.writes, [])

    def test_timeout_blocks_blind_retry(self):
        request = self.request
        def timeout(method, path, body):
            response = request(method, path, body)
            if method != 'GET':
                raise TimeoutError('Remote result unknown')
            return response
        self.adapter.request = timeout
        with self.assertRaises(TimeoutError):
            self.adapter.publish(**self.args)
        self.assertEqual(len(self.rows), 1)  # Remote write happened before timeout.
        with self.assertRaisesRegex(ValueError, 'Uncertain'):
            self.adapter.publish(**self.args)
        self.assertEqual(len(self.writes), 1)

    def test_adjudicated_review_updates_risk_on_same_comment(self):
        args = dict(adjudication=dict(reviewed_head=self.head, completed=True,
                    material_unknowns=False, findings=[]), scope='full branch',
                    channel='combined', details='Reviewed the complete change.',
                    run_version=1, coordinator=self.coordinator)
        self.assertEqual(self.adapter.publish_review(**args)['action'], 'create')
        self.assertIn('Merge risk 🟢 Low', self.rows[0]['body'])
        self.assertEqual(self.adapter.publish_review(**args)['action'], 'noop')
        args['adjudication']['findings'] = [dict(id='F1', support='supported',
                                               impact='important', introduced=True)]
        self.assertEqual(self.adapter.publish_review(**args)['action'], 'update')
        self.assertIn('Merge risk 🔴 High', self.rows[0]['body'])
        self.assertEqual(self.rows[0]['id'], 7)
        self.assertEqual(len(self.writes), 2)

    def test_adjudicated_review_rechecks_head(self):
        adjudication = dict(reviewed_head=self.head, completed=True,
                            material_unknowns=False, findings=[])
        args = dict(adjudication=adjudication, scope='full branch', channel='combined',
                    details='Complete review.', run_version=1, coordinator=self.coordinator)
        request = self.request
        reads = 0
        def changed(method, path, body):
            nonlocal reads
            if '/pulls/' in path:
                reads += 1
                adjudication['completed'] = False
                if reads == 2:
                    self.head = 'b' * 40
            return request(method, path, body)
        self.adapter.request = changed
        with self.assertRaisesRegex(ValueError, 'state changed'):
            self.adapter.publish_review(**args)
        self.assertEqual(self.writes, [])
        self.adapter.request = request
        self.assertEqual(self.adapter.publish_review(**args)['action'], 'skip_stale')

    def test_adjudication_is_frozen_before_provider_reads(self):
        adjudication = dict(reviewed_head=self.head, completed=True,
                            material_unknowns=False, findings=[])
        request = self.request
        def mutate(method, path, body):
            adjudication['findings'].append(dict(id='F1', support='supported',
                                                impact='important', introduced=True))
            return request(method, path, body)
        self.adapter.request = mutate
        self.adapter.publish_review(adjudication=adjudication, scope='full branch',
            channel='combined', details='Complete review.', run_version=1,
            coordinator=self.coordinator)
        self.assertIn('Merge risk 🟢 Low', self.rows[0]['body'])

    def test_scoped_adjudication_cannot_publish_low(self):
        args = dict(adjudication=dict(reviewed_head=self.head, completed=True,
                    material_unknowns=False, findings=[]), scope='src/ only',
                    channel='combined', details='Only src/ was reviewed.',
                    run_version=1, coordinator=self.coordinator)
        self.adapter.publish_review(**args)
        self.assertIn('Merge risk ⚪ Unknown', self.rows[0]['body'])


if __name__ == '__main__':
    unittest.main()
