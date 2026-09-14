"""Development GitLab updater for already-owned inline roots only.

No new threads, deletes, replies, relocation, or resolution. Not wired to native
skills or CLI. All publishers must share the same persistent local coordinator.
"""
from copy import deepcopy
import hashlib
import json
import re

from inline_ownership import plan_owned_findings
from publication_batch import PublicationBatch
from reconcile_findings import _sha


def snapshot_digest(snapshot):
    """Freeze the provider context presented for correspondence adjudication."""
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode()).hexdigest()


class GitLabInlineUpdates:
    def __init__(self, reader):
        self.reader = reader

    def publish_updates(self, *, reviewed_head, scope, channel, findings,
                        adjudicated_snapshot_sha256, run_version, coordinator):
        _sha(reviewed_head)
        if not isinstance(adjudicated_snapshot_sha256, str) or not re.fullmatch(
                r'[0-9a-f]{64}', adjudicated_snapshot_sha256):
            raise ValueError('Frozen correspondence snapshot digest required')
        findings = deepcopy(findings)
        with coordinator.claim(self.reader.resource, run_version) as tx:
            expected = self.reader.snapshot()
            if expected['current_head'] != reviewed_head:
                result = dict(action='skip_stale', reviewed_head=reviewed_head,
                              current_head=expected['current_head'])
                tx.complete(result)
                return result
            if snapshot_digest(expected) != adjudicated_snapshot_sha256:
                raise ValueError('Discussion changed since adjudication; obtain fresh correspondence')
            planned = plan_owned_findings(tx, expected, scope=scope, channel=channel,
                                          reviewed_head=reviewed_head, findings=findings)
            if any(p['action'] == 'create' for p in planned['actions']):
                raise ValueError('New inline creation requires the separate diff-position publishing path')
            writes = [p for p in planned['actions'] if p['action'] == 'update']
            for plan in writes:
                if not re.fullmatch(r'[A-Za-z0-9_-]+', plan['thread_id']):
                    raise ValueError('Discussion identity cannot be safely addressed')
            if not writes:
                result = dict(action='noop', reviewed_head=reviewed_head, writes=0)
                tx.complete(result)
                return result
            if self.reader.snapshot() != expected:
                raise ValueError('Provider changed before batch; no write attempted')
            batch = PublicationBatch(tx, writes)
            for _ in writes:
                # Compare against the exact initial snapshot plus ONLY our own
                # confirmed body replacements. Never refresh the baseline to
                # silently accept intervening human replies or source changes.
                if self.reader.snapshot() != expected:
                    raise ValueError('Discussion changed during batch; stop and recover without replay')
                plan = batch.start_step()
                path = (self.reader.root + '/discussions/' + plan['thread_id']
                        + '/notes/' + str(plan['comment_id']))
                try:
                    row = self.reader.request('PUT', path, {'body': plan['body']})
                    if (row.get('system') is not False or row.get('internal', False) is not False
                            or row.get('type') != 'DiffNote'
                            or row.get('resolved') is not False
                            or type(row.get('project_id')) is not int
                            or row['project_id'] != self.reader.project_id
                            or type(row.get('noteable_id')) is not int
                            or row['noteable_id'] != expected['merge_request_id']
                            or row.get('noteable_type') != 'MergeRequest'):
                        raise ValueError('Update response is not the expected public MR diff root')
                    batch.finish_step(dict(comment_id=row['id'], publisher_id=row['author']['id'],
                                           body=row['body'], thread_id=plan['thread_id']))
                except BaseException:
                    tx.uncertain()
                    raise
                for thread in expected['threads']:
                    if thread['id'] == plan['thread_id']:
                        thread['body'] = plan['body']
                for comment in expected['comments']:
                    if comment.get('thread_id') == plan['thread_id']:
                        comment['body'] = plan['body']
            result = batch.finish()
            return {**result, 'reviewed_head': reviewed_head}
