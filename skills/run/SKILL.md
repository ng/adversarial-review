---
name: run
description: Adversarial multi-model code review with progressive cost-gating. Mechanical checks first (free), then Optimizer/Skeptic agents scaled to change complexity. Post-fix verification loop catches regressions.
---

Review all code changes on the current branch that have not been merged yet.

**Usage:**
```
/adversarial-review:run              # review only (default), auto-detect PR
/adversarial-review:run 405          # review only, specific PR
/adversarial-review:run --fix        # review + auto-fix, auto-detect PR
/adversarial-review:run --fix 405    # review + auto-fix, specific PR
```

## Review artifacts

All agent reports are saved to `.claude/reviews/[branch]/` in the project directory so humans can review the raw findings after the review completes. The directory structure:

```text
.claude/reviews/[branch]/
├── optimizer-sonnet.md      # Sonnet Optimizer findings
├── optimizer-opus.md        # Opus Optimizer findings (full depth only)
├── optimizer-merged.md      # Merged Optimizer report
├── skeptic-sonnet.md        # Sonnet Skeptic challenges
├── skeptic-opus.md          # Opus Skeptic challenges (full depth only)
├── skeptic-merged.md        # Merged Skeptic report
└── summary.md               # Persistent review summary (the artifact of record)
```

Before writing reports, ensure the directory exists: `mkdir -p .claude/reviews/[branch]`

Agent reports (optimizer-*.md, skeptic-*.md) are working artifacts — add `.claude/reviews/` to `.gitignore`.

The `summary.md` is the **review artifact of record** — it captures the full outcome (what was fixed, disputed, deferred, and any filed issue numbers). If the team wants to keep review history, they can copy or commit summary files separately.

## Step 0: Parse Arguments and Choose Mode

Parse `$ARGUMENTS` for:
- A PR number (any bare number like `405`)
- `--fix` flag to enable auto-fix mode

If `--fix` is present, set `[mode]` to `auto-fix`. Otherwise, set `[mode]` to `review-only`.

If no PR number is provided, auto-detect via `gh pr view --json number`.

| Mode | Behavior |
|------|----------|
| `review-only` (default) | Report findings as suggestions. No code is modified. |
| `auto-fix` (`--fix`) | Apply consensus Critical/Major fixes + bounded verification loop (max 2 iterations). |

## Step 1: Get Context

Run in parallel:
1. `git branch --show-current` → store as `[branch]`
2. `git remote -v` → extract `[owner]/[repo]`
3. Detect base branch: try `gh pr view --json baseRefName -q .baseRefName 2>/dev/null`, else check if `origin/develop` exists (`git rev-parse --verify origin/develop 2>/dev/null`) — use `develop` if it exists, otherwise `main`. Store as `[base]`.

Then:
4. `git fetch origin [base]`
5. `git log origin/[base]..HEAD --oneline`
6. `git diff origin/[base]...HEAD --stat`
7. `git diff origin/[base]...HEAD`

## Step 2: Pull GitHub PR Feedback (if PR exists)

Try to detect or use the provided PR number. If a PR exists:

1. Get PR metadata: `gh pr view <number> --json title,body,state,headRefName,baseRefName,labels`
2. Get all review comments (Copilot, CodeRabbit, humans):
   - `gh api repos/[owner]/[repo]/pulls/<number>/comments` — inline review comments
   - `gh pr view <number> --json comments,reviews` — top-level comments and review summaries
3. Check CI status: `gh pr checks <number>`
4. Parse and deduplicate feedback into actionable items with file, line, description
5. Present a summary table of all feedback items

If no PR exists, skip to Step 4.

## Step 3: Address GitHub Feedback

For each feedback item, triage:
- **Fix now**: If the issue is valid and in scope, fix it directly
- **Create issue**: If valid but out of scope or pre-existing, create a GitHub issue
- **Dismiss**: If the feedback is incorrect or not applicable, note why

After addressing all items:
1. Run the project's validation commands (check CLAUDE.md for typecheck/build/lint commands)
2. Commit fixes: `fix: address PR review feedback`
3. Push to the branch

## Step 4: Review Against Convention Docs

Read any `.claude/docs/` files relevant to the changed files. Use the `--stat` output from Step 1 to determine which docs apply. At minimum, always check for:
- `REVIEW.md` (repo root) — review-only guidance: what to flag, what to skip, style rules
- `.claude/docs/code-review.md` — domain-specific review checklist
- `.claude/docs/architecture.md` — system architecture context
- `.claude/docs/trust-boundaries.md` — security patterns

