from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from summary_coordinator import LocalCoordinator


class SummaryCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.coordinator = LocalCoordinator(self.temp.name)
        self.resource = ('github', 'owner/repo', 7)

    def test_lock_and_monotonic_order_survive_new_instance(self):
        with self.coordinator.claim(self.resource, 2) as transaction:
            with self.assertRaisesRegex(ValueError, 'holds'):
                with LocalCoordinator(self.temp.name).claim(self.resource, 3):
                    self.fail('Concurrent lock acquired')
            transaction.complete({'action': 'noop'})
        for version in (1, 2):
            with self.assertRaisesRegex(ValueError, 'Stale'):
                with LocalCoordinator(self.temp.name).claim(self.resource, version):
                    self.fail('Old run admitted')
        with LocalCoordinator(self.temp.name).claim(self.resource, 3) as transaction:
            transaction.complete({'action': 'noop'})

    def test_pending_outcome_blocks_future_runs(self):
        with self.coordinator.claim(self.resource, 1) as transaction:
            transaction.pending({'action': 'create', 'body': 'planned'})
            # Simulate process exit after request but before response handling.
        with self.assertRaisesRegex(ValueError, 'Uncertain'):
            with LocalCoordinator(self.temp.name).claim(self.resource, 2):
                self.fail('Blind retry admitted')

    def test_separate_process_observes_lock(self):
        script = ('from summary_coordinator import LocalCoordinator\n'
                  'import sys\n'
                  'with LocalCoordinator(sys.argv[1]).claim(("github", "owner/repo", 7), 2):\n'
                  '    print("unexpected acquisition")\n')
        with self.coordinator.claim(self.resource, 1) as transaction:
            result = subprocess.run([sys.executable, '-c', script, self.temp.name],
                cwd=Path(__file__).resolve().parents[1] / 'scripts',
                capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('holds this resource lock', result.stderr)
            transaction.complete({'action': 'noop'})

    def test_prewrite_abort_and_successful_write(self):
        with self.assertRaises(RuntimeError):
            with self.coordinator.claim(self.resource, 1):
                raise RuntimeError('Provider changed before write')
        with self.coordinator.claim(self.resource, 2) as transaction:
            with self.assertRaisesRegex(ValueError, 'pending record'):
                transaction.complete({'action': 'create'})
            transaction.pending({'action': 'create'})
            transaction.complete({'action': 'create', 'comment_id': 5})
        with self.coordinator.claim(self.resource, 3) as transaction:
            transaction.complete({'action': 'noop'})


if __name__ == '__main__':
    unittest.main()
