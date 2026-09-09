# Running PR-quality improvement notes

This log separates observed evidence from hypotheses. The experiment is still in
its pilot; the observations below are dated by their evidence rather than meant
as a live completion counter (see RESULTS.md). Do not tune the pinned reviewer on these cases and then
report the same cases as an untouched evaluation set.

## Review-quality observations

### 0. First paired case: the Skeptic increased volume without increasing reference coverage

**Observed on `calcom__cal.com-14740`:**

| Stage | Findings | Matched reference issues | Core reference-match precision |
|---|---:|---:|---:|
| Single-pass baseline | 2 | 3/6 | 100% |
| Native Optimizer | 9 | 3/6 | 33.3% |
| Native final after Skeptic | 12 | 3/6 | 25% |

The native review really spawned and completed two subagents and produced
Optimizer, Skeptic, and summary artifacts. The Skeptic rejected no candidates
and added three. The shared judge labeled all nine unmatched final findings
PLAUSIBLE, with zero FABRICATED labels. The baseline and native review caught
partly different reference issues despite matching the same count.

**Hypothesis:** The Skeptic may act as another issue collector unless its remit
includes a clear reporting threshold. Compare unsupported assumptions, severity
inflation, and low-value nits before proposing a stricter acceptance gate.
Do not equate unmatched with wrong: manually adjudicate these additional findings.

**Resource observation:** This pilot's native review took 1,024 seconds versus
219 seconds for the baseline. Command-permission friction affected the pilot;
repeat latency comparisons under the finalized harness before attributing all
overhead to adversarial review itself.

**Evidence:** `WORK/runs/martian/calcom__cal.com-14740/{single,adversarial}/score.json`,
the native `usage.json`, and its `artifacts/{optimizer-merged,skeptic-merged,summary}.md`.

### 1. Classify reference issues before interpreting recall

**Observed:** SWE-PRBench `server__8570` has four reference comments about message
punctuation, the name “current” versus “remaining,” explanatory comments, and
renaming tests. The single-pass reviewer produced no findings, giving 0/4
reference coverage. This does not establish that it missed four correctness bugs.

**Improvement to evaluation:** Report correctness/security findings separately
from editorial, naming, and rationale requests. Keep the original benchmark
score, with an additional clearly labeled breakdown. Do not change the reference
set after seeing a model's output to improve its score.

**Potential PR practice:** Explain surprising bounds and buffer-resizing choices
in code comments or the PR description; keep unrelated test renames separate.

**Evidence:** `WORK/cases.json` (`swe-prbench/server__8570`),
`WORK/runs/swe-prbench/server__8570/single/{response,score}.json`.

### 2. Optional-dependency hypothesis — initial evidence excluded

**Validity correction:** This observation came from an excluded pilot whose diff
included unrelated base-branch drift. It is retained as a hypothesis, not scored
evidence; the corrected-scope rerun must be evaluated before drawing conclusions.

**Originally observed:** On c-CRAB `xorbitsai__inference-2079@5ae18b2`, the single-pass
reviewer reported four other concerns but missed the retained reference issue:
a new top-level `from transformers import AutoTokenizer` import in
`xinference/model/llm/vllm/core.py`, despite `transformers` being optional.
The released test still failed after applying the review's suggested fixes.

**Hypothesis:** A dependency-change pass would improve recall: inspect new
imports, optional extras, platform guards, and deferred imports before moving
deeply into the implementation. Confirm on held-out PRs, not just this example.

**Potential PR practice:** Test importing the package with only its minimum
dependencies installed. Keep optional-backend imports inside the feature boundary.

**Evidence:** `WORK/runs/c-crab/xorbitsai__inference-2079@5ae18b2/single/execution/`
previously contained the baseline oracle output, applied patch, and final test output.
Those attempts are now archived under `WORK/excluded-pilots/c-crab-direct-endpoints/`.
Its `response.json` contains the four reported concerns; those are not yet
independently adjudicated as true or false.

### 3. Local conventions helped the baseline catch authorization and email issues

**Observed:** On Martian `calcom__cal.com-14740`, two single-pass findings matched
three of six Core reference issues: authorization composition and email
normalization. The report explicitly traced the permission helpers and compared
email handling against another implementation in the repository.

**Hypothesis:** Asking reviewers to compare changed code against nearby callers
and existing implementations may improve precision. Measure which concrete
evidence each accepted finding used before turning this into a general claim.

**Potential PR practice:** Add a role matrix for permission changes, plus mixed-case
email tests for blacklist checks and attendee deduplication.