Read whatever exists. `REVIEW.md` is for review-specific rules that don't belong in `CLAUDE.md` (e.g., "always flag new API routes without integration tests", "skip generated files under `/gen/`"). The `.claude/docs/` files contain project-specific review lenses that the adversarial agents will reference.

## Step 5: Mechanical Checks (Stage 0)

Before spending LLM tokens, run free mechanical checks to catch obvious issues. Detect and run whatever the project supports (check CLAUDE.md, package.json, Makefile, Cargo.toml, etc.):

| Check | Example commands | What it catches |
|-------|-----------------|-----------------|
| Linter | `pnpm lint`, `eslint .`, `terraform validate`, `cargo clippy` | Style violations, syntax errors, basic logic issues |
| Type checker | `pnpm typecheck`, `tsc --noEmit`, `mypy .`, `pyright` | Type mismatches, missing imports |
| Build | `pnpm build`, `go build ./...`, `cargo build` | Compilation errors, SSR issues, missing deps |
| Tests | `pnpm test`, `pytest`, `go test ./...`, `cargo test` | Regressions, broken contracts |

Run all available checks in parallel. Collect failures as **mechanical findings**:

```markdown
## Mechanical Findings

### MF-1: [check name] failure
- **Check**: [linter | typecheck | build | test]
- **Output**: [relevant error output, trimmed]
- **File**: [path]:[line] (if identifiable from output)
- **Severity**: 🔴 Critical (build/test failure) | 🟡 Major (type error) | 🟢 Minor (lint warning)
```

These are free, high-confidence issues that go directly into the final report. They also inform the cost-gating decision in Step 6.

## Step 6: Adversarial Agent Review

### Cost gating — choose review depth

Before launching agents, classify the change to avoid overspending on simple PRs:

| Trigger | Review depth | Agents |
|---------|-------------|--------|
| Docs, config, typos only | **Skip** — mechanical checks (Step 5) are sufficient | 0 |
| Standard code changes | **Standard** — Sonnet-only Optimizer + Skeptic | 2 |
| Any escalation trigger fires | **Full** — dual-model Optimizer + Skeptic (Sonnet + Opus) | 4 |

**Escalation triggers** (if ANY are true, use full dual-model):
- Changed files touch auth, security, IAM, database migrations, or encryption
- PR labels include `security`, `breaking-change`, or `migration`
- Mechanical checks (Step 5) found build or test failures
- More than 20 files changed (large blast radius)
- `.claude/docs/code-review.md` contains 🔴 Critical lenses that match changed file patterns

For **standard depth**, use the same Optimizer/Skeptic pipeline below but launch only one Sonnet agent per pass instead of two. The single report IS the merged report — skip the merge step.

For **full depth**, launch both Sonnet and Opus per pass as described below.

---

**Important**: Neither agent auto-fixes code. Both produce reports only. The main context synthesizes and applies fixes after both agents complete. This prevents merge conflicts and gives the user control over disputed items.

**Model diversity** (full depth only): Each pass runs on BOTH Sonnet and Opus in parallel, then merges their findings. Different models have different blind spots — running both maximizes coverage within each pass, and the adversarial structure (Optimizer vs Skeptic) catches over-corrections across passes.

### Pass 1 — The Optimizer

For **full depth**, launch TWO agents in parallel (same prompt, different models). For **standard depth**, launch one Sonnet agent. Both run in worktrees and produce findings reports — neither modifies source files.

```javascript
// Full depth — launch BOTH in a single message (parallel tool calls):

Agent({
  name: "optimizer-sonnet",
  subagent_type: "general-purpose",
  isolation: "worktree",
  mode: "bypassPermissions",
  run_in_background: true,
  model: "sonnet",
  prompt: `You are "The Optimizer (Sonnet)" — reviewing branch [branch].
  [OPTIMIZER_PROMPT — see below]
  Write findings to .claude/reviews/[branch]/optimizer-sonnet.md`
})

Agent({
  name: "optimizer-opus",
  subagent_type: "general-purpose",
  isolation: "worktree",
  mode: "bypassPermissions",
  run_in_background: true,
  model: "opus",
  prompt: `You are "The Optimizer (Opus)" — reviewing branch [branch].
  [OPTIMIZER_PROMPT — see below]
  Write findings to .claude/reviews/[branch]/optimizer-opus.md`
})

// Standard depth — launch ONE agent only:

Agent({
  name: "optimizer-sonnet",
  subagent_type: "general-purpose",
  isolation: "worktree",
  mode: "bypassPermissions",
  run_in_background: true,
  model: "sonnet",
  prompt: `You are "The Optimizer" — reviewing branch [branch].
  [OPTIMIZER_PROMPT — see below]
  Write findings to .claude/reviews/[branch]/optimizer-merged.md`
})
```

