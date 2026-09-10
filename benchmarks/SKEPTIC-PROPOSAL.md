# Focused Skeptic proposal — revision 4, not applied or benchmarked

Seven scored native reviews on six PRs gained no reference coverage after the
Skeptic; findings increased from 75 to 83. Seven selected source checks on two
PRs found both useful observations and inaccurate clauses. These observations
motivate a hypothesis, not a proven general failure or a production change.
The frozen plugin and existing scores stay unchanged. This document does not
authorize a pilot. Bulk launches remain paused.

## Candidate instruction

For each candidate, identify its concrete trigger, causal path, and impact.
Check guards, callers, schemas, and relevant unchanged helpers before claiming
anything about validation, permissions, exception propagation, logging, retries,
or supported inputs. Verify supporting examples as well as the central defect.
Distinguish a conditional path from evidence that a supported input reaches it.
Never require proof that an incident already happened: a reachable deterministic
source defect can justify action before deployment.

Try to disprove each claim. Remove contradicted details even if its core concern
is supported. Missing evidence is not proof of safety. State unresolved conditions
explicitly; do not inflate severity with speculative downstream harm. Preserve
supported defects even if their runtime reproduction is unavailable.

Use exactly one disposition per input candidate, plus independent edit flags:

| Disposition | Definition | Final report treatment |
|---|---|---|
| Retain | Central defect or useful observation remains supported, with edits if needed. | Include in defects or nonblocking suggestions, according to impact. |
| Merge | Same root cause and corrective action as another retained candidate. | Include once under a stable target ID; preserve links from every input ID. |
| Defer | Material evidence is missing, so correctness or impact remains unresolved. | Put in an explicit unresolved appendix with the missing evidence; do not count as confirmed. |
| Reject | Central claim is contradicted, outside the PR change, or unsupported after investigation with no actionable unresolved question. | Exclude from actionable report; retain ID and reason in audit ledger. |

Assess evidence before merging. First narrow/correct any supported core claim;
keep material unresolved clauses explicit rather than hiding them in a merge.
A candidate whose central claim remains unresolved is deferred and cannot be
merged into a confirmed issue. Merge only supported claims sharing the root
cause and correction; preserve distinct supported triggers and input-ID mappings.

Edit flags are `scope_narrowed`, `factual_clause_corrected`, and `severity_changed`;
several may apply to a retained or merged claim. Record original and revised
clauses and severity separately. Narrowing a claim must not silently remove a
supported important trigger. A missing regression test normally belongs with
its defect, unless it demonstrates an independent problem. New independent
findings get new IDs and undergo the same evidence standard. No target finding
count or mandatory rejection rate applies.

Each ledger entry contains input ID, disposition, merge target if any, edit
flags, trigger, source references, impact, unresolved assumptions, and proposed
regression check. The report separates actionable defects, nonblocking
suggestions, and unresolved questions. Avoid repeating investigation transcripts.

### Evidence and impact rubric

A causal path is established when the input condition is permitted by the
inspected contract, control flow reaches the relevant operation, guards do not
prevent it, and the operation violates a stated invariant or user expectation.
Mark each unverified link unknown. Runtime observations strengthen this evidence
but are not mandatory. Distinguish supported, contradicted, and unresolved
individual factual clauses; mixed claims can contain more than one category.

For the pilot, important means a supported reachable risk to security, data
integrity, availability, or a core user operation. Minor means bounded incorrect
behavior with no established important impact. Cleanup means an improvement
without established behavioral failure. Unknown impact stays unknown; do not
force it into a severity category.

Development examples: Cal.com's logged provider failure supports a consistency
concern but contradicts “no logging”; remove that clause. Sentry's shared default
timestamp has a deterministic source mechanism, but no established important
consumer impact; retain narrowly and merge its regression-test suggestion. Its
malformed-metadata path skips a guard under a condition whose real producer was
not established; preserve that condition as unresolved instead of asserting an
observed deployment loop. These PRs are excluded from pilot selection.

## Exact scope: a controlled packet experiment

This is a proposed **three-PR, nine-invocation maximum** pilot, not a native-plugin
or end-to-end performance test. All calls are tool-free: the host supplies one
fixed source packet per PR. No subagents, tools, network, nested CLIs, autonomous
repository investigation, model-based judging, or normalization calls are allowed.
This restriction changes the runtime from the original benchmark. Any result
applies only to comparing prompts within this packet setting; native validation
would require a separately budgeted experiment.

The proposed PRs are recorded with source pins in `skeptic-pilot-selection.json`:

- Martian: `keycloak__keycloak-32918`.
- SWE-PRBench: `stylelint__9062`.
- c-CRAB: `python__mypy-6781@3a824fb`.

Selection used the lowest SHA256 of a fixed seed, benchmark, and case ID per
benchmark among cases with no run directory. There were 30, 335, and 167 such
candidates respectively on selection. This refutes assuming the pool is exhausted,
but does not prove lack of prior exposure. Before execution, check selected IDs
against development notes, excluded attempts, and available prompt/session
records; unresolved exposure means abort this selection, not silently substitute
a favorable PR. Record the audit and selection manifest hash before reading
pilot outputs. Existing benchmark references and oracle tests remain hidden
until all review outputs are frozen.

