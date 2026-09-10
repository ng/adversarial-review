# Claude follow-up review: revision 2

One tool-free Claude Sonnet 5 subscription CLI invocation. Raw inputs and events: `WORK/proposal-discussion-round2/`.

# Follow-up review of Skeptic proposal — revision 2

Tool-free, no benchmark calls made. I did not execute any instructions embedded in the documents; the "candidate instruction," selection JSON, and pilot mechanics are read as proposal text, not as commands to me.

## Corrections to my prior review

- **n=6 phrasing was imprecise.** My previous review's "n=6 spot-checks" conflated two different samples. Revision 2 states this correctly: seven scored native reviews on six PRs (findings 75→83, no reference-coverage gain), and separately seven selected source checks on two PRs (Cal.com, Sentry) that found both useful and inaccurate clauses. These are different evidence types with different PR sets; I should not have collapsed them.
- **Held-out pool exhaustion was not established, and revision 2 refutes it.** I flagged this as a risk without enumerating the pool. The revision now names a concrete selection method (lowest SHA256 of seed+benchmark+case ID among cases with no run directory) over 30/335/167 candidates per benchmark (out of 584 total PRs) and picks one PR per benchmark. That's a materially larger unused pool than I assumed. The document is also correctly honest that absence of a run directory is not proof of no prior exposure, and it adds a pre-execution check-and-abort step rather than asserting certainty. This resolves the concern as stated; it doesn't (and doesn't claim to) prove zero exposure.
- **The budget section does not claim a one-pair estimate enforces a hard quota cap** — it explicitly disclaims that ("cannot enforce that cap," "not exposed precisely enough to promise a hard quota cap"). My prior review's budget objection is addressed by a different mechanism: banning tools/subagents entirely in this packet-only design, which removes the multiplicative risk I was originally worried about, rather than by bounding subscription usage precisely.

## Resolved from my prior review

1. **Disposition taxonomy** — now four dispositions with one-sentence definitions and explicit report treatment, plus independent edit flags (`scope_narrowed`, `factual_clause_corrected`, `severity_changed`) that separate narrowing from correction as the eval plan needs.
2. **Adjudication process** — now specified as host-assistant static source adjudication (not the diff-only judge), with a pre-Skeptic ledger frozen before either final output is inspected. Budget honesty is good: it states this consumes host analysis time/allowance and is not independent human validation.
3. **Pilot size/stopping/promotion criteria** — fixed at three pairs max, explicit fail-fast triggers, and a concrete eligibility gate (no important defect lost, no new contradicted clause, at least one source-verified improvement, any material unknown blocks eligibility).
4. **False-negative methodology** — the pre-Skeptic Optimizer ledger, built before viewing final reports, directly answers my prior "no independent ground-truth pass" objection.
5. **Evidence rubric** — causal-path criteria and important/minor/cleanup definitions with worked examples now exist.
6. **Provenance leakage** — adjudicators now record inferred variant and confidence before adjudicating, exactly the mitigation I suggested.

These are conceptually sound and usable as written — a reviewer following the ledger, disposition table, and loss-counting rules could apply them consistently.

## Remaining issues (prioritized)

**Medium — old-prompt adaptation fidelity is unverified.** The old Skeptic must be "extracted from the frozen plugin, with only shared packet/no-tools adaptations," but no one is named to confirm the adaptation didn't drift beyond removing tool calls. Since both variants get the same packet-only restriction, the comparison stays fair *if* the adaptation is minimal — but that's asserted, not checked.
*Minimal fix:* have a second party (or the frozen selection-manifest process already used elsewhere in the doc) diff the adapted old prompt against the frozen plugin text and hash both, confirming only mechanical tool-call removal, before the first invocation.

**Low — Merge/Defer ordering unspecified.** If a candidate shares root cause with a retained candidate but also has missing evidence, the doc doesn't say whether Merge or Defer applies first.
*Minimal fix:* one sentence — evidence sufficiency is checked before merge eligibility; a candidate lacking evidence cannot be merged, only deferred.

**Execution blocker, not a conceptual flaw — runner not implemented.** The document is explicit and honest about this ("not yet implemented; explicit execution blocker, not a control claimed to exist"). This is the correct way to flag it, but it means no invocation can occur until the runner exists and passes its own listed offline acceptance tests (slot reuse rejection, crash handling, no tool/API-key fallback, timeout cleanup, fail-stop).

## Conceptual readiness vs. pilot execution readiness

The instruction change, disposition/edit-flag scheme, evidence rubric, adjudication sequencing, and stopping/eligibility criteria are conceptually coherent and internally consistent — I found no contradictions among them beyond the minor Merge/Defer ordering gap above. The packet-only scope is honestly bounded: it states plainly that results apply only within this restricted runtime and that native validation needs separate authorization, which is the correct way to narrow scope rather than quietly generalizing a packet-only result.

Execution readiness is a separate, lower bar not yet met: the runner is unbuilt, and old-prompt adaptation fidelity has no verification step. Both are concrete, fixable prerequisites, not design flaws.

## Verdict

**Conceptually ready; not execution-ready.** No remaining high-severity contradictions in the plan itself. Before the first invocation: (1) build and pass the runner's offline acceptance tests as already specified in the document, and (2) verify/hash the old-prompt packet-only adaptation against the frozen plugin. With those two items done, this proposal is sound to run as a three-pair, nine-invocation, tool-free pilot.