**OPTIMIZER_PROMPT** (shared by all Optimizer agents):

```
YOUR ROLE: Find every issue worth fixing. Be thorough and constructive.
CONSTRAINT: Do NOT modify any source files. Write your findings to a report file only.

1. WALKTHROUGH FIRST: Before looking for issues, write a 2-3 sentence summary of what
   this branch does and why. Understand the intent before critiquing the implementation.
   This goes in the Summary section of your report.

2. Read ALL changed files: git diff origin/[base]...HEAD

3. Read `REVIEW.md` (repo root, if it exists) for review-only guidance.
   Read `.claude/docs/code-review.md` (if it exists) for the project's domain-specific
   review checklist. Also read any other relevant `.claude/docs/` files for architecture
   and convention context.

4. COMPLETENESS CHECK: Check the PR body/title and commit messages for linked issues
   (references like #123, closes #123, fixes #123, or URLs to issues/tickets). If any
   are found, read the linked issue with `gh issue view <number>` and verify the
   implementation addresses ALL requirements and acceptance criteria. Flag gaps as
   findings with category "Completeness".

5. Review against these universal lenses:
   - Security: auth checks, input validation, secrets handling, injection vectors
   - Performance: N+1 queries, missing indexes, unnecessary computation, missing limits
   - Correctness: edge cases, error handling, race conditions, state management
   - Architecture: separation of concerns, DRY, naming, module boundaries
   - Type safety: proper types, no `any`, exhaustive checks
   - Missing test coverage for critical paths
   - Deception detection: verify that function/variable names, comments, and docstrings
     accurately describe what the code actually does. Flag mismatches between naming and
     behavior — misleading names can cause reviewers (both human and AI) to overlook
     vulnerabilities hiding behind trustworthy-sounding abstractions.

   PLUS any domain-specific lenses from the project's `.claude/docs/code-review.md`.

6. Write your findings in this exact format:

   # Optimizer Findings ([model]) — [branch]

   ## Summary
   [2-3 sentence walkthrough of what this PR does and why]

   Overall code quality assessment.

   ## Findings

   ### Finding 1: [title]
   - **File**: [path]:[line number]
   - **Severity**: 🔴 Critical | 🟡 Major | 🟢 Minor | ⚪ Nit | 🟣 Pre-existing
   - **Category**: [Security | Performance | Correctness | Pattern | Type Safety | Architecture | Testing | Completeness | Deception]
   - **Problem**: [what is wrong]
   - **Suggested fix**: [concrete code change or approach]
   - **Rationale**: [why this matters — cite convention doc if applicable]

   ### Finding 2: [title]
   ...

   ## Statistics
   - Total findings: [count]
   - 🔴 Critical: [count]
   - 🟡 Major: [count]
   - 🟢 Minor: [count]
   - ⚪ Nit: [count]
   - 🟣 Pre-existing: [count]

7. PRE-EXISTING BUGS: If you notice bugs in the surrounding code that were NOT
   introduced by this PR, still report them but mark severity as 🟣 Pre-existing.
   These are valuable to surface but are not the PR author's fault.

8. Do NOT commit, push, or modify source files. Report only.
```

Wait for Optimizer agent(s) to complete. For **full depth**, merge findings:
1. Read both `.claude/reviews/[branch]/optimizer-sonnet.md` and `.claude/reviews/[branch]/optimizer-opus.md`
2. Deduplicate findings that both models flagged (these are high-confidence issues)
3. Write a merged report to `.claude/reviews/[branch]/optimizer-merged.md` noting which findings came from which model, and which were flagged by both

### Pass 2 — The Skeptic

For **full depth**, launch TWO agents in parallel. For **standard depth**, launch one Sonnet agent. Both read the merged Optimizer findings AND the code.