**Evidence:** `WORK/runs/martian/calcom__cal.com-14740/single/{response,score}.json`.
Core result: precision 100%, reference recall 50%, F1 66.7%, on one PR only.

### 4. Watch for multiple issues bundled into one finding

**Observed:** The Cal.com email finding describes both blacklist bypass and
duplicate attendee creation. The judge maps it to multiple reference comments.

**Hypothesis:** Splitting independent triggers into discrete findings will improve
Skeptic verdict tracking and make each requested fix easier to review. Measure
duplicate/compound rates alongside precision, so formatting changes cannot
artificially improve the score.

### 5. Preserve missing confidence rather than filling in a number

**Observed:** The first completed Cal.com cross-provider extraction assigned a
placeholder confidence of 50 to five Skeptic additions that had no numeric
confidence in the Markdown. This changes the meaning of the source report even
though reference-match scoring does not use that field.

**Harness improvement:** Permit `null` and require it for absent confidence.
Keep raw reports authoritative; do not analyze confidence thresholds until the
normalized data has been audited for invented values.

**Evidence:** `WORK/runs/martian/calcom__cal.com-14740/cross-provider/response.json`
and the corresponding `artifacts/summary.md`.

## Harness and runtime observations

- **c-CRAB comparison scope:** upstream `run_batch_baselines.py` explicitly uses
  `merge-base(base_commit, head_commit)`. The initial direct-endpoint pilot
  included unrelated branch drift. All three configurations' attempts were
  excluded and archived before retrying. The harness now resolves the merge base
  outside reviewer access and requires its stable Git patch ID to match the
  released `patch_to_review`. First case resolved to
  `54c418e745992a8623596577dc466d2b12f7bc15`; patch equivalence passed.

- **Judge identifier fidelity:** the first three-way Cal.com judge returned 62
  labels for 62 candidates but mistyped one opaque ID by one digit. Validation
  rejected the complete score. Candidate and duplicate IDs are now constrained
  to supplied IDs in the output schema; invalid cached judgments are archived
  and can be retried. This is a formatting failure, not a reviewer-quality result.

- **Frozen-context enforcement:** the Keycloak single-pass pilot attempted a
  filesystem-wide source search. Exclude that attempt and rerun with filesystem
  restrictions. The harness now applies inherited macOS Seatbelt rules denying
  reference-data and sibling-case contents while retaining the current checkout,
  its shared Git objects, and the frozen plugin. Runtime metadata must remain
  readable so subscription CLIs can initialize; CLI startup itself is a required
  preflight. This is evaluation validity work, not evidence of a review defect.

- **Frozen checkout:** shallow local clones initially omitted the base commit.
  Fixed by explicitly fetching the local base ref. A regression test now checks
  the complete base/head diff and absence of a remote URL.
- **Artifact permissions:** the initial path-scoped Write rule was rejected by
  the installed CLI. The corrected harness permits report writes and audits
  tracked source changes. Those failed pilot attempts are not review-quality
  results. Subsequent retries archive prior transcripts.
- **Codex model access:** the full native lane's `gpt-5.4-mini` returned an
  unsupported-model error under ChatGPT authentication. The experiment uses the
  plugin's supported `--with-codex` sidecar with `gpt-5.5`. The amendment precedes
  any successful cross-provider result.
- **Codex executable permissions:** an initial command allowlist blocked even
  `codex --version`, causing a Claude-only fallback. A requested cross-provider
  run must fail validation if Codex artifacts are absent. The corrected harness
  allows local shell execution while denying common publication/network tools.
- **c-CRAB test membership:** the released archive has 458 successful earlier-stage
  tests for the 184 final PRs. Exact matching to retained Stage-4 reference comments
  selects the intended **234** tests. Scoring all 458 would change the benchmark.
- **Runtime dependencies:** c-CRAB's execution imports require `packaging` even
  when only using the runtime/test helpers. The runbook pins `packaging==26.3`
  through uv, avoiding installation of the full upstream research environment.
- **Waiting for subagents:** a Cal.com adversarial pilot successfully spawned an
  Optimizer but then called `ScheduleWakeup` with a `noop` field and no required
  `prompt`, producing an error. Minimal anonymous and named/background delegation
  probes both succeeded. This is wait orchestration overhead, not evidence that
  the reviewer cannot delegate. The finalized harness exposes review/agent tools
  without scheduling and notification tools; future invocations record exact
  CLI arguments and a runner hash for reproducibility.
