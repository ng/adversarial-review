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

All agent reports are saved to `.claude/reviews/[branch_safe]/` in the project directory so humans can review the raw findings after the review completes. The directory structure:

```text
.claude/reviews/[branch_safe]/
├── optimizer-sonnet.md      # Sonnet Optimizer findings
├── optimizer-opus.md        # Opus Optimizer findings (full depth only)
├── optimizer-merged.md      # Merged Optimizer report
├── skeptic-sonnet.md        # Sonnet Skeptic challenges
├── skeptic-opus.md          # Opus Skeptic challenges (full depth only)
├── skeptic-merged.md        # Merged Skeptic report
└── summary.md               # Persistent review summary (the artifact of record)
```

Before writing reports, ensure the directory exists: `mkdir -p [repo_root]/.claude/reviews/[branch_safe]`

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

**Prompt for issue creation preference before proceeding:**

> "Should I file issues for out-of-scope, pre-existing, or deferred findings discovered during the review? (y/n)"

Store the answer as `[file-issues]` (`yes` or `no`). This controls whether Steps 3 and 9 create issues or just note them in the report.

## Step 1: Get Context

Run in parallel:
1. `git branch --show-current` → store as `[branch]`. Sanitize for use in team/directory names: `[branch_safe]` = branch name with `/` replaced by `-` (e.g., `feat/agent-teams` → `feat-agent-teams`). Also: `git rev-parse --show-toplevel` → store as `[repo_root]`
2. `git remote -v` → extract `[owner]/[repo]` and detect `[platform]`:
   - If remote URL contains `github.com` → `[platform]` = `github`
   - If remote URL contains `gitlab` or is not `github.com` → `[platform]` = `gitlab`
   - For GitLab, extract `[gitlab_url]` (e.g., `https://gitlab.example.com`) and resolve project ID:
     `curl --header "PRIVATE-TOKEN: $GITLAB_PAT" "$GITLAB_URL/api/v4/projects?search=[repo]"` → store as `[project_id]`
   - Token lookup order: `$GITLAB_PAT` → `$GITLAB_ORG_PAT` → error with instructions
3. Detect base branch:
   - GitHub: try `gh pr view --json baseRefName -q .baseRefName 2>/dev/null`
   - GitLab: `curl --header "PRIVATE-TOKEN: $TOKEN" "$GITLAB_URL/api/v4/projects/[project_id]/merge_requests?source_branch=[branch]&state=opened" | jq -r '.[0].target_branch'`
   - Fallback: check if `origin/develop` exists (`git rev-parse --verify origin/develop 2>/dev/null`) — use `develop` if it exists, otherwise `main`. Store as `[base]`.

Then:
4. `git fetch origin [base]`
5. `git log origin/[base]..HEAD --oneline`
6. `git diff origin/[base]...HEAD --stat`
7. `git diff origin/[base]...HEAD`

## Step 2: Pull PR Feedback (if PR/MR exists)

Try to detect or use the provided PR number. If a PR/MR exists:

**GitHub (`[platform]` = `github`):**
1. Get PR metadata: `gh pr view <number> --json title,body,state,headRefName,baseRefName,labels`
2. Get all review comments (Copilot, CodeRabbit, humans):
   - `gh api repos/[owner]/[repo]/pulls/<number>/comments` — inline review comments
   - `gh pr view <number> --json comments,reviews` — top-level comments and review summaries
3. Check CI status: `gh pr checks <number>`

**GitLab (`[platform]` = `gitlab`):**
1. Get MR metadata: `curl --header "PRIVATE-TOKEN: $TOKEN" "$GITLAB_URL/api/v4/projects/[project_id]/merge_requests/[iid]"`
2. Get all MR notes (comments): `curl --header "PRIVATE-TOKEN: $TOKEN" "$GITLAB_URL/api/v4/projects/[project_id]/merge_requests/[iid]/notes"`
3. Get MR discussions (inline review threads): `curl --header "PRIVATE-TOKEN: $TOKEN" "$GITLAB_URL/api/v4/projects/[project_id]/merge_requests/[iid]/discussions"`
4. Check pipeline status: `curl --header "PRIVATE-TOKEN: $TOKEN" "$GITLAB_URL/api/v4/projects/[project_id]/merge_requests/[iid]/pipelines"`