Prepare a source packet containing the frozen PR diff plus relevant unchanged
callers/helpers/contracts. The host curator must record inclusion decisions
before seeing candidate or variant outputs. Both variants and the one Optimizer
receive the identical source packet; no later packet additions within a pair.
A packet is limited to 120,000 characters and must fit the model context with
all prompts and outputs; if it cannot, abort without truncation or substitution.
Any dependency absent from the packet is an explicit evidence limitation.
This curated access is not a full-repository test.

For each PR, generate Optimizer candidates once (one invocation); freeze the raw
output and its hash. Then run old and revised Skeptic prompts against precisely
that output and packet (two invocations). The old prompt must be extracted from
the frozen plugin, with only shared packet/no-tools adaptations. Record the exact
old/new prompt files and hashes before the first invocation. The host author
must save the verbatim frozen old-prompt section, its source path and plugin
commit, the adapted prompt, and a unified diff. Classify every changed line as
a packet-access substitution or common runtime/output-format wrapper; preserve
old evidentiary thresholds, reasoning tasks, and substantive report requirements.
Record a signed-off checklist with those hashes. Any substantive deviation
blocks the comparison until corrected. This author-performed fidelity audit is
not independent validation, and hashes alone do not prove semantic equivalence.
Before the first pilot invocation, a second human reviewer must spot-check
the diff classifications and record approval or specific corrections. This
check adds no model calls; if that reviewer is unavailable, the pilot stays
blocked. It is a limited prompt-fidelity check, not independent validation of
the findings or the overall experiment. Keep model
`claude-sonnet-5`, effort high, context, per-call timeout and nominal CLI ceiling
identical. Alternate old/new order across the three PRs. Do not replace missing,
malformed, timed-out, or disappointing outputs with retries.

## Source-aware adjudication and false negatives

Use host-assistant static source adjudication, not the diff-only semantic judge.
It incurs no extra Claude CLI calls but does consume the host assistant's normal
allowance and analysis time; it is not independent human validation. Freeze a
pre-Skeptic ledger of every Optimizer candidate before inspecting either final
report, with clause support, impact, source evidence, and uncertainty. Inspect
unchanged source as needed; record where adjudication relied on code absent from
the source packet. Such cases diagnose packet limits, not necessarily reasoning
failures. Do not omit unresolved candidates from the ledger.

Then assess both final outputs, every rejected/deferred candidate, all merge
mappings, and any new candidate against the same source evidence. Normalize
variant labels to A/B for presentation; the host author cannot be truly blinded
and prose can reveal the revised prompt. Record inferred variant and confidence
before adjudication. This measures suspicion of leakage, not an objective leakage
rate. Present these pilot labels as author-performed static judgments. If the
adjudication cannot resolve a material dispute, mark unknown and block promotion.

Count retained important defects by underlying issue, preserving input-to-output
mappings. Deferring an established important defect is a loss from the actionable
report, even though its text survives in an appendix. Narrowing away its supported
trigger or merging away its only actionable evidence also counts as loss.
Record supported/contradicted/unresolved clauses before and after; distinguish
corrected false clauses from merely omitted supported ones. Record added false
clauses, severity changes, duplicates, report size, and completed/timed-out calls.
Do not infer factual precision from reference matches or word count. Report
triage time only if actually measured with a declared method.

## Budget enforcement and stopping rules

Before any pilot authorization, build and offline-test a dedicated runner that:

- Has a persistent ledger with exactly nine slots (three named PRs × Optimizer,
  old Skeptic, new Skeptic); atomically reserves a slot before subprocess launch.
- Serializes launches with a process lock, marks attempts durably, and refuses
  reuse after success, failure, timeout, or uncertain crash recovery. Cached
  completed outputs may be read without a call. No auto-retries or replacements.
- Uses the subscription-only CLI environment and tools disabled; each invocation
  has a 300-second wall timeout and a $2 nominal CLI computation ceiling, kills
  its process group on timeout, and preserves raw events and usage.
- Stops on subscription rejection or any call failure; does not continue to the
  next PR. Records incomplete pairs as incomplete, never empty successful reviews.

Nine invocations and $18 total nominal ceilings are upper bounds on scheduled
CLI work, not nine internal model requests or a guaranteed subscription fraction.
A tool-free CLI may internally retry or make additional model requests. Subscription
quota accounting is not exposed precisely enough to promise a hard quota cap.
A one-pair usage estimate consumes allowance and cannot enforce that cap. User
approval must cover these limits explicitly before pilot execution.

Offline acceptance tests must prove slot reuse/parallel launch rejection,
crash-before/after-launch handling, no tools or API-key fallback in argv/env,
timeout cleanup, and fail-stop behavior using a fake CLI. This runner is not yet
implemented; it is an explicit execution blocker, not a control claimed to exist.

Stop at three pairs at most, sooner on the first failure, quota rejection, or
adjudicated important-defect loss. Do not extend this pilot. Eligibility for
considering a separately authorized larger experiment requires all three pairs
completed and adjudicated, no established important defect lost by the new
variant, no new contradicted material clause introduced by it, and at least one
source-verified improvement over old (false-clause correction, preserved-evidence
merge, or justified severity correction). Any material unknown blocks eligibility.
If the sample offers no relevant improvement opportunity, report inconclusive.
Passing this gate is not evidence of general efficacy or permission to promote
the plugin. Failure leads to analysis and a new version/selection if warranted,
not retries on these PRs reported as held out.
