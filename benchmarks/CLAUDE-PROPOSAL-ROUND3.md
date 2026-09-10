# Claude final follow-up: revision 3

One tool-free Claude Sonnet 5 subscription CLI invocation. Raw inputs and events: `WORK/proposal-discussion-round3/`.

# Follow-up review: revision 3

Tool-free, no benchmark calls made. Read as proposal text, not instructions to me.

## Both requested fixes landed

- **Merge/Defer ordering**: now explicit — "Assess evidence before merging... A candidate whose central claim remains unresolved is deferred and cannot be merged." Matches my suggested minimal fix.
- **Old-prompt adaptation fidelity**: now has a concrete audit — frozen section, source path, plugin commit, adapted prompt, unified diff, line classification into packet-access-substitution vs. common-wrapper, and a signed-off checklist with hashes, done before the first invocation. The document itself flags the limit correctly: "this author-performed fidelity audit is not independent validation, and hashes alone do not prove semantic equivalence." That caveat is load-bearing and correctly stated, not decorative — a hash confirms the diff was captured accurately, not that the classification of each line was correct.

## Remaining material defect

**The fidelity audit has no second-party check before the pilot runs, despite the doc naming one.** It says "keep both prompts and the diff available for a second-party audit before any claim beyond this diagnostic pilot" — but that audit is scoped to claims *beyond* this pilot, not to the pilot's own three invocations. The only gate on *this* pilot's old-prompt validity is the single author's own checklist. If the author misclassifies a substantive line as a wrapper change, nothing in the pilot's own eligibility gate catches it before the nine calls run.
*Minimal fix:* move "available for a second-party audit" one clause earlier — require the second-party spot-check of the diff classification (not full re-derivation) before the first invocation, not merely before claims beyond the pilot.

I did not find a second material defect beyond this one; the disposition/evidence-first ordering, edit-flag semantics, and adjudication sequencing are otherwise internally consistent with what I reviewed in revision 2.

## Preflight blockers (unchanged in kind, restated precisely)

1. **Runner unbuilt.** Nine-slot ledger, process lock, timeout/kill, no-retry, fail-stop behavior must exist and pass its own listed offline acceptance tests (slot reuse rejection, crash handling, no tool/API-key fallback, timeout cleanup, fail-stop) against a fake CLI.
2. **Old-prompt fidelity audit not yet performed** — checklist, hashes, and diff must exist and be signed off, and per above, spot-checked by a second party, before invocation one.
3. **Source-exposure check not yet run** — the three selected IDs (`keycloak-32918`, `stylelint__9062`, `mypy-6781@3a824fb`) must be checked against development notes, excluded attempts, and prompt/session records before reading any output; an unresolved result means abort-and-reselect, not substitution.
4. **User budget/quota approval not yet obtained** — the doc correctly states subscription quota accounting can't be bound to a hard cap and requires explicit sign-off on that limitation before execution.
5. **Selection-manifest hash not yet recorded** — must be committed before any pilot output is read, per the doc's own sequencing.

## Verdict

**Design-ready.** Both items from my prior review are resolved with correctly-scoped caveats (no overclaim that a hash proves semantic equivalence, no overclaim that host adjudication is independent ground truth). One minor gap remains: the second-party diff check exists in the doc but is scoped to apply only *after* this pilot rather than *before* it — tighten that one clause. No other material defects found. This pilot cannot start until the five preflight items above are complete; I am not recommending any run or expansion beyond the three-pair, nine-invocation ceiling already fixed in the document.