**Then (both platforms):**
4. Parse and deduplicate feedback into actionable items with file, line, description
5. Present a summary table of all feedback items

If no PR/MR exists, skip to Step 4.

## Step 3: Address PR/MR Feedback

For each feedback item, triage:
- **Fix now**: If the issue is valid and in scope, fix it directly
- **Create issue** (only if `[file-issues]` = `yes`): If valid but out of scope or pre-existing, create an issue (GitHub: `gh issue create`, GitLab: `curl -X POST ... "$GITLAB_URL/api/v4/projects/[project_id]/issues"`)
- **Note for report** (if `[file-issues]` = `no`): If valid but out of scope or pre-existing, note it in the report for manual follow-up
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

For **standard depth**, use the same pipeline but with 2 teammates (one per pass). For **full depth**, use 4 teammates (Sonnet + Opus per pass).

---

**Important**: No teammate auto-fixes code. All produce reports only. The lead synthesizes and applies fixes after both passes complete. This prevents merge conflicts and gives the user control over disputed items. Teammates run without worktree isolation — containment is enforced by prompt constraints ("Do NOT modify any source files. Report only."). Worktrees were removed because agents in worktrees cannot write reports to the main repo's `.claude/reviews/` directory without triggering permission prompts.

**Model diversity** (full depth only): Each pass runs on BOTH Sonnet and Opus in parallel, then merges their findings. Different models have different blind spots — running both maximizes coverage within each pass, and the adversarial structure (Optimizer vs Skeptic) catches over-corrections across passes.

### Create review team

```javascript
TeamCreate({
  team_name: "review-[branch_safe]",
  description: "Adversarial code review for [branch_safe]"
})
```

Ensure the shared report directory exists: `mkdir -p [repo_root]/.claude/reviews/[branch_safe]`

### Create tasks with dependencies

**Full depth** — 6 tasks:

```javascript
TaskCreate({ subject: "Optimizer review (Sonnet)", description: "Review as The Optimizer. Write to .claude/reviews/[branch_safe]/optimizer-sonnet.md" })
// → task ID 1

TaskCreate({ subject: "Optimizer review (Opus)", description: "Review as The Optimizer. Write to .claude/reviews/[branch_safe]/optimizer-opus.md" })
// → task ID 2

TaskCreate({ subject: "Merge Optimizer findings", description: "Deduplicate Sonnet+Opus reports into optimizer-merged.md" })
// → task ID 3
TaskUpdate({ taskId: "3", addBlockedBy: ["1", "2"], owner: "lead" })

TaskCreate({ subject: "Skeptic challenge (Sonnet)", description: "Challenge merged Optimizer findings. Write to .claude/reviews/[branch_safe]/skeptic-sonnet.md" })
// → task ID 4
TaskUpdate({ taskId: "4", addBlockedBy: ["3"] })

TaskCreate({ subject: "Skeptic challenge (Opus)", description: "Challenge merged Optimizer findings. Write to .claude/reviews/[branch_safe]/skeptic-opus.md" })
// → task ID 5
TaskUpdate({ taskId: "5", addBlockedBy: ["3"] })

TaskCreate({ subject: "Merge Skeptic challenges", description: "Merge Sonnet+Opus Skeptic reports into skeptic-merged.md" })
// → task ID 6
TaskUpdate({ taskId: "6", addBlockedBy: ["4", "5"], owner: "lead" })
```

**Standard depth** — 2 tasks (no merge tasks needed):

