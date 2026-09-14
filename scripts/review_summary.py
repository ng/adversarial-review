"""Compose adjudicated risk and owned-summary planning from one provider snapshot."""
from merge_risk import assess
from reconcile_summary import plan_summary


def plan_review_summary(*, repository, change_number, scope, channel, adjudication,
                        details, snapshot):
    if not isinstance(details, str) or not details.strip():
        raise ValueError('Self-contained review details required')
    if set(adjudication) != {'reviewed_head', 'completed', 'material_unknowns', 'findings'}:
        raise ValueError('Explicit final adjudication required')
    # Caller provides canonical scope; do not let a separately supplied full_scope
    # flag contradict the visible scope of the published summary.
    risk = assess(**adjudication, current_head=snapshot['current_head'], full_scope=scope == 'full branch')
    plan = plan_summary(repository=repository, change_number=change_number, scope=scope,
                        channel=channel, reviewed_head=adjudication['reviewed_head'],
                        summary=risk['summary'] + '\n\n' + details, **snapshot)
    return {'risk': risk, 'publication_plan': plan}
