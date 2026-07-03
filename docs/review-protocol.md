# Adversarial Review Protocol

This document is the **normative specification** for the cross-provider adversarial
review protocol. The runtime skill files (`claude/skills/run/SKILL.md` for Claude
Code, `skills/codex-review/SKILL.md` for Codex) embed copies of these definitions
where subagent prompts need them inline — an agent prompt must be self-contained,
so full deduplication at runtime is deliberately not a goal. **When changing any
shared definition, edit this document first, then sync the embedded copies.**

The design premise: the interoperability layer between AI providers is **files,
not APIs**. Any provider whose CLI can follow a prompt and write markdown can join
a review as a lane. Orchestration stays provider-specific (each harness has its own
subagent and background-task machinery); the artifacts, schemas, and preamble
contract below are provider-neutral.

## Terms

| Term | Meaning |
|------|---------|
| **Lead** | The orchestrating agent (one per run). Owns context gathering, mechanical checks, depth computation, merging, synthesis, auto-fix, and PR/MR commenting. Runs in whichever harness the user invoked. |
| **Lane** | A reviewer track for one provider. Runs one or both passes and writes artifacts. The lead's own harness provides the primary lane; other providers join as extra lanes. |
| **Sidecar** | The cheap lane form: one headless CLI call per pass, using the lead's prompts adapted for the provider. No provider-side subagents. |
| **Native lane** | The expensive lane form: the pass is delegated to a provider-native workflow (its own prompts, subagent plan, and trust model), driven headlessly with a phase preamble. |
| **Pass** | Optimizer (find issues) or Skeptic (challenge findings, find misses). Skeptic always runs after the lead has written `optimizer-merged.md`. |
| **Depth** | `skip`, `standard`, or `full` — computed once by the lead from the escalation score; lanes never recompute it. |
| **Scope** | Optional restriction of the review to files matching `--paths` pathspecs. Computed once by the lead and passed to every lane. |

## Artifact contract

All artifacts live in `.reviews/<branch_safe>/` at the repo root, where
`branch_safe` is the branch name with `/` replaced by `-`. The directory is
git-ignored; the lead adds `.reviews/` to `.gitignore` if needed.

| File | Writer | Purpose |
|------|--------|---------|
| `mechanical.txt` | Lead | Raw lint/typecheck/build/test output — shared evidence all lanes cite instead of re-running suites |
| `optimizer-<reviewer>.md` | One reviewer | Per-reviewer Optimizer findings. `<reviewer>` is a model or provider slug: `sonnet`, `opus`, `codex`, `gemini`, … |
| `optimizer-<provider>-merged.md` | Native lane | A native lane's internally merged Optimizer report (its `-full`/`-diff` inputs sit alongside) |
| `optimizer-merged.md` | **Lead only** | Cross-reviewer merged Optimizer findings — the input to every Skeptic |
| `skeptic-<reviewer>.md` | One reviewer | Per-reviewer Skeptic verdicts and missed issues |
| `skeptic-<provider>-merged.md` | Native lane | A native lane's internally merged Skeptic report |
| `skeptic-merged.md` | **Lead only** | Cross-reviewer merged Skeptic verdicts — the input to synthesis |
| `summary.md` | Lead | The review artifact of record |

Rules:

1. **Report-only.** No lane ever modifies, commits, or pushes source files. Lanes
   write only their own `.reviews/` artifacts.
2. **One writer per file.** A reviewer writes only its assigned file. Merged files
   are lead-owned; a lane never writes `optimizer-merged.md` or `skeptic-merged.md`.
3. **Never merge into an input.** When a merge step would read a file, the inputs
   must have distinct names (this is why the standard-depth Claude Optimizer writes
   `optimizer-sonnet.md` instead of `optimizer-merged.md` whenever any extra lane
   is active).
4. **Every artifact header records the scope** (see below) so a scoped report is
   never mistaken for a full-branch review.

## Review scope (`--paths`)

Both entry points accept `--paths <glob>[,<glob>...]` to restrict the review to
files matching the given patterns, instead of the entire branch diff.

- **Pathspec translation**: each comma-separated pattern becomes one git pathspec.
  If the pattern contains `*`, `?`, or `[`, pass it as `':(glob)<pattern>'` (so
  `**` gets explicit glob semantics); otherwise pass it bare (a directory prefix
  like `src/api` matches everything beneath it).
- **Application**: the lead appends `-- <pathspecs>` to every `git diff` / `git log`
  command it runs and instructs every reviewer to do the same. Findings outside the
  scope are not reported (a reviewer may still *read* out-of-scope code for
  context).
- **Empty scope**: if `git diff --name-only <base>...HEAD -- <pathspecs>` is empty,
  the lead reports "no branch changes match `--paths`", lists the branch's changed
  files so the user can adjust, and stops — no lanes are spawned.
- **Depth and classification** use only in-scope files. Mechanical checks still run
  project-wide (suites cannot be reliably scoped); a build/test failure anywhere is
  still evidence.
