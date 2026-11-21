# Core cross-review

Status: historical finding **resolved** in the final code. Session-list deletion now commits before history cleanup; failed metadata writes preserve history, and later cleanup failures return `failedHistoryIds` for a warning. Both failure traces are locked by passing regressions. Final core suite: 12/12 passed. The findings and 9-test count below describe the earlier snapshot, not the final implementation.

Read-only review of request.js, all composables, stores/app.js, App.vue and global.css; no product files changed.

## Confirmed finding: P1 — session deletion destroys history before metadata commit

`web/src/composables/useLocalStorage.js` `removeSession` deletes `chat_history_${sessionId}` before `persistSessions` writes `chat_sessions`. If that metadata write throws, the caller receives failure and the shared session list stays unchanged, but the conversation history is already gone. This contradicts the new failure-preservation contract (ERR-002).

Reproduced against the actual module in a Node VM using installed Vue: seed one session plus its history; make storage.setItem throw `quota`; call removeSession. Observed: operation throws `quota`, `sessions.length === 1`, stored `chat_sessions` still exists, history key is absent.

`clearAll` has the same partial-delete problem: seed A/B and make removing B throw `denied`. Observed: operation throws, both session metadata entries remain, A history is absent and B history remains. The current UI reports a failure while prior history is irreversibly removed.

Repair should establish the session-list deletion commit before noncritical history cleanup, or provide a tested rollback/transaction contract. A failure before the deletion commit must retain histories. Cleanup failure after an established commit must not misleadingly report that the whole deletion failed; orphan cleanup is safer than destroying a still-listed conversation. Add regression tests for metadata write failure and interruption during multi-history cleanup.

## Verification and retained conclusions

`node --test docs/frontend-audit/core-regression.test.mjs`: 9/9 passed. Its failed-persistence test covers upsert, not removeSession/clearAll. Both additional failure traces above reproduced independently.

Shared theme state, single-action MobileMenu integration, and identical listener callback removal agree with the current code and passing regression. Store notification timer replacement/disposal and request cancellation/write retry paths likewise passed. No additional factually confirmed issues found in the reviewed App/CSS/request/theme changes. Browser rendering, real quota behavior and mounted lifecycle transitions were not exercised.
