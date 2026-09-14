# Inline finding reconciliation: development planner

`scripts/reconcile_findings.py` now plans updates to existing root comments using
explicit, SHA-bound correspondence adjudication. It does not publish comments,
discover ownership, or automatically establish that two reports describe the same
defect. Native review instructions remain unchanged for inline publication.

The reviewer must compare the underlying failure, trigger, and affected operation
against source and existing discussion. Per-run finding IDs and line numbers are
not stable identities. A moved line may still describe the same defect; two
different defects can occupy the same line. The planner requires a written
explanation and the reviewed commit for every existing/new determination, but
these fields are assertions, not independent proof of correspondence.

For an existing issue, the plan targets the same bot-owned managed root comment.
Its body records the current source location and commit without relocating the
original thread. Replies are never update targets. An unchanged body produces
no write. Unknown targets, multiple findings matched to one thread, human-owned
or unmanaged roots, and already-resolved threads require manual adjudication.
Omitted prior findings remain untouched; omission is never evidence of a fix.
There are no delete, resolve, or reopen actions.

Plans now include a digest of the complete normalized discussion, including human
and unmatched threads and all replies. A new reply or edited discussion changes
the plan even when the intended root body is unchanged. An adapter must require
fresh adjudication after such a change, not just regenerate and publish a new
digest around the old correspondence decision. The digest detects snapshot drift;
it does not prove that the reviewer read or understood that snapshot. Pagination
must include every reply, not merely all top-level threads.

Before enabling publication, provider adapters still need to:

- Fetch complete thread state for the correct PR/MR and canonical scope, and
  establish managed ownership from a trusted durable registry. Do not accept
  `managed`, author identity, or thread state from model-produced JSON.
- Validate the current location against the pinned diff for a new inline comment.
- Bind plans to the provider/repository/PR/scope and serialize them with summary
  publishing, rechecking SHA, ownership, resolution, prior body hash, and the
  complete discussion digest.
- Persist create/update intent and uncertain outcomes before writes, with no
  blind retries. Record newly created thread identities before admitting reruns.
- Capture the entire discussion for correspondence adjudication while preserving
  human replies. Provide an explicit verification protocol before adding any
  automatic resolution or reopening.

The planner's create action alone is not idempotent: repeat safety requires the
adapter's durable ownership registry and a fresh correspondence decision. Do not
wire this planner directly to POST requests or claim deployed deduplication.

The summary publisher still uses one write per monotonic run claim. The new
development-only `scripts/publication_batch.py` supports multiple writes within
that same PR-wide claim. It freezes the batch, persists each step's intent before
returning the write plan, and records each validated normalized response before
admitting the next step. Completed batches and provider identities remain in
`batch_history` across later claims, including ordinary summary publications.
History has no automatic pruning or migration and contains private review text.
It is durable response history; the ownership binding described below uses
qualifying creation records rather than treating all responses as ownership.

A crash, failed result persistence, or malformed response leaves the batch pending
and blocks new runs. There is no automatic resume, retry, rollback, or recovery.
Even a failure between writes conservatively leaves the batch pending. The
summary-only recovery routine explicitly rejects batch recovery before provider
reads.

`LocalCoordinator.recover_batch` now supports explicit read-only recovery through
a trusted observer callback under the same lock. Updates require an exact owned
comment ID/body and matching thread identity. Creates additionally require a
unique operator-generated `<!-- adversarial-review-write:v1 HEX64 -->` marker
frozen in `recovery_marker` and the body before the request. Marker reuse within
the batch or retained history is rejected. Unmarked uncertain creates remain
blocked, even when similar text exists. The adapter must list the exact PR/MR's
summary comments and inline roots, excluding replies; the recovery helper checks
resource identity, publisher identity, complete listing, and target kind.

Recovery preserves earlier durable responses and retires unstarted steps as
`not_attempted`. It never resumes the old batch or treats an absent pending write
as proof of failure. Missing, edited, duplicate or wrong-owner observations remain
blocked. A later push or closed PR need not prevent read-only inspection of an
old write, but the next publication needs a fresh review. The caller must still
account for delayed requests and uncoordinated writers; observing intended state
does not prove request attribution or global exactly-once delivery. Provider
observers are only partially implemented; operator-facing batch recovery remains unwired.

