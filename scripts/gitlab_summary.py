"""GitLab MR summary notes over the shared coordinated upsert lifecycle.

Request transport must be bound to the configured trusted GitLab origin. Uses
numeric project IDs so project renames do not change summary identity.
"""
from urllib.parse import urlsplit

from github_summary import GitHubSummary


class GitLabSummary(GitHubSummary):
    def __init__(self, request, origin, project_id, number):
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
            raise ValueError('Require trusted HTTPS GitLab origin without credentials or path')
        if any(type(v) is not int or v <= 0 for v in (project_id, number)):
            raise ValueError('Require numeric project ID and MR IID')
        self.request, self.number = request, number
        # An explicit default HTTPS port is the same provider, not a new lock
        # namespace or summary owner key for the very same MR.
        host = parsed.hostname.lower()
        if ':' in host:
            host = '[' + host + ']'
        port = parsed.port
        self.origin = 'https://' + host + (':' + str(port) if port not in (None, 443) else '')
        self.root = '/projects/' + str(project_id) + '/merge_requests/' + str(number)
        self.resource = ('gitlab', self.origin, project_id, number)
        self.context_repository = 'gitlab:' + self.origin + '/projects/' + str(project_id)

    def snapshot(self, *, require_open=True):
        publisher = self.request('GET', '/user', None)['id']
        mr = self.request('GET', self.root, None)
        if require_open and mr['state'] != 'opened':
            raise ValueError('MR is not open')
        comments = []
        for page in range(1, 1001):
            rows = self.request('GET', self.root + '/notes?per_page=100&sort=asc&order_by=created_at&page=' + str(page), None)
            if not isinstance(rows, list) or len(rows) > 100:
                raise ValueError('Invalid note page')
            for row in rows:
                # System events, internal notes and discussion replies are not
                # public standalone summaries even if they contain a marker.
                if row.get('system') is not False or row.get('internal', False) or row.get('type') not in (None, ''):
                    continue
                comments.append({'id': row['id'], 'author_id': row['author']['id'], 'body': row['body']})
            if len(rows) < 100:
                return {'publisher_id': publisher, 'current_head': mr['sha'],
                        'comments': comments, 'listing_complete': True}
        raise ValueError('Note pagination limit reached')

    def write(self, plan):
        path = self.root + '/notes'
        method = 'POST'
        if plan['action'] == 'update':
            path += '/' + str(plan['comment_id'])
            method = 'PUT'
        response = self.request(method, path, {'body': plan['body']})
        if response.get('system') is not False or response.get('internal', False) or response.get('type') not in (None, ''):
            raise ValueError('Response is not a public standalone summary note')
        return {'id': response['id'], 'body': response['body'], 'user': response['author']}
