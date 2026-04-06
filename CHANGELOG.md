# Changelog

## [1.4.0](https://github.com/ng/adversarial-review/compare/v1.3.0...v1.4.0) (2026-04-06)


### Features

* add GitHub Action for CI integration ([#12](https://github.com/ng/adversarial-review/issues/12)) ([0588a75](https://github.com/ng/adversarial-review/commit/0588a7530d84b4f02e480993d903aa33c77ec18c))
* auto-move major version tag on release for GHA consumers ([c0af300](https://github.com/ng/adversarial-review/commit/c0af300ab77b927a3f923278ebfd6c6fac4a71da))
* replace version-bump with release-please, extract changelog ([f01a12c](https://github.com/ng/adversarial-review/commit/f01a12c11b41cd2f3425d941e8a46ae2713a23cb))
* signal quality gates from OpenAI Codex review prompt ([#13](https://github.com/ng/adversarial-review/issues/13)) ([149f452](https://github.com/ng/adversarial-review/commit/149f452654e77b7de9a0f38be040d0f62e05532d))


### Bug Fixes

* default to no-fix mode for CI review-only workflow ([d3fa64c](https://github.com/ng/adversarial-review/commit/d3fa64c85e502021c579f0948395c5a146b405d7))
* shorten action description to under 125 chars for Marketplace ([47d6450](https://github.com/ng/adversarial-review/commit/47d6450da29291a6f03b95d2516097bb80460aaa))

## [1.4.0] — Signal quality gates

Signal-to-noise improvements adapted from [OpenAI Codex's review guidelines](https://github.com/openai/codex/blob/main/codex-rs/core/review_prompt.md).

- **Signal gate**: 8-point checklist every Optimizer finding must pass before being written up — actionable, introduced by this PR, calibrated to repo quality, no unstated assumptions, provably affected code identified. Silently drops findings that fail any check
- **Trigger field**: Findings now require a `Trigger` field specifying the scenarios, environments, or inputs needed for the bug to manifest (or "universal"). Forces reviewers to be concrete about when issues actually fire
- **Critical severity tightened**: 🔴 Critical is now reserved for universal issues that fire regardless of inputs/environment. Scenario-dependent bugs cap at 🟡 Major
- **Overall verdict**: Both Optimizer and Skeptic reports now end with a binary "patch is correct / patch is incorrect" verdict with 1-3 sentence justification
- **Tone guidance**: PR inline comments use matter-of-fact tone — no flattery, no overclaiming severity, immediately graspable by the author

## [1.3.0](https://github.com/ng/adversarial-review/compare/v1.2.2...v1.3.0) (2026-04-01)

Improvements informed by first-principles patterns from Claude Code's agent orchestration internals.

- **Anti-rationalization guards**: Skeptic prompt now explicitly names its failure modes (rubber-stamping, lazy disagreement), lists invalid verdict bases, and requires tool-output evidence for every Agree/Disagree verdict. New 🚫 Cannot verify verdict (confidence capped at 40) for when tools can't validate
- **Change-type classification**: Every changed file is mapped to a type (auth, database, crypto, api, frontend, infra, config, test, docs, types) with type-specific priority checks and activated lenses — agents focus on what matters for this specific PR instead of applying all lenses uniformly
- **Weighted escalation scoring**: Replaced binary "any trigger fires → full depth" with a point-based system. High-risk domains (auth/crypto/db) score +3, medium-risk (api/infra) +2, with de-escalation (-10) for pure docs/config/test changes. Score breakdown logged in report for auditability
- **Coordinator-only synthesis**: Lead operates in read-only mode during synthesis — source modifications restricted to the explicit "Apply agreed fixes" sub-step, preventing accidental edits during analysis
- **Prompt engineering**: Numeric word-count anchors (findings ≤50 words, fixes ≤30 words) reduce verbose reasoning. Fix Quality Guardrails prevent over-engineered suggestions (no premature abstractions, no feature flags for direct fixes, minimum viable change only)

## [1.2.2](https://github.com/ng/adversarial-review/compare/v1.2.1...v1.2.2) (2026-03-28)

- **Review artifacts moved**: `.claude/reviews/` → `.reviews/` — the `.claude/` directory is protected by Claude Code (settings/hooks/config), causing permission prompts even with `bypassPermissions`

## [1.2.1](https://github.com/ng/adversarial-review/compare/v1.1.0...v1.2.1) (2026-03-28)

Restructured adversarial review pipeline from background agents to agent teams.

- **Agent team orchestration**: Optimizer and Skeptic agents are now coordinated as teammates via `TeamCreate`, `TaskCreate` with explicit dependencies, and `SendMessage` for wake-up signals — replacing ad-hoc background agent spawning
- **Task dependency model**: Sequential pipeline constraints (Skeptic blocked until Optimizer merge completes) are now declarative via `addBlockedBy` rather than implicit wait-and-spawn
- **No worktree isolation**: Teammates run in the main repo (not worktrees) so they can write reports to `.reviews/` without permission prompts. Containment enforced by prompt constraints ("report only, do not modify source files")
- **Branch name sanitization**: `[branch_safe]` (slashes replaced with dashes) used in team names and directory paths to handle `feat/`, `fix/` branch conventions
- **Teams API semantics documented**: Spawn section documents sequential task IDs, idle notifications, `shutdown_request` protocol, and `TeamDelete` behavior
- **Auto-fix by default**: Auto-fix now runs by default (no flag required). Use `--no-fix` to opt out and get review-only mode (no code modifications)

## [1.1.0](https://github.com/ng/adversarial-review/compare/v1.0.0...v1.1.0) (2026-03-17)

Improvements informed by head-to-head comparison with Anthropic's official code-review plugin.

- **Specialized Optimizer lenses**: Added git history, code comment compliance, and prior review pattern lenses to catch regressions against intentional guards, stale comments, and reintroduced issues
- **Skeptic confidence scoring**: Each Skeptic verdict now includes a 0-100 confidence score (0=guess, 50=reasoning only, 75=tool-validated, 100=mechanically confirmed) with filtering rules that downgrade low-confidence agreements and preserve weak disagreements
- **Haiku scoring pass**: Optional post-synthesis pass launches parallel Haiku agents per finding to independently score confidence without adversarial context, catching groupthink false positives
- **Lower confidence report section**: Findings where only one model flagged it, Skeptic confidence was 50-74, or Haiku score was marginal are surfaced as "worth a second look" rather than dropped
- **Independent Skeptic assessment**: Skeptic now reads the diff and forms impressions before seeing Optimizer findings, strengthening its ability to catch false positives and find missed issues
- **GitLab support**: Platform auto-detection via `git remote -v`, with GitLab API support for MR metadata, inline discussions, issue filing, and pipeline status (via `$GITLAB_PAT` / `$GITLAB_ORG_PAT`)
- **Post-review issue filing**: Issue creation offered after the review completes rather than blocking at the start

## [1.0.0](https://github.com/ng/adversarial-review/releases/tag/v1.0.0) (2026-03-14)

Initial release.

- Adversarial multi-model code review with Optimizer/Skeptic pipeline
- Progressive cost-gating: skip (docs only), standard (2 agents), full (4 agents)
- Mechanical checks (lint, typecheck, build, tests) before LLM spend
- Auto-fix mode with bounded verification loop (max 2 iterations)
- Cross-model consensus signals (Sonnet + Opus)
- GitHub PR feedback integration (CodeRabbit, Copilot, human comments)
- Deception detection lens for misleading names/comments
- Inline PR comment posting and persistent `summary.md` artifact
- Issue filing for deferred, disputed, and pre-existing items
