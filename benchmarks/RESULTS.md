# Adversarial reviewer benchmark results

Generated: 2026-09-09T18:06:08.775837+00:00

**Status: in progress; all planned trials require recorded outcomes and successful reviews require evaluation.**

| Benchmark | Planned PRs | Configuration | Completed reviews | Failed attempts (includes budget failures) | Scored |
|---|---:|---|---:|---:|---:|
| martian | 50 | single | 18 | 1 | 17 |
| martian | 50 | adversarial | 2 | 7 | 2 |
| martian | 50 | cross-provider | 2 | 7 | 2 |
| swe-prbench | 350 | single | 13 | 1 | 12 |
| swe-prbench | 350 | adversarial | 3 | 1 | 3 |
| swe-prbench | 350 | cross-provider | 0 | 1 | 0 |
| c-crab | 184 | single | 15 | 1 | 7 |
| c-crab | 184 | adversarial | 2 | 1 | 2 |
| c-crab | 184 | cross-provider | 1 | 1 | 1 |

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
| c-crab test pass rate (macro) | 1 | single | — | 0.0% | — | — | — |
| c-crab test pass rate (macro) | 1 | adversarial | — | 0.0% | — | — | — |
| c-crab test pass rate (macro) | 1 | cross-provider | — | 0.0% | — | — | — |

## Observed review resource use

**Authentication: signed-in Claude subscription and ChatGPT/Codex subscription; no API keys configured.**
Review wall time excludes repository preparation. Token counts below include cached input and Claude
subagent usage when reported by the CLI; nested Codex usage is separate. The CLI also emits
`total_cost_usd`, an API-equivalent estimate retained in raw metadata, not a billing receipt.

| Benchmark | Configuration | Completed reviews | Median seconds | Claude input tokens (incl. cache) | Claude output tokens |
|---|---|---:|---:|---:|---:|
| martian | single | 18 | 268.4 | 22729807 | 378842 |
| martian | adversarial | 2 | 830.0 | 9274218 | 143918 |
| martian | cross-provider | 2 | 1324.9 | 14999034 | 307391 |
| swe-prbench | single | 13 | 226.2 | 22299177 | 268583 |
| swe-prbench | adversarial | 3 | 727.9 | 14286609 | 232775 |
| swe-prbench | cross-provider | 0 | — | — | — |
| c-crab | single | 15 | 146.0 | 13573309 | 208107 |
| c-crab | adversarial | 2 | 932.2 | 8305615 | 178729 |
| c-crab | cross-provider | 1 | 1187.5 | 8143761 | 123573 |

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

- `martian/calcom__cal.com-10967/single`: Subscription rejected this request; batch paused without API fallback.
- `martian/ai-code-review-evaluation__discourse-graphite-10/adversarial`: Review timed out; partial output retained, excluded from quality scores.
- `martian/ai-code-review-evaluation__discourse-graphite-3/adversarial`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object e25638dab0d4b98f99c8fe8976ccaae8f4fb9db3

- `martian/calcom__cal.com-11059/adversarial`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object bc89fe00ea84d20bedcec782f0701b9711dc8201

- `martian/getsentry__sentry-80168/adversarial`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object bdd229e3f22e307fe40b30ef99e92ff3f6723da4

- `martian/ai-code-review-evaluation__sentry-greptile-2/adversarial`: Subscription rejected this request; batch paused without API fallback.
- `martian/grafana__grafana-80329/adversarial`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object a886bd3c79a417a70b51509384d1f1ec3e87e96b

- `martian/ai-code-review-evaluation__keycloak-greptile-1/adversarial`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object 30f804af450dec523909a52f2a4b97302d27f5cc

- `martian/ai-code-review-evaluation__discourse-graphite-3/cross-provider`: Subscription rejected this request; batch paused without API fallback.
- `martian/getsentry__sentry-77754/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object bb5a6837cb5b3d8d3b174e17d42ec14486ef8738

- `martian/calcom__cal.com-11059/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object bc89fe00ea84d20bedcec782f0701b9711dc8201

- `martian/getsentry__sentry-80168/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object bdd229e3f22e307fe40b30ef99e92ff3f6723da4

- `martian/ai-code-review-evaluation__sentry-greptile-2/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object 28e3db2520d4ea28c57b08da57b83917ba7b2e15

- `martian/grafana__grafana-80329/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object a886bd3c79a417a70b51509384d1f1ec3e87e96b

- `martian/ai-code-review-evaluation__keycloak-greptile-1/cross-provider`: ['git', 'update-ref', 'refs/remotes/origin/main'] failed (128): fatal: update_ref failed for ref 'refs/remotes/origin/main': cannot update ref 'refs/remotes/origin/main': trying to write ref 'refs/remotes/origin/main' with nonexistent object 30f804af450dec523909a52f2a4b97302d27f5cc

- `swe-prbench/chia-blockchain__19848/single`: Subscription rejected this request; batch paused without API fallback.
- `swe-prbench/pipecat__3084/adversarial`: Subscription rejected this request; batch paused without API fallback.
- `swe-prbench/server__8570/cross-provider`: Subscription rejected this request; batch paused without API fallback.
- `c-crab/zulip__zulip-25349@67de2a4/single`: Subscription rejected this request; batch paused without API fallback.
- `c-crab/ansible__ansible-27435@da1a331/adversarial`: Subscription rejected this request; batch paused without API fallback.
- `c-crab/deepset-ai__haystack-92@accd8b1/cross-provider`: Subscription rejected this request; batch paused without API fallback.
