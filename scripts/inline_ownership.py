"""Bind inline ownership to durable creation history and current provider roots.

Only trusted coordinator state and authenticated provider snapshots belong here.
Do not deserialize either from a model's review artifact. No historical adoption,
provider writes, or semantic correspondence inference is performed.
"""
from copy import deepcopy
import json

from reconcile_findings import _id, _text, _thread_id, plan_findings


def bind_owned_threads(transaction, snapshot, *, scope, channel):
    transaction.require_active()
    if transaction.state['status'] != 'claimed':
        raise ValueError('Ownership must be bound before beginning publication')
    if (snapshot.get('listing_complete') is not True
            or json.dumps(snapshot.get('resource'), separators=(',', ':')) != transaction.state['resource']):
        raise ValueError('Complete snapshot for the claimed resource required')
    if _text(scope) != scope or _text(channel) != channel:
        raise ValueError('Canonical operator scope/channel required')
    owner = _id(snapshot['publisher_id'])
    owned, roots = {}, set()
    for record in transaction.state.get('batch_history', []):
        for step in record['plan']['steps']:
            plan = step['plan']
            if (step['status'] != 'complete' or plan['action'] != 'create'
                    or plan.get('target_kind') != 'inline'):
                continue
            # Old development records lacking operator context cannot grant
            # ownership in an arbitrarily selected scope or publisher channel.
            if plan.get('scope') != scope or plan.get('channel') != channel:
                continue
            response = step['response']
            tid = _thread_id(response['thread_id'])
            cid = _id(response['comment_id'])
            author = _id(response['publisher_id'])
            if (author != plan['preconditions']['publisher_id']
                    or response['body'] != plan['body']):
                raise ValueError('Creation history differs from its recorded write plan')
            if author != owner:
                continue
            if tid in owned or cid in roots:
                raise ValueError('Conflicting durable inline creation identities')
            owned[tid] = cid
            roots.add(cid)
    result = deepcopy(snapshot)
    seen = set()
    for thread in result['threads']:
        tid = _thread_id(thread['id'])
        if tid in seen:
            raise ValueError('Duplicate provider thread identity')
        seen.add(tid)
        # Ignore any upstream managed assertion, even on unrelated threads.
        thread['managed'] = False
        if tid in owned:
            if (_id(thread['root_comment_id']) != owned[tid]
                    or _id(thread['author_id']) != owner):
                raise ValueError('Recorded inline root identity changed; adjudicate manually')
            candidates = [row for row in result['comments']
                          if row.get('target_kind') == 'inline' and row.get('thread_id') == tid]
            if (len(candidates) != 1 or candidates[0]['comment_id'] != owned[tid]
                    or candidates[0]['publisher_id'] != owner
                    or candidates[0]['body'] != thread['body']):
                raise ValueError('Recorded root is not a uniquely observed inline comment')
            thread['managed'] = True
    if set(owned) - seen:
        raise ValueError('Previously owned inline thread is missing; do not infer a fix or replacement')
    return result


def plan_owned_findings(transaction, snapshot, *, scope, channel, reviewed_head, findings):
    snapshot = bind_owned_threads(transaction, snapshot, scope=scope, channel=channel)
    plan = plan_findings(reviewed_head=reviewed_head, current_head=snapshot['current_head'],
                         publisher_id=snapshot['publisher_id'], threads=snapshot['threads'],
                         findings=findings, listing_complete=True)
    plan.update(resource=deepcopy(snapshot['resource']), scope=scope, channel=channel)
    for action in plan.get('actions', []):
        action.update(target_kind='inline', scope=scope, channel=channel)
        action['preconditions']['resource'] = deepcopy(snapshot['resource'])
    return plan
