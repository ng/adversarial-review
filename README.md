# adversarial-review

Claude Code plugin for adversarial multi-model code review.

Two AI agents — **The Optimizer** and **The Skeptic** — review your code independently across both Sonnet and Opus, then challenge each other's findings. Only consensus issues get auto-fixed; disputes are presented for your decision.

## Install

```
/plugin marketplace add ng/adversarial-review
/plugin install adversarial-review
```

## Usage

```
/adversarial-review:code-review        # review current branch
/adversarial-review:code-review 405    # review PR #405
```

## How it works

```mermaid
flowchart TD
    Start(["/adversarial-review:code-review"]) --> Context["Step 1: Get Context\ngit diff, branch, PR detection"]
    Context --> PR{PR exists?}
    PR -->|Yes| Feedback["Step 2: Pull GitHub Feedback\nCodeRabbit · Copilot · Human reviews"]
    PR -->|No| Docs
    Feedback --> Triage["Step 3: Triage Feedback\nFix now · Create issue · Dismiss"]
    Triage --> Docs["Step 4: Read Convention Docs\n.claude/docs/code-review.md\n.claude/docs/architecture.md"]

    Docs --> Optimizer

    subgraph Pass1["Pass 1 — The Optimizer"]
        Optimizer["Find every issue worth fixing"]
        OptSonnet["Sonnet agent\n(worktree)"]
        OptOpus["Opus agent\n(worktree)"]
        MergeOpt["Merge & deduplicate\nfindings"]
        Optimizer --> OptSonnet & OptOpus
        OptSonnet & OptOpus --> MergeOpt
    end

    MergeOpt --> Skeptic

    subgraph Pass2["Pass 2 — The Skeptic"]
        Skeptic["Challenge findings +\ncatch missed issues"]
        SkpSonnet["Sonnet agent\n(worktree)"]
        SkpOpus["Opus agent\n(worktree)"]
        MergeSkp["Merge challenges"]
        Skeptic --> SkpSonnet & SkpOpus
        SkpSonnet & SkpOpus --> MergeSkp
    end

    MergeSkp --> Confidence

    subgraph Synthesis["Step 6 — Synthesize"]
        Confidence{"Cross-model\nconsensus?"}
        AutoFix["Auto-fix\nCritical/Major"]
        Dispute["Present dispute\nto author"]
        Note["Note for author\n(Minor/Nit)"]
        Confidence -->|"Both models agree"| AutoFix
        Confidence -->|"Models disagree"| Dispute
        Confidence -->|"Low confidence"| Note
    end

    AutoFix & Dispute & Note --> Report["Step 7: Structured Report\nFindings · Disputes · Recommendation"]
    Report --> Done([Author reviews & approves])
```

1. Pulls existing GitHub PR feedback (CodeRabbit, Copilot, human reviewers)
2. Reviews against your project's `.claude/docs/` convention files
3. Runs **The Optimizer** (Sonnet + Opus in parallel) — finds every issue worth fixing
4. Runs **The Skeptic** (Sonnet + Opus in parallel) — challenges findings, catches what was missed
5. Cross-model consensus matrix determines confidence level per finding
6. Auto-fixes high-confidence Critical/Major issues; presents disputes for author decision

## Project-specific lenses

The plugin reads `.claude/docs/code-review.md` from your repo for domain-specific review criteria. Without it, universal lenses apply (security, performance, correctness, architecture, type safety, test coverage).

## License

MIT