```javascript
TaskCreate({ subject: "Optimizer review", description: "Review as The Optimizer. Write to .claude/reviews/[branch_safe]/optimizer-merged.md" })
// → task ID 1

TaskCreate({ subject: "Skeptic challenge", description: "Challenge Optimizer findings. Write to .claude/reviews/[branch_safe]/skeptic-merged.md" })
// → task ID 2
TaskUpdate({ taskId: "2", addBlockedBy: ["1"] })
```

### Spawn teammates

**Variable substitution**: When constructing Agent prompts below, replace all template variables with actual values from Step 1: `[repo_root]`, `[branch]`, `[branch_safe]`, `[base]`. Replace `[OPTIMIZER_PROMPT — see below]` with the full OPTIMIZER_PROMPT text from the "Pass 1" section, and `[SKEPTIC_PROMPT — see below]` with the full SKEPTIC_PROMPT text from the "Pass 2" section.

**Teams API semantics**: Task IDs are sequential starting from 1 within a team. Idle notifications are automatic — teammates send them when their turn ends. `shutdown_request` is a built-in protocol message handled at the platform level. `TeamDelete()` uses the current session's team context (no arguments needed).

Spawn all teammates in a single message. They check TaskList, claim unblocked tasks, and work. Teammates with blocked tasks idle until the lead wakes them after completing the merge.

**Full depth** — 4 teammates in one message:

```javascript
Agent({
  name: "optimizer-sonnet",
  subagent_type: "general-purpose",
  team_name: "review-[branch_safe]",
  mode: "bypassPermissions",
  model: "sonnet",
  prompt: `You are "The Optimizer (Sonnet)" on team "review-[branch_safe]".
  Check TaskList, claim your Optimizer task with TaskUpdate({ taskId: <id>, status: "in_progress" }), and when done, verify your report file is non-empty, then call TaskUpdate({ taskId: <id>, status: "completed" }).
  [OPTIMIZER_PROMPT — see below]
  Write findings to .claude/reviews/[branch_safe]/optimizer-sonnet.md`
})

Agent({
  name: "optimizer-opus",
  subagent_type: "general-purpose",
  team_name: "review-[branch_safe]",
  mode: "bypassPermissions",
  model: "opus",
  prompt: `You are "The Optimizer (Opus)" on team "review-[branch_safe]".
  Check TaskList, claim your Optimizer task with TaskUpdate({ taskId: <id>, status: "in_progress" }), and when done, verify your report file is non-empty, then call TaskUpdate({ taskId: <id>, status: "completed" }).
  [OPTIMIZER_PROMPT — see below]
  Write findings to .claude/reviews/[branch_safe]/optimizer-opus.md`
})

Agent({
  name: "skeptic-sonnet",
  subagent_type: "general-purpose",
  team_name: "review-[branch_safe]",
  mode: "bypassPermissions",
  model: "sonnet",
  prompt: `You are "The Skeptic (Sonnet)" on team "review-[branch_safe]".
  Your task is blocked — wait for the lead to message you when the Optimizer merge is ready.
  Then check TaskList, claim your Skeptic task with TaskUpdate({ taskId: <id>, status: "in_progress" }), and when done, verify your report file is non-empty, then call TaskUpdate({ taskId: <id>, status: "completed" }).
  [SKEPTIC_PROMPT — see below]
  Write challenge report to .claude/reviews/[branch_safe]/skeptic-sonnet.md`
})

Agent({
  name: "skeptic-opus",
  subagent_type: "general-purpose",
  team_name: "review-[branch_safe]",
  mode: "bypassPermissions",
  model: "opus",
  prompt: `You are "The Skeptic (Opus)" on team "review-[branch_safe]".
  Your task is blocked — wait for the lead to message you when the Optimizer merge is ready.
  Then check TaskList, claim your Skeptic task with TaskUpdate({ taskId: <id>, status: "in_progress" }), and when done, verify your report file is non-empty, then call TaskUpdate({ taskId: <id>, status: "completed" }).
  [SKEPTIC_PROMPT — see below]
  Write challenge report to .claude/reviews/[branch_safe]/skeptic-opus.md`
})
```

