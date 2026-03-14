---
name: code-review
description: Adversarial multi-model code review. Dual Optimizer/Skeptic agents (Sonnet + Opus) challenge each other's findings. Pulls GitHub PR feedback, reviews against project conventions, auto-fixes consensus issues, presents disputes for author decision.
---

Review all code changes on the current branch that have not been merged yet.

Optionally pass a PR number as argument: `/code-review 405`. If no number is given, auto-detect via `gh pr view --json number`.

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
- `.claude/docs/code-review.md` — domain-specific review checklist
- `.claude/docs/architecture.md` — system architecture context
- `.claude/docs/trust-boundaries.md` — security patterns

Read whatever exists. These docs contain project-specific review lenses that the adversarial agents will reference.

## Step 5: Adversarial Agent Review

For new features, refactors, UI changes, or security-sensitive changes, run the adversarial pipeline below. For simple typo/doc/config fixes, skip to Step 7.

**Important**: Neither agent auto-fixes code. Both produce reports only. The main context synthesizes and applies fixes after both agents complete. This prevents merge conflicts and gives the user control over disputed items.

**Model diversity**: Each pass runs on BOTH Sonnet and Opus in parallel, then merges their findings. Different models have different blind spots — running both maximizes coverage within each pass, and the adversarial structure (Optimizer vs Skeptic) catches over-corrections across passes.

### Pass 1 — The Optimizer (Sonnet + Opus in parallel)

Launch TWO agents in parallel (same prompt, different models). Both run in worktrees and produce findings reports — neither modifies source files.

```
// Launch BOTH in a single message (parallel tool calls):

Agent({
  name: "optimizer-sonnet",
  subagent_type: "general-purpose",
  isolation: "worktree",
  mode: "bypassPermissions",
  run_in_background: true,
  model: "sonnet",
  prompt: `You are "The Optimizer (Sonnet)" — reviewing branch [branch].
  [OPTIMIZER_PROMPT — see below]
  Write findings to /tmp/code-review-optimizer-sonnet-[branch].md`
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
  Write findings to /tmp/code-review-optimizer-opus-[branch].md`
})
```

**OPTIMIZER_PROMPT** (shared by both agents):

```
YOUR ROLE: Find every issue worth fixing. Be thorough and constructive.
CONSTRAINT: Do NOT modify any source files. Write your findings to a report file only.

1. WALKTHROUGH FIRST: Before looking for issues, write a 2-3 sentence summary of what
   this branch does and why. Understand the intent before critiquing the implementation.
   This goes in the Summary section of your report.

2. Read ALL changed files: git diff origin/[base]...HEAD

3. Read `.claude/docs/code-review.md` (if it exists) for the project's domain-specific
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

   PLUS any domain-specific lenses from the project's `.claude/docs/code-review.md`.

6. Write your findings in this exact format:

   # Optimizer Findings ([model]) — [branch]

   ## Summary
   [2-3 sentence walkthrough of what this PR does and why]

   Overall code quality assessment.

   ## Findings

   ### Finding 1: [title]
   - **File**: [path]:[line number]
   - **Severity**: 🔴 Critical | 🟡 Major | 🟢 Minor | ⚪ Nit
   - **Category**: [Security | Performance | Correctness | Pattern | Type Safety | Architecture | Testing | Completeness]
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

7. Do NOT commit, push, or modify source files. Report only.
```

Wait for BOTH Optimizer agents to complete. Then merge their findings:
1. Read both `/tmp/code-review-optimizer-sonnet-[branch].md` and `/tmp/code-review-optimizer-opus-[branch].md`
2. Deduplicate findings that both models flagged (these are high-confidence issues)
3. Write a merged report to `/tmp/code-review-optimizer-[branch].md` noting which findings came from which model, and which were flagged by both

### Pass 2 — The Skeptic (Sonnet + Opus in parallel)

Launch TWO agents in parallel. Both read the merged Optimizer findings AND the code. Both challenge suggestions and catch missed issues.

```
// Launch BOTH in a single message (parallel tool calls):

