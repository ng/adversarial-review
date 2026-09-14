"""Pure inline-comment planner; no provider writes or automatic issue matching.

The caller adjudicates correspondence against source at reviewed_head. A match
is not established by title similarity, a line number, or a per-run finding ID.
Adapters must obtain complete provider state and recheck each precondition under
the same PR/MR coordinator used by the summary publisher before any write.
"""
import hashlib
import json
import re


def _text(value):
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise ValueError('Nonempty text required')
    return value.strip()


def _id(value):
    if type(value) is not int or value <= 0:
        raise ValueError('Positive provider identity required')
    return value


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', value):
        raise ValueError('Full immutable SHA required')
    return value


def _thread_id(value):
    # GitHub GraphQL thread IDs and GitLab discussion IDs are opaque strings.
    if _text(value) != value or any(ord(c) < 33 for c in value):
        raise ValueError('Opaque provider thread identity required')
    return value


def plan_findings(*, reviewed_head, current_head, publisher_id, threads,
                  findings, listing_complete):
    """Plan updates using explicit correspondence, or new inline comments.

    threads: complete normalized listing of roots in the target PR/MR and scope;
      {id, root_comment_id, author_id, body, managed, resolved, replies}.
      replies is a complete chronological list of {id, author_id, body}.
      managed must be established by the trusted adapter's ownership registry,
      not an unverified marker or review-supplied assertion.
    findings: {id, body, location, disposition, evidence, verified_head,
      matched_thread_id}; disposition is 'existing' or 'new'. New findings must
      explicitly use matched_thread_id=None. evidence explains correspondence
      (or why no existing thread describes this issue) at verified_head.

    Evidence is a caller assertion, not machine-verified semantic truth. Returned
    plans are not publication authorization. Resolved threads need manual review;
    absent findings remain untouched. This version never resolves or reopens.
    """
    _sha(reviewed_head)
    _sha(current_head)
    _id(publisher_id)
    if listing_complete is not True:
        raise ValueError('Complete paginated thread listing required')
    if not isinstance(threads, list) or not isinstance(findings, list):
        raise ValueError('Thread and finding lists required')
    if reviewed_head != current_head:
        return {'action': 'skip_stale', 'reviewed_head': reviewed_head,
                'current_head': current_head}
    indexed, comment_ids = {}, set()
    for thread in threads:
        tid = _thread_id(thread['id'])
        root = _id(thread['root_comment_id'])
        _id(thread['author_id'])
        if tid in indexed or root in comment_ids:
            raise ValueError('Duplicate provider thread or root identity')
        if not isinstance(thread['body'], str):
            raise ValueError('Invalid root body')
        if type(thread['managed']) is not bool or type(thread['resolved']) is not bool:
            raise ValueError('Explicit ownership and resolution state required')
        comment_ids.add(root)
        if not isinstance(thread.get('replies'), list):
            raise ValueError('Complete reply listing required, including an explicit empty list')
        for reply in thread['replies']:
            rid = _id(reply['id'])
            _id(reply['author_id'])
            if rid in comment_ids or not isinstance(reply['body'], str):
                raise ValueError('Invalid or duplicate reply identity/body')
            comment_ids.add(rid)
        indexed[tid] = thread

    # New-vs-existing adjudication depends on all discussion, not just the root
    # selected for an update. Include unmatched/human threads too. Canonicalize
    # thread order but preserve reply order; never put reply bodies in actions.
    snapshot = [{field: thread[field] for field in (
        'id', 'root_comment_id', 'author_id', 'body', 'managed', 'resolved', 'replies')}
        for _, thread in sorted(indexed.items())]
    discussion_sha256 = hashlib.sha256(json.dumps(
        snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()

    actions, finding_ids, matched = [], set(), set()
    for finding in findings:
        fid = _text(finding['id'])
        if fid in finding_ids:
            raise ValueError('Duplicate finding identity')
        finding_ids.add(fid)
        body = _text(finding['body'])
        location = finding['location']
        if not isinstance(location, dict) or set(location) != {'path', 'line'}:
            raise ValueError('Explicit current source location required')
        path = _text(location['path'])
        if path != location['path'] or path.startswith('/') or any(
                p in ('', '.', '..') for p in path.split('/')) or any(
                ord(c) < 32 or c == '\\' for c in path):
            raise ValueError('Repository-relative source path required')
        _id(location['line'])
        if _sha(finding['verified_head']) != reviewed_head:
            raise ValueError('Correspondence evidence belongs to another commit')
        evidence = _text(finding['evidence'])
        tid = finding['matched_thread_id']
        disposition = finding['disposition']
        rendered = (f'Reviewed through `{reviewed_head}`.\n'
                    f'Current location: {path}:{location["line"]}\n\n{body}')
        common = {'finding_id': fid, 'body': rendered,
                  'evidence': evidence, 'preconditions': {
                      'current_head': current_head, 'publisher_id': publisher_id,
                      'discussion_sha256': discussion_sha256,
                      'requires_serialized_recheck': True}}
        if disposition == 'new' and tid is None:
            actions.append({**common, 'action': 'create',
                            'location': dict(location)})
            continue
        if disposition != 'existing' or tid is None:
            raise ValueError('Explicit new/existing correspondence required')
        _thread_id(tid)
        if tid not in indexed or tid in matched:
            raise ValueError('Missing or multiply matched thread; adjudicate manually')
        matched.add(tid)
        thread = indexed[tid]
        if thread['author_id'] != publisher_id or not thread['managed']:
            raise ValueError('Cannot edit an unowned or unmanaged thread')
        if thread['resolved']:
            raise ValueError('Resolved thread requires manual adjudication')
        common['preconditions'].update({
            'previous_body_sha256': hashlib.sha256(thread['body'].encode()).hexdigest(),
            'thread_resolved': False})
        actions.append({**common,
                        'action': 'noop' if rendered == thread['body'] else 'update',
                        'thread_id': tid, 'comment_id': thread['root_comment_id']})
    return {'action': 'plan', 'reviewed_head': reviewed_head,
            'discussion_sha256': discussion_sha256, 'actions': actions,
            'preserved_thread_ids': sorted(set(indexed) - matched)}
