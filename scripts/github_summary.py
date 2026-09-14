"""GitHub summary adapter. Publishing requires a caller-owned coordinator.

The coordinator must serialize all writers for the PR across hosts, reject old
run versions, persist a pending write before sending it, and block uncertain
outcomes until read-only recovery. No command-line publish entry point is exposed.
"""
import re
from copy import deepcopy

from reconcile_summary import plan_summary
from review_summary import plan_review_summary


class GitHubSummary:
    def __init__(self, request, repository, number):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('Require owner/repository')
        if type(number) is not int or number <= 0:
            raise ValueError('Require positive PR number')
        self.request = request
        self.repository = repository.lower()
        self.number = number
        self.root = '/repos/' + self.repository
        self.resource = ('github', self.repository, self.number)
        self.context_repository = 'github:' + self.repository

    def snapshot(self, *, require_open=True):
        # /user verifies token identity, not a guessed bot name. Installation
        # tokens needing a different identity flow fail here rather than falling
        # back to matching a mutable display name.
        publisher = self.request('GET', '/user', None)['id']
        pr = self.request('GET', self.root + '/pulls/' + str(self.number), None)
        if require_open and pr['state'] != 'open':
            raise ValueError('PR is not open')
        comments = []
        for page in range(1, 1001):
            rows = self.request('GET', self.root + '/issues/' + str(self.number)
                + '/comments?per_page=100&page=' + str(page), None)
            if not isinstance(rows, list) or len(rows) > 100:
                raise ValueError('Invalid comment page')
            comments.extend({'id': row['id'], 'author_id': row['user']['id'], 'body': row['body']} for row in rows)
            if len(rows) < 100:
                return {'publisher_id': publisher, 'current_head': pr['head']['sha'],
                        'comments': comments, 'listing_complete': True}
        raise ValueError('Comment pagination limit reached; listing incomplete')

    def plan(self, reviewed_head, scope, channel, summary):
        return plan_summary(repository=self.context_repository, change_number=self.number,
                            reviewed_head=reviewed_head, scope=scope, channel=channel,
                            summary=summary, **self.snapshot())

    def recover(self, coordinator):
        return coordinator.recover(self.resource, lambda plan: self.snapshot(require_open=False))

    def write(self, plan):
        if plan['action'] == 'create':
            return self.request('POST', self.root + '/issues/' + str(self.number) + '/comments', {'body': plan['body']})
        return self.request('PATCH', self.root + '/issues/comments/' + str(plan['comment_id']), {'body': plan['body']})

    def publish(self, *, reviewed_head, scope, channel, summary, run_version, coordinator):
        return self._publish(lambda: self.plan(reviewed_head, scope, channel, summary),
                             reviewed_head, run_version, coordinator)

    def publish_review(self, *, adjudication, scope, channel, details, run_version, coordinator):
        """Publish final adjudication with risk derived from each fresh snapshot.

        Freeze caller-owned findings before reads so both rechecks assess the
        same review. Scope and head cannot be independently overridden for risk.
        """
        adjudication = deepcopy(adjudication)
        def plan():
            return plan_review_summary(repository=self.context_repository,
                change_number=self.number, scope=scope, channel=channel,
                adjudication=adjudication, details=details,
                snapshot=self.snapshot())['publication_plan']
        return self._publish(plan, adjudication['reviewed_head'], run_version, coordinator)

    def _publish(self, make_plan, reviewed_head, run_version, coordinator):
        # Coordinator identity is PR-wide, not scope-specific: separate scopes
        # cannot bypass ordering/locking on the same provider resource.
        with coordinator.claim(self.resource, run_version) as transaction:
            first = make_plan()
            if first['action'] in ('skip_stale', 'noop'):
                result = first if first['action'] == 'skip_stale' else {
                    'action': 'noop', 'comment_id': first['comment_id'],
                    'reviewed_head': reviewed_head}
                transaction.complete(result)
                return result
            latest = make_plan()
            if latest != first:
                raise ValueError('Provider state changed before write; no write attempted')
            # GitHub offers no transaction tying a PR head read to a comment
            # write. Rechecks plus coordinator cannot exclude unrelated writers
            # or a push at this final instant; the body remains SHA-bound.
            transaction.pending(first)
            try:
                response = self.write(first)
                if (response['body'] != first['body']
                        or response['user']['id'] != first['preconditions']['publisher_id']
                        or type(response['id']) is not int
                        or response['id'] <= 0
                        or (first['action'] == 'update' and response['id'] != first['comment_id'])):
                    raise ValueError('Write response differs from planned owned comment')
            except BaseException:
                # Never blindly repeat POST/PATCH after a timeout or malformed
                # response: the write may already have succeeded remotely.
                transaction.uncertain()
                raise
            result = {'action': first['action'], 'comment_id': response['id'],
                      'reviewed_head': reviewed_head}
            transaction.complete(result)
            return result
