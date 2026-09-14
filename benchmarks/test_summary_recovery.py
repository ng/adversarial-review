from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from github_summary import GitHubSummary
from summary_coordinator import LocalCoordinator


class SummaryRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.coordinator = LocalCoordinator(self.temp.name)
        self.rows, self.writes = [], 0
        self.owner = 42
        self.timeout = True
        self.adapter = GitHubSummary(self.request, 'owner/repo', 1)
        self.args = dict(reviewed_head='a' * 40, scope='full branch', channel='combined',
                         summary='Result', run_version=1, coordinator=self.coordinator)

    def request(self, method, path, body):
        if method == 'GET':
            if path == '/user':
                return {'id': self.owner}
            if '/pulls/' in path:
                return {'state': 'open', 'head': {'sha': 'a' * 40}}
            return self.rows
        self.writes += 1
        self.rows = [{'id': 7, 'body': body['body'], 'user': {'id': 42}}]
        if self.timeout:
            raise TimeoutError('Response lost after remote success')
        return self.rows[0]

    def pending(self):
        with self.assertRaises(TimeoutError):
            self.adapter.publish(**self.args)

    def test_recovery_after_restart_is_read_only_then_new_run_noop(self):
        self.pending()
        restarted = LocalCoordinator(self.temp.name)
        result = self.adapter.recover(restarted)
        self.assertEqual(result['comment_id'], 7)
        self.assertEqual(self.writes, 1)
        self.args.update(run_version=2, coordinator=restarted)
        self.assertEqual(self.adapter.publish(**self.args)['action'], 'noop')
        self.assertEqual(self.writes, 1)

    def test_absence_and_duplicates_do_not_clear_uncertainty(self):
        self.pending()
        original = self.rows[0]
        for rows in ([], [original, {**original, 'id': 8}]):
            self.rows = rows
            with self.assertRaisesRegex(ValueError, 'remain blocked'):
                self.adapter.recover(self.coordinator)
            self.args['run_version'] = 2
            with self.assertRaisesRegex(ValueError, 'Uncertain'):
                self.adapter.publish(**self.args)
        self.assertEqual(self.writes, 1)

    def test_changed_body_and_identity_remain_blocked(self):
        self.pending()
        original = self.rows[0]['body']
        self.rows[0]['body'] = 'edited\n' + original
        with self.assertRaisesRegex(ValueError, 'remain blocked'):
            self.adapter.recover(self.coordinator)
        self.rows[0]['body'] = original
        self.owner = 99
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.adapter.recover(self.coordinator)


if __name__ == '__main__':
    unittest.main()