**Standard depth** — 2 teammates:

```javascript
Agent({
  name: "optimizer-sonnet",
  subagent_type: "general-purpose",
  team_name: "review-[branch_safe]",
  mode: "bypassPermissions",
  model: "sonnet",
  prompt: `You are "The Optimizer" on team "review-[branch_safe]".
  Check TaskList, claim your task with TaskUpdate({ taskId: <id>, status: "in_progress" }), and when done, verify your report file is non-empty, then call TaskUpdate({ taskId: <id>, status: "completed" }).
  [OPTIMIZER_PROMPT — see below]
  Write findings to .claude/reviews/[branch_safe]/optimizer-merged.md`
})

Agent({
  name: "skeptic-sonnet",
  subagent_type: "general-purpose",
  team_name: "review-[branch_safe]",
  mode: "bypassPermissions",
  model: "sonnet",
  prompt: `You are "The Skeptic" on team "review-[branch_safe]".
  Your task is blocked — wait for the lead to message you when the Optimizer report is ready.
  Then check TaskList, claim your task, and mark it completed when done.
  [SKEPTIC_PROMPT — see below]
  Write challenge report to .claude/reviews/[branch_safe]/skeptic-merged.md`
})
```

### Pass 1 — The Optimizer

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
   - Git history: Run `git log --oneline -5 -- <file>` for key changed files. Check if a
     pattern was deliberately established by previous commits that this PR removes or
     contradicts. Flag regressions against intentional guards.
   - Code comment compliance: Read JSDoc and inline comments in modified files. Verify
     comments accurately describe the code's current behavior. Flag stale counts,
     misleading toggle/switch descriptions, and TODO items that this PR should have
     addressed.
   - Prior review patterns: Check recent commits for messages containing "fix:", "address
     review", or "review findings". If similar issues were fixed before in these files,
     verify this PR doesn't reintroduce the same class of problem (e.g., hardcoded colors,
     unmemoized callbacks, missing Orchestra wrappers).

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

### Orchestration — Optimizer phase

Optimizer teammates auto-claim their tasks and begin reviewing immediately. The lead waits for idle notifications.

1. **Wait for Optimizer teammates** — they send idle notifications when their tasks are complete
2. **Lead handles Optimizer merge** (full depth only):
   - Read `[repo_root]/.claude/reviews/[branch_safe]/optimizer-sonnet.md` and `optimizer-opus.md`
   - Deduplicate findings that both models flagged (these are high-confidence issues)
   - Write merged report to `[repo_root]/.claude/reviews/[branch_safe]/optimizer-merged.md` noting which findings came from which model
   - Mark merge task completed: `TaskUpdate({ taskId: "3", status: "completed" })`
3. **Wake Skeptic teammates** — their tasks are now unblocked:
   ```javascript
   // Both depths — always wake the Sonnet Skeptic:
   SendMessage({
     to: "skeptic-sonnet",
     summary: "Optimizer complete — begin challenge",
     message: "Optimizer findings are ready at [repo_root]/.claude/reviews/[branch_safe]/optimizer-merged.md — check TaskList and begin your challenge."
   })
   // Full depth only — also wake the Opus Skeptic:
   SendMessage({
     to: "skeptic-opus",
     summary: "Optimizer complete — begin challenge",
     message: "Optimizer findings are ready at [repo_root]/.claude/reviews/[branch_safe]/optimizer-merged.md — check TaskList and begin your challenge."
   })
   ```

   **Standard depth**: There is no merge step — the Optimizer's single report IS the merged report. After the Optimizer teammate completes, immediately wake the Skeptic with the SendMessage above.

### Pass 2 — The Skeptic

Skeptic teammates are already spawned and waiting. Once woken by the lead, they claim their tasks and read the merged Optimizer findings AND the code.