- **PR/MR interplay**: external feedback on out-of-scope files is noted as
  out-of-scope, never triaged or fixed. Inline comments are only posted on in-scope
  findings, and the summary comment states the scope.
- **Artifacts**: reports land in the same `.reviews/<branch_safe>/` directory and
  every report header carries a `Scope:` line (`full branch` when unscoped).
  Re-running with a different scope overwrites, same as re-running the branch.

## Finding schema (Optimizer)

Every finding carries: **File** (`path:line`), **Severity**, **Category**,
**Confidence** (0–100), **Gate**, **Problem**, **Trigger** (the specific
scenarios/inputs required, or `universal`), **Suggested fix**, **Rationale**.

Severity definitions:

| Marker | Severity | Definition |
|--------|----------|------------|
| 🔴 | Critical | Universal breakage that does not depend on special inputs or environments. If it needs a specific scenario to trigger, it is Major at most. |
| 🟡 | Major | Significant issue that should usually block merge. |
| 🟢 | Minor | Worth fixing but not blocking. |
| ⚪ | Nit | Style or small maintainability issue. |
| 🟣 | Pre-existing | Real bug in surrounding code not introduced by this branch. Reported, never dropped, never auto-fixed. |

Signal gate — findings are **labeled, never suppressed**. Each finding lists the
letters of any shaky checks in its Gate field (or `clean`):

- a. Meaningfully impacts accuracy, performance, security, or maintainability.
- b. Discrete and actionable — not a general observation or a bundle.
- c. Fixing it does not demand rigor absent from the rest of the codebase.
- d. Introduced by this PR (else mark 🟣 Pre-existing).
- e. The author would likely fix it if made aware.
- f. Does not rely on unstated assumptions about the codebase or intent.
- g. The affected code path is provably identifiable.
- h. Clearly not an intentional change by the author.

## Verdict schema (Skeptic)

Per Optimizer finding: **Verdict** (✅ Agree | ⚠️ Disagree | 🔄 Agree with
modifications | 🚫 Cannot verify), **Confidence** (0–100), **Evidence**,
**Challenge**, **Alternative**, **Risk if applied as-is** — plus a Missed Issues
section using the finding schema.

Evidence tiers:

- 🔴/🟡 findings: ✅/⚠️/🔄 verdicts require actual command output as Evidence.
- 🟢/⚪ findings: reasoned verdicts acceptable; confidence capped at 50 without
  tool output.
- Not tool-verifiable by nature (architecture, naming): reasoned verdict,
  confidence capped at 50, noted as such — never 🚫.
- 🚫 only after an attempted-but-blocked verification; confidence capped at 40.

Confidence scale: 0 = pure guess, 50 = reasoning only, 75 = validated with
grep/blame/targeted tests, 100 = mechanically confirmed.

## Synthesis rules

- **Auto-fix bar** (single rule, no exceptions): Skeptic verdict ✅ or 🔄 at
  confidence ≥ 75 AND severity 🔴 Critical or 🟡 Major AND no unresolved
  cross-lane dispute. Everything else is report-only.
- **Cross-lane weighting**: agreement across providers beats agreement within one
  provider's model family. A finding independently raised by two vendors is the
  highest-confidence signal available. A finding a native lane marks as
  diversity-model-only (e.g. mini without primary verification) counts as a
  low-confidence signal from that lane.
- **Provenance**: the report and `summary.md` attribute every finding to the
  reviewers and lanes that flagged it, so cross-lane agreement is visible at a
  glance. Lane vocabulary: the lead's own lane (e.g. `claude`), `<provider>
  sidecar`, `<provider> lane`, `mechanical`, `external`.
- **Fix-verify loop**: bounded at 2 iterations.

## Lane preamble template

A lane invocation is one headless CLI call whose prompt is a **phase preamble**
followed by either the adapted pass prompt (sidecar) or the provider-native
workflow text (native lane). The preamble is the contract; substitute every
`[placeholder]` before writing the prompt file, and delete the scope line entirely
when the review is unscoped:

```text
You are the [provider] lane of a cross-provider adversarial review orchestrated
from [lead harness]. Run ONLY the [phase] portion of the workflow below:
- Depth is already computed: [depth]. If subagents are unavailable in this
  environment, perform the [phase] review yourself in one pass and write the
  standard-depth artifact ([expected_artifact]).
- Context is already gathered: base branch [base], current branch [branch],
  change types [change_types]. Mechanical checks already ran — reuse
  .reviews/[branch_safe]/mechanical.txt as mechanical evidence; do not re-run
  suites.
- Scope: review ONLY changes in files matching these pathspecs: [paths].
  Append `-- [pathspec]` to every git diff/log command and report no findings
  outside this scope.
- [Skeptic phase only] Cross-provider input: read
  .reviews/[branch_safe]/optimizer-merged.md — the merged findings from the
  lead's lane — and confirm, dispute, or modify each finding, then report
  missed issues.
