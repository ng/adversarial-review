from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from summary_http import SummaryHTTP, SummaryHTTPError
from github_summary import GitHubSummary
from summary_coordinator import LocalCoordinator


class SummaryHTTPTests(unittest.TestCase):
    def setUp(self):
        patcher = patch('summary_http.http.client.HTTPSConnection')
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.connection = self.factory.return_value
        self.response = self.connection.getresponse.return_value
        self.response.status = 200
        self.response.getheader.return_value = 'application/json; charset=utf-8'
        self.response.read.return_value = b'{"id":42}'

    def test_provider_headers_and_paths(self):
        for provider, origin, prefix, header in [
                ('github', None, '', 'Authorization'),
                ('gitlab', 'https://gitlab.example:8443', '/api/v4', 'PRIVATE-TOKEN')]:
            with self.subTest(provider=provider):
                transport = SummaryHTTP(provider=provider, token='test-secret', origin=origin)
                self.assertEqual(transport('GET', '/user', None), {'id': 42})
                args, kwargs = self.connection.request.call_args
                self.assertEqual(args, ('GET', prefix + '/user'))
                self.assertIn(header, kwargs['headers'])
                self.assertIsNone(kwargs['body'])
                self.connection.close.assert_called()

    def test_redirect_errors_and_timeouts_never_retry(self):
        transport = SummaryHTTP(provider='github', token='test-secret')
        for status in (301, 302, 307, 308, 401, 429, 500):
            self.connection.reset_mock()
            self.response.status = status
            with self.assertRaises(SummaryHTTPError) as error:
                transport('POST', '/repos/a/b/issues/1/comments', {'body': 'Review'})
            self.assertNotIn('test-secret', str(error.exception))
            self.connection.request.assert_called_once()
            self.response.read.assert_not_called()
        self.connection.reset_mock()
        self.connection.getresponse.side_effect = TimeoutError('test-secret')
        with self.assertRaises(SummaryHTTPError) as error:
            transport('PATCH', '/repos/a/b/issues/comments/7', {'body': 'Update'})
        self.assertNotIn('test-secret', str(error.exception))
        self.connection.request.assert_called_once()
        self.connection.close.assert_called_once()

    def test_unsafe_targets_rejected_before_network(self):
        transport = SummaryHTTP(provider='github', token='test-secret')
        for path in ('https://evil/user', '//evil/user', '/x/../user', '/%2e%2e/user', '/user\r\nX: bad'):
            with self.assertRaises(ValueError):
                transport('GET', path, None)
        for origin in ('http://gitlab.example', 'https://user:secret@gitlab.example', 'https://gitlab.example/path'):
            with self.assertRaises(ValueError):
                SummaryHTTP(provider='gitlab', token='test-secret', origin=origin)
        self.factory.assert_not_called()

    def test_invalid_response_is_not_retried(self):
        transport = SummaryHTTP(provider='github', token='test-secret')
        self.response.read.return_value = b'not json'
        with self.assertRaises(SummaryHTTPError):
            transport('PUT', '/example', {'body': 'Review'})
        self.connection.request.assert_called_once()

    def test_transport_timeout_blocks_second_publisher_write(self):
        import json
        responses = []
        for payload in ([{'id': 42}, {'state': 'open', 'head': {'sha': 'a' * 40}}, []] * 2):
            response = MagicMock(status=200)
            response.getheader.return_value = 'application/json'
            response.read.return_value = json.dumps(payload).encode()
            responses.append(response)
        self.connection.getresponse.side_effect = responses + [TimeoutError('unknown outcome')]
        adapter = GitHubSummary(SummaryHTTP(provider='github', token='test-secret'), 'owner/repo', 1)
        with tempfile.TemporaryDirectory() as directory:
            args = dict(adjudication=dict(reviewed_head='a' * 40, completed=True,
                        material_unknowns=False, findings=[]), scope='full branch',
                        channel='combined', details='Review complete.', run_version=1,
                        coordinator=LocalCoordinator(directory))
            with self.assertRaises(SummaryHTTPError):
                adapter.publish_review(**args)
            args.update(run_version=2, coordinator=LocalCoordinator(directory))
            with self.assertRaises(ValueError):
                adapter.publish_review(**args)
        writes = [call for call in self.connection.request.call_args_list if call.args[0] != 'GET']
        self.assertEqual(len(writes), 1)

    def test_response_size_and_content_type_are_bounded(self):
        transport = SummaryHTTP(provider='github', token='test-secret')
        self.response.getheader.return_value = 'text/html'
        with self.assertRaises(SummaryHTTPError):
            transport('GET', '/user', None)
        self.response.read.assert_not_called()
        self.response.getheader.return_value = 'application/json'
        self.response.read.return_value = b'x' * (8 * 1024 * 1024 + 1)
        with self.assertRaises(SummaryHTTPError):
            transport('GET', '/user', None)
        self.response.read.assert_called_once_with(8 * 1024 * 1024 + 1)


if __name__ == '__main__':
    unittest.main()