Agent({
  name: "skeptic-sonnet",
  subagent_type: "general-purpose",
  isolation: "worktree",
  mode: "bypassPermissions",
  run_in_background: true,
  model: "sonnet",
  prompt: `You are "The Skeptic (Sonnet)" — challenging the Optimizer findings for branch [branch].
  [SKEPTIC_PROMPT — see below]
  Write challenge report to /tmp/code-review-skeptic-sonnet-[branch].md`
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
  Write challenge report to /tmp/code-review-skeptic-opus-[branch].md`
})
```

**SKEPTIC_PROMPT** (shared by both agents):

```
YOUR ROLE: Challenge The Optimizer's findings. Find flaws in their suggestions. Catch what they missed.
CONSTRAINT: Do NOT modify any source files. Write your challenge report only.

1. Read The Optimizer's merged findings: /tmp/code-review-optimizer-[branch].md
2. Read ALL changed files: git diff origin/[base]...HEAD
3. Read `.claude/docs/code-review.md` (if it exists) for project context.
   Also read any other relevant `.claude/docs/` files.

For EACH of The Optimizer's findings, evaluate:
- Is the issue real or a false positive?
- Would the suggested fix introduce new bugs, breaking changes, or regressions?
- Is the fix over-engineered for the actual risk?
- Does the severity rating match the actual impact?
- Is there a simpler or safer alternative?

REQUIREMENT: You MUST challenge at least 2 of The Optimizer's findings with substantive
objections (not just "I agree"). Push back where the suggestion is risky, wrong,
premature, or over-engineered.

Then, independently review the code for issues The Optimizer missed, especially:
- Edge cases: empty/null/boundary values, partial input, malformed responses
- Race conditions: cleanup, stale responses, timing issues
- Accessibility: ARIA labels, keyboard nav, screen reader support
- UX gaps: loading states, error feedback, empty states, confirmation dialogs
- Consistency: naming patterns, style, import ordering
- Blast radius: could this change break existing behavior or downstream consumers?

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
   - **Severity**: 🔴 Critical | 🟡 Major | 🟢 Minor | ⚪ Nit
   - **Category**: [Edge Case | Race Condition | Accessibility | UX | Consistency | Blast Radius]
   - **Problem**: [what is wrong]
   - **Suggested fix**: [concrete code change or approach]

   ## Statistics
   - Optimizer findings challenged: [count]
   - Findings agreed with: [count]
   - Findings agreed with modifications: [count]
   - New issues found: [count]

5. Do NOT commit, push, or modify source files. Report only.
```

Wait for BOTH Skeptic agents to complete. Then merge:
1. Read both `/tmp/code-review-skeptic-sonnet-[branch].md` and `/tmp/code-review-skeptic-opus-[branch].md`
2. For each Optimizer finding: note where both Skeptics agree vs disagree (cross-model consensus strengthens the signal)
3. Write a merged report to `/tmp/code-review-skeptic-[branch].md`

## Step 6: Synthesize and Apply

Read both merged reports:
1. `/tmp/code-review-optimizer-[branch].md`
2. `/tmp/code-review-skeptic-[branch].md`

### Cross-model confidence signals

Use model agreement to gauge confidence:

| Signal | Meaning |
|--------|---------|
| Both Optimizer models flagged it + both Skeptic models agree | Very high confidence — auto-fix |
| One Optimizer model flagged it + both Skeptic models agree | High confidence — auto-fix |
| Both Optimizer models flagged it + Skeptic models disagree | Disputed — present to user |
| Only one model flagged + only one Skeptic agrees | Low confidence — note but don't auto-fix |

### Resolve each finding

For each Optimizer finding, cross-reference The Skeptic's verdict:

| Skeptic Verdict | Action |
|-----------------|--------|
| ✅ Agree | Apply the fix (Critical/Major) or note it (Minor/Nit) |
| ⚠️ Disagree | Present the dispute to the user — do NOT auto-fix |
| 🔄 Agree with modifications | Apply the modified version (Critical/Major) or note it (Minor/Nit) |

For Skeptic's missed issues: treat as new findings and apply Critical/Major fixes.

### Apply agreed fixes

1. Fix all undisputed 🔴 Critical and 🟡 Major issues
2. Run the project's validation commands (check CLAUDE.md for typecheck/build/lint/validate commands)
3. If fixes were applied, commit: `fix: address code review findings`
4. Do NOT push yet — present the report first

## Step 7: Structured Report

Compile findings from all sources into:

| Source | Severity | File | Finding | Skeptic Verdict | Status |
|--------|----------|------|---------|-----------------|--------|
| GitHub | ...      | ...  | ...     | —               | Fixed / Skipped / Needs discussion |
| Optimizer | ...   | ...  | ...     | Agree / Disagree / Modified | Fixed / Disputed / Deferred |
| Skeptic (missed) | ... | ... | ...  | —               | Fixed / Deferred |

Report sections:
- **Summary**: What was added/modified/removed
- **GitHub Feedback** (if PR exists): Items addressed vs issues created vs dismissed
- **Consensus Fixes Applied**: Issues both agents agreed on that were auto-fixed (note which models flagged each)
- **Disputed Items** (requires author decision): Issues where models disagreed — present both sides with a recommendation
- **Remaining Items**: 🟢 Minor and ⚪ Nit issues not auto-fixed (for author to decide)
- **Model Agreement Summary**: How many findings had full cross-model consensus vs split opinions
- **Recommendation**: Approve, Request Changes, or Comment

After the user reviews disputed items and remaining items:
1. Apply any additional fixes the user approves
2. Re-run validation commands
3. Commit and push
4. If PR exists, re-request reviews: `gh api repos/[owner]/[repo]/pulls/<number>/requested_reviewers -f "reviewers[]=copilot-pull-request-reviewer[bot]"`
