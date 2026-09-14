# Prompt-first reviewer evaluation

The goal is a better adversarial reviewer, not a new review execution platform.
Run the actual plugin with its normal agent tools on benchmark PRs. Compare
original and candidate prompt snapshots on the same cases and model settings;
score output using the existing suite adapters. Preserve raw reviews and cost.

The user has offered macOS/Docker execution. Continue using
[MAC-HANDOFF.md](MAC-HANDOFF.md); this session still runs on Linux and has no
connection to that machine. Do not retry local namespace setup or revive the
retired harness while waiting for the environment switch.

## Cleanup, 2026-09-14

Removed the experimental `benchmarks/pilot/` tree, five top-level `pilot_*.py`
modules, their fixtures and 48 dependent test files from the active repository.
They are recoverable under:
`/workspaces/adversarial-review-retired-harness-VoRFfa/benchmarks/`.
This is retirement, not destruction of evidence. Existing raw model artifacts
and ledger remain at `/workspaces/adversarial-review-pilot-20260912`.
Do not resume retired stages. The last navigation study completed Optimizer and
Skeptic; synthesis was deliberately left unused after the user changed direction.
Frozen integrity tools can be recovered from the archive if historical auditing
is necessary; they are no longer an active development requirement.

Kept the original native runner, dataset locks/preparation, suite scorers and
`test_harness.py`; retained prompt edits and the separately requested summary,
merge-risk and comment-update code/tests. Unrelated `.serena/` changes were untouched.

## What the investigation taught us

- Source access alone did not fix review judgment. With ten successful lookups,
  the Optimizer still overstated a line-ending concern without consumer impact.
- Its scripts inspected dictionary mutation but missed the concrete repeat-call
  deserialization failure. The Skeptic noticed mutation but did not establish
  that exact failure either.
- The Skeptic identified a potentially harmful merged-cell deduplication fix,
  but otherwise repeated unsupported impact claims. Agreement is not validation.
- Isolated scripts and passing harness tests are not evidence of better review
  accuracy. These exposed development cases cannot support a promotion claim.

## Next experiment

1. Use a fixed, recorded sample across Martian, SWE-PRBench and c-CRAB. Disclose
   previously examined cases; keep development examples separate from evaluation.
2. Freeze original and candidate plugin prompt snapshots before running either.
   Use the same exact available model, cases, tools and budgets for both. No
   per-case hints or reference findings in reviewer inputs.
3. Run native reviews with the existing runner. Use its existing report extraction
   and scoring; record infrastructure failures separately from empty reviews.
4. Compare important defects retained/lost, unsupported findings, severity, harmful
   suggested fixes, cost and latency. Inspect unmatched findings against source;
   reference matching alone is not correctness proof.
5. Keep only prompt changes with demonstrated benefits and no unexplained loss of
   important findings. Report inconclusive results without tuning on the test set.

Martian and SWE-PRBench primarily require review/issue matching, not simply running
the projects' unit tests. c-CRAB additionally supplies executable tests for assessing
review-guided repairs. The existing adapters implement these different evaluations;
their documented deviations from official scoring remain applicable.

Before new model calls: the original runner's macOS-only isolation must be resolved
using a supported environment, and its historical model configuration must be
checked against current access. Do not launch the 1,752-review historical full run
as the first prompt-comparison experiment. Start with the declared fixed sample.

## Compatibility check and comparison boundaries (2026-09-14)

Verified locally: Linux; Claude Code 2.1.270 is installed; neither Docker nor
Podman is on PATH and `/var/run/docker.sock` is absent. Bubblewrap is installed,
but a minimal read-only `/usr/bin/true` invocation fails because this container
does not permit creation of the required namespace. No host security settings
were changed. Claude's [built-in Bash sandbox](https://code.claude.com/docs/en/sandboxing)
also uses bubblewrap on Linux; it is not an immediately available substitute for
the runner's macOS process-tree isolation here. Bash-only isolation would also
need an explicit assessment before claiming equivalent protection of reference
files from other tools. No benchmark model call was launched during this check.

Baseline prompt source is the current committed tree at
`d170f2de668f11921b7de63d6307dfe7553e103a`; the candidate is the working-tree
evidence-relevance and synthesis changes. The comparison must hold publishing
instructions constant (and publication disabled) rather than count merge-risk or
comment-update changes as evidence-prompt improvements. Current experiment.json
is historical configuration, not a newly frozen matched experiment. Runtime,
sample, exact model availability and both prompt snapshots still need to be
settled before launch. Do not label this document a completed benchmark.
