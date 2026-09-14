from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from gitlab_summary import GitLabSummary
from summary_coordinator import LocalCoordinator


class GitLabSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.rows, self.writes = [], []
        self.head = 'a' * 40
        self.adapter = GitLabSummary(self.request, 'https://gitlab.example', 17, 3)
        self.args = dict(reviewed_head=self.head, scope='full branch', channel='combined', summary='Findings',
                         run_version=1, coordinator=LocalCoordinator(self.temp.name))

    def request(self, method, path, body):
        if method == 'GET':
            if path == '/user':
                return {'id': 42}
            if '/notes?' not in path:
                return {'state': 'opened', 'sha': self.head}
            page = int(path.rsplit('=', 1)[1])
            return self.rows[(page - 1) * 100:page * 100]
        self.writes.append((method, path))
        note = {'id': 55, 'body': body['body'], 'author': {'id': 42}, 'system': False, 'type': None}
        self.rows = [note]
        return note

    def test_create_noop_update_reuses_note(self):
        self.assertEqual(self.adapter.publish(**self.args)['action'], 'create')
        self.args['run_version'] = 2
        self.assertEqual(self.adapter.publish(**self.args)['action'], 'noop')
        self.args.update(run_version=3, summary='New findings')
        self.assertEqual(self.adapter.publish(**self.args)['action'], 'update')
        self.assertEqual(self.writes, [('POST', '/projects/17/merge_requests/3/notes'),
                                       ('PUT', '/projects/17/merge_requests/3/notes/55')])

    def test_pagination_does_not_stop_on_filtered_page(self):
        self.rows = [{'id': i, 'system': True} for i in range(100)]
        self.rows.append({'id': 101, 'system': False, 'author': {'id': 7}, 'body': 'human'})
        self.assertEqual(len(self.adapter.snapshot()['comments']), 1)

    def test_adjudicated_review_uses_shared_risk_lifecycle(self):
        args = dict(adjudication=dict(reviewed_head=self.head, completed=True,
                    material_unknowns=False, findings=[]), scope='full branch',
                    channel='combined', details='Complete review.', run_version=1,
                    coordinator=self.args['coordinator'])
        self.adapter.publish_review(**args)
        self.assertIn('Merge risk 🟢 Low', self.rows[0]['body'])
        args['adjudication']['material_unknowns'] = True
        args['run_version'] = 2
        self.assertEqual(self.adapter.publish_review(**args)['action'], 'update')
        self.assertIn('Merge risk ⚪ Unknown', self.rows[0]['body'])
        self.assertEqual(self.writes[-1], ('PUT', '/projects/17/merge_requests/3/notes/55'))

    def test_instance_identity_and_stale_head(self):
        default_port = GitLabSummary(self.request, 'https://GITLAB.EXAMPLE:443/', 17, 3)
        self.assertEqual(default_port.resource, self.adapter.resource)
        self.assertEqual(default_port.context_repository, self.adapter.context_repository)
        other = GitLabSummary(self.request, 'https://other.example', 17, 3)
        self.assertNotEqual(other.resource, self.adapter.resource)
        self.head = 'b' * 40
        self.assertEqual(self.adapter.publish(**self.args)['action'], 'skip_stale')
        self.assertEqual(self.writes, [])
        with self.assertRaises(ValueError):
            GitLabSummary(self.request, 'https://user:secret@example.com', 17, 3)


if __name__ == '__main__':
    unittest.main()