The development `scripts/gitlab_discussions.py` reader now implements GitLab's
[MR discussion listing](https://docs.gitlab.com/api/discussions/#list-all-merge-request-discussion-items).
It paginates discussions and retains their returned notes, distinguishing standalone
summaries, diff roots, and overview discussions. Public replies remain context,
never recovery targets. System/internal roots are excluded without promoting a
reply. The reader validates project/MR membership and duplicate identities and
rechecks MR/publisher identity after collection. Raw reader output marks all
threads unmanaged. Original diff positions are retained
as context, not treated as verified current locations.

`GitLabDiscussions.recover_batch` connects this reader to the locked recovery
helper, including read-only inspection of merged MRs. Tests use realistic mocked
responses and assert GET-only requests; live GitLab authentication and behavior
have not been tested. Exhausted pagination means the endpoint listing was fully
traversed, not that GitLab provided a transactionally consistent snapshot during
concurrent edits. Publication still needs discussion rechecks. GitHub collection,
inline writes, and CLI integration remain unfinished.

`scripts/inline_ownership.py` now binds current inline roots to durable completed
creation records within an active claim. The snapshot must match the claimed
provider resource. Only the configured scope/channel and authenticated publisher
can claim their recorded thread/root IDs. Author identity, copied markers, an
incoming `managed` flag, update-only history, or old records without scope/channel
do not establish ownership. Missing or replaced owned roots require adjudication;
the helper does not infer that the issue was fixed or create a replacement.

`GitLabDiscussions.plan_findings` connects provider collection, ownership binding,
and the existing explicit-correspondence planner. Plans carry target kind,
resource, scope/channel, and discussion/body recheck preconditions. Integration
tests exercise durable creation → new claim → current provider snapshot → update
plan for the original root, preserving the human reply as context. No provider
writes occur in this path. This validates ownership and planning, not the truth
of the caller's semantic match or a deployed review-to-publish workflow.

## GitLab existing-root update path (development library)

`scripts/gitlab_inline_updates.py` now implements body-only updates using the
documented [thread-note update endpoint](https://docs.gitlab.com/api/discussions/#update-a-merge-request-thread-note).
It requires the digest of the provider snapshot presented for correspondence
adjudication, so replies that arrived before publishing cannot silently become
the baseline for an old match. It obtains a fresh snapshot, binds durable ownership,
and rejects any create action before writing. Stale source is skipped; unchanged
results produce no write. It never resolves, reopens, relocates, or edits replies.

Multiple root updates share one batch claim. Before every request, the reader's
snapshot must equal the frozen original plus only this batch's confirmed body
replacements. Unexpected replies, edits, resolution, or source changes stop the
batch. Response checks include project/MR membership, root ID, author, body, and
diff-note type. Timeout or malformed responses remain uncertain; read-only
recovery confirms observed writes without replaying the tail.

Tests cover two updates followed by a no-write rerun, preserved human replies,
discussion changes before and during publication, foreign response membership,
stale HEAD, rejected creates, and remote-success/response-timeout recovery. These
use a mock provider, not live comments. The library is not wired into the CLI or
native skills, does not yet combine summary and inline publication in one batch,
and cannot create initial inline threads. New-thread diff-position validation,
GitHub support, and live validation remain required for the full feature. The
last-instant push/write race remains; bodies stay bound to the reviewed SHA.

The batch helper does not make API calls or prove provider membership or semantic
matching. Adapters must normalize authenticated responses and recheck each step
under the lock. Expected changes from earlier writes in the same batch must be
accounted for explicitly when comparing discussion snapshots; unexpected changes
require fresh adjudication. Never simply replace the frozen snapshot digest.
Calling the standalone summary publisher and each inline action with the same
run version still fails; inventing completion-time versions would lose review-
start ordering. Native publishing has not switched to the batch helper.

Local tests cover moved-line updates, repeated no-op, new issues at an existing
location, omitted findings, ambiguous matches, ownership/resolution exclusions,
stale commits, incomplete listings, and input preservation. These establish
planner behavior, not semantic matching accuracy or live-provider correctness.