```javascript
// Full depth — launch BOTH in a single message (parallel tool calls):

Agent({
  name: "skeptic-sonnet",
  subagent_type: "general-purpose",
  isolation: "worktree",
  mode: "bypassPermissions",
  run_in_background: true,
  model: "sonnet",
  prompt: `You are "The Skeptic (Sonnet)" — challenging the Optimizer findings for branch [branch].
  [SKEPTIC_PROMPT — see below]
  Write challenge report to .claude/reviews/[branch]/skeptic-sonnet.md`
})

Agent({
  name: "skeptic-opus",
  subagent_type: "general-purpose",
  isolation: "worktree",
  mode: "bypassPermissions",
  run_in_background: true,
  model: "opus",
  prompt: `You are "The Skeptic (Opus)" — challenging the Optimizer findings for branch [branch].
  [SKEPTIC_PROMPT — see below]
  Write challenge report to .claude/reviews/[branch]/skeptic-opus.md`
})

// Standard depth — launch ONE agent only:

Agent({
  name: "skeptic-sonnet",
  subagent_type: "general-purpose",
  isolation: "worktree",
  mode: "bypassPermissions",
  run_in_background: true,
  model: "sonnet",
  prompt: `You are "The Skeptic" — challenging the Optimizer findings for branch [branch].
  [SKEPTIC_PROMPT — see below]
  Write challenge report to .claude/reviews/[branch]/skeptic-merged.md`
})
```

**SKEPTIC_PROMPT** (shared by all Skeptic agents):

```text
YOUR ROLE: Challenge The Optimizer's findings. Find flaws in their suggestions. Catch what they missed.
CONSTRAINT: Do NOT modify any source files. Write your challenge report only.

1. Read The Optimizer's merged findings: .claude/reviews/[branch]/optimizer-merged.md
2. Read ALL changed files: git diff origin/[base]...HEAD
3. Read `REVIEW.md` (repo root, if it exists) for review-only guidance.
   Read `.claude/docs/code-review.md` (if it exists) for project context.
   Also read any other relevant `.claude/docs/` files.

For EACH of The Optimizer's findings, evaluate:
- Is the issue real or a false positive?
- Would the suggested fix introduce new bugs, breaking changes, or regressions?
- Is the fix over-engineered for the actual risk?
- Does the severity rating match the actual impact?
- Is there a simpler or safer alternative?

Challenge findings where you have substantive objections — but only where you genuinely
believe the Optimizer is wrong, the fix is risky, or the severity is misrated. Do NOT
force disagreements just to be contrarian. If all findings are valid, say so.

TOOL-BASED VALIDATION: Where possible, validate your judgments with external tools rather
than pure reasoning. Run the project's test suite, linter, or type checker to confirm
whether an issue is real. Check git blame to understand if a pattern is intentional.
Use grep/search to find similar patterns elsewhere in the codebase. Ground your
challenges in evidence, not just reasoning.
If tools cannot run, explicitly state "validation unavailable", cite the blocking reason,
and downgrade confidence for that challenge.

Then, independently review the code for issues The Optimizer missed, especially:
- Edge cases: empty/null/boundary values, partial input, malformed responses
- Race conditions: cleanup, stale responses, timing issues
- Accessibility: ARIA labels, keyboard nav, screen reader support
- UX gaps: loading states, error feedback, empty states, confirmation dialogs
- Consistency: naming patterns, style, import ordering
- Blast radius: could this change break existing behavior or downstream consumers?
- Deception: do names/comments accurately describe behavior? (see Optimizer lens)

4. Write your challenge report in this exact format:

   # Skeptic Challenge Report ([model]) — [branch]

   ## Challenges to Optimizer Findings

   ### RE: Finding [N] — [Optimizer's title]
   - **Verdict**: ✅ Agree | ⚠️ Disagree | 🔄 Agree with modifications
   - **Challenge**: [why the suggestion is wrong, risky, or over-engineered — be specific]
   - **Alternative**: [better approach, if applicable]
   - **Risk if applied as-is**: [what could break]

   (Repeat for each Optimizer finding)

   ## Missed Issues

   ### Missed Issue 1: [title]
   - **File**: [path]:[line number]
   - **Severity**: 🔴 Critical | 🟡 Major | 🟢 Minor | ⚪ Nit | 🟣 Pre-existing
   - **Category**: [Edge Case | Race Condition | Accessibility | UX | Consistency | Blast Radius | Deception]
   - **Problem**: [what is wrong]
   - **Suggested fix**: [concrete code change or approach]

   ## Statistics
   - Optimizer findings challenged: [count]
   - Findings agreed with: [count]
   - Findings agreed with modifications: [count]
   - New issues found: [count]

5. Do NOT commit, push, or modify source files. Report only.
```

