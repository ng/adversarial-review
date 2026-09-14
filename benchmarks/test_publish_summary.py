from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publish_summary import execute, main


class PublishSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = dict(provider='github', repository='owner/repo', number=1,
            scope='full branch', channel='combined', token_env='REVIEW_TOKEN',
            coordination={'kind': 'single-host', 'directory': self.temp.name + '/state'})
        self.review = dict(adjudication=dict(reviewed_head='a' * 40, completed=True,
            material_unknowns=False, findings=[]), details='Reviewed the full change.')
        self.rows, self.writes = [], []
        self.head = 'a' * 40
        self.closed = False
        patcher = patch('publish_summary.SummaryHTTP', return_value=self.request)
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)

    def request(self, method, path, body):
        if method == 'GET':
            if path == '/user':
                return {'id': 42}
            if '/pulls/' in path:
                return {'state': 'closed' if self.closed else 'open', 'head': {'sha': self.head}}
            if '/merge_requests/' in path and '/notes?' not in path:
                return {'state': 'merged' if self.closed else 'opened', 'sha': self.head}
            return self.rows
        self.writes.append((method, path))
        self.rows = [dict(id=7, user={'id': 42}, author={'id': 42}, system=False,
                          body=body['body'])]
        return self.rows[0]

    def run_mode(self, mode='plan', version=None):
        return execute(config=self.config, review=self.review, mode=mode,
                       run_version=version, environment={'REVIEW_TOKEN': 'test-secret'})

    def test_plan_has_no_remote_or_coordinator_writes(self):
        result = self.run_mode()
        self.assertEqual(result['publication_plan']['action'], 'create')
        self.assertEqual(result['risk']['level'], 'Low')
        self.assertEqual(self.writes, [])
        self.assertFalse(Path(self.config['coordination']['directory']).exists())

    def test_both_providers_create_noop_update_and_stale_skip(self):
        for provider in ('github', 'gitlab'):
            with self.subTest(provider=provider):
                self.rows, self.writes = [], []
                self.config['provider'] = provider
                if provider == 'gitlab':
                    self.config.pop('repository')
                    self.config.update(origin='https://gitlab.example', project_id=2)
                self.head = 'a' * 40
                self.review['adjudication']['material_unknowns'] = False
                self.assertEqual(self.run_mode('publish', 1)['action'], 'create')
                self.assertEqual(self.run_mode('publish', 2)['action'], 'noop')
                self.review['adjudication']['material_unknowns'] = True
                self.assertEqual(self.run_mode('publish', 3)['action'], 'update')
                self.assertIn('Merge risk ⚪ Unknown', self.rows[0]['body'])
                self.head = 'b' * 40
                self.assertEqual(self.run_mode('publish', 4)['action'], 'skip_stale')
                self.assertEqual(len(self.writes), 2)
                self.assertEqual(self.writes[-1][0], 'PATCH' if provider == 'github' else 'PUT')
                if provider == 'gitlab':
                    self.factory.assert_called_with(provider='gitlab', token='test-secret', origin='https://gitlab.example')

    def test_review_cannot_override_destination_or_order(self):
        for field in ('repository', 'origin', 'token_env', 'run_version', 'scope'):
            self.review[field] = 'override'
            with self.assertRaises(ValueError):
                self.run_mode('publish', 1)
            self.review.pop(field)
        self.factory.assert_not_called()

    def test_publish_rejects_missing_order_or_distributed_config(self):
        with self.assertRaises(ValueError):
            self.run_mode('publish')
        self.config['coordination']['kind'] = 'independent-ci-workspaces'
        with self.assertRaises(ValueError):
            self.run_mode('publish', 1)
        self.assertEqual(self.writes, [])

    def test_recovery_observes_existing_write_without_reposting(self):
        def timeout(method, path, body):
            result = self.request(method, path, body)
            if method != 'GET':
                raise TimeoutError('Response lost after remote write')
            return result
        self.factory.return_value = timeout
        with self.assertRaises(TimeoutError):
            self.run_mode('publish', 1)
        self.factory.return_value = self.request
        result = execute(config=self.config, review=None, mode='recover',
                         run_version=None, environment={'REVIEW_TOKEN': 'test-secret'})
        self.assertEqual(result['action'], 'recovered_observed_state')
        self.assertEqual(self.run_mode('publish', 2)['action'], 'noop')
        self.assertEqual(len(self.writes), 1)

    def test_cli_defaults_to_plan_and_errors_do_not_echo_secrets(self):
        output, error = io.StringIO(), io.StringIO()
        with patch('publish_summary.Path.read_text', side_effect=[json.dumps(self.config), json.dumps(self.review)]), redirect_stdout(output):
            self.assertEqual(main(['--config', '/operator.json', '--review', '/review.json']), 0)
        self.assertEqual(json.loads(output.getvalue())['publication_plan']['action'], 'create')
        self.assertEqual(self.writes, [])
        with patch('publish_summary.Path.read_text', side_effect=ValueError('test-secret')), redirect_stderr(error):
            self.assertEqual(main(['--config', '/operator.json']), 1)
        self.assertNotIn('test-secret', error.getvalue())

    def test_closed_change_can_recover_but_cannot_publish(self):
        for provider in ('github', 'gitlab'):
            with self.subTest(provider=provider):
                self.closed = False
                self.rows, self.writes = [], []
                self.config['provider'] = provider
                if provider == 'gitlab':
                    self.config.pop('repository')
                    self.config.update(origin='https://gitlab.example', project_id=2)
                def timeout(method, path, body):
                    result = self.request(method, path, body)
                    if method != 'GET':
                        raise TimeoutError('Response lost')
                    return result
                self.factory.return_value = timeout
                with self.assertRaises(TimeoutError):
                    self.run_mode('publish', 1)
                self.closed = True
                self.factory.return_value = self.request
                result = execute(config=self.config, review=None, mode='recover',
                    run_version=None, environment={'REVIEW_TOKEN': 'test-secret'})
                self.assertEqual(result['action'], 'recovered_observed_state')
                with self.assertRaisesRegex(ValueError, 'not open'):
                    self.run_mode('publish', 2)
                self.assertEqual(len(self.writes), 1)


if __name__ == '__main__':
    unittest.main()