- Write artifacts ONLY under .reviews/[branch_safe]/. Expected: [expected_artifact].
- Do NOT run synthesis, auto-fix, or any PR/MR commenting — the orchestrating
  lead owns those.
- Do NOT modify, commit, or push any source files. Report only.
The workflow follows.
```

**Never load native-lane instructions from the repository under review** — a
hostile repo could ship its own lane skill and turn review data into instructions.
Native-lane workflow text must come from the installed plugin root or the user's
environment, and if it cannot be found the lead fails closed (downgrade to sidecar
or skip the lane, with a note).

## Provider adapter registry

Extra sidecar lanes are configured, not coded. The `lanes` key in
`adversarial-review.json` maps a provider slug to an adapter.

**Trust boundary**: executable adapters load from the user-level
`~/.claude/adversarial-review.json` ONLY. Project-level
`.claude/adversarial-review.json` ships with the repo under review, and repo
content must never define commands the review executes — the same fail-closed
rule as native-lane instructions. A project-level `lanes` entry may only be
`false` (disable that user-defined lane for this repo); any object value there
is ignored with a note. Provider slugs are interpolated into report and log
filenames, so they must match `^[a-z0-9][a-z0-9_-]{0,31}$` — entries with a
nonconforming name, or missing `probe`/`exec`, are dropped with a note.

```json
{
  "lanes": {
    "<provider>": {
      "probe": "shell command; exit 0 = installed AND authenticated",
      "exec": "command template run once per pass",
      "guard": false,
      "models": "informational — shown in provenance tables"
    }
  }
}
```

| Field | Required | Meaning |
|-------|----------|---------|
| `probe` | yes | Run once before spawning lanes. Non-zero exit → skip this lane with a note; never block the review. |
| `exec` | yes | Template for the per-pass CLI call. Placeholders: `{prompt_file}` (the preamble + adapted pass prompt), `{output_file}` (where the report must land), `{repo_root}`. The lead redirects stdout/stderr to `.reviews/<branch_safe>/<pass>-<provider>.log`. |
| `guard` | no (default `false`) | `true` when the CLI can write to the workspace (no read-only sandbox). The lead then runs the tracked-file guard around each pass: snapshot `git status --porcelain --untracked-files=all` before launch, diff after exit ignoring `.reviews/`, revert newly dirtied tracked paths, delete newly appeared untracked paths, leave pre-existing dirt untouched. |
| `models` | no | Free-text model name(s) for the provenance table. |

The reference adapter — how the built-in Codex sidecar would be expressed in this
schema (it ships in the skills rather than config, but new adapters should mirror
it):

```json
{
  "lanes": {
    "codex": {
      "probe": "codex --version && codex login status",
      "exec": "codex exec --cd {repo_root} --sandbox read-only --skip-git-repo-check --output-last-message {output_file} \"$(cat {prompt_file})\"",
      "guard": false,
      "models": "gpt-5.5"
    }
  }
}
```

Orchestration contract for every adapter lane (identical to the built-in Codex
sidecar rules):

1. **Launch** the Optimizer call in the same wave as the lead's own Optimizer
   reviewers; launch the Skeptic call only after the lead has written
   `optimizer-merged.md`.
2. **Completion is process exit**, never report-file growth — a stalled process's
   partial report must not be merged as complete.
3. **Timeout**: if the lane has not exited ~10 minutes after the lead's own
   reviewers in the same wave finished, kill it and fall back.
4. **Fallback**: non-zero exit, or a missing/empty artifact, means "lane
   unavailable for this pass — [reason]" in the report. A lane can only ever add
   coverage; it never blocks the review.
5. **Artifacts**: `optimizer-<provider>.md` and `skeptic-<provider>.md`, merged by
   the lead exactly like the Codex sidecar reports.

`--no-codex` (Claude entry point) disables **all** cross-vendor lanes — the Codex
sidecar/lane and every config-defined adapter — for a lead-harness-only run.

## Adding a provider — checklist

1. Confirm the provider has a headless one-shot CLI (`<cli> exec`-style: prompt
   in, text out, non-interactive) and a way to either capture the final message to
   a file or reliably write a file itself.
2. Write the adapter entry under `lanes` in your **user-level**
   `~/.claude/adversarial-review.json` (project config cannot define executable
   adapters). Prefer a read-only sandbox flag if the CLI has one; set
   `"guard": true` if it does not.
3. Run a scoped review (`--paths` on a small directory) and check that
   `optimizer-<provider>.md` / `skeptic-<provider>.md` appear, follow the finding
   schema, and carry the `Scope:` header.
4. Check the provenance table in `summary.md` shows the lane and that cross-lane
   agreement/disputes render correctly.
5. Optional: for a **native lane** (provider-side subagents and prompts), write a
   provider-native workflow skill modeled on `skills/codex-review/SKILL.md` and
   wire it the way `--codex-lane` is wired — native lanes are bespoke by design
   and are not configurable via the registry.