- **Premature successful exit:** a Cal.com cross-provider attempt returned CLI
  `subtype=success` with one completed Claude Optimizer and a still-running Codex
  Optimizer, but no Skeptic wave. Its own final notes said structured output had
  interrupted the pipeline; the transcript shows the Codex task was stopped at
  exit. The harness rejected the result. The suspected formatting interaction is
  being addressed by running the native Markdown workflow without `--json-schema`,
  then extracting JSON in a separate tool-free call. Validate that change with a
  completed three-way pilot; a schema-valid response alone never proves the
  review protocol finished.
- **Docker startup:** a hanging `docker-credential-desktop get` blocked public
  image pulls. An isolated empty Docker config fixed this without changing
  global settings or copying credentials into containers.
- **Subscription accounting:** both CLIs use subscription logins. CLI dollar
  estimates are retained only as metadata; the report foregrounds tokens and
  latency. They are not billing receipts. The Claude preflight reported
  `isUsingOverage: false` and `overageDisabledReason: org_level_disabled`.

## Questions to answer as paired results arrive

1. How many matched real issues does the Skeptic discard, and why?
2. How many factually wrong findings does it remove, separate from unmatched
   but plausible findings?
3. Does the cross-provider pass add unique correctness/security findings?
4. Does a severity or confidence threshold suppress actionable conditional bugs?
5. Are missing dependencies being confused with failing product checks or used
   to escalate depth unnecessarily?
6. Do native subagents actually run, and do their verdicts cite command evidence?
7. Which accepted findings translate into passing c-CRAB tests, and which fail
   because of incomplete advice versus repair-agent behavior?

Record future observations with a case ID, configuration, artifact path, observed
behavior, proposed change, and a held-out validation criterion. Keep proposed
reviewer changes separate from the frozen experiment until the baseline finishes.

## First three-way paired score (preliminary)

The shared judgment for Cal.com matched 2/6 reference issues for single-pass,
3/6 for Claude adversarial, and 5/6 for cross-provider. Final reference-match
precision was 100%, 25%, and 22.7%, respectively (2, 12, and 22 unique findings).
The judge labeled all unmatched findings PLAUSIBLE, not FABRICATED. The cross-provider
Skeptic removed one unmatched candidate and added five, with no increase in matched
reference coverage between its Optimizer and final stages.

The single-pass result changed from 3/6 in the earlier two-way judgment to 2/6 in
this shared three-way judgment. This illustrates judge variability/context effects;
retain both raw judgments and use a common judgment for paired comparisons. One
PR cannot establish statistical significance or general superiority.

Evidence: `WORK/runs/martian/calcom__cal.com-14740/*/score.json`, shared judge hash
`616bed9def56a9e5` (invalid first response archived under `rejected/`).

