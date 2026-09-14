"""Deterministic risk rendering from final adjudication, not model vote counts.

This communicates findings/coverage; it is not a probability or merge certificate.
Only unresolved findings should be supplied. A missing finding in a later model
response is not evidence that it was fixed.
"""
import argparse
import json
from pathlib import Path
import re

from reconcile_summary import PREFIX


def assess(*, reviewed_head, current_head, full_scope, completed, material_unknowns, findings):
    for head in (reviewed_head, current_head):
        if not isinstance(head, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', head):
            raise ValueError('Full reviewed/current commit hashes required')
    if any(type(value) is not bool for value in (full_scope, completed, material_unknowns)):
        raise ValueError('Explicit coverage and uncertainty booleans required')
    if not isinstance(findings, list):
        raise ValueError('Final finding list required')
    ids = set()
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {'id', 'support', 'impact', 'introduced'}:
            raise ValueError('Finding fields must be id, support, impact, introduced')
        if not isinstance(finding['id'], str) or not finding['id'] or finding['id'] in ids:
            raise ValueError('Unique nonempty finding IDs required')
        if PREFIX in finding['id'] or any(ord(c) < 32 or ord(c) == 127 for c in finding['id']):
            raise ValueError('Finding IDs must contain no control characters or reserved summary marker')
        ids.add(finding['id'])
        if finding['support'] not in ('supported', 'contradicted', 'unresolved'):
            raise ValueError('Invalid support')
        if finding['impact'] not in ('important', 'minor', 'cleanup', 'unknown'):
            raise ValueError('Invalid impact')
        if type(finding['introduced']) is not bool:
            raise ValueError('Explicit attribution required')
    relevant = [f for f in findings if f['introduced'] and f['support'] != 'contradicted']
    important = [f['id'] for f in relevant if f['support'] == 'supported' and f['impact'] == 'important']
    minor = [f['id'] for f in relevant if f['support'] == 'supported' and f['impact'] == 'minor']
    unknown = [f['id'] for f in relevant if f['support'] == 'unresolved' or f['impact'] == 'unknown']
    gaps = []
    if not full_scope:
        gaps.append('Only part of the change was reviewed.')
    if not completed:
        gaps.append('Required review or verification work is incomplete.')
    if material_unknowns or unknown:
        gaps.append('Material questions remain unresolved.')
    reviewed_level = ('High' if important else 'Unknown' if gaps else 'Medium' if minor else 'Low')
    stale = reviewed_head != current_head
    level = 'Unknown' if stale else reviewed_level
    icon = {'High': '🔴', 'Medium': '🟡', 'Low': '🟢', 'Unknown': '⚪'}[level]
    heading = f'Merge risk {icon} {level} — up to `{reviewed_head[:12]}`'
    if stale:
        reason = 'Outdated review: the current head has not been reviewed. The earlier revision was assessed as ' + reviewed_level + '.'
    elif important:
        reason = 'Supported important defects remain.'
    elif gaps:
        reason = 'Coverage or material evidence is incomplete.'
    elif minor:
        reason = 'Supported behavioral defects remain with bounded impact.'
    else:
        reason = 'No supported behavioral defects or material unresolved concerns were identified in the completed review.'
    if important:
        reason += '\nKnown important finding IDs at the reviewed revision: ' + ', '.join(important) + '.'
    if gaps:
        reason += '\n' + ' '.join(gaps)
    reason += '\nThis is a review assessment, not a guarantee that merging is safe.'
    return {'level': level, 'reviewed_level': reviewed_level, 'stale': stale,
            'reviewed_head': reviewed_head, 'current_head': current_head,
            'known_important_ids': important, 'known_minor_ids': minor, 'unresolved_ids': unknown,
            'coverage_gaps': gaps, 'summary': heading + '\n\n' + reason}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    print(json.dumps(assess(**json.loads(args.input.read_text())), indent=2))
