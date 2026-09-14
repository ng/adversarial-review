"""Host-bound JSON transport for summary adapters; no redirects or retries.

Tokens and the GitLab origin must come from trusted operator configuration,
never a review artifact. Direct HTTPS uses the system TLS trust store and does
not inherit proxy settings. This transport does not provide coordination.
"""
import http.client
import json
import re
from urllib.parse import urlsplit


class SummaryHTTPError(RuntimeError):
    pass


class SummaryHTTP:
    def __init__(self, *, provider, token, origin=None, timeout=30):
        if not isinstance(token, str) or not re.fullmatch(r'[!-~]+', token):
            raise ValueError('Require a nonempty token without whitespace')
        if type(timeout) not in (int, float) or not 0 < timeout <= 120:
            raise ValueError('Timeout must be between zero and 120 seconds')
        if provider == 'github':
            if origin not in (None, 'https://api.github.com'):
                raise ValueError('Only github.com API is supported')
            origin, self.prefix = 'https://api.github.com', ''
            self.headers = {'Authorization': 'Bearer ' + token,
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2026-03-10'}
        elif provider == 'gitlab':
            self.prefix = '/api/v4'
            self.headers = {'PRIVATE-TOKEN': token, 'Accept': 'application/json'}
        else:
            raise ValueError('Unsupported provider')
        if not isinstance(origin, str) or not re.fullmatch(r'https://[A-Za-z0-9.-]+(?::[0-9]+)?/?', origin):
            raise ValueError('Require trusted HTTPS origin without path or credentials')
        parsed = urlsplit(origin)
        self.host, self.port = parsed.hostname, parsed.port
        self.timeout = timeout
        self.headers.update({'Content-Type': 'application/json', 'User-Agent': 'adversarial-review-summary'})

    def __call__(self, method, path, body):
        # Adapter-generated paths only: reject authority replacement, encoded
        # traversal, control characters and arbitrary URLs before attaching auth.
        if (not isinstance(path, str) or not re.fullmatch(r'/[A-Za-z0-9_./?=&-]+', path)
                or '//' in path or any(part in ('.', '..') for part in path.split('?', 1)[0].split('/'))):
            raise ValueError('Invalid API-relative path')
        if method not in ('GET', 'POST', 'PATCH', 'PUT'):
            raise ValueError('Unsupported HTTP method')
        if (method == 'GET' and body is not None) or (method != 'GET' and
                (not isinstance(body, dict) or set(body) != {'body'} or not isinstance(body['body'], str))):
            raise ValueError('Invalid summary request body')
        data = None if body is None else json.dumps(body, allow_nan=False).encode('utf-8')
        connection = http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout)
        try:
            connection.request(method, self.prefix + path, body=data, headers=self.headers)
            response = connection.getresponse()
            if not 200 <= response.status < 300:
                # Do not include untrusted response text, Location or credentials.
                raise SummaryHTTPError('Provider returned HTTP ' + str(response.status))
            if response.getheader('Content-Type', '').split(';', 1)[0].strip().lower() != 'application/json':
                raise SummaryHTTPError('Expected JSON provider response')
            payload = response.read(8 * 1024 * 1024 + 1)
            if len(payload) > 8 * 1024 * 1024:
                raise SummaryHTTPError('Provider response exceeds size limit')
            return json.loads(payload)
        except SummaryHTTPError:
            raise
        except (OSError, http.client.HTTPException, ValueError):
            # In particular, a write timeout is an uncertain result, not an
            # invitation to replay the request. The adapter persists that state.
            raise SummaryHTTPError('Provider request failed; no retry attempted') from None
        finally:
            connection.close()