Scope audit follow-up: SWE-PRBench `operator__3197` also had endpoint drift (13
files rather than the released patch's 3). Its attempts are excluded. The scope
preflight now covers all 584 PRs. Cal.com `calcom__cal.com-14740` resolves to the
same base used in its pilot, so its three-way comparison is unaffected.

Harness handling error: an audit cleanup briefly moved the active corrected c-CRAB
checkout. Its transcript recorded missing-file and cwd-recovery errors. That
single-pass attempt is excluded and will be rerun; it is not reviewer evidence.
Future invalidation must compare the snapshot ref itself and require no live
review process before moving any workspace.

Scope-validation refinement: some released diffs omit binary payloads, and the
first shallow merge base for `scipy__scipy-13893@4fcbd8b` was incomplete. Deeper
history resolves the intended base. Validation now applies text changes to a
separate Git index and compares the full resulting tree to head; binary payloads
omitted by the release come from the pinned head after checking file operations.
This distinguishes formatting/binary omissions from real scope mismatches.

Nested-sandbox observation: the restricted Codex CLI started successfully but
could not run shell tools (`sandbox_apply: Operation not permitted`). An actual
nonce-file read succeeded when Codex relied on the inherited outer sandbox.
The cross-provider prompt now explicitly overrides the plugin's inner read-only
sandbox flag while keeping the outer Seatbelt restrictions. Probe artifacts:
`WORK/probe/{protected-codex-shell,codex-outer-sandbox}/events.jsonl`.

Completed scope audit: all 584 cases validated. An additional GitHub compare check
independently confirmed all 50 Martian merge bases. Exact comparison bases and
input hashes are preserved in `comparison-base-lock.json` for repeat runs.

Source spot-checks of three unmatched Cal.com findings are recorded in
[ADJUDICATION.md](ADJUDICATION.md). They are assistant static checks, not blinded
human evaluation. They support separating factual validity from reference match
and from whether an issue should block the PR.

Corrected c-CRAB baseline: the clean rerun of
`xorbitsai__inference-2079@5ae18b2` reported two concerns (InternVL prompt-role
formatting and single-image token accounting). The downstream repair still passed
0/1 retained executable tests. This is current valid evidence; earlier drifted
and interrupted attempts remain excluded. The two extra findings have not been
independently adjudicated. Evidence: current `WORK/runs/c-crab/` case's
`single/{response,score}.json` and `single/execution/` artifacts.

Judge masking limitation: explicit configuration/stage labels are withheld, but
some finding bodies mention Sonnet, Codex, or Skeptics. Bodies are preserved for
fidelity, so this is partial masking, not complete blinding. The runbook now
states this directly. A future held-out evaluation should measure whether
removing provenance language changes judgments without changing issue content.

First corrected c-CRAB two-way result: both single-pass (2 final findings) and
Claude adversarial (15 Optimizer candidates, 16 final findings) yielded 0/1
retained tests passing after the same downstream repair setup. The native review
completed two independent subagents at standard depth in 890 seconds, excluding
normalization and execution scoring. Neither final report mentioned the retained
AutoTokenizer import issue. Additional finding volume did not improve this
case's executable coverage; this does not establish that the extra findings are
false. Cross-provider scoring is still pending.

Budget outcome: the protected Claude adversarial review of
`martian/ai-code-review-evaluation__discourse-graphite-10` hit the declared
1,800-second cap while finishing its artifacts. Preserve this as a terminal
review-budget failure; partial output is excluded from quality metrics. Do not
retry clean budget failures until a favorable outcome appears. This keeps the
full 1,752-trial scope while distinguishing model-budget outcomes from repairable
setup errors. Cross-provider and single-pass results remain separately recorded.

## Passing executable example: preserve non-boolean parameters

On `c-crab/ansible__ansible-20646@f695114`, the single-pass baseline reported one
finding: a change intended to preserve False-valued booleans also filtered out
ordinary string/dict parameters. The downstream repair changed the condition to
check for `is not None`; the retained test passed (1/1). This validates that
specific repair outcome, not the entire module or the reviewer generally.

Potential PR practice: when changing truthiness/filter logic, test a value matrix
including None, False, True, zero, a nonempty string, and a dict, then trace which
values reach the downstream API. Evidence: the case's current
`single/{response,score}.json` and `single/execution/fix.patch`.

Confidence-data limitation: this baseline emitted 0.9 while native reports often
emit values such as 90. The schema did not declare a common unit. Do not compare
raw confidence numerically or claim calibrated thresholds from this run without
an explicit unit audit. Current reference/test metrics do not use confidence.

Timeout-stage evidence for Discourse: the Claude-only run started at 09:55 UTC.
Its merged Optimizer artifact became available at 10:09:26, the last independent
Skeptic report at 10:22:50, and the merged Skeptic report at 10:24:22. The 10:25
cap arrived before summary completion. Individual reviewer artifacts were
17–33 KB. These timestamps include investigation and writing; they do not prove
that prose generation was the primary bottleneck.

Held-out hypothesis: a more compact evidence/report format could reserve time
for synthesis within the same review cap. Measure completion rate and retained
issue coverage together; do not optimize only for shorter reports. Raw evidence
remains in the failed case's `.reviews/benchmark/` workspace and transcript.

Discourse cross-provider execution completed at full depth: four Claude subagents
and both Codex passes produced artifacts; native elapsed time was 1,625 seconds,
followed by separate normalization. It reported 27 Optimizer candidates and 27
final findings. The Claude-only run of the same case reached the 1,800-second cap.
This single outcome does not establish a provider speed advantage; scoring is
pending and investigation paths vary between independent runs.

A fourth source spot-check in ADJUDICATION.md found mixed factual support in
Cal.com F3: the data-consistency concern is supported, but the Skeptic summary's
“no logging” claim is contradicted by CalendarManager's error logs. Issue-level
reference matching and PLAUSIBLE labels can miss false supporting clauses,
especially when unchanged helper code is absent from the judge's diff context.

Discourse shared score: cross-provider matched all 7/7 Core reference issues with
27 final findings (25.9% reference-match precision); single-pass matched 4/7 with
5 findings (80% reference-match precision). Cross-provider already matched 7/7
in its Optimizer stage; its final count stayed 27 after one unmatched removal
and an addition. Unmatched candidates were labeled PLAUSIBLE by the limited-
context judge, which is not independent proof of correctness. The Claude-only
budget failure excludes this PR from the three-way successful-case table, while
these two successful configurations remain directly comparable on this case.
Evidence: `WORK/runs/martian/ai-code-review-evaluation__discourse-graphite-10/`
`{single,cross-provider}/score.json`.