**SKEPTIC_PROMPT** (shared by all Skeptic agents):

```text
YOUR ROLE: Challenge The Optimizer's findings. Find flaws in their suggestions. Catch what they missed.
CONSTRAINT: Do NOT modify any source files. Write your challenge report only.

1. Read ALL changed files FIRST: git diff origin/[base]...HEAD
2. Form your own initial impressions of the code quality — note potential issues
   before seeing the Optimizer's report. This independent assessment strengthens
   your ability to catch false positives and find missed issues.
3. Read `REVIEW.md` (repo root, if it exists) for review-only guidance.
   Read `.claude/docs/code-review.md` (if it exists) for project context.
   Also read any other relevant `.claude/docs/` files.
4. THEN read The Optimizer's merged findings: .claude/reviews/[branch_safe]/optimizer-merged.md
5. Challenge findings where your independent assessment disagrees with the Optimizer.

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

6. Write your challenge report in this exact format:

   # Skeptic Challenge Report ([model]) — [branch]

   ## Challenges to Optimizer Findings

   ### RE: Finding [N] — [Optimizer's title]
   - **Verdict**: ✅ Agree | ⚠️ Disagree | 🔄 Agree with modifications
   - **Confidence**: [0-100] (0=pure guess, 50=reasoning only — no tool validation,
     75=validated with grep/blame/tests, 100=mechanically confirmed — test fails, lint errors, etc.)
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

7. Do NOT commit, push, or modify source files. Report only.
```

### Orchestration — Skeptic phase

1. **Wait for Skeptic teammates** — they send idle notifications when their tasks are complete
2. **Lead handles Skeptic merge** (full depth only):
   - Read `[repo_root]/.claude/reviews/[branch_safe]/skeptic-sonnet.md` and `skeptic-opus.md`
   - For each Optimizer finding: note where both Skeptics agree vs disagree (cross-model consensus strengthens the signal)
   - Write merged report to `[repo_root]/.claude/reviews/[branch_safe]/skeptic-merged.md`
   - Mark merge task completed: `TaskUpdate({ taskId: "6", status: "completed" })`
3. **Shutdown the team**:
   ```javascript
   SendMessage({ to: "*", message: { type: "shutdown_request" } })
   // Wait for all teammates to acknowledge, then:
   TeamDelete()
   ```

## Step 7: Synthesize, Apply, and Verify

Read both merged reports:
1. `[repo_root]/.claude/reviews/[branch_safe]/optimizer-merged.md`
2. `[repo_root]/.claude/reviews/[branch_safe]/skeptic-merged.md`

### Cross-model confidence signals

Use model agreement to gauge confidence (full depth only — for standard depth, treat the single-model findings as the consensus):

| Signal | Meaning |
|--------|---------|
| Both Optimizer models flagged it + both Skeptic models agree | Very high confidence |
| One Optimizer model flagged it + both Skeptic models agree | High confidence |
| Both Optimizer models flagged it + Skeptic models disagree | Disputed — present to user |
| Only one model flagged + only one Skeptic agrees | Low confidence — note only |

### Confidence-based filtering

Before resolving findings, apply confidence filters to Skeptic verdicts:

| Skeptic Verdict | Confidence | Treatment |
|-----------------|------------|-----------|
| ✅ Agree | 75-100 | Confirmed — high confidence |
| ✅ Agree | 50-74 | Confirmed — lower confidence (see "Lower Confidence Items" in report) |
| ✅ Agree | < 50 | Downgrade to "Low confidence — note only" |
| ⚠️ Disagree | 75-100 | Strong disagreement — present as Disputed |
| ⚠️ Disagree | < 50 | Weak disagreement — treat as "Disputed" rather than rejected |
| 🔄 Modified | any | Apply modified suggestion at stated confidence |

### Resolve each finding

For each Optimizer finding, cross-reference The Skeptic's verdict and confidence:

**If `[mode]` is `review-only`:**

