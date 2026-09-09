# Adversarial reviewer benchmark results

Generated: 2026-09-09T10:07:50.393334+00:00

**Status: incomplete until every requested review and evaluation has succeeded.**

| Benchmark | Planned PRs | Configuration | Completed reviews | Failed attempts awaiting retry | Scored |
|---|---:|---|---:|---:|---:|
| martian | 50 | single | 11 | 0 | 10 |
| martian | 50 | adversarial | 1 | 7 | 1 |
| martian | 50 | cross-provider | 1 | 7 | 1 |
| swe-prbench | 350 | single | 4 | 0 | 3 |
| swe-prbench | 350 | adversarial | 1 | 0 | 1 |
| swe-prbench | 350 | cross-provider | 0 | 1 | 0 |
| c-crab | 184 | single | 1 | 0 | 1 |
| c-crab | 184 | adversarial | 0 | 0 | 0 |
| c-crab | 184 | cross-provider | 0 | 0 | 0 |

## Quality on paired completed cases

Only cases with scores for all three configurations enter this comparison.
Scores use the adapted evaluation described in the runbook; they are not published leaderboard scores.

| Benchmark/profile | Paired PRs | Configuration | Precision | Recall | F1 | Gold lost after Skeptic | Net unmatched removed |
|---|---:|---|---:|---:|---:|---:|---:|
| martian/strict | 1 | single | 100.0% | 33.3% | 50.0% | 0 | 0 |
| martian/core | 1 | single | 100.0% | 33.3% | 50.0% | 0 | 0 |
| martian/all | 1 | single | 100.0% | 33.3% | 50.0% | 0 | 0 |
| martian/strict | 1 | adversarial | 25.0% | 50.0% | 33.3% | 0 | -3 |
| martian/core | 1 | adversarial | 25.0% | 50.0% | 33.3% | 0 | -3 |
| martian/all | 1 | adversarial | 25.0% | 50.0% | 33.3% | 0 | -3 |
| martian/strict | 1 | cross-provider | 22.7% | 83.3% | 35.7% | 0 | -4 |
| martian/core | 1 | cross-provider | 22.7% | 83.3% | 35.7% | 0 | -4 |
| martian/all | 1 | cross-provider | 22.7% | 83.3% | 35.7% | 0 | -4 |
| swe-prbench | 0 | All | — | — | — | — | — |
| c-crab | 0 | All | — | — | — | — | — |

## Observed review resource use

**Authentication: signed-in Claude subscription and ChatGPT/Codex subscription; no API keys configured.**
Review wall time excludes repository preparation. Token counts below include cached input and Claude
subagent usage when reported by the CLI; nested Codex usage is separate. The CLI also emits
`total_cost_usd`, an API-equivalent estimate retained in raw metadata, not a billing receipt.

| Benchmark | Configuration | Completed reviews | Median seconds | Claude input tokens (incl. cache) | Claude output tokens |
|---|---|---:|---:|---:|---:|
| martian | single | 11 | 219.5 | 13185771 | 213334 |
| martian | adversarial | 1 | 1023.8 | 6559415 | 97360 |
| martian | cross-provider | 1 | 1024.5 | 7193592 | 104081 |
| swe-prbench | single | 4 | 187.6 | 6042168 | 72623 |
| swe-prbench | adversarial | 1 | 1376.8 | 6936972 | 124165 |
| swe-prbench | cross-provider | 0 | — | — | — |
| c-crab | single | 1 | 235.8 | 779392 | 20615 |
| c-crab | adversarial | 0 | — | — | — |
| c-crab | cross-provider | 0 | — | — | — |

## Source pins

Plugin commit: `6aff53cbc1e66e7b5f588fb5526da52b77695f54`; file hashes in `lock.json`.

- martian: `e616e849755441da38f18bf3adba2c9583b03803` (https://github.com/withmartian/code-review-benchmark.git)
- swe-prbench: `379f0bfd8978a1734cd8399e115d04d4fdceeb89` (https://github.com/FoundryHQ-AI/swe-prbench.git)
- swe-prbench-data: `b87f5797aef3ed2c3153bb1304ea4d801d36ba6e` (https://huggingface.co/datasets/foundry-ai/swe-prbench)
- c-crab: `856dfa3102b8996d168c4f195217b7603e1d1bc6` (https://github.com/c-CRAB-Benchmark/dataset.git)

## Reproduction

See [the experiment runbook](README.md). Raw data, locked inputs, prompts, events, usage,
and per-case status are in `/private/tmp/adversarial-review-benchmarks`. Published benchmark scores are not our results.

No missing, failed, or unscored review is treated as a zero-finding successful review.

## Failures

- `martian/ai-code-review-evaluation__discourse-graphite-3/adversarial`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object e25638dab0d4b98f99c8fe8976ccaae8f4fb9db3

- `martian/getsentry__sentry-77754/adversarial`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object bb5a6837cb5b3d8d3b174e17d42ec14486ef8738

- `martian/calcom__cal.com-11059/adversarial`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object bc89fe00ea84d20bedcec782f0701b9711dc8201

- `martian/getsentry__sentry-80168/adversarial`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object bdd229e3f22e307fe40b30ef99e92ff3f6723da4

- `martian/ai-code-review-evaluation__sentry-greptile-2/adversarial`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object 28e3db2520d4ea28c57b08da57b83917ba7b2e15

- `martian/grafana__grafana-80329/adversarial`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object a886bd3c79a417a70b51509384d1f1ec3e87e96b

- `martian/ai-code-review-evaluation__keycloak-greptile-1/adversarial`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object 30f804af450dec523909a52f2a4b97302d27f5cc

- `martian/ai-code-review-evaluation__discourse-graphite-3/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object e25638dab0d4b98f99c8fe8976ccaae8f4fb9db3

- `martian/getsentry__sentry-77754/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object bb5a6837cb5b3d8d3b174e17d42ec14486ef8738

- `martian/calcom__cal.com-11059/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object bc89fe00ea84d20bedcec782f0701b9711dc8201

- `martian/getsentry__sentry-80168/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object bdd229e3f22e307fe40b30ef99e92ff3f6723da4

- `martian/ai-code-review-evaluation__sentry-greptile-2/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object 28e3db2520d4ea28c57b08da57b83917ba7b2e15

- `martian/grafana__grafana-80329/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object a886bd3c79a417a70b51509384d1f1ec3e87e96b

- `martian/ai-code-review-evaluation__keycloak-greptile-1/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object 30f804af450dec523909a52f2a4b97302d27f5cc

- `swe-prbench/server__8570/cross-provider`: Pilot stopped: verified artifact-write permission mismatch; full native mini model unavailable with ChatGPT login. Raw attempt retained.