Wait for Skeptic agent(s) to complete. For **full depth**, merge:
1. Read both `.claude/reviews/[branch]/skeptic-sonnet.md` and `.claude/reviews/[branch]/skeptic-opus.md`
2. For each Optimizer finding: note where both Skeptics agree vs disagree (cross-model consensus strengthens the signal)
3. Write a merged report to `.claude/reviews/[branch]/skeptic-merged.md`

## Step 7: Synthesize, Apply, and Verify

Read both merged reports:
1. `.claude/reviews/[branch]/optimizer-merged.md`
2. `.claude/reviews/[branch]/skeptic-merged.md`

### Cross-model confidence signals

Use model agreement to gauge confidence (full depth only — for standard depth, treat the single-model findings as the consensus):

| Signal | Meaning |
|--------|---------|
| Both Optimizer models flagged it + both Skeptic models agree | Very high confidence |
| One Optimizer model flagged it + both Skeptic models agree | High confidence |
| Both Optimizer models flagged it + Skeptic models disagree | Disputed — present to user |
| Only one model flagged + only one Skeptic agrees | Low confidence — note only |

### Resolve each finding

For each Optimizer finding, cross-reference The Skeptic's verdict:

**If `[mode]` is `review-only`:**

| Skeptic Verdict | Action |
|-----------------|--------|
| ✅ Agree | Report as confirmed finding with suggested fix |
| ⚠️ Disagree | Report the dispute with both sides |
| 🔄 Agree with modifications | Report with the modified suggestion |

All findings are suggestions only. No code is modified.

**If `[mode]` is `auto-fix`:**

| Skeptic Verdict | Action |
|-----------------|--------|
| ✅ Agree | Apply the fix (Critical/Major) or note it (Minor/Nit) |
| ⚠️ Disagree | Present the dispute to the user — do NOT auto-fix |
| 🔄 Agree with modifications | Apply the modified version (Critical/Major) or note it (Minor/Nit) |

For Skeptic's missed issues: treat as new findings. In auto-fix mode, apply Critical/Major fixes.

### Apply agreed fixes (auto-fix mode only)

**Skip this section entirely if `[mode]` is `review-only`.** Proceed directly to Step 8.

1. Fix all undisputed 🔴 Critical and 🟡 Major issues

### Verify fixes (auto-fix mode only — bounded loop)

After applying fixes, verify they didn't introduce regressions. **Hard limit: 2 iterations maximum.**

```text
iteration = 0

LOOP:
  iteration += 1
  Run mechanical checks from Step 5 (lint, typecheck, build, tests)

  IF all checks pass → EXIT LOOP (proceed to Step 8)
  IF iteration >= 2 → EXIT LOOP (report remaining failures to user)

  Fix ONLY the regressions introduced by the previous fixes
  (do NOT fix pre-existing issues or go beyond what the auto-fixes broke)

  → GOTO LOOP
```

**Why max 2 iterations**: Research shows LLM self-correction can degrade quality
(Huang et al., 2023). Each fix attempt can introduce new issues at a similar rate to
fixing them. Two iterations catches genuine regressions; more risks an infinite
fix-break cycle. If code can't be made clean in 2 rounds, it needs human judgment.

After exiting the verify loop:
- If fixes were applied and checks pass, commit: `fix: address code review findings`
- If checks still fail after 2 iterations, commit what's clean and note the
  remaining failures in the report
- Do NOT push yet — present the report first

## Step 8: Structured Report

Compile findings from all sources into:

| Source | Severity | File | Finding | Skeptic Verdict | Status |
|--------|----------|------|---------|-----------------|--------|
| Mechanical | ... | ... | ... | — | Fixed / Reported |
| GitHub | ...      | ...  | ...     | —               | Fixed / Skipped / Needs discussion |
| Optimizer | ...   | ...  | ...     | Agree / Disagree / Modified | Fixed / Disputed / Deferred |
| Skeptic (missed) | ... | ... | ...  | —               | Fixed / Deferred |
| Pre-existing | 🟣 | ... | ... | — | Issue filed / Noted |