| Skeptic Verdict | Action |
|-----------------|--------|
| ✅ Agree (confidence >= 50) | Report as confirmed finding with suggested fix |
| ✅ Agree (confidence < 50) | Report as low-confidence note |
| ⚠️ Disagree (confidence >= 50) | Report the dispute with both sides |
| ⚠️ Disagree (confidence < 50) | Report as disputed (weak disagreement) — do not reject |
| 🔄 Agree with modifications | Report with the modified suggestion |

All findings are suggestions only. No code is modified.

**If `[mode]` is `auto-fix`:**

| Skeptic Verdict | Action |
|-----------------|--------|
| ✅ Agree (confidence >= 50) | Apply the fix (Critical/Major) or note it (Minor/Nit) |
| ✅ Agree (confidence < 50) | Note only — do NOT auto-fix low-confidence items |
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

### Haiku confidence scoring (optional final filter)

After synthesis, launch parallel Haiku agents — one per confirmed finding — to independently
score confidence 0-100. Each Haiku agent sees ONLY the single finding (problem + suggested fix +
file context) without the adversarial debate context, preventing groupthink bias.

```javascript
// For each confirmed finding, launch in parallel:
Agent({
  name: "scorer-[N]",
  subagent_type: "general-purpose",
  mode: "bypassPermissions",
  run_in_background: true,
  model: "haiku",
  prompt: `Score this code review finding 0-100 for confidence that it is a real issue.
  Read the file [path] around line [line].
  Finding: [title] — [problem description]
  Suggested fix: [fix]
  Score 0=false positive, 50=plausible but unvalidated, 75=likely real, 100=mechanically confirmed.
  Reply with ONLY: {"score": N, "reason": "one sentence"}`
})
```

Use Haiku scores as a final filter:
- Haiku score < 30: Downgrade to "Low confidence — note only" regardless of Skeptic verdict
- Haiku score 30-60 + Skeptic confidence < 50: Downgrade to "Lower Confidence Items"
- Haiku score > 60: No change — trust the adversarial pipeline's verdict

This catches the edge case where Optimizer and Skeptic both agree on something that's actually
a false positive (groupthink), because Haiku sees each finding in isolation.

**Skip this pass if total confirmed findings < 3** — the overhead isn't worth it for small reviews.

## Step 8: Structured Report

Compile findings from all sources into:

| Source | Severity | File | Finding | Skeptic Verdict | Confidence | Status |
|--------|----------|------|---------|-----------------|------------|--------|
| Mechanical | ... | ... | ... | — | — | Fixed / Reported |
| PR Feedback | ... | ... | ... | — | — | Fixed / Skipped / Needs discussion |
| Optimizer | ... | ... | ... | Agree / Disagree / Modified | [0-100] | Fixed / Disputed / Deferred |
| Skeptic (missed) | ... | ... | ... | — | [0-100] | Fixed / Deferred |
| Pre-existing | 🟣 | ... | ... | — | — | Issue filed / Noted |

Report sections:
- **Summary**: What was added/modified/removed
- **Review Depth**: Which tier was used (skip / standard / full) and why
- **Mechanical Findings**: Issues caught by lint/typecheck/build/tests (free)
- **PR Feedback** (if PR/MR exists): Items addressed vs issues created vs dismissed
- **Consensus Fixes Applied**: Issues both agents agreed on that were auto-fixed (note which models flagged each)
- **Disputed Items** (requires author decision): Issues where models disagreed — present both sides with a recommendation
- **Lower Confidence Items**: Findings where only one model flagged it OR Skeptic confidence was 50-74 OR Haiku score was 30-60. Present as "worth a second look" rather than confirmed issues. These are NOT auto-fixed but are surfaced to the author for manual review.
- **Pre-existing Issues**: Bugs found in surrounding code not introduced by this PR (🟣)
- **Remaining Items**: 🟢 Minor and ⚪ Nit issues not auto-fixed (for author to decide)
- **Verification Loop Results**: How many fix-verify iterations ran, what passed/failed
- **Model Agreement Summary**: How many findings had full cross-model consensus vs split opinions
- **Recommendation**: Approve, Request Changes, or Comment

