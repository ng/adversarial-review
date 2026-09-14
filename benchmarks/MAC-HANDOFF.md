# Resume the prompt comparison on macOS

Use branch `prompt-evaluation-handoff`, which packages the prompt changes,
`scripts/`, their tests, the new publishing docs, and `PROMPT-EVALUATION.md` for
transfer to macOS. Do not copy the retired pilot harness back into the repository.
The archive and raw trial artifacts mentioned in the evaluation notes are local
to the Linux workspace and are not included in the branch.

## First checks (from the repository root)

```bash
uname -s
test -x /usr/bin/sandbox-exec
python3 --version
git lfs version
uv --version
claude --version
docker info
python3 -m unittest discover -s benchmarks -p 'test_*.py'
```

Expected platform: Darwin. Use Python 3.12+, authenticated Claude and Codex CLIs,
and Docker with Linux/amd64 support for c-CRAB. Do not transfer credentials from
this workspace. The last Linux test run passed 106 tests with one macOS-only skip;
the skipped isolation test should run on Mac. Tests are setup checks, not reviewer
accuracy measurements.

## Resume instructions for the agent

Read `PROMPT-EVALUATION.md`, then use `run.py`, `score.py`, `ccrab.py` and
`prepare_scopes.py`. No new source tools, execution runtimes or review frameworks.

Before model calls:

- Freeze two plugin snapshots: committed original review instructions at
  `d170f2de668f11921b7de63d6307dfe7553e103a` and the candidate evidence/synthesis
  changes. Keep publishing instructions identical and disable publication.
- Use separate fresh durable work roots for the snapshots. Bootstrap copies the
  current plugin into each root; ensure the intended snapshot is present first.
  Do not alter a bootstrapped snapshot or resume the missing original workspace.
- Set the same exact available lead/judge models and budgets for both arms before
  bootstrap. `experiment.json` contains historical settings, not approved current
  access evidence. User-specified Opus names are `claude-opus-4-6[1m]` and
  `claude-opus-4-8[1m]`. Keep native lane model choices identical across arms.
- Start with the existing deterministic selection at `--limit 3` (three cases per
  suite), record the nine case IDs and overlap/exposure, and hold them fixed across
  both arms. Use `--variant adversarial`: `single` versus `adversarial` is a workflow
  comparison, not the requested original-versus-candidate prompt comparison.
- Validate comparison scopes using `prepare_scopes.py` before reviews. If a case
  cannot run, record it; do not silently replace it based on results. Review sample
  coverage before launch; absence of important-defect opportunities limits what
  can be concluded about retention. Do not claim a small pilot proves superiority.

Then run and score the same cases in both roots with the documented existing
commands. Use distinct report output paths so historical `RESULTS.md` is not
overwritten. Record pre-/post-Skeptic findings and manually adjudicate unsupported
claims, lost important defects, severity and harmful advice alongside suite scores,
cost and latency. Report c-CRAB repair/test limitations separately. No result from
the retired exposed Haystack trials is a clean accuracy baseline.

The Linux session launched no new benchmark calls for this comparison. Execution
awaits this Mac environment; prompt snapshots and nine-case selection are not yet
frozen. Do not describe preparation as completed evaluation.
