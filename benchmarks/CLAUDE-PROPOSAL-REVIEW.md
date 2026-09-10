# Claude review of the Skeptic proposal

Date: September 10, 2026. Model: claude-sonnet-5. One tool-free CLI invocation using subscription authentication; no benchmark trials or subagents. Input documents: SKEPTIC-PROPOSAL.md, ANALYSIS.md, ADJUDICATION.md. Raw prompt, events, invocation, and usage are in `WORK/proposal-review-2026-09-10/`. The proposal was reviewed as supplied; these are Claude's judgments, not newly verified benchmark findings.

---

# Review: Skeptic Revision Proposal & Evaluation Plan

## Findings

### High — Disposition taxonomy is underspecified
**Section:** Candidate instruction change
**Problem:** Five dispositions are listed (retain, narrow/correct, merge, defer, reject) but only "retain" and "reject" have unambiguous meaning. "Defer" is never defined operationally — does a deferred finding appear in the final report, get logged separately, or vanish? "Narrow/correct" bundles two distinct actions (scoping a claim down vs. fixing a factual error) that the evaluation plan later needs to count *separately* ("factual clauses removed, retained, or introduced" vs. "severity corrections").
**Consequence:** Without a fixed coding scheme, the same output could be adjudicated inconsistently across pilot runs, making "important defect incorrectly rejected" counts noisy before the Skeptic variant itself is even the variable being tested.
**Correction:** Define each disposition with one sentence and specify its downstream report treatment (included/excluded/logged-only) before running the pilot.

### High — No accounting mechanism for the stated budget risk
**Section:** Budget boundary
**Problem:** The document itself admits: "a cap on top-level trials is not a cap on model calls or subscription usage... this proposal does not yet implement that control." Yet conserving subscription allowance is the explicit motivation for pausing bulk runs (per ANALYSIS.md checkpoint).
**Consequence:** Because the native workflow can spawn subagents, a "small number of paired PRs" could consume an unpredictable multiple of intended usage — exactly the failure this whole review cycle is trying to avoid. This is a known, named gap, not a hidden one, which makes it worse to leave unresolved.
**Correction:** Before any pilot call, either (a) set a hard subagent call ceiling per trial, or (b) require a dry-run cost estimate from one paired PR before committing to the full pilot set.

### High — Adjudication process for the pilot is unspecified and may inherit the blind spot it's meant to catch
**Section:** Evaluation plan
**Problem:** The plan calls for "source-aware adjudication, not reference matching alone," but doesn't say who or what performs it. ADJUDICATION.md's own spot-checks show the *existing* semantic judge "sees the diff rather than all unchanged helper implementations" — which is precisely how the false "no logging" clause survived a PLAUSIBLE label in the current pipeline.
**Consequence:** If the pilot's adjudication reuses the same diff-limited judge (rather than the manual static checks used in ADJUDICATION.md), the evaluation may fail to detect the exact class of error (contradicted supporting clause) that motivated the whole proposal, producing false confidence that the new Skeptic "removed unsupported clauses" when it didn't.
**Consequence (secondary):** The manual-check approach used in ADJUDICATION.md doesn't scale and wasn't blinded or randomized — reusing it for the pilot means adjudication effort competes directly with the budget this proposal is trying to protect.
**Correction:** State explicitly whether pilot adjudication is manual (like ADJUDICATION.md), judge-based, or hybrid, and budget adjudicator time/calls as a first-class line item alongside review calls.

### Medium — No predefined pilot size or promotion/stopping criterion
**Section:** Budget boundary / Evaluation plan
**Problem:** "Agree on a small number of paired PRs" and "stop at the agreed boundary" defer the actual numbers to a later, unrecorded conversation. The plan correctly states a small pilot "cannot establish a reliable overall improvement rate" but never defines what *would* justify a second, larger pilot versus abandoning the change.
**Consequence:** Without a stopping/promotion rule, the pilot risks becoming open-ended iteration ("just one more paired PR to check") — the same failure mode (1,752-trial plan going unfinished) that produced the current paused state.
**Correction:** Fix pair count (e.g., 3–4 pairs) and a concrete promotion trigger (e.g., zero important defects lost, at least one factual clause correctly removed) before the first pilot call.

### Medium — Held-out PR pool may already be exhausted
**Section:** Examples from development observations / Evaluation plan
**Problem:** The instruction's worked examples are drawn from Cal.com (#14740) and Sentry (#77754) — the same two PRs already used for prompt development in ADJUDICATION.md. The evaluation plan correctly requires PRs "not used in these source checks or prompt development," but the corpus already touched (Cal.com, Discourse, Sentry, xorbitsai, haystack, Ansible, ccxt, plus SWE-PRBench cases) is large relative to the paused, budget-constrained benchmark set.
**Consequence:** The genuinely-unseen pool available for a fair pilot may be smaller than assumed, risking either accidental reuse or a pilot too small to be informative.
**Correction:** Enumerate the actual candidate held-out PRs by name before agreeing on pair count, to confirm enough clean ones exist.

### Medium — No false-negative measurement methodology
**Section:** Evaluation plan
**Problem:** The plan tracks "important supported defects... incorrectly rejected," but determining this requires an independent ground-truth pass on the *pre-Skeptic* Optimizer output per held-out PR — not currently budgeted or described as a separate step.
**Consequence:** Without this, false rejections can only be caught if they happen to match the reference set, reintroducing "reference-match precision is not factual precision" — the exact conflation ADJUDICATION.md warns against.
**Correction:** Add an explicit static/manual check of Optimizer-stage candidates for held-out PRs as a budgeted prerequisite, not an afterthought.

### Low — Evidence standard is judgment-heavy with no rubric
**Section:** Candidate instruction change
**Problem:** "A deterministic source proof can be enough; a full reproduction is not mandatory when the causal path is established" gives no criteria for what counts as "established."
**Consequence:** Inter-run variability in how conservatively the causal-path bar is applied could swing findings-count and factual-accuracy metrics independent of the intended verification improvement.
**Correction:** Add 2–3 worked pass/fail examples of "established causal path" directly in the prompt (the document already has good candidate material in ADJUDICATION.md's Sentry F3 conditional-bypass case).

### Low — Provenance leakage unmitigated
**Section:** Evaluation plan
**Problem:** Labels are hidden "where feasible," but the document itself acknowledges "prose may reveal provenance," and the new prompt's structured trigger/evidence/impact format is stylistically distinctive.
**Consequence:** Adjudicators could unconsciously favor the recognizable "new" format, inflating perceived improvement.
**Correction:** At minimum, have adjudicators guess-and-record which variant they think they're reading, to quantify leakage rather than assume it away.

## Counterargument worth noting
One could argue the proposal's repeated explicit caveats (non-authorization, "these are development examples," "cannot establish a reliable overall improvement rate") are themselves a strength — the document is unusually careful not to overclaim from n=6 spot-checks. The weaknesses above are mostly about *operationalizing* that caution (definitions, budgets, adjudication process), not about the document's epistemic honesty, which is good.

## Verdict
**Not yet ready for even a small pilot.** The document is analytically sound and appropriately humble about its tiny sample, but it authorizes no action and leaves three operational gaps that would undermine a pilot if run as written.

**Three changes required first:**
1. Define disposition semantics (especially "defer" and split "narrow" from "correct") with report-treatment rules.
2. Specify and budget the pilot adjudication process — manual static check vs. judge — so it can actually detect contradicted clauses, and add a subagent call ceiling to protect the stated budget goal.
3. Fix pair count, promotion/stop criteria, and confirm the held-out PR pool is genuinely unused, before scheduling any pilot calls.
