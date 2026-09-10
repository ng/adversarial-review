# Proposal discussion with Claude — September 10

The user authorized working through the gaps with Claude. We used exactly two
additional tool-free Claude Sonnet 5 subscription CLI invocations, each capped
at 300 seconds and a $2 nominal CLI ceiling. No subagents, benchmark trials,
normalization calls, or pilot calls were started. Bulk schedulers stayed paused.
Raw prompt/event/usage records are under `WORK/proposal-discussion-round{2,3}/`.

## Exchange and decisions

| Gap from initial review | Revision and outcome |
|---|---|
| Ambiguous dispositions | Four dispositions with explicit report treatment; narrowing, factual correction, and severity changes are independent flags. Claude accepted. |
| False negatives and factual-error measurement | Freeze a source-aware ledger of all Optimizer candidates before final outputs; audit rejected/deferred candidates and new clauses. Important defects hidden through deferral, narrowing, or merging count as losses. Claude accepted the design; labels remain author judgments, not independent ground truth. |
| Unbounded native subagent work | Proposed a distinct packet-only prompt pilot: three PRs, at most nine tool-free CLI invocations, no retries. This does not validate the native workflow and cannot guarantee a subscription-percentage cap. Claude accepted the explicit scope and limit. |
| Undefined stopping criteria | Fixed fail-stop rules and eligibility criteria; inconclusive results cannot trigger extra pairs. Claude accepted. |
| Allegedly exhausted held-out pool | Enumerated 30/335/167 cases without run directories, selected one per benchmark deterministically, and recorded pins plus a manifest hash. Claude withdrew its exhaustion concern. Prior-exposure audit remains necessary; these counts do not prove pristine holdout status. |
| Prompt fidelity | Revision 3 added provenance, hashes, unified diff, line classifications, and an author checklist. Claude requested a second-party spot-check before running. Revision 4 incorporates that exact request as a second-human check with no model calls. |
| Uncertain claims hidden by merging | Evidence is assessed first; unresolved central claims are deferred and cannot be merged into confirmed findings. Claude accepted. |

Claude's final verdict was **design-ready**, conditional on tightening the
second-party check and completing execution prerequisites. Revision 4 makes that
last requested change; it has not received a third additional Claude review.
The complete critiques are preserved in [round 2](CLAUDE-PROPOSAL-ROUND2.md) and
[round 3](CLAUDE-PROPOSAL-ROUND3.md).

We corrected two overstatements rather than treating agreement as proof: a usage
estimate is not a hard quota control, and the absence of observed holdout PRs in
a small analyzed sample does not mean the 584-PR pool is exhausted. Claude also
corrected its conflation of six PRs with the number of static source checks.

## What remains before any pilot

1. Implement and fake-CLI-test the dedicated nine-slot runner; current native
   benchmark commands do not enforce this proposed pilot budget.
2. Audit prior exposure for the three selected PRs and freeze source packets.
   Abort on unresolved eligibility or inadequate packet fit; do not substitute
   PRs within this frozen selection.
3. Extract, adapt, diff, and hash old/new prompts; complete the author checklist
   and second-human prompt-fidelity spot-check.
4. Obtain authorization for the concrete bounded pilot. This discussion's
   authorization covers document review, not benchmark execution.

The proposed selection and its SHA256 are now checked in. Neither selection nor
Claude's design verdict is evidence that the revised Skeptic improves PR quality.
See [the revised proposal](SKEPTIC-PROPOSAL.md) for the exact protocol and limits.
