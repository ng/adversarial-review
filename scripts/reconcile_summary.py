"""Plan an owned PR/MR summary upsert. Pure planning: no network or publishing.

Adapters must fetch all comments and verify publisher identity from the provider,
then recheck head/body preconditions under a per-PR publisher lock before writing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

PREFIX = '<!-- adversarial-review-summary:v1 '


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def summary_key(repository, change_number, scope, channel):
    if not all(isinstance(v, str) and v.strip() for v in (repository, scope, channel)):
        raise ValueError('Repository, scope and publisher channel required')
    if any('\n' in v or '\r' in v or PREFIX in v for v in (repository, scope, channel)):
        raise ValueError('Context fields must be single-line and contain no reserved marker')
    if type(change_number) is not int or change_number < 1:
        raise ValueError('Positive PR/MR number required')
    return digest(json.dumps([repository, change_number, scope, channel], separators=(',', ':')))


def plan_summary(*, repository, change_number, scope, channel, publisher_id,
                 reviewed_head, current_head, summary, comments, listing_complete):
    if listing_complete is not True:
        raise ValueError('Complete paginated comment listing required')
    if not isinstance(comments, list):
        raise ValueError('Normalized comment list required')
    if type(publisher_id) is not int or publisher_id <= 0:
        raise ValueError('Verified numeric publisher identity required')
    for head in (reviewed_head, current_head):
        if not isinstance(head, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', head):
            raise ValueError('Full immutable head SHA required')
    if reviewed_head != current_head:
        return {'action': 'skip_stale', 'reviewed_head': reviewed_head, 'current_head': current_head}
    if not isinstance(summary, str) or not summary.strip() or PREFIX in summary:
        raise ValueError('Nonempty summary without reserved ownership markers required')
    key = summary_key(repository, change_number, scope, channel)
    marker = PREFIX + key + ' -->'
    # Scope must be the caller's canonical review scope, not a display-only alias.
    body = f'Scope: {scope}\nReviewed through `{reviewed_head}`.\n\n{summary.strip()}\n\n{marker}'
    owned = []
    seen_ids = set()
    for comment in comments:
        cid = comment['id']
        if type(cid) is not int or cid <= 0 or cid in seen_ids:
            raise ValueError('Invalid or duplicated provider comment identity')
        seen_ids.add(cid)
        text = comment['body']
        if not isinstance(text, str):
            raise ValueError('Invalid comment body')
        if comment['author_id'] != publisher_id or type(comment['author_id']) is not int:
            continue
        if marker in text:
            if not text.endswith(marker) or text.count(PREFIX) != 1:
                raise ValueError('Ambiguous owned summary marker; reconcile manually')
            owned.append(comment)
    if len(owned) > 1:
        raise ValueError('Multiple owned summaries for scope; do not choose or delete implicitly')
    preconditions = {'current_head': current_head, 'publisher_id': publisher_id,
                     'summary_key': key, 'requires_serialized_recheck': True}
    if not owned:
        return {'action': 'create', 'body': body, 'preconditions': {**preconditions, 'owned_summary_absent': True}}
    comment = owned[0]
    return {'action': 'noop' if comment['body'] == body else 'update',
            'comment_id': comment['id'], 'body': body,
            'preconditions': {**preconditions, 'previous_body_sha256': digest(comment['body'])}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='JSON object with plan_summary keyword arguments')
    args = parser.parse_args()
    print(json.dumps(plan_summary(**json.loads(args.input.read_text())), indent=2))