### Post findings as PR/MR comments (if PR/MR exists)

If a PR/MR exists, post findings as inline comments on the specific lines where issues were found.

**GitHub (`[platform]` = `github`):**
```bash
gh api repos/[owner]/[repo]/pulls/[number]/reviews --method POST \
  --field event=COMMENT \
  --field body="[summary comment]" \
  --field 'comments[]={ "path": "[file]", "line": [line], "body": "[finding]" }'
```

**GitLab (`[platform]` = `gitlab`):**
```bash
# Post summary note on MR
curl -X POST --header "PRIVATE-TOKEN: $TOKEN" \
  --header "Content-Type: application/json" \
  -d '{"body":"[summary comment]"}' \
  "$GITLAB_URL/api/v4/projects/[project_id]/merge_requests/[iid]/notes"

# Post inline discussion on specific lines
curl -X POST --header "PRIVATE-TOKEN: $TOKEN" \
  --header "Content-Type: application/json" \
  -d '{"body":"[finding]","position":{"base_sha":"[base_sha]","start_sha":"[start_sha]","head_sha":"[head_sha]","position_type":"text","new_path":"[file]","new_line":[line]}}' \
  "$GITLAB_URL/api/v4/projects/[project_id]/merge_requests/[iid]/discussions"
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

Write a self-contained summary to `[repo_root]/.claude/reviews/[branch_safe]/summary.md` that captures the full review outcome. This file is the **review artifact of record** — it survives after agent reports are cleaned up and contains everything needed to understand what was reviewed, decided, and deferred.

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

### Lower Confidence ([count])
[findings where only one model flagged it, Skeptic confidence was 50-74, or Haiku score
was 30-60 — worth a second look but not confirmed issues]

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

**Skip this step entirely if `[file-issues]` = `no`.** Note deferred/disputed items in the report only.

If `[file-issues]` = `yes`, create an issue for each deferred, disputed, or pre-existing item:

**GitHub (`[platform]` = `github`):**
```bash
gh issue create \
  --title "[severity emoji] [finding title]" \
  --label "code-review" \
  --label "[severity: critical|major|minor]" \
  --body "$(cat <<'ISSUE'
[ISSUE_BODY — see below]
ISSUE
)"
```

**GitLab (`[platform]` = `gitlab`):**
```bash
curl -X POST --header "PRIVATE-TOKEN: $TOKEN" \
  --header "Content-Type: application/json" \
  -d "$(cat <<'ISSUE'
{
  "title": "[severity emoji] [finding title]",
  "labels": "code-review,[severity: critical|major|minor]",
  "description": "[ISSUE_BODY — see below]"
}
ISSUE
)" \
  "$GITLAB_URL/api/v4/projects/[project_id]/issues"
```

**ISSUE_BODY** (shared by both platforms):
```markdown
## Problem

[problem description]

**File**: `[path]:[line]`
**Severity**: [severity]
**Category**: [category]

## Context

[Optimizer's reasoning for flagging this]

[Skeptic's challenge or agreement, if applicable]
**Skeptic confidence**: [0-100]

## Suggested fix

[concrete fix from the review]

## Source

- Review of PR/MR #[number] (`[branch]` → `[base]`)
- Review date: [YYYY-MM-DD]
- Review depth: [standard | full]
- [Link to review summary if available]

---
*Filed by [adversarial-review](https://github.com/ng/adversarial-review) plugin*
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
4. If PR/MR exists, re-request reviews:
   - GitHub: `gh api repos/[owner]/[repo]/pulls/<number>/requested_reviewers -f "reviewers[]=copilot-pull-request-reviewer[bot]"`
   - GitLab: No automated re-request — note in report that MR is ready for re-review
