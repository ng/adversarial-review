"""Regression checks for benchmark accounting and isolation setup."""
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from run import command, rows, subscription_env, reviewer_sandbox, subscription_guard, record_subscription_limit, SubscriptionLimit, comparison_base
from score import metrics, validate_labels


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.gold = [{'id': 'g1', 'category': 'bug'}, {'id': 'g2', 'category': 'style'}]
        self.labels = {
            'a': {'id': 'a', 'gold_ids': ['g1'], 'classification': 'CONFIRMED', 'duplicate_of': None},
            'b': {'id': 'b', 'gold_ids': ['g1'], 'classification': 'CONFIRMED', 'duplicate_of': 'a'},
            'c': {'id': 'c', 'gold_ids': ['g2'], 'classification': 'CONFIRMED', 'duplicate_of': None},
            'd': {'id': 'd', 'gold_ids': [], 'classification': 'PLAUSIBLE', 'duplicate_of': None},
        }

    def test_duplicates_and_excluded_categories_do_not_inflate_or_penalize(self):
        m = metrics(self.gold, ['a', 'b', 'c', 'd'], self.labels)
        self.assertEqual(m['caught_gold'], 1)
        self.assertEqual(m['tp_candidates'], 1)
        self.assertEqual(m['matched_excluded'], 1)
        self.assertEqual(m['precision'], .5)
        self.assertEqual(m['fabricated'], 0)

    def test_duplicate_original_absent_from_configuration(self):
        m = metrics(self.gold, ['b'], self.labels)
        self.assertEqual(m['precision'], 1)
        self.assertEqual(m['recall'], 1)

    def test_empty_success_is_distinct_from_failed_or_missing_run(self):
        m = metrics(self.gold, [], self.labels)
        self.assertIsNone(m['precision'])
        self.assertEqual(m['recall'], 0)

    def test_incomplete_judge_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_labels({'labels': [self.labels['a']]}, ['a', 'b'], self.gold)

    def test_invented_gold_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_labels({'labels': [dict(self.labels['a'], gold_ids=['unknown'])]}, ['a'], self.gold)

    def test_jsonl_unicode_line_separator(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'data.jsonl'
            path.write_text(json.dumps({'body': 'a\u2028b'}, ensure_ascii=False) + '\n')
            self.assertEqual(rows(path), [{'body': 'a\u2028b'}])

    def test_subscription_runs_do_not_inherit_api_billing_credentials(self):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-only-placeholder',
                                      'OPENAI_API_KEY': 'test-only-placeholder',
                                      'BENCHMARK_SENTINEL': 'preserved'}):
            env = subscription_env()
        self.assertNotIn('ANTHROPIC_API_KEY', env)
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertEqual(env['BENCHMARK_SENTINEL'], 'preserved')


class SubscriptionLimitTests(unittest.TestCase):
    def test_rejected_primary_window_pauses_but_disabled_overage_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'cases.json').write_text('[]')
            out = root / 'runs/test/case/single'
            marker = subscription_guard(out)
            record_subscription_limit([{'type': 'rate_limit_event', 'rate_limit_info':
                {'status': 'allowed', 'overageStatus': 'rejected'}}], marker)
            self.assertFalse(marker.exists())
            with self.assertRaises(SubscriptionLimit):
                record_subscription_limit([{'type': 'rate_limit_event', 'rate_limit_info':
                    {'status': 'rejected', 'resetsAt': 9999999999}}], marker)
            with self.assertRaises(SubscriptionLimit):
                subscription_guard(out)
            marker.write_text(json.dumps({'retry_after': 1}))
            self.assertEqual(subscription_guard(out), marker)


