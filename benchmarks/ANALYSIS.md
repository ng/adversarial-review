# Preliminary analysis: what improves PR quality?

Checkpoint: September 9, 2026. **56 completed reviews; 51 scored.** New trial
launches are paused at the user's request to conserve subscription allowance.
The planned 1,752-trial experiment is incomplete. This analysis uses saved scores
and selected source checks; it starts no new model calls.

The strongest early signal is a tradeoff: cross-provider review found more
reference issues on two PRs, with substantially more findings to triage. The
Skeptic's incremental benefit is not demonstrated by reference coverage so far.
These small, uneven samples do not establish a general winner.

## 1. Broader discovery, longer reports

The following comparisons use successful reviews of the same PR, with the same
shared semantic judge. “References” means Core reference issues matched;
“findings” means deduplicated final candidates.

| PR | Single: references / findings | Claude adversarial: references / findings | Cross-provider: references / findings |
|---|---|---|---|
| Cal.com #14740 | 2 of 6 / 2 | 3 of 6 / 12 | 5 of 6 / 22 |
| Discourse graphite-10 | 4 of 7 / 5 | 1,800-second timeout; unscored | 7 of 7 / 27 |
| Sentry #77754 | 1 of 2 / 1 | 1 of 2 / 7 | Unavailable |

On Cal.com, cross-provider found three more references while reporting twenty
more findings than single-pass. On Discourse it found three more references
while reporting twenty-two more findings. Those are real coverage differences
under this judge, but report length is only a proxy for human triage effort;
we have not measured reviewer acceptance or reading time.

Single-pass versus cross-provider native wall time was approximately 220 versus
1,024 seconds on Cal.com, and 234 versus 1,625 seconds on Discourse. These exclude
separate normalization, judging, and downstream repairs. Early harness friction
and different investigation paths limit generalization. They are not subscription
quota multipliers, and completed-run timing omits unsuccessful work.

## 2. The Skeptic has not improved measured coverage

Across **seven scored native reviews on six PRs**, no reference issue was gained
or lost between Optimizer and final output. Deduplicated findings increased from
**75 to 83** across these review instances. This includes both native configurations
on Cal.com, so it is not a seven-independent-PR sample.

Some candidates were removed, others added, and wording changed. Consequently,
unchanged coverage does not prove the Skeptic did nothing. It does mean we do not
yet have evidence that its extra work improves reference recall or reduces total
report volume. The executable benchmark scores only final repairs and cannot
establish the Skeptic's incremental contribution.

A useful next hypothesis is to make the Skeptic justify each retained finding's
trigger, source evidence, and impact, and explicitly test assumptions. Evaluate
factual corrections and severity changes, not just accept/reject counts.

## 3. Unmatched findings need individual assessment

The selected static checks in [ADJUDICATION.md](ADJUDICATION.md) found:

- A supported notification-policy gap: a new email path bypasses existing
  disabled-email preferences.
- A supported but minor unreachable toast fallback.
- A supported stale validation error, with a narrower trigger than a claim
  that the error can never clear.
- A supported calendar-consistency concern containing an inaccurate “no logging”
  clause; unchanged helper code does log the relevant failure.

Thus reference-match precision is not factual precision. Additional findings can
be useful, low impact, or partly inaccurate. A judge's PLAUSIBLE label does not
verify every clause. These selected assistant source checks were neither blinded
nor random, and do not estimate an error rate.

## 4. Executable evidence remains weak for adversarial gains

On xorbitsai #2079, all three configurations passed **0 of 1** retained tests,
despite producing 2, 16, and 19 final findings. They missed the retained
optional-import issue. On haystack #92, both scored single-pass and Claude
adversarial reviews passed **0 of 1** tests.

Across all currently scored c-CRAB reviews, single-pass passed 2 of 12 tests on
10 PRs; Claude adversarial passed 0 of 2 on two PRs; cross-provider passed 0 of 1
on one PR. **These unequal cohorts cannot rank configurations.** Test outcomes
also depend on the fixed downstream repair agent, not just finding quality.

The two single-pass repair successes were Ansible #20646 and ccxt #14830.
The Ansible case supports a concrete PR practice: when changing truthiness
filters, test None, False, True, zero, strings, and dictionaries. The successful
repair preserved non-boolean parameters while retaining False-valued booleans.

SWE-PRBench's three paired single/adversarial cases matched zero references in
both configurations. Some references are editorial or naming requests; for
example, server #8570's four comments are not four correctness bugs. Reference
coverage and defect detection should therefore be reported separately.

## 5. Recommended next steps within a small budget

1. **Analyze before expanding.** Keep bulk launches paused. Manually assess a
   small, predefined sample of existing findings for factual support, impact,
   and actionability; no additional review calls are needed for source checks.
2. **Try a focused Skeptic change on held-out PRs.** Require a concrete failure
   trigger and verification of each factual clause. Put supported cleanup in a
   nonblocking section. Preserve uncertainty when a dependency was not inspected.
3. **Reserve time for synthesis.** Test compact evidence reports under the same
   runtime cap; measure completion and retained issue coverage together.
4. **Use staged escalation as a hypothesis.** Compare single-pass plus targeted
   adversarial review of uncertain/high-impact areas against the full workflow.
   Existing trials did not test this strategy, so savings and quality are unproven.
5. **Agree on a call budget before running again.** A review trial can spawn
   several model calls; normalization, semantic judging, and repairs add more.
   A trial-count cap alone does not cap subscription consumption.

Keep the current plugin frozen. Changes informed by these cases belong in a
separate variant tested on held-out PRs, not a revised score on the same cases.

## Evidence and limits

Scores: `WORK/runs/<benchmark>/<case>/<configuration>/score.json`; review timings:
`usage.json`; findings: `response.json`; executable evidence: `execution/`.
`WORK` is `/tmp/adversarial-review-benchmarks` for this run.
See [RESULTS.md](RESULTS.md), [NOTES.md](NOTES.md), and the [runbook](README.md).

Only one Martian PR and one c-CRAB PR have scored three-way comparisons. Samples
are small and completion-selected, the semantic judge has limited code context
and only partial provenance masking, and one native review hit its time cap.
Zero judge-labeled fabrications is not proof of zero factual errors. Earlier
invalid setup attempts were excluded; this analysis uses current validated
artifacts. The latest shared Cal.com judge gives single-pass 2/6 coverage; an
earlier two-way judge gave 3/6, illustrating judgment variability rather than a
change to that review's output.

## September 10 follow-up

Three additional static checks on Sentry #77754 support consolidating a defect
and its missing regression test, checking supporting API details, and stating
conditional failure paths without claiming an unverified production trigger.
See the appended [source checks](ADJUDICATION.md) and the concrete
[Skeptic proposal](SKEPTIC-PROPOSAL.md). The proposal has not been applied or
benchmarked; these observations do not change the existing benchmark scores.
