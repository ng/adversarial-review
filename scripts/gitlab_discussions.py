"""Read-only GitLab MR discussion collection for development reconciliation.

Uses the documented discussions endpoint, including each discussion's notes.
Never infers managed ownership from author identity or a copied body marker.
"""
from copy import deepcopy

from gitlab_summary import GitLabSummary
from reconcile_findings import _id, _sha, _thread_id


class GitLabDiscussions:
    def __init__(self, request, origin, project_id, number):
        target = GitLabSummary(request, origin, project_id, number)
        self.request, self.root, self.resource = request, target.root, target.resource
        self.project_id, self.number = project_id, number

    def _identity(self, require_open):
        publisher = _id(self.request('GET', '/user', None)['id'])
        mr = self.request('GET', self.root, None)
        if (type(mr.get('project_id')) is not int or mr['project_id'] != self.project_id
                or type(mr.get('iid')) is not int or mr['iid'] != self.number):
            raise ValueError('MR response belongs to another target')
        if require_open and mr['state'] != 'opened':
            raise ValueError('MR is not open')
        return publisher, _id(mr['id']), _sha(mr['sha']), mr['state']

    def snapshot(self, *, require_open=True):
        identity = self._identity(require_open)
        owner, mr_id, head, _ = identity
        threads, comments, positions = [], [], {}
        discussion_ids, note_ids = set(), set()
        for page in range(1, 1001):
            rows = self.request('GET', self.root + '/discussions?per_page=100&page=' + str(page), None)
            if not isinstance(rows, list) or len(rows) > 100:
                raise ValueError('Invalid discussion page')
            for discussion in rows:
                tid = _thread_id(discussion['id'])
                if tid in discussion_ids:
                    raise ValueError('Duplicate discussion; listing may have changed')
                discussion_ids.add(tid)
                notes = discussion['notes']
                individual = discussion['individual_note']
                if (type(individual) is not bool or not isinstance(notes, list) or not notes
                        or (individual and len(notes) != 1)):
                    raise ValueError('Invalid discussion root/reply structure')
                for note in notes:
                    nid = _id(note['id'])
                    _id(note['author']['id'])
                    if (nid in note_ids or not isinstance(note['body'], str)
                            or type(note.get('project_id')) is not int or note['project_id'] != self.project_id
                            or type(note.get('noteable_id')) is not int or note['noteable_id'] != mr_id
                            or note.get('noteable_type') != 'MergeRequest'
                            or type(note.get('system')) is not bool
                            or type(note.get('internal', False)) is not bool):
                        raise ValueError('Invalid, duplicated, or foreign discussion note')
                    note_ids.add(nid)
                # Keep the actual root; never promote a reply when its root is
                # excluded. Provider note ordering is retained for discussion.
                root = notes[0]
                if root['system'] or root.get('internal', False):
                    continue
                kind = root.get('type')
                if kind not in (None, '', 'DiscussionNote', 'DiffNote'):
                    raise ValueError('Unsupported discussion note type')
                if individual and kind not in (None, ''):
                    raise ValueError('Individual note has a threaded note type')
                if not individual and kind in (None, ''):
                    raise ValueError('Thread root has an individual note type')
                resolved = root.get('resolved')
                if type(resolved) is not bool:
                    raise ValueError('Explicit root resolution state required')
                replies = [dict(id=n['id'], author_id=n['author']['id'], body=n['body'])
                           for n in notes[1:] if not n['system'] and not n.get('internal', False)]
                threads.append(dict(id=tid, root_comment_id=root['id'], author_id=root['author']['id'],
                                    body=root['body'], resolved=resolved, managed=False, replies=replies))
                if kind == 'DiffNote':
                    if not isinstance(root.get('position'), dict) or not root['position']:
                        raise ValueError('Diff root lacks position metadata')
                    positions[tid] = deepcopy(root['position'])
                if individual or kind == 'DiffNote':
                    row = dict(comment_id=root['id'], publisher_id=root['author']['id'],
                               body=root['body'], target_kind='summary' if individual else 'inline')
                    if not individual:
                        row['thread_id'] = tid
                    comments.append(row)
            if len(rows) < 100:
                if self._identity(require_open) != identity:
                    raise ValueError('MR or publisher changed during collection')
                return dict(resource=list(self.resource), publisher_id=owner, current_head=head,
                            merge_request_id=mr_id,
                            listing_complete=True, comments=comments, threads=threads, positions=positions)
        raise ValueError('Discussion pagination limit reached; listing incomplete')

    def recover_batch(self, coordinator):
        return coordinator.recover_batch(self.resource, lambda _: self.snapshot(require_open=False))

    def plan_findings(self, transaction, *, scope, channel, reviewed_head, findings):
        """Read-only planning inside an existing PR-wide coordinator claim."""
        from inline_ownership import plan_owned_findings
        findings = deepcopy(findings)
        return plan_owned_findings(transaction, self.snapshot(), scope=scope,
                                   channel=channel, reviewed_head=reviewed_head, findings=findings)
