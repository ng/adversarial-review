# Comment reconciliation — implementation in progress

Inline update planning is now available as a development-only pure helper; see
[inline reconciliation](inline-reconciliation.md). It requires explicit source-
grounded correspondence and preserves omitted findings and human discussion.
Provider wiring, durable inline ownership, and live validation remain unfinished.

Identity regression check: the GitLab adapter now canonicalizes explicit HTTPS
port 443 to the same provider identity as an omitted port. Previously these two
spellings could split the summary key and coordinator lock for the same MR.
Tests cover equal resource and summary-context identities. If any pre-release
deployment used the earlier explicit-port keys, inspect its existing summaries
and coordinator state before switching; this change does not migrate old keys.

Current operator entry point: [summary publisher usage](summary-publisher-usage.md).
`scripts/publish_summary.py` now provides default read-only planning and explicit
single-host publishing/recovery. Both native skills now route configured summary
publishing through this CLI and no longer prescribe an unconditional summary POST.
Live workflow validation, inline reconciliation and distributed coordination
remain incomplete. The sections below include historical progress
notes; statements about the lack of a CLI describe those earlier stages.

## Authenticated transport

`scripts/summary_http.py` supplies a callable transport for either adapter.
It uses direct HTTPS with default certificate verification, bounded JSON reads,
and a per-socket timeout. It neither follows redirects nor retries requests.
Errors omit response bodies and credentials. A trusted operator supplies the
token and (for GitLab) origin; review artifacts must never choose either.
GitHub is restricted to `api.github.com`; GitLab URL subpaths and IPv6 literals
are not supported yet. Environment proxies are not used. This is not a total
wall-clock deadline against a slow server.