Report sections:
- **Summary**: What was added/modified/removed
- **Review Depth**: Which tier was used (skip / standard / full) and why
- **Mechanical Findings**: Issues caught by lint/typecheck/build/tests (free)
- **GitHub Feedback** (if PR exists): Items addressed vs issues created vs dismissed
- **Consensus Fixes Applied**: Issues both agents agreed on that were auto-fixed (note which models flagged each)
- **Disputed Items** (requires author decision): Issues where models disagreed — present both sides with a recommendation
- **Pre-existing Issues**: Bugs found in surrounding code not introduced by this PR (🟣)
- **Remaining Items**: 🟢 Minor and ⚪ Nit issues not auto-fixed (for author to decide)
- **Verification Loop Results**: How many fix-verify iterations ran, what passed/failed
- **Model Agreement Summary**: How many findings had full cross-model consensus vs split opinions
- **Recommendation**: Approve, Request Changes, or Comment

### Post findings as PR comments (if PR exists)

If a PR exists, post findings as inline comments on the specific lines where issues were found. Use the GitHub API to create review comments:

```bash
gh api repos/[owner]/[repo]/pulls/[number]/reviews --method POST \
  --field event=COMMENT \
  --field body="[summary comment]" \
  --field 'comments[]={ "path": "[file]", "line": [line], "body": "[finding]" }'
```

For each finding, format the comment as:
```markdown
**[severity emoji] [title]** ([category])

[problem description]

**Suggested fix:** [fix]

<details>
<summary>Review context</summary>

- Source: [Optimizer / Skeptic / Mechanical]
- Skeptic verdict: [Agree / Disagree / Modified]
- Model consensus: [which models flagged this]
- Confidence: [Very high / High / Low]
</details>
```

### Save persistent review summary

Write a self-contained summary to `.claude/reviews/[branch]/summary.md` that captures the full review outcome. This file is the **review artifact of record** — it survives after agent reports are cleaned up and contains everything needed to understand what was reviewed, decided, and deferred.

```markdown
# Code Review Summary — [branch] (PR #[number])
Date: [YYYY-MM-DD]
Depth: [skip | standard | full]
Branch: [branch] → [base]

## What changed
[2-3 sentence walkthrough]

## Findings

### Fixed ([count])
[list of findings that were auto-fixed, with file:line and one-line description]

### Disputed ([count])
[findings where agents disagreed, with both sides and author's decision if made]

### Deferred ([count])
[findings not addressed in this PR, with issue numbers if filed]

### Pre-existing ([count])
[bugs in surrounding code not from this PR, with issue numbers if filed]

## Mechanical checks
[pass/fail status of lint, typecheck, build, tests]

## Verification
[how many fix-verify iterations, final status]
```

## Step 9: File Issues for Deferred and Disputed Items

After presenting the report, ask the user:

> "Would you like me to file GitHub issues for deferred, disputed, or pre-existing items?
> This preserves the full review context so the team can pick up where we left off."

If yes, for each item the user approves, create a GitHub issue with full context:

```bash
gh issue create \
  --title "[severity emoji] [finding title]" \
  --label "code-review" \
  --label "[severity: critical|major|minor]" \
  --body "$(cat <<'ISSUE'
## Problem

[problem description]

**File**: `[path]:[line]`
**Severity**: [severity]
**Category**: [category]

## Context

[Optimizer's reasoning for flagging this]

[Skeptic's challenge or agreement, if applicable]

## Suggested fix

[concrete fix from the review]

## Source

- Review of PR #[number] (`[branch]` → `[base]`)
- Review date: [YYYY-MM-DD]
- Review depth: [standard | full]
- [Link to review summary if available]

---
*Filed by [adversarial-review](https://github.com/ng/adversarial-review) plugin*
ISSUE
)"
```

For disputed items, include BOTH the Optimizer's argument and the Skeptic's challenge in the issue body so future readers have the full debate context.

After filing, update the review summary with issue numbers:
```markdown
### Deferred
- #[issue] — [finding title] (file:line)
```

### Final steps

After the user reviews all items:
1. Apply any additional fixes the user approves
2. Re-run mechanical checks
3. Commit and push
4. If PR exists, re-request reviews: `gh api repos/[owner]/[repo]/pulls/<number>/requested_reviewers -f "reviewers[]=copilot-pull-request-reviewer[bot]"`
