import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from inline_ownership import bind_owned_threads, plan_owned_findings
from publication_batch import PublicationBatch
from summary_coordinator import LocalCoordinator


class InlineOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.coordinator = LocalCoordinator(self.temp.name)
        self.resource = ('gitlab', 'https://gitlab.example', 17, 3)
        self.context = dict(scope='full branch', channel='combined')
        self.snapshot = dict(resource=list(self.resource), publisher_id=42, current_head='a' * 40,
                             listing_complete=True, threads=[dict(id='thread-1', root_comment_id=9,
                                 author_id=42, body='Existing issue', replies=[], resolved=False, managed=True)],
                             comments=[dict(target_kind='inline', thread_id='thread-1', comment_id=9,
                                            publisher_id=42, body='Existing issue')])
        self.finding = dict(id='new-run-id', body='New evidence, same issue',
                            location={'path': 'a.py', 'line': 25}, disposition='existing',
                            matched_thread_id='thread-1', evidence='Same null dereference trigger',
                            verified_head='a' * 40)

    def seed(self):
        with self.coordinator.claim(self.resource, 1) as tx:
            plan = dict(action='create', body='Existing issue', target_kind='inline',
                        preconditions={'publisher_id': 42, 'current_head': 'a' * 40}, **self.context)
            batch = PublicationBatch(tx, [plan])
            batch.start_step()
            batch.finish_step(dict(comment_id=9, thread_id='thread-1', publisher_id=42, body=plan['body']))
            batch.finish()

    def test_durable_creation_binds_same_thread_to_update_after_restart(self):
        self.seed()
        with LocalCoordinator(self.temp.name).claim(self.resource, 2) as tx:
            plan = plan_owned_findings(tx, self.snapshot, reviewed_head='a' * 40,
                                      findings=[self.finding], **self.context)
            action = plan['actions'][0]
            self.assertEqual((action['action'], action['comment_id']), ('update', 9))
            self.assertEqual(action['preconditions']['resource'], list(self.resource))
            self.assertEqual(action['scope'], 'full branch')

    def test_bot_authorship_and_managed_assertion_without_history_not_adopted(self):
        with self.coordinator.claim(self.resource, 1) as tx:
            bound = bind_owned_threads(tx, self.snapshot, **self.context)
            self.assertFalse(bound['threads'][0]['managed'])
            with self.assertRaisesRegex(ValueError, 'unowned or unmanaged'):
                plan_owned_findings(tx, self.snapshot, reviewed_head='a' * 40,
                                    findings=[self.finding], **self.context)

    def test_other_scope_or_channel_cannot_adopt_owned_thread(self):
        self.seed()
        with self.coordinator.claim(self.resource, 2) as tx:
            for context in (dict(scope='a.py', channel='combined'),
                            dict(scope='full branch', channel='other')):
                self.assertFalse(bind_owned_threads(tx, self.snapshot, **context)['threads'][0]['managed'])

    def test_missing_or_replaced_root_requires_adjudication(self):
        self.seed()
        with self.coordinator.claim(self.resource, 2) as tx:
            for mutation in ({'root_comment_id': 10}, {'author_id': 99}):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot['threads'][0].update(mutation)
                with self.assertRaises(ValueError):
                    bind_owned_threads(tx, snapshot, **self.context)
            with self.assertRaisesRegex(ValueError, 'missing'):
                bind_owned_threads(tx, {**self.snapshot, 'threads': []}, **self.context)

    def test_changed_resource_and_incomplete_snapshot_rejected(self):
        self.seed()
        with self.coordinator.claim(self.resource, 2) as tx:
            for mutation in ({'resource': ['gitlab', 'https://other.example', 17, 3]},
                             {'listing_complete': False}):
                with self.assertRaises(ValueError):
                    bind_owned_threads(tx, {**self.snapshot, **mutation}, **self.context)

    def test_inputs_unchanged_and_inactive_claim_rejected(self):
        self.seed()
        original = copy.deepcopy(self.snapshot)
        with self.coordinator.claim(self.resource, 2) as tx:
            bind_owned_threads(tx, self.snapshot, **self.context)
        self.assertEqual(self.snapshot, original)
        with self.assertRaisesRegex(ValueError, 'no longer active'):
            bind_owned_threads(tx, self.snapshot, **self.context)


if __name__ == '__main__':
    unittest.main()
