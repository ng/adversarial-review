# Independent publishing development review

Claude Code 2.1.270 completed one tool-free source review using the requested
`claude-opus-4-6[1m]` at high effort. Provider metadata reported success,
765,544 ms duration, $1.19137875 cost, 43,279 output tokens (41,809 thinking),
1,000,000 context window, no tool searches, no subagents and no permission denials.
Session: `7e5f56eb-2507-477c-bdb9-c53b3766a986`.

Input was the concatenated eight publishing Python modules and the publisher
usage document, before the default-port identity and closed-change recovery
fixes. The prompt requested concrete correctness defects, exact triggers and
regression tests, distinguishing declared limitations from implementation bugs.
It did not supply suspected bugs or desired answers. Built-in tools, skills,
hooks and MCP servers were disabled for the call. No remote comments were posted.
This was not a frozen benchmark trial or a native reviewer evaluation.

## Adjudication

1. **Cleanup IDs absent from risk output lists:** observed, but not a publishing
   defect under this interface. The lists describe important/minor/unresolved
   risk contributors, not the complete findings ledger. Self-contained `details`
   carries cleanup findings. Added a composition regression test showing cleanup
   remains in the published body while risk stays Low. Claude proposed a cleanup
   list or other output evidence, not necessarily a higher risk rating; an earlier
   conversational update characterized that recommendation too broadly.
2. **No-op result lacks `reviewed_head`:** confirmed interface inconsistency.
   No existing crashing consumer was demonstrated, so classify as an interface
   improvement, not a proven production failure. Publish now returns the same
   compact action/comment-ID/reviewed-head shape for create, update and no-op.
   Pure plans retain their body and preconditions. The proposed privacy concern
   was not established: private coordinator state already stores pending bodies,
   and the usage contract discloses that it contains review content.
3. **Reserved marker in a finding ID fails downstream:** confirmed validation
   inconsistency, not an ownership bypass (the downstream planner rejected it).
   Finding IDs now reject reserved summary markers and control characters before
   rendering, consistently across impact classes. Regression tests cover each
   impact class. This tightens previously accepted ID inputs intentionally.

The review did not report the two independently reproduced lifecycle defects
fixed while it was running: equivalent GitLab default-port spellings splitting
identity, and recovery requiring a PR/MR to remain open. It acknowledged documented
single-host, final-instant push-race, pending-crash and consumed-version limits.

Conclusion: useful interface feedback, with overstatement to adjudicate and
missed lifecycle defects. Neither agreement nor successful execution demonstrates
reviewer accuracy gains. Martian, SWE-PRBench and c-CRAB evaluation remains a
separate unfinished track; no benchmark result is inferred from this review.
