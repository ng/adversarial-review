"""Plan (default), publish, or recover one owned review summary.

Run from a trusted installation, not PR-controlled code. Configuration belongs
to the operator; review JSON contains only adjudication and display details.
Single-host publishing requires every writer to share persistent local state.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys

from github_summary import GitHubSummary
from gitlab_summary import GitLabSummary
from review_summary import plan_review_summary
from summary_coordinator import LocalCoordinator
from summary_http import SummaryHTTP, SummaryHTTPError


def object_fields(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError('Invalid ' + label + ' fields')


def adapter_from_config(config, environment):
    if not isinstance(config, dict):
        raise ValueError('Configuration must be an object')
    common = {'provider', 'number', 'scope', 'channel', 'token_env', 'coordination'}
    provider = config.get('provider')
    if provider not in ('github', 'gitlab'):
        raise ValueError('Unsupported provider')
    object_fields(config, common | ({'repository'} if provider == 'github' else {'origin', 'project_id'}), 'configuration')
    token_env = config['token_env']
    if not isinstance(token_env, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]*', token_env):
        raise ValueError('Invalid credential environment variable name')
    for field in ('scope', 'channel'):
        if not isinstance(config[field], str) or not config[field].strip() or any(c in config[field] for c in '\r\n'):
            raise ValueError('Invalid ' + field)
    origin = config.get('origin')
    transport = SummaryHTTP(provider=provider, token=environment.get(token_env), origin=origin)
    if provider == 'github':
        return GitHubSummary(transport, config['repository'], config['number'])
    return GitLabSummary(transport, origin, config['project_id'], config['number'])


def execute(*, config, review, mode, run_version, environment):
    if mode not in ('plan', 'publish', 'recover'):
        raise ValueError('Invalid mode')
    if mode == 'recover':
        if review is not None or run_version is not None:
            raise ValueError('Recovery does not accept a review or run version')
    else:
        object_fields(review, {'adjudication', 'details'}, 'review')
        if mode == 'publish' and (type(run_version) is not int or run_version < 1):
            raise ValueError('Publishing requires a trusted positive run version assigned at review start')
        if mode == 'plan' and run_version is not None:
            raise ValueError('Read-only planning does not consume a run version')
    adapter = adapter_from_config(config, environment)
    if mode == 'plan':
        return plan_review_summary(repository=adapter.context_repository,
            change_number=adapter.number, scope=config['scope'], channel=config['channel'],
            adjudication=review['adjudication'], details=review['details'], snapshot=adapter.snapshot())
    coordination = config['coordination']
    object_fields(coordination, {'kind', 'directory'}, 'coordination')
    if coordination['kind'] != 'single-host' or not isinstance(coordination['directory'], str) or not Path(coordination['directory']).is_absolute():
        raise ValueError('Publishing requires a persistent absolute single-host coordinator directory')
    coordinator = LocalCoordinator(coordination['directory'])
    if mode == 'recover':
        return adapter.recover(coordinator)
    return adapter.publish_review(adjudication=review['adjudication'], details=review['details'],
        scope=config['scope'], channel=config['channel'], run_version=run_version, coordinator=coordinator)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True, help='Trusted operator JSON; never model-generated')
    parser.add_argument('--review', type=Path, help='Final adjudication and self-contained details JSON')
    parser.add_argument('--mode', choices=('plan', 'publish', 'recover'), default='plan')
    parser.add_argument('--run-version', type=int, help='Trusted monotonic version assigned when review starts')
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text())
        review = json.loads(args.review.read_text()) if args.review else None
        result = execute(config=config, review=review, mode=args.mode,
                         run_version=args.run_version, environment=os.environ)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, TypeError, KeyError, OSError, SummaryHTTPError):
        # Provider payloads, local paths and arbitrary JSON may contain secrets.
        # Avoid tracebacks or echoing those values from the CLI.
        print('Summary operation failed. No automatic retry was attempted. '
              'For a publish failure, inspect coordinator state before another run.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