class IsolationTests(unittest.TestCase):
    @unittest.skipUnless(Path('/usr/bin/sandbox-exec').exists(), 'macOS Seatbelt required')
    def test_reference_contents_denied_and_current_artifacts_writable(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / 'cases.json').write_text('[]')
            checkout = root / 'review-workspaces/test/case/single'
            checkout.mkdir(parents=True)
            (checkout / 'code.py').write_text('current')
            artifacts = checkout / '.reviews'
            artifacts.mkdir()
            out = root / 'runs/test/case/single'
            out.mkdir(parents=True)
            script = """
import pathlib, sys
root, checkout = map(pathlib.Path, sys.argv[1:])
assert (checkout / 'code.py').read_text() == 'current'
assert root.stat().st_mode
for path, mode in [(root / 'cases.json', 'r'), (checkout / 'code.py', 'w')]:
    try:
        path.open(mode)
    except PermissionError:
        pass
    else:
        raise AssertionError(str(path))
(checkout / '.reviews/report.md').write_text('allowed')
"""
            result = subprocess.run(['/usr/bin/sandbox-exec', '-p',
                reviewer_sandbox(checkout, out), sys.executable, '-c', script,
                str(root), str(checkout)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((artifacts / 'report.md').read_text(), 'allowed')


class CheckoutTests(unittest.TestCase):
    def test_ccrab_resolves_fork_point_and_validates_released_patch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); upstream = root / 'upstream'; upstream.mkdir()
            command(['git', 'init', '-q'], upstream)
            command(['git', 'config', 'user.email', 'benchmark@example.invalid'], upstream)
            command(['git', 'config', 'user.name', 'Benchmark test'], upstream)
            (upstream / 'feature').write_text('before')
            command(['git', 'add', '.'], upstream)
            command(['git', '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'common'], upstream)
            common = command(['git', 'rev-parse', 'HEAD'], upstream)
            (upstream / 'feature').write_text('after')
            (upstream / 'binary.dat').write_bytes(b'\x00binary fixture\x01')
            command(['git', 'add', '.'], upstream)
            command(['git', '-c', 'core.hooksPath=/dev/null', 'commit', '-qam', 'feature'], upstream)
            head = command(['git', 'rev-parse', 'HEAD'], upstream)
            released = command(['git', 'diff', common, head], upstream)
            command(['git', 'checkout', '-q', '-b', 'target', common], upstream)
            (upstream / 'drift').write_text('unrelated')
            command(['git', 'add', '.'], upstream)
            command(['git', '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'target drift'], upstream)
            base = command(['git', 'rev-parse', 'HEAD'], upstream)
            case = dict(benchmark='c-crab', id='case', repo='test/repo', base=base,
                        head=head, diff=released, input_hash='test')
            def local_command(args, cwd=None, timeout=300):
                return command([upstream.as_uri() if x == 'https://github.com/test/repo.git'
                                else x for x in args], cwd, timeout)
            with patch('run.command', side_effect=local_command):
                self.assertEqual(comparison_base(root, case), common)
                broken = dict(case, id='bad-patch', diff=released.replace('+after', '+wrong'))
                with self.assertRaisesRegex(RuntimeError, 'diff differs'):
                    comparison_base(root, broken)

    def test_shallow_clone_preserves_both_frozen_endpoints(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root / 'source'; source.mkdir()
            command(['git', 'init', '-q'], source)
            command(['git', 'config', 'user.email', 'benchmark@example.invalid'], source)
            command(['git', 'config', 'user.name', 'Benchmark test'], source)
            (source / 'code.py').write_text('before\n')
            command(['git', 'add', '.'], source)
            command(['git', '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'base'], source)
            base = command(['git', 'rev-parse', 'HEAD'], source)
            (source / 'code.py').write_text('after\n')
            command(['git', '-c', 'core.hooksPath=/dev/null', 'commit', '-qam', 'head'], source)
            head = command(['git', 'rev-parse', 'HEAD'], source)
            frozen = root / 'frozen'; frozen.mkdir()
            command(['git', 'init', '-q'], frozen)
            for sha in [base, head]:
                command(['git', 'fetch', '--depth', '1', source.as_uri(), sha], frozen)
            command(['git', 'checkout', '-q', '-B', 'benchmark', head], frozen)
            command(['git', 'update-ref', 'refs/remotes/origin/main', base], frozen)
            target = root / 'target'
            command(['git', 'clone', '--shared', '--no-hardlinks', str(frozen), str(target)])
            command(['git', 'remote', 'remove', 'origin'], target)
            command(['git', 'fetch', '--update-shallow', str(frozen),
                     'refs/remotes/origin/main:refs/remotes/origin/main'], target)
            diff = command(['git', 'diff', base, head], target)
            self.assertIn('-before', diff)
            self.assertIn('+after', diff)
            self.assertEqual(command(['git', 'remote'], target), '')


if __name__ == '__main__':
    unittest.main()
