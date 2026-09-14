"""Durable POSIX coordinator for publishers sharing one trusted local directory.

Not distributed coordination. Do not use independent CI workspaces as if they
shared ordering. Pending/uncertain writes require explicit read-only recovery.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile

from reconcile_summary import PREFIX


def save(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.summary-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Transaction:
    def __init__(self, path, state):
        self.path, self.state = path, state
        self.active = True

    def require_active(self):
        if not self.active:
            raise ValueError('Publisher claim is no longer active')

    def pending(self, plan):
        self.require_active()
        if self.state['status'] != 'claimed':
            raise ValueError('Write can be attempted only once per claim')
        self.state = {**self.state, 'status': 'pending', 'plan': plan}
        save(self.path, self.state)

    def uncertain(self):
        self.require_active()
        if self.state['status'] != 'pending':
            raise ValueError('No pending write')
        self.state = {**self.state, 'status': 'uncertain'}
        save(self.path, self.state)

    def complete(self, result):
        self.require_active()
        if self.state['status'] not in ('claimed', 'pending'):
            raise ValueError('Cannot complete uncertain or terminal transaction')
        if self.state['status'] == 'claimed' and result.get('action') not in ('noop', 'skip_stale'):
            raise ValueError('Successful write requires a durable pending record')
        if self.state.get('plan', {}).get('action') == 'publication_batch_v1':
            if (result.get('action') != 'publication_batch_complete'
                    or any(s['status'] != 'complete' for s in self.state['plan']['steps'])):
                raise ValueError('Incomplete batch cannot be completed through single-write API')
        self.state = {**self.state, 'status': 'complete', 'result': result}
        save(self.path, self.state)


class LocalCoordinator:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.is_symlink() or self.directory.stat().st_uid != os.getuid():
            raise ValueError('Coordinator directory must be owned by this user and not a symlink')
        if self.directory.stat().st_mode & 0o022:
            raise ValueError('Coordinator directory must not be writable by other users')

    def recover_batch(self, resource, observe):
        """Read-only batch observation under the same PR-wide lock.

        Caller must account for delayed requests/uncoordinated writers before
        recovery. Never retry requests or resume unattempted steps here.
        """
        from copy import deepcopy
        from publication_batch import reconcile_batch_recovery
        identity = json.dumps(resource, separators=(',', ':'))
        key = hashlib.sha256(identity.encode()).hexdigest()
        path = self.directory / (key + '.json')
        fd = os.open(self.directory / (key + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('Another publisher holds this resource lock') from None
            with path.open() as stream:
                state = json.load(stream)
            if (state['resource'] != identity or state['status'] not in ('pending', 'uncertain')
                    or state.get('plan', {}).get('action') != 'publication_batch_v1'):
                raise ValueError('Resource is not awaiting batch recovery')
            snapshot = observe(deepcopy(state['plan']))
            recovered = reconcile_batch_recovery(state, snapshot)
            save(path, recovered)
            return recovered['result']
        finally:
            os.close(fd)

    def recover(self, resource, observe):
        """Read provider state under the lock; never retry or undo a remote write.

        observe(plan) must return a fresh complete normalized provider snapshot.
        A mismatch/absence is not proof that an earlier request cannot complete.
        """
        identity = json.dumps(resource, separators=(',', ':'))
        key = hashlib.sha256(identity.encode()).hexdigest()
        path = self.directory / (key + '.json')
        fd = os.open(self.directory / (key + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('Another publisher holds this resource lock') from None
            with path.open() as stream:
                state = json.load(stream)
            if state['resource'] != identity or state['status'] not in ('pending', 'uncertain'):
                raise ValueError('Resource is not awaiting recovery')
            plan = state['plan']
            if plan.get('action') == 'publication_batch_v1':
                raise ValueError('Batch requires batch-specific recovery; summary recovery cannot clear it')
            snapshot = observe(plan)
            if snapshot.get('listing_complete') is not True:
                raise ValueError('Recovery requires complete provider listing')
            owner = plan['preconditions']['publisher_id']
            if type(snapshot.get('publisher_id')) is not int or snapshot['publisher_id'] != owner:
                raise ValueError('Recovery publisher identity changed')
            marker = PREFIX + plan['preconditions']['summary_key'] + ' -->'
            owned, ids = [], set()
            for comment in snapshot['comments']:
                cid = comment['id']
                if type(cid) is not int or cid <= 0 or cid in ids or not isinstance(comment['body'], str):
                    raise ValueError('Ambiguous recovery listing')
                ids.add(cid)
                if type(comment['author_id']) is int and comment['author_id'] == owner and marker in comment['body']:
                    owned.append(comment)
            if (len(owned) != 1 or owned[0]['body'] != plan['body']
                    or (plan['action'] == 'update' and owned[0]['id'] != plan['comment_id'])
                    or plan['action'] not in ('create', 'update')):
                raise ValueError('Intended remote state not uniquely observed; remain blocked')
            result = {'action': 'recovered_observed_state', 'comment_id': owned[0]['id'],
                      'reviewed_head': plan['preconditions']['current_head'],
                      'current_head_at_recovery': snapshot['current_head'],
                      'note': 'Observed intended state; not proof of which request wrote it'}
            save(path, {**state, 'status': 'complete', 'result': result})
            return result
        finally:
            os.close(fd)

    @contextmanager
    def claim(self, resource, run_version):
        if type(run_version) is not int or run_version < 1:
            raise ValueError('Trusted positive monotonic run version required')
        identity = json.dumps(resource, separators=(',', ':'))
        key = hashlib.sha256(identity.encode()).hexdigest()
        path = self.directory / (key + '.json')
        fd = os.open(self.directory / (key + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('Another publisher holds this resource lock') from None
            history = []
            if path.exists():
                with path.open() as stream:
                    prior = json.load(stream)
                if prior['resource'] != identity:
                    raise ValueError('Resource identity mismatch')
                if prior['status'] in ('pending', 'uncertain'):
                    raise ValueError('Uncertain prior write; read-only recovery required')
                if prior['status'] not in ('claimed', 'complete', 'aborted_before_write'):
                    raise ValueError('Unknown persisted state')
                if run_version <= prior['run_version']:
                    raise ValueError('Stale or already consumed run version')
                history = prior.get('batch_history', [])
                if prior.get('plan', {}).get('action') == 'publication_batch_v1':
                    history = [*history, {'run_version': prior['run_version'],
                                         'plan': prior['plan'], 'result': prior['result']}]
            state = {'resource': identity, 'run_version': run_version, 'status': 'claimed',
                     'batch_history': history}
            save(path, state)
            transaction = Transaction(path, state)
            try:
                yield transaction
            finally:
                transaction.active = False
                # Exceptions before pending cannot have sent a coordinated write.
                # A crash after pending leaves an uncertain outcome permanently
                # blocking, including when the remote write actually succeeded.
                if transaction.state['status'] == 'claimed':
                    save(path, {**transaction.state, 'status': 'aborted_before_write'})
        finally:
            os.close(fd)