Authentication follows the official [GitHub authentication documentation](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api)
and [GitLab authentication documentation](https://docs.gitlab.com/api/rest/authentication/).
Use user/PAT credentials compatible with the adapter's `/user` identity check;
installation tokens and CI job tokens do not gain support from this transport.
Construct the GitLab adapter and transport with the same trusted origin.

Transport tests mock HTTPS connections, including redirects, invalid destinations,
malformed/oversized responses, and an integrated timeout that persists uncertain
state and blocks a later publish. No live provider authentication or writes have
been tested. The transport is available as a library, not a publish CLI; native
workflow wiring and distributed coordination remain unfinished. References below
to missing transport describe earlier implementation stages.

## Adjudicated publishing entry point

Both provider adapters expose `publish_review(adjudication=..., scope=...,
channel=..., details=..., run_version=..., coordinator=...)`. This freezes the
final adjudication before provider reads and derives merge risk from the same
snapshot used to plan the comment. It reuses the coordinated create/no-op/update
lifecycle, including a second snapshot before writing. A stale head skips
publication; a head change between snapshots aborts without a write. Scoped
reviews cannot independently claim full coverage for a Low risk label.

The lower-level `publish(summary=...)` remains available for preformatted content
and does not enforce risk derivation. Native workflow integration should use
`publish_review`, not that lower-level entry point. Caller-supplied adjudication
is still an input, not independently verified evidence; these tests demonstrate
publishing behavior, not review accuracy. Tests use mocked provider requests.
Native workflow wiring remains unfinished; the transport library is described above.

`scripts/reconcile_summary.py` is a pure planner, not a publisher. It reads
normalized provider state and emits `create`, `update`, `noop`, or `skip_stale`.
The current reviewer workflows still use their previous posting instructions;
this helper is not yet wired into GitHub/GitLab publishing.

One summary is identified by repository/provider, PR/MR number, canonical review
scope and publisher channel (for example, the combined review rather than each
lane). The hidden marker is only a lookup key. Verified numeric author identity
is also required; a human copying the marker does not grant permission to edit
their comment. Existing duplicate owned summaries fail closed without deleting
anything. Existing unmarked historical comments are not automatically adopted.

The planner requires a complete paginated listing, includes the full reviewed
SHA in the body, and skips results that no longer match current HEAD. Repeating
identical input produces no write. Updates target the same comment ID and carry
the previous body's hash as an optimistic precondition. No comments, replies or
threads are deleted or resolved by this implementation.

An adapter must obtain identities and state from the provider, serialize writes
per PR/MR, and recheck the head, ownership, body hash (or absence for create) just
before publishing. These preconditions are **not** remote atomic enforcement.
The planner alone does not prevent concurrent publishers or order different runs
of the same SHA; the adapter needs a monotonic run identity and coordination.
Do not claim concurrency safety merely because a plan includes a hash.

Next: provider adapters and mocked repeated/concurrent-run tests, monotonic run
ordering, SHA-bound merge-risk rendering with incomplete-review safeguards, and
finding-thread matching that survives moved lines. Mark a finding fixed only
after source verification, never merely because a later review omits it. Preserve
human replies and avoid moving an existing inline thread to an unrelated issue.
Only then replace native workflow posting instructions and validate end-to-end.

## GitHub adapter progress

`scripts/github_summary.py` now implements endpoint selection, paginated listing,
two snapshots before writes, create/update response checks and no-write handling
for unchanged/stale results. It uses GitHub's top-level issue-comment endpoints
for PR summaries, not inline review comments. See the official
[issue-comment API](https://docs.github.com/en/rest/issues/comments#update-an-issue-comment).
It accepts an injected request transport; no live API request or posting occurred
during implementation. Mock tests cover create → noop → update, pagination, a
head change during recheck, and a remote-success/local-timeout sequence.

Publishing requires an injected coordinator that serializes writers and durably
records pending/uncertain outcomes. That production coordinator and HTTP/CLI
transport are **not implemented yet**; tests use a deliberately minimal fake,
not evidence of cross-host concurrency safety. There is no publish CLI entrypoint.
The adapter's `/user` identity flow supports user-authenticated tokens; installation
token/bot identity needs an explicitly verified alternative before Actions use.
GitHub does not make the PR-head read and comment write one transaction; even
coordinated writes must remain visibly SHA-bound and acknowledge that last-moment
pushes/uncoordinated edits cannot be excluded by preflight reads alone.

## Local durable coordination

`scripts/summary_coordinator.py` supplies a POSIX `LocalCoordinator` for all
publishers sharing a trusted persistent directory. It holds a nonblocking flock
through the provider operation and atomically saves/fsyncs monotonic run state.
The run version must be assigned by the orchestrator when a review starts, not
derived from its completion time or a model-generated number. Consumed or older
versions are rejected, including after creating a new coordinator instance.

Before a request, `pending` is durable. A crash, timeout or ambiguous response
then blocks all subsequent writes until explicit read-only recovery; nothing
automatically resets that state. Pre-write failures can admit a newer run. Tests
exercise another process contending for the same lock and persisted uncertain
state. State is outside source artifacts and must not be placed in an untrusted
or independently recreated checkout.

This implements **local** durability, not the previously required cross-host
coordinator. It is not sufficient for ordinary ephemeral Actions runners. The
adapter still has no live transport/CLI or installation-token identity flow, and
the workflows have not switched publishers. Shared CI coordination and audited
uncertain-write recovery remain required before enabling remote writes.

## Read-only uncertain-write recovery

The local coordinator now supports an explicit recovery operation, exposed by
the injected GitHub adapter. It holds the same resource lock and requires a fresh
complete listing, unchanged authenticated publisher identity, exactly one owned
marker, the exact intended body, and the original comment ID for an update.
Only then does it record `recovered_observed_state` and admit newer run versions.
Recovery itself makes no remote writes. Missing, edited, duplicated, wrong-owner
or incomplete state stays blocked; absence does not prove a timed-out request
cannot complete later. There is no reset or automatic blind retry path.

Tests use the real local coordinator with a mock provider that commits remotely
then loses the response. Recovery after a new coordinator instance observes that
comment, and the next run performs no duplicate write. Tests also preserve the
block for absence, duplicate markers, edited bodies and changed identity.

Observed-state recovery is not proof of which request performed the write or
global exactly-once delivery. The deployment must exclude concurrent uncoordinated
writers and account for still-running remote requests before operational recovery.
Distributed CI coordination, real transport and bot identity remain unfinished;
no workflow publishing behavior has switched yet.

## SHA-bound merge-risk rendering

`scripts/merge_risk.py` now renders the requested `Merge risk [icon] Level — up
to SHA` line from explicit final adjudication and coverage, not model agreement
counts. Low requires current HEAD, full scope, completed review and no material
unknowns or supported behavioral defects. Bounded behavioral defects produce
Medium; supported important defects produce High even when coverage is incomplete,
with the gaps shown. A stale review gives current risk Unknown while preserving
its historical rating and known important IDs. Rejected advice, cleanup and
pre-existing-only findings do not inflate PR-introduced risk.

`scripts/review_summary.py` composes that rendering with the upsert planner from
the same provider snapshot. Visible canonical scope determines full-scope status;
a separate caller flag cannot mark a scoped summary Low. The planner still refuses
to publish a stale result. This composition is tested locally but not yet wired
into the native publishing steps. The caller must supply adjudicated unresolved
findings; the renderer does not independently establish source truth or infer that
omitted findings were fixed. The earlier benchmark-only risk helper remains
unchanged for historical reproducibility.

## GitLab adapter progress

`scripts/gitlab_summary.py` now adapts the same coordinated lifecycle to GitLab
MR summary notes: paginated reads, POST for creation and PUT for updates to the
same note ID. It verifies the authenticated user, open MR and reviewed SHA,
and excludes system events, internal notes and discussion replies from summary
matching. Its identity includes the trusted instance origin and numeric project
ID, preventing cross-instance collisions and project-rename identity changes.
Endpoint behavior follows the official [GitLab Notes API](https://docs.gitlab.com/api/notes/).

Mock tests cover create/noop/update, pagination through a fully filtered page,
instance separation and stale-head suppression. Existing GitHub and recovery
tests still pass after sharing the lifecycle. Neither adapter has a real network
transport or enabled publish CLI yet. GitLab installations under a URL subpath
are currently rejected rather than silently targeting the wrong API root.
