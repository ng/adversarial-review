# Run the adversarial-review experiment

Give Claude this document and say:

> Follow benchmarks/README.md. Resume the experiment, run every benchmark and all
> three configurations, validate the results, and regenerate benchmarks/RESULTS.md.
> Preserve failures and raw evidence. Do not publish PR comments or read reference
> answers while reviewing.

This harness runs the actual local plugin. It does not replace the Optimizer and
Skeptic with short imitation prompts. The plugin snapshot is frozen at bootstrap.
Native reviews produce normal Markdown artifacts first; a separate tool-free
call extracts their findings into the scoring schema. Structured-output mode is
not imposed on the native multi-agent review loop.

Track evidence and proposed PR-quality improvements in [NOTES.md](NOTES.md).

## Experiment

| Configuration | Review workflow |
|---|---|
| `single` | One Claude reviewer; no delegation |
| `adversarial` | Native plugin, `--no-fix --no-codex`; normal depth selection |
| `cross-provider` | Native plugin, `--no-fix --with-codex`; normal depth selection plus Codex sidecar |

The lead model and per-review ceilings are in [experiment.json](experiment.json).
The full `--codex-lane` was probed during setup: its required `gpt-5.4-mini`
model is unsupported with the current ChatGPT account. The cross-provider
configuration therefore uses the plugin's supported sidecar. This is recorded
as a protocol amendment before any successful cross-provider result.
The plugin selects its own reviewer models; the transcripts record the actual
models, subagent use, depth, and artifacts. A shared ceiling is **not** equal
actual token expenditure. Compare quality alongside observed cost and latency.
Run a separately configured, equal-token experiment before making claims about
efficiency at a precisely matched token budget.

