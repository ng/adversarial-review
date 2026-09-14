import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publication_batch import PublicationBatch, RECOVERY_PREFIX
from summary_coordinator import LocalCoordinator


class BatchRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.coordinator = LocalCoordinator(self.temp.name)
        self.resource = ('github', 'owner/repo', 7)
        self.plan = dict(action='update', comment_id=9, thread_id='thread-1',
                         target_kind='inline', body='Updated issue', preconditions={
                             'publisher_id': 42, 'current_head': 'a' * 40})
        self.snapshot = dict(resource=list(self.resource), listing_complete=True,
                             publisher_id=42, current_head='b' * 40, comments=[dict(
                                 target_kind='inline', comment_id=9, thread_id='thread-1',
                                 publisher_id=42, body='Updated issue')])

    def interrupt(self, *, start=True, finish=False):
        with self.coordinator.claim(self.resource, 1) as tx:
            later = {**copy.deepcopy(self.plan), 'body': 'Later write'}
            later.pop('recovery_marker', None)
            batch = PublicationBatch(tx, [self.plan, later])
            if start:
                batch.start_step()
            if finish:
                batch.finish_step(dict(comment_id=9, publisher_id=42,
                                       thread_id='thread-1', body='Updated issue'))
            self.path = tx.path

    def recover(self, snapshot=None):
        return LocalCoordinator(self.temp.name).recover_batch(
            self.resource, lambda _: self.snapshot if snapshot is None else snapshot)

    def test_observed_update_retires_tail_and_preserves_history(self):
        self.interrupt()
        result = self.recover()
        self.assertEqual((result['confirmed_writes'], result['not_attempted']), (1, 1))
        state = json.loads(self.path.read_text())
        self.assertEqual([s['status'] for s in state['plan']['steps']], ['complete', 'not_attempted'])
        with self.coordinator.claim(self.resource, 2) as tx:
            self.assertEqual(tx.state['batch_history'][0]['plan']['steps'][0]['response']['comment_id'], 9)
            tx.complete({'action': 'noop'})

    def test_absent_edited_human_wrong_thread_or_kind_stays_pending(self):
        self.interrupt()
        snapshots = []
        for mutation in ({'body': 'Edited'}, {'publisher_id': 99},
                         {'thread_id': 'other'}, {'target_kind': 'summary'}):
            value = copy.deepcopy(self.snapshot)
            value['comments'][0].update(mutation)
            snapshots.append(value)
        snapshots.append({**self.snapshot, 'comments': []})
        for value in snapshots:
            with self.subTest(snapshot=value):
                with self.assertRaises(ValueError):
                    self.recover(value)
                self.assertEqual(json.loads(self.path.read_text())['status'], 'pending')

    def test_wrong_resource_identity_or_incomplete_snapshot_rejected(self):
        self.interrupt()
        for mutation in ({'resource': ['github', 'owner/other', 7]},
                         {'publisher_id': 99}, {'listing_complete': False}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.recover({**self.snapshot, **mutation})

    def test_marked_create_recovers_only_uniquely_owned_exact_body(self):
        marker = RECOVERY_PREFIX + 'c' * 64 + ' -->'
        self.plan.update(action='create', recovery_marker=marker, body='New issue\n' + marker)
        del self.plan['comment_id']
        del self.plan['thread_id']
        self.interrupt()
        self.snapshot['comments'][0]['body'] = self.plan['body']
        duplicate = {**self.snapshot['comments'][0], 'comment_id': 10, 'thread_id': 'thread-2'}
        with self.assertRaises(ValueError):
            self.recover({**self.snapshot, 'comments': [*self.snapshot['comments'], duplicate]})
        self.assertEqual(self.recover()['confirmed_writes'], 1)

    def test_unmarked_create_cannot_be_inferred_from_body_similarity(self):
        self.plan['action'] = 'create'
        self.interrupt()
        with self.assertRaisesRegex(ValueError, 'unique recovery marker'):
            self.recover()

    def test_crash_between_writes_keeps_confirmed_result_without_replaying_tail(self):
        self.interrupt(finish=True)
        result = self.recover({**self.snapshot, 'comments': []})
        self.assertEqual((result['confirmed_writes'], result['not_attempted']), (1, 1))

    def test_crash_before_any_step_does_not_claim_write_success(self):
        self.interrupt(start=False)
        result = self.recover({**self.snapshot, 'comments': []})
        self.assertEqual((result['confirmed_writes'], result['not_attempted']), (0, 2))

    def test_recovery_contends_with_same_resource_lock(self):
        with self.coordinator.claim(self.resource, 1) as tx:
            PublicationBatch(tx, [self.plan])
            with self.assertRaisesRegex(ValueError, 'holds this resource lock'):
                self.coordinator.recover_batch(self.resource, lambda _: self.fail('Read outside lock'))

    def test_marker_reuse_rejected_within_batch_and_after_recovery(self):
        marker = RECOVERY_PREFIX + 'd' * 64 + ' -->'
        self.plan.update(action='create', recovery_marker=marker, body='New issue\n' + marker)
        with self.coordinator.claim(self.resource, 1) as tx:
            with self.assertRaisesRegex(ValueError, 'unique across batch history'):
                PublicationBatch(tx, [self.plan, self.plan])
            batch = PublicationBatch(tx, [self.plan])
            batch.start_step()
        self.snapshot['comments'][0]['body'] = self.plan['body']
        self.recover()
        with self.coordinator.claim(self.resource, 2) as tx:
            with self.assertRaisesRegex(ValueError, 'unique across batch history'):
                PublicationBatch(tx, [self.plan])


if __name__ == '__main__':
    unittest.main()
