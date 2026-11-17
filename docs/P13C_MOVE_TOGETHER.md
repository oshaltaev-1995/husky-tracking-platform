# P13C Move Together

Implemented locally for independent review on top of accepted P13B. This document
describes the editor contract, not a production rollout or completed independent
acceptance. P13D–P13G and P14 remain separate, unauthorized packages.

## One editor in two map views

The Kennel Map starts in View mode. Move dogs is enabled only when the loaded server
snapshot's `housing_edit` is editable and provides a date, revision, and precondition.
Revision zero is valid. Historical or missing-workspace contexts explain why editing
is unavailable; the editor never changes the date automatically.

Overview and Ground share the committed snapshot and draft. Changing view or layer
retains pending moves and does not write or request a new snapshot for the same date.
The selected view is the only mounted map. Date, layer, and view remain URL state;
drafts and preconditions never enter URLs, localStorage, sessionStorage, or logs.

Select a dog and destination using controls, or drag the dog to an active location on
desktop. The explicit selector supports keyboard and mobile touch without requiring
dragging. In Move mode, selection does not unexpectedly open a profile; an explicit
profile link remains available through the dirty-navigation guard. Dog dragging and
Ground background pan are separate interactions. A cancelled drag stages nothing.
Ground keeps its current zoom during the gesture and retains its bounded viewport.

Occupied and empty destinations are equally valid, including adult dogs with puppies.
Availability, sex, work role, class, location type, and nominal capacity are not new
client-side move prohibitions. Backend lifecycle/date checks remain authoritative.
Every prior resident stays in the destination, with all names accessible. Occupancy
above capacity is neutral context, never a claim about real animal safety.

## Committed data, preview, and Undo

Feature-local state keeps the latest server snapshot and editing context, a
`ReadonlyMap<dog UUID, destination code>`, and an action history. The pure helpers in
`housing-move-draft.ts` derive preview locations and review changes without mutating
the API snapshot. A→B→C becomes one pending A→C move. Returning to the committed
location removes the pending entry; choosing the current preview location is a no-op.
Real Undo restores the previous intention, including an earlier destination for the
same dog, rather than merely deleting its final entry.

The preview is labelled as unsaved. It updates housing codes and occupancy while
preserving the complete dog UUID/name set and location order. Search uses that preview,
so a moved dog's highlighted enclosure is its proposed location. Reveal/focus remains
post-render and cancellable following P13A-R1. Cancel in review keeps the draft;
Discard clears the whole draft and history. Neither sends a mutation.

## Review and the only write

Review presents the effective date, workspace-only effect, each committed source and
proposed destination, and every resident in each affected location after the changes.
An emptied source is still included. Counts describe the preview rather than silently
mixing committed and pending occupancy. An empty draft cannot be confirmed.

One explicit Confirm sends one `POST /api/v1/kennel-map/moves` through
`KennelMapService.moveDogs`. Its body contains only `effective_date`, `precondition`,
and `moves[{dog_id,destination_code}]`, copied from the same committed editing context.
The HttpOnly cookie remains browser-managed. While saving, confirmation and edits to
the submitted batch are blocked. There is no automatic mutation retry.
Close review remains available during a save so the existing shell Reset can be used;
it explicitly says the submitted save continues. It neither cancels nor rolls back
the request. Editing remains blocked until a confirmed response or reconciliation.

Success requires HTTP 200. The complete response replaces the committed snapshot and
editing context, clears the confirmed draft and Undo history, and permits a new reviewed
batch without reloading the entire page. The client never fabricates committed housing
by merging its preview into an old server response. P13B still supplies the transaction,
revision/precondition verification, and all-or-nothing persistence. See
`P13C_HOUSING_HANDOFF.md` for that unchanged API contract.

## Recovery and pending requests

| Result | Editor behavior |
|---|---|
| 401 | Disable the old confirmation, explain session loss, explicitly reinitialize the existing session service, and load a new snapshot. Never replay the former draft into a new workspace. |
| 409 | Treat the draft/context as stale. Offer reload with explicit discard and require a new draft/review. Never silently replace its token. |
| 422 | Show a controlled request error, including normal validation-detail handling, without claiming partial success. |
| 403 | Explain that this request is not allowed; do not bypass Origin protection. |
| Network failure, timeout, or uncertain 5xx | Explain that the save result is unconfirmed. Block another confirmation until a GET reconciles server state; never promise rollback or automatically retry the POST. |

`DemoSessionService.reinitialize` clears the cached session/request before the normal
initialization call, which is necessary if the browser loses its cookie while the
cached expiry still appears valid. It neither resets all data nor replays a mutation.

Unsubscribing or leaving the route cannot undo an already accepted write. Late responses
are tied to their original request/context and cannot replace a newer date/session or
restore old focus. Recovery accepts the freshly read server projection and requires
another deliberate review for new changes.

## Leaving, Reset, and focus

Changing date, exiting Move with dirty state, navigating to a profile, or leaving the
route requires confirmation to discard. Cancelling preserves the draft, selected date,
and URL, including Back/Forward cases. View and layer changes retain the draft. A
standard beforeunload warning protects relevant unsaved work where browsers support
it; drafts are not restored after a reload.

The shell's existing Reset flow sends the same workspace reset API. Narrow session
notifications invalidate the editor after reset/replacement and coordinate review
state, avoiding a second dirty-discard prompt for an intentionally confirmed reset.
An in-flight housing request still has an uncertain server result until reset or a
fresh read establishes the authoritative state. Other tabs remain protected by P13B's
precondition even without polling or real-time synchronization.

Dialogs have accessible names, focus trapping, Escape/Cancel behavior, and sensible
focus restoration. Selections, destinations, Undo, Review, Confirm, and Cancel work
without a mouse. Destruction and cancelled navigation clear stale drag/focus callbacks
and event subscriptions; normal map links remain available in View mode.

## Verification and scope

Package evidence must include unit/component/API-client results and the actual built
frontend with the accepted backend against a specifically identified disposable
PostgreSQL instance. Browser acceptance covers real drag in both views at different
zooms, touch/select and keyboard use, Cancel/Undo/Confirm, competing tabs/workspaces,
Reset/session recovery, fault-injected lost response, high occupancy, and R1 result
visibility inside both the map client area and browser window. Test desktop, tablet,
and mobile and report physical-phone or additional-engine checks as NOT RUN when
unavailable. Unit tests do not substitute for browser evidence or PostgreSQL isolation.

No backend/API change, migration, seed change, new distance, work-policy change, or
production write belongs to this package. The accepted schema remains `b7e13a9d4c20`;
the baseline remains 140 sessions, 1,120 starts, 60 portraits, and checksum
`2ad3418ecb5edad1d4676a9a6e0cf43b2cfbfa167c0218e96d9749fd12e24af2`.
Plans, teams, actual positions, workload totals, and historical housing remain unchanged
by housing-only moves and must be checked in the disposable acceptance environment.

Retain P13B's rollback caveat: old backend code ignores overrides, and old Reset does
not remove them. Invalidate temporary workspaces with compatible code in a controlled
step before an older-code rollback; do not perform a blind production downgrade.
Swap, multi-select, print/PDF, Dog Summary, Training Day, laps, and the Operations Agent
remain outside P13C. Push, merge, tag, and deployment require separate authorization.
