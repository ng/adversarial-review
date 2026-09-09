# Preliminary source spot-checks

These are assistant-performed static checks, selected after reading the review
outputs. They are not blinded human labels, a random sample, or a replacement for
benchmark scores. No application dependencies were installed and no end-to-end
behavior was executed. The checks help distinguish reference coverage from
whether an additional observation has support in the source.

Case: `martian/calcom__cal.com-14740`, cross-provider final review.
Head: `92f44dcea7ff19e9123a30c63c167a2938df5a55`.
Source root: `WORK/snapshots/martian/calcom__cal.com-14740`.

| Finding | Source evidence | Assessment | PR-quality implication |
|---|---|---|---|
| F8: add-guests emails bypass disabled-standard-email settings | `packages/emails/email-manager.ts:81` defines host/attendee guards; `sendScheduledEmails` uses them. `sendAddGuestsEmails` at line 525 accepts no metadata and queues host/attendee mail unconditionally. Its caller at `packages/trpc/server/routers/viewer/bookings/addGuests.handler.ts:168` supplies only event and guests. | Supported static policy inconsistency. The new path has no equivalent preference check. Actual mail delivery was not executed. | For new notification paths, compare preference enforcement with existing send functions and add disabled-host/disabled-attendee cases. |
| F16: toast fallback is unreachable | `apps/web/components/dialog/AddGuestsDialog.tsx:43` constructs a string containing a literal colon and space before using a logical-OR fallback. That string cannot be empty. | Supported, but a small cleanup. It does not by itself establish a user-visible failure. | Separate harmless dead-code cleanup from findings that should block a PR. |
| C: invalid-email error remains after editing | `AddGuestsDialog.tsx:56` sets the error flag on invalid submission. `MultiEmail` receives only the value setter at line 73; changing an address does not clear the flag. Cancel explicitly clears it at line 91. | Supported for the stated trigger: invalid submit, then edit the address. It is not true that the flag can never clear. | Test invalid-submit → edit → retry transitions, and require findings to state the narrow trigger accurately. |

All three were unmatched by the shared reference judge and labeled PLAUSIBLE.
These spot-checks support keeping “unmatched” separate from “factually wrong.”
They also show why factual support alone is insufficient to set PR-blocking
severity: the notification-policy gap and dead fallback have different impact.

Proposed held-out experiment: require a concrete trigger, source evidence, and
impact statement for each retained finding, while keeping low-impact cleanup in
a separate nonblocking section. Evaluate reference recall, independently assessed
correctness, and report length on held-out PRs before changing the frozen plugin.

## Skeptic reframing can still contain a false detail

Cal.com cross-provider finding F3 describes DB/calendar consistency. Its final
summary reframes the Optimizer's possible HTTP-500 scenario as a silent calendar
failure with “no logging.” The core consistency concern is supported: the handler
persists attendees before sync, and `EventManager.updateCalendarAttendees`
(`packages/core/EventManager.ts:596`) awaits the update without returning the
per-calendar results to its caller.

The no-logging detail is contradicted by unchanged source:
`packages/core/CalendarManager.ts:336` catches provider-update rejection and logs
it at line 340; another failure log appears at line 351. For that caught rejection
path, the Skeptic's narrower account of the client failure mode is useful, but
its logging claim is inaccurate. This check does not prove that every possible
failure is swallowed: setup occurs outside that promise catch, and the outer
manager returns `Promise.all(result)` from its try block.

Assessment: **mixed factual support**, not a wholly invented finding. A semantic
reference match or PLAUSIBLE label can hide an inaccurate supporting clause.
The current judge sees the diff rather than all unchanged helper implementations;
this limits factual verification. This selected example is not an estimate of the
judge's error rate or the reviewers' precision.

PR-quality hypothesis: require the Skeptic to trace both error handling and logging
before replacing an Optimizer's failure narrative, and preserve uncertainty for
paths it has not checked. Evaluate factual corrections at the claim level as well
as counting accepted/rejected findings on a held-out sample.
