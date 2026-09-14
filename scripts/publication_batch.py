"""Development-only multi-write journal inside one LocalCoordinator claim.

No provider calls or retries. Adapters must recheck plans before
start_step(), and normalize authenticated provider responses for finish_step().
A started batch remains pending until all results are durable, including on crash.
"""
from copy import deepcopy
import re

from summary_coordinator import save

RECOVERY_PREFIX = '<!-- adversarial-review-write:v1 '


def validate_recovery_markers(plans, history):
    used = set()
    for record in history:
        for step in record['plan']['steps']:
            marker = step['plan'].get('recovery_marker')
            if marker is not None:
                used.add(marker)
    for plan in plans:
        marker = plan.get('recovery_marker')
        if marker is None:
            continue
        if (not isinstance(marker, str) or not re.fullmatch(
                re.escape(RECOVERY_PREFIX) + r'[0-9a-f]{64} -->', marker)
                or plan['body'].count(RECOVERY_PREFIX) != 1 or marker not in plan['body']
                or marker in used):
            raise ValueError('Recovery marker must be valid and unique across batch history')
        used.add(marker)


def reconcile_batch_recovery(state, snapshot):
    """Validate read-only observation; retire unattempted steps, never resume.

    Snapshot is trusted adapter output scoped to state.resource. It must include
    all summary comments and inline roots (not replies), normalized as comment_id,
    publisher_id, body, target_kind, thread_id (inline only). Create recovery also
    requires an operator-generated, unique per-write marker frozen in the body
    and plan.recovery_marker BEFORE the original request. Unmarked creates stay
    blocked rather than being inferred from similar text.
    """
    state = deepcopy(state)
    if (state['status'] not in ('pending', 'uncertain')
            or state['plan'].get('action') != 'publication_batch_v1'):
        raise ValueError('No recoverable pending batch')
    import json
    if (snapshot.get('listing_complete') is not True
            or json.dumps(snapshot.get('resource'), separators=(',', ':')) != state['resource']):
        raise ValueError('Complete snapshot of the exact provider resource required')
    steps = state['plan']['steps']
    validate_recovery_markers([s['plan'] for s in steps], state.get('batch_history', []))
    statuses = [s['status'] for s in steps]
    # Only a complete prefix, at most one uncertain request, then untouched plans.
    rank = {'complete': 0, 'pending': 1, 'planned': 2}
    if (not steps or any(s not in rank for s in statuses)
            or statuses.count('pending') > 1
            or [rank[s] for s in statuses] != sorted(rank[s] for s in statuses)):
        raise ValueError('Invalid batch step ordering')
    owner = steps[0]['plan']['preconditions']['publisher_id']
    if type(snapshot.get('publisher_id')) is not int or snapshot['publisher_id'] != owner:
        raise ValueError('Recovery publisher identity changed')
    head = snapshot.get('current_head')
    if not isinstance(head, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', head):
        raise ValueError('Recovery requires current immutable commit')
    rows = snapshot.get('comments')
    if not isinstance(rows, list):
        raise ValueError('Normalized complete comment listing required')
    identities = set()
    for row in rows:
        kind = row.get('target_kind')
        cid = row.get('comment_id')
        if (kind not in ('summary', 'inline') or type(cid) is not int or cid <= 0
                or (kind, cid) in identities or type(row.get('publisher_id')) is not int
                or row['publisher_id'] <= 0 or not isinstance(row.get('body'), str)
                or (kind == 'inline' and (not isinstance(row.get('thread_id'), str)
                                         or not row['thread_id']))):
            raise ValueError('Ambiguous normalized recovery listing')
        identities.add((kind, cid))
    for step in steps:
        if step['status'] != 'pending':
            continue
        plan = step['plan']
        kind = plan.get('target_kind')
        if kind not in ('summary', 'inline'):
            raise ValueError('Recovery requires a frozen target kind')
        candidates = [r for r in rows if r['target_kind'] == kind and r['publisher_id'] == owner]
        if plan['action'] == 'create':
            marker = plan.get('recovery_marker')
            if (not isinstance(marker, str) or not re.fullmatch(
                    re.escape(RECOVERY_PREFIX) + r'[0-9a-f]{64} -->', marker)
                    or plan['body'].count(RECOVERY_PREFIX) != 1 or marker not in plan['body']):
                raise ValueError('Uncertain create lacks a frozen unique recovery marker')
            candidates = [r for r in candidates if marker in r['body']]
        elif plan['action'] == 'update':
            candidates = [r for r in candidates if r['comment_id'] == plan['comment_id']]
        else:
            raise ValueError('Unknown pending write action')
        if (len(candidates) != 1 or candidates[0]['body'] != plan['body']
                or ('thread_id' in plan and candidates[0].get('thread_id') != plan['thread_id'])):
            raise ValueError('Intended remote state not uniquely observed; remain blocked')
        row = candidates[0]
        response = {k: row[k] for k in ('comment_id', 'publisher_id', 'body')}
        if kind == 'inline':
            response['thread_id'] = row['thread_id']
        step.update(status='complete', response=response,
                    recovery='observed_intended_state_not_request_attribution')
    skipped = 0
    for step in steps:
        if step['status'] == 'planned':
            step['status'] = 'not_attempted'
            skipped += 1
    result = {'action': 'publication_batch_recovered',
              'confirmed_writes': len(steps) - skipped, 'not_attempted': skipped,
              'current_head_at_recovery': head,
              'note': 'No replay; new run requires fresh review and correspondence'}
    state.update(status='complete', result=result)
    return state


class PublicationBatch:
    def __init__(self, transaction, plans):
        if not isinstance(plans, list) or not plans:
            raise ValueError('Nonempty write plan list required')
        plans = deepcopy(plans)
        validate_recovery_markers(plans, transaction.state.get('batch_history', []))
        for plan in plans:
            if plan.get('action') not in ('create', 'update'):
                raise ValueError('Batch contains write plans only')
            if not isinstance(plan.get('body'), str) or not plan['body'].strip():
                raise ValueError('Planned body required')
            preconditions = plan['preconditions']
            owner = preconditions['publisher_id']
            if type(owner) is not int or owner <= 0:
                raise ValueError('Verified numeric publisher required')
            head = preconditions['current_head']
            if not isinstance(head, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', head):
                raise ValueError('Full immutable reviewed commit required')
            if plan['action'] == 'update':
                cid = plan['comment_id']
                if type(cid) is not int or cid <= 0:
                    raise ValueError('Positive update comment identity required')
        if len({p['preconditions']['publisher_id'] for p in plans}) != 1:
            raise ValueError('Batch publisher identity must be constant')
        if len({p['preconditions']['current_head'] for p in plans}) != 1:
            raise ValueError('Batch reviewed commit must be constant')
        self.transaction = transaction
        self.poisoned = False
        # pending() fsyncs the whole frozen plan before a step can be returned.
        transaction.pending({'action': 'publication_batch_v1', 'steps': [
            {'plan': p, 'status': 'planned'} for p in plans]})

    def _check(self):
        self.transaction.require_active()
        if self.poisoned or self.transaction.state['status'] != 'pending':
            raise ValueError('Batch is terminal or requires recovery')

    def _persist(self, state):
        # Failure may happen before or after atomic replacement. Do not let the
        # same object authorize further writes after either ambiguous outcome.
        self.poisoned = True
        save(self.transaction.path, state)
        self.transaction.state = state
        self.poisoned = False

    def start_step(self):
        """After provider rechecks, persist intent and return the next plan.

        Calling this twice before finish_step is forbidden. A missing response
        never grants permission to restart or skip the pending step.
        """
        self._check()
        state = deepcopy(self.transaction.state)
        steps = state['plan']['steps']
        if any(s['status'] == 'pending' for s in steps):
            raise ValueError('Prior batch step outcome is pending')
        step = next((s for s in steps if s['status'] == 'planned'), None)
        if step is None:
            raise ValueError('No remaining batch steps')
        step['status'] = 'pending'
        self._persist(state)
        return deepcopy(step['plan'])

    def finish_step(self, response):
        """Record an authenticated normalized response, never a model report.

        response: {comment_id, publisher_id, body, thread_id?}. The adapter must
        validate provider/repository/PR membership and that thread_id identifies
        this root before normalizing. Stored thread IDs support a future owned-
        thread registry; their presence alone does not establish ownership.
        """
        self._check()
        state = deepcopy(self.transaction.state)
        pending = [s for s in state['plan']['steps'] if s['status'] == 'pending']
        if len(pending) != 1:
            raise ValueError('Exactly one pending batch step required')
        step = pending[0]
        plan = step['plan']
        # A malformed response can follow a successful remote write. Poison the
        # object before inspecting it, leaving the durable request pending.
        self.poisoned = True
        response = deepcopy(response)
        if (not isinstance(response, dict)
                or set(response) - {'comment_id', 'publisher_id', 'body', 'thread_id'}
                or type(response.get('comment_id')) is not int
                or response['comment_id'] <= 0
                or type(response.get('publisher_id')) is not int
                or response['publisher_id'] != plan['preconditions']['publisher_id']
                or response.get('body') != plan['body']
                or (plan['action'] == 'update' and response['comment_id'] != plan['comment_id'])
                or ('thread_id' in plan and response.get('thread_id') != plan['thread_id'])
                or ('thread_id' in response and (
                    not isinstance(response['thread_id'], str) or not response['thread_id']))):
            raise ValueError('Batch response does not match planned write; recovery required')
        step.update(status='complete', response=response)
        self._persist(state)

    def finish(self):
        self._check()
        steps = self.transaction.state['plan']['steps']
        if any(s['status'] != 'complete' for s in steps):
            raise ValueError('Cannot finish an incomplete batch')
        result = {'action': 'publication_batch_complete', 'writes': len(steps)}
        self.poisoned = True
        self.transaction.complete(result)
        return result
