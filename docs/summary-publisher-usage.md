# Summary publisher (single-host operation)

The CLI can plan, publish, or recover a persistent review summary on GitHub or
GitLab. Both native review skills now direct configured runs to this CLI; an
operator must supply a trusted installation, configuration and start-time run
ordering. This is instruction-level integration, not a managed CI deployment or
evidence of a successful live review-to-publish run. Inline finding threads are
not reconciled by this command. Do not fall back to posting a fresh summary when
an update fails; that can duplicate an already successful write.

## Trust and coordination

Run the publisher from a trusted installation, not a checked-out PR's modified
scripts. The operator configuration must likewise live outside attacker-controlled
review artifacts. Tokens are read from the named environment variable, not JSON
or command-line arguments. Use a user/PAT credential that supports `/user`.

Every publisher for a PR/MR must run on the same host and use the same persistent
coordinator directory. Do not use separate ephemeral CI directories, and do not
assume NFS or a shared-looking path provides the local filesystem guarantees.
Keep coordinator state across runs; deleting it loses ordering and uncertain-write
protection. Select `single-host` only when this deployment condition actually holds.
The CLI cannot discover other publishers or prove that condition itself.

Assign an increasing integer run version **when each review starts**, from one
trusted ordering source for the PR/MR. Never derive it from model output, completion
order, or a timestamp that may collide. A consumed version cannot be reused, even
after a pre-write failure. Multi-host CI coordination remains unsupported.

## Inputs

Example operator config for GitHub (replace paths and target):

```json
{
  "provider": "github",
  "repository": "OWNER/REPO",
  "number": 123,
  "scope": "full branch",
  "channel": "combined",
  "token_env": "REVIEW_PUBLISH_TOKEN",
  "coordination": {
    "kind": "single-host",
    "directory": "/absolute/persistent/private/review-publisher-state"
  }
}
```

For GitLab, replace `repository` with `origin` (such as
`https://gitlab.example.com`) and numeric `project_id`, and use `provider: gitlab`.
`number` is the MR IID. The factory binds the adapter and transport to that same
origin. Custom URL subpaths are not supported. For a scoped review, replace
`full branch` with its canonical scope; the risk renderer will not claim full
coverage for that review.

Review JSON has only these top-level fields:

```json
{
  "adjudication": {
    "reviewed_head": "FULL_40_OR_64_CHARACTER_LOWERCASE_COMMIT_HASH",
    "completed": true,
    "material_unknowns": false,
    "findings": []
  },
  "details": "Self-contained final review, evidence, findings and limitations."
}
```

Replace the hash placeholder before use. Each finding has exactly `id` (unique
string without control characters or the reserved summary marker), `support`
(`supported`, `contradicted`, or `unresolved`), `impact`
(`important`, `minor`, `cleanup`, or `unknown`), and `introduced` (boolean).
Use final adjudicated findings and truthful coverage; the publisher cannot prove
that the review or adjudication is correct. Do not omit an old unresolved finding
merely because a later model response did not mention it.

## Commands

Read-only provider inspection and planning is the default. It needs authentication
but neither sends writes nor creates coordinator state:

```bash
python3 /trusted/adversarial-review/scripts/publish_summary.py --config /operator/publisher.json --review /reviews/final.json
```

Publish explicitly, supplying the version allocated at review start:

```bash
python3 /trusted/adversarial-review/scripts/publish_summary.py --config /operator/publisher.json --review /reviews/final.json --mode publish --run-version 17
```

The command recomputes its plan under the coordinator lock; a prior plan is not
authorization to replay its API request. It updates only a uniquely owned marked
summary, preserves other comments, and makes no write for unchanged or stale
results. Summary bodies include the reviewed commit and scope. A last-instant push
can still race the API write, so this is not an atomic current-head guarantee.
Successful create, update and no-op results contain `action`, `comment_id` and
`reviewed_head`; unlike a read-only plan, they do not return the comment body or
planning preconditions. Stale skips contain the reviewed and current heads.

After a write with an uncertain outcome, exclude/account for delayed requests and
uncoordinated writers, then inspect the actual remote state using recovery:

```bash
python3 /trusted/adversarial-review/scripts/publish_summary.py --config /operator/publisher.json --mode recover
```

Recovery performs provider reads only, but updates local coordinator state when
the intended remote body is uniquely observed. Absence or ambiguity stays blocked.
Closed/merged changes can be inspected for recovery, but cannot receive new
publications. Recovering an observed historical write does not reopen the change.
The CLI never retries or deletes a remote comment to resolve that uncertainty.
Errors exit nonzero without printing arbitrary provider payloads or credentials.
Consult the private coordinator JSON for status, but do not edit it to bypass a
pending/uncertain result. CLI output and state can contain private review content.

Tests exercise both providers with mocked requests, including recovery after a
remote write succeeds but its response is lost. Live authentication, permissions,
and service behavior have not been validated by those tests.
