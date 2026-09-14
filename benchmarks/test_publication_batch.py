import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publication_batch import PublicationBatch
from summary_coordinator import LocalCoordinator


class PublicationBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.coordinator = LocalCoordinator(self.temp.name)
        self.resource = ('github', 'owner/repo', 7)
        self.plans = [dict(action='create', body=body, preconditions={
            'publisher_id': 42, 'current_head': 'a' * 40})
            for body in ('Summary', 'Inline issue')]

    def read(self, tx):
        return json.loads(tx.path.read_text())

    def response(self, body, cid=8):
        return dict(comment_id=cid, publisher_id=42, body=body)

    def test_two_writes_one_claim_and_durable_history_after_later_summary(self):
        with self.coordinator.claim(self.resource, 1) as tx:
            batch = PublicationBatch(tx, self.plans)
            for i, body in enumerate(('Summary', 'Inline issue')):
                plan = batch.start_step()
                self.assertEqual(plan['body'], body)
                self.assertEqual(self.read(tx)['plan']['steps'][i]['status'], 'pending')
                batch.finish_step(self.response(body, i + 8))
                self.assertEqual(self.read(tx)['plan']['steps'][i]['status'], 'complete')
            self.assertEqual(batch.finish()['writes'], 2)
        # A subsequent ordinary summary transaction must not discard inline IDs.
        with LocalCoordinator(self.temp.name).claim(self.resource, 2) as tx:
            history = self.read(tx)['batch_history']
            self.assertEqual(history[0]['plan']['steps'][1]['response']['comment_id'], 9)
            tx.complete({'action': 'noop'})
        with LocalCoordinator(self.temp.name).claim(self.resource, 3) as tx:
            self.assertEqual(len(self.read(tx)['batch_history']), 1)
            tx.complete({'action': 'noop'})

    def test_crash_after_first_result_retains_it_and_blocks_retry(self):
        with self.coordinator.claim(self.resource, 1) as tx:
            batch = PublicationBatch(tx, self.plans)
            batch.start_step()
            batch.finish_step(self.response('Summary'))
            batch.start_step()
            # Simulate missing response after the second remote request.
        state = self.read(tx)
        self.assertEqual([s['status'] for s in state['plan']['steps']], ['complete', 'pending'])
        with self.assertRaisesRegex(ValueError, 'Uncertain'):
            with LocalCoordinator(self.temp.name).claim(self.resource, 2):
                self.fail('Blind batch retry admitted')
        with self.assertRaisesRegex(ValueError, 'batch-specific recovery'):
            self.coordinator.recover(self.resource, lambda _: self.fail('Summary recovery called provider'))

    def test_step_cannot_be_retried_skipped_or_completed_early(self):
        with self.coordinator.claim(self.resource, 1) as tx:
            batch = PublicationBatch(tx, self.plans)
            with self.assertRaises(ValueError):
                batch.finish()
            batch.start_step()
            with self.assertRaises(ValueError):
                batch.start_step()
            with self.assertRaises(ValueError):
                tx.complete({'action': 'create'})
            with self.assertRaises(ValueError):
                tx.complete({'action': 'publication_batch_complete'})

    def test_plan_and_response_are_detached_from_caller(self):
        with self.coordinator.claim(self.resource, 1) as tx:
            batch = PublicationBatch(tx, self.plans)
            self.plans[0]['body'] = 'Changed by caller'
            emitted = batch.start_step()
            emitted['body'] = 'Changed returned copy'
            response = self.response('Summary')
            batch.finish_step(response)
            response['body'] = 'Changed response'
            self.assertEqual(self.read(tx)['plan']['steps'][0]['response']['body'], 'Summary')

    def test_wrong_response_poisoned_and_preserves_pending(self):
        with self.coordinator.claim(self.resource, 1) as tx:
            batch = PublicationBatch(tx, self.plans)
            batch.start_step()
            with self.assertRaisesRegex(ValueError, 'does not match'):
                batch.finish_step(self.response('Wrong body'))
            with self.assertRaisesRegex(ValueError, 'requires recovery'):
                batch.finish_step(self.response('Summary'))
            self.assertEqual(self.read(tx)['plan']['steps'][0]['status'], 'pending')

    def test_failed_result_persistence_does_not_admit_next_write(self):
        with self.coordinator.claim(self.resource, 1) as tx:
            batch = PublicationBatch(tx, self.plans)
            batch.start_step()
            with patch('publication_batch.save', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    batch.finish_step(self.response('Summary'))
            with self.assertRaises(ValueError):
                batch.start_step()
            self.assertEqual(self.read(tx)['plan']['steps'][0]['status'], 'pending')

    def test_update_root_and_thread_identity_checked(self):
        self.plans = [{**self.plans[0], 'action': 'update', 'comment_id': 8,
                       'thread_id': 'thread-7'}]
        with self.coordinator.claim(self.resource, 1) as tx:
            batch = PublicationBatch(tx, self.plans)
            batch.start_step()
            with self.assertRaises(ValueError):
                batch.finish_step({**self.response('Summary'), 'thread_id': 'thread-8'})

    def test_batch_cannot_authorize_step_after_lock_release(self):
        with self.coordinator.claim(self.resource, 1) as tx:
            batch = PublicationBatch(tx, self.plans)
        with self.assertRaisesRegex(ValueError, 'no longer active'):
            batch.start_step()
        with self.assertRaisesRegex(ValueError, 'no longer active'):
            tx.uncertain()


if __name__ == '__main__':
    unittest.main()