| Dataset | Full scope | Evaluation |
|---|---:|---|
| [Martian](https://github.com/withmartian/code-review-benchmark) | 50 PRs | Strict/Core/All reference matching, precision/recall/F1 |
| [SWE-PRBench](https://github.com/FoundryHQ-AI/swe-prbench) | 350 PRs | Human issue coverage plus confirmed/plausible/fabricated labels |
| [c-CRAB](https://github.com/c-CRAB-Benchmark/dataset) | 184 Stage-4 PRs | Released executable review tests; fixed downstream repair agent |

All three configurations use identical frozen code and reference sets within a
case. Pilot order is deterministic from the seed and spans repositories. The
10-PR pilot is for harness validation, not prompt tuning. Full runs reuse completed
pilot reviews rather than paying for them again.

## Requirements

- Python 3.12+, uv, Git with Git LFS, authenticated Claude Code, authenticated Codex CLI.
- Docker running for c-CRAB; images use Linux/amd64 (emulation may be needed on Mac).
- Sufficient free disk space for repository snapshots and container images.
- Model access to the exact names in experiment.json and the pinned plugin.

The harness uses the signed-in CLIs; API keys are not required for its adapted
judge. Claude's `total_cost_usd` is recorded as reported API-equivalent cost,
**not a statement of subscription billing**. It does not include nested Codex
spend. Keep raw Codex lane transcripts and report missing cost data explicitly.
Reviewer, judge, and repair subprocesses explicitly omit API-key and third-party
provider environment settings so rerunning the document does not silently switch
to API-key billing. The `--max-budget-usd` value is a CLI computation ceiling
based on its nominal estimate, not permission to charge that amount.

Do not copy account credentials into benchmark containers. The c-CRAB adapter
runs its repair agent in a separate local checkout, then applies the resulting
patch in the test container after the agent has finished.

## Start or resume

Run commands from the plugin repository root. The default workspace is
`benchmarks/work/` (gitignored). The initial September 9 run uses
`/tmp/adversarial-review-benchmarks`; pass that path to resume it on this machine.
Use a durable directory for long-lived experiments.

```bash
python3 -m unittest discover -s benchmarks -p 'test_*.py' -v
python3 benchmarks/run.py bootstrap --work-root /tmp/adversarial-review-benchmarks
python3 benchmarks/run.py prepare --work-root /tmp/adversarial-review-benchmarks

# Pilot: ten PRs PER benchmark, all three configurations.
python3 benchmarks/run.py run --work-root /tmp/adversarial-review-benchmarks --limit 10 --workers 2
python3 benchmarks/score.py --work-root /tmp/adversarial-review-benchmarks --limit 10 --workers 2
uv run --no-project --with packaging==26.3 python benchmarks/ccrab.py --work-root /tmp/adversarial-review-benchmarks --limit 10 --workers 1
python3 benchmarks/run.py report --work-root /tmp/adversarial-review-benchmarks

# Full datasets: no --limit. Successful reviews resume automatically.
python3 benchmarks/run.py run --work-root /tmp/adversarial-review-benchmarks --workers 2
python3 benchmarks/score.py --work-root /tmp/adversarial-review-benchmarks --workers 2
uv run --no-project --with packaging==26.3 python benchmarks/ccrab.py --work-root /tmp/adversarial-review-benchmarks --workers 1
python3 benchmarks/run.py report --work-root /tmp/adversarial-review-benchmarks
```

Use `--benchmark martian`, `--benchmark swe-prbench`, or `--benchmark c-crab` on
`run.py run` to run one dataset. Use `--variant single`, `--variant adversarial`,
or `--variant cross-provider` to run one configuration. Scoring automatically
uses only successful reviews. A failed or missing review is never scored as an
empty successful review. Inspect errors, fix execution problems, and rerun the
same command. Do not run overlapping commands on the same case/configuration.

If Docker stalls in `docker-credential-desktop get` while pulling public images,
use a separate empty Docker configuration for public pulls:

```bash
mkdir -p /tmp/adversarial-review-benchmarks/docker-config
uv run --no-project --with packaging==26.3 python benchmarks/ccrab.py --work-root /tmp/adversarial-review-benchmarks \
  --docker-config /tmp/adversarial-review-benchmarks/docker-config
```

Do not delete unrelated Docker images or change the user's global Docker config.
Each test container created by the harness is removed when its evaluation ends.

## What is frozen and hidden

The checked-in `source-lock.json` pins the benchmark and dataset commits;
bootstrap checks out those exact revisions even if upstream branches advance.
`WORK/lock.json` records those source repository SHAs, the plugin commit and file hashes,
experiment settings, and CLI versions. `cases.json` records the exact base/head
SHAs and input hashes. `martian-pr-lock.json` freezes the 50 Martian PR metadata
records as collected during initial curation. Fresh runs use that manifest rather
than re-querying mutable PR heads. No GitHub review comments are fetched.

Each reviewer gets a dedicated clone containing the frozen code. Reference
comments, judge outputs, later fixes, and other configurations' artifacts remain
outside that checkout. Remote URLs are removed. The prompt explicitly disables
PR feedback import, memory/config import, network, source fixes, publication, and
access to sibling workspaces. Common network/publication tools are denied.

On macOS the harness also applies inherited Seatbelt restrictions to deny file
contents in reference-data and sibling-case directories, allowing the current
checkout, its frozen Git objects, and the pinned plugin. File metadata and CLI
runtime/authentication paths remain available. This is not a complete host or
network sandbox for actively malicious reviewers. Audit transcripts for forbidden
access before accepting results; earlier pilot invocations predate these rules. Source mutations and missing native
reviewer artifacts already cause the harness to reject a run.

Preparation resolves each PR's dataset base/head merge base in an isolated
history checkout. For c-CRAB and SWE-PRBench it also verifies the diff against the
released patch by applying it to a temporary Git index and requiring exact head
tree equality. For binary files whose released patch omits the payload, the
harness checks the same path and file operation and supplies the binary payload
from the pinned head. Shallow history is deepened until the scope validates. Only the resolved base and head enter
the reviewer snapshot. Cached scope metadata records both original and resolved
SHAs. A mismatch fails preparation before review. Reviewers use `git diff BASE HEAD`
with the already-resolved base; they do not infer ancestry from shallow history.
No dependencies are installed by reviewers; missing checks must be reported as
environment limitations, not defects. This can affect the plugin's depth gate.

## Scoring and limits on comparisons

The CLI judge sees anonymized candidate bodies, the diff, and reference findings.
It never sees the producing model, workflow, or before/after label. Identical
findings share an opaque hash; semantically duplicate findings are grouped.
Each judge response must account for every candidate and use valid reference IDs.
Incomplete or inconsistent judge output fails scoring rather than receiving
optimistic fallback labels.

Martian uses its published issue-matching criterion and scoring categories.
SWE-PRBench uses its CONFIRMED/PLAUSIBLE/FABRICATED distinction. This harness
**batches** matching and labeling through a signed-in CLI. It is an adapted
evaluation, not a verbatim run of either official API-based judge. SWE reviewers
also have full repository access instead of being limited to the published A/B/C
rendered contexts. Do not compare these numbers directly with published
leaderboards or label the SWE results as official A/B/C scores.

c-CRAB uses released tests and container images, with a fixed host-based repair
agent. This differs from the publication's in-container repair invocation.
Report the exact resolver model and image digests. Tests are supplied only after
the repair agent finishes. Check the test fails for the expected assertion at
the reviewed head before attributing a later pass to review usefulness.

Measure before/after reference coverage, unmatched candidates, and fabricated
candidates. Report gold issues lost and gained after the Skeptic. A reference
match is not independent proof of correctness, and an unmatched issue is not
automatically wrong. Manually inspect a sample of unmatched and rejected
findings, record decisions and code evidence in `ADJUDICATION.md`, and keep those
decisions separate from the frozen automatic scores.

## Evidence and completion checks

```text
WORK/lock.json                         Frozen sources and settings
WORK/cases.json                        Full case manifest, including hidden references
WORK/snapshots/                        Frozen source repositories
WORK/review-workspaces/                Separate native reviewer checkouts
WORK/runs/BENCH/CASE/VARIANT/
  status.json                         Complete/failed/running, with error if any
  prompt.txt                          Exact reviewer prompt
  events.jsonl                        CLI transcript, tool calls, model usage
  usage.json                          Latency and reported cost
  response.json                       Final and pre-Skeptic findings
  artifacts/                          Native Optimizer/Skeptic/summary reports
  score.json                          Validated evaluation
  execution/                          c-CRAB patch, image digest, test outputs
WORK/judges/                          Blind judge prompts, responses, errors
```

Before calling the experiment finished:

1. Verify 50 + 350 + 184 cases, each with all three configurations: **1,752 reviews**.
2. Verify every review completed with the required native lanes and no source
   changes or reference-answer access. Inspect actual model/depth/permission data.
3. Verify every successful review is scored; distinguish environment failures
   from benchmark failures. Do not silently drop cases to improve scores.
4. Compare configurations on the same completed cases and disclose missingness.
5. Check the report includes Skeptic effects, quality, cost coverage, latency,
   manual adjudication, limitations, reproduction commands, and source pins.
6. Regenerate `RESULTS.md` from the current artifacts. Never fill in estimated or
   published numbers as measured results. Keep incomplete status if work remains.

### Subscription limits and resuming

A verified primary subscription-window rejection creates
`WORK/subscription-pause.json` with the provider's reset timestamp (or a minimum
five-minute cooldown). New CLI calls pause while that timestamp is in the future;
rerun the same commands after it expires. Disabled overage alone does not pause
an otherwise allowed subscription request. No API-key fallback is attempted.
Already completed reviews are preserved. Invalid judge responses are archived
under their judgment's `rejected/` directory before retrying; validation never
silently substitutes missing labels.

### Scope preflight

Run `python3 benchmarks/prepare_scopes.py --work-root WORK --workers 4` to resolve
all 584 comparison scopes before model evaluation. `WORK/scope-audit/` contains a
per-case result; investigate failed scopes rather than scoring a different diff.
The review runner performs the same check lazily if it has not been precomputed.
Earlier direct-endpoint pilots with unrelated branch drift are excluded and
retained under `WORK/excluded-pilots/`.
