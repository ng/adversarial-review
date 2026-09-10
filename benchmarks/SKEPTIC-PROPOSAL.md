# Proposed Skeptic revision — not yet applied or benchmarked

The current seven scored native reviews gained no reference coverage after the
Skeptic, while total findings increased from 75 to 83. Selected source checks
also found useful corrections, supported cleanup, and inaccurate clauses inside
otherwise supported findings. The next experiment should test whether focused
verification improves final reports without losing important defects.

This document is a reviewable proposal. The benchmark's frozen plugin and
existing scores remain unchanged. No additional benchmark calls are authorized
by this document.

## Candidate instruction change

> For each Optimizer candidate, identify its concrete trigger, causal path, and
> user or system impact. Inspect relevant unchanged helpers before making claims
> about validation, permissions, exception propagation, logging, or retries.
>
> Try to disprove the claim using existing guards, callers, schema constraints,
> and supported input contracts. Distinguish “this path would fail under X” from
> “a supported caller can produce X.” A deterministic source proof can be enough;
> a full reproduction is not mandatory when the causal path is established.
>
> Choose retain, narrow/correct, merge, defer, or reject, with a short reason.
> Verify supporting clauses and code examples as well as the main issue. Remove
> unsupported details even when the central defect is valid. Do not imply that
> missing evidence proves safety or that a plausible trigger is observed fact.
>
> Merge findings with the same root cause and corrective action. Attach the
> missing regression test to its defect unless it demonstrates an independent
> problem. Separate supported nonblocking cleanup from defects with demonstrated
> material impact; do not use speculative downstream harm to inflate severity.
>
> If investigation reveals a new independent defect, apply the same evidence
> standard and mark it as new. Do not impose a target finding count or reject
> findings solely to make the report shorter. Reserve time for final synthesis.

Suggested compact record: candidate ID; disposition; trigger; inspected evidence;
impact; unresolved assumption; proposed regression check. Link repeated evidence
instead of copying full investigation transcripts into the final report.

## Examples from the development observations

| Observation | Intended change in final report |
|---|---|
| Cal.com calendar consistency plus “no logging” | Preserve the supported consistency concern; remove the contradicted logging claim and limit exception statements to traced paths. |
| Cal.com unreachable toast fallback | Present as nonblocking cleanup unless a concrete user-facing failure is demonstrated. |
| Sentry shared timestamp plus weak test | One narrowly stated defect with a controlled-clock regression test recommendation. |
| Sentry malformed metadata | State the conditional bypass and remaining configuration guards; require producer evidence before claiming an observed deployment failure. |

These are development examples, not held-out evaluation cases.

## Evaluation plan before promotion

Use the same frozen Optimizer output for each old/new Skeptic comparison so
changes in discovery do not obscure changes in verification. This isolates the
Skeptic stage; it does not estimate end-to-end performance of a modified plugin.
Select held-out PRs not used in these source checks or prompt development, freeze
their selection before reading outputs, and match model, context access, and
runtime allowance between variants. Later end-to-end testing remains necessary.

Assess final reports with configuration labels hidden where feasible, noting
that prose may reveal provenance. Use source-aware adjudication, not reference
matching alone. Record:

- Important supported defects retained, narrowed, or incorrectly rejected.
- Unsupported factual clauses removed, retained, or introduced.
- Duplicates merged, severity corrections, and new supported defects.
- Completion within the cap, final report size, and human triage time if measured.
- Model calls and reported usage, including unsuccessful work and normalization.

Treat loss of an independently verified important defect as a case requiring
investigation before promotion. Do not declare success from shorter reports or
reference precision alone. A small pilot can identify failure modes; it cannot
establish a reliable overall improvement rate.

## Budget boundary

Keep bulk runs paused. Before executing, agree on a small number of paired PRs
and a budget covering both Skeptic variants, any preparation, normalization, and
adjudication calls. Use one worker initially and stop at the agreed boundary.
The existing native workflow can spawn subagents, so a cap on top-level trials
is not a cap on model calls or subscription usage. Enforcing a true call budget
requires accounting for those child calls as well; this proposal does not yet
implement that control.
