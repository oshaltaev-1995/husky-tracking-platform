# P13C housing API handoff

This document preserves P13B's accepted backend contract. P13C's separately authorized
local Move UI is described in `P13C_MOVE_TOGETHER.md`; that implementation remains
subject to independent acceptance and is not a production deployment. Swap UI remains
outside scope. The examples and transaction semantics below are unchanged by P13C.

## Read a committed snapshot

Use `GET /api/v1/kennel-map?date=2026-03-31` with normal same-origin credentials.
The existing demo-session guard initializes a session. Map GET itself never issues
or replaces a cookie. Without a valid cookie it returns the canonical baseline and
this non-editable metadata:

```json
{
  "housing_edit": {
    "editable": false,
    "effective_date": "2026-03-31",
    "revision": null,
    "precondition": null,
    "reason": "workspace_required"
  }
}
```

The normal response also contains the existing summary and all location/resident
arrays. A valid workspace at the reference date instead receives `editable: true`,
an integer revision, `reason: null`, and a token of the form `h1.<64 lowercase hex>`.
Copy the exact returned token; the format description is not a usable credential.
Earlier dates remain read-only with `reason: "historical_date"` and null revision
and precondition. Never derive editability from machine today or a client-side revision.

The HMAC-SHA256 binds a version namespace, workspace identity, reference date, and
monotonic housing revision under the existing server secret. It exposes no cookie,
secret, or plaintext workspace ID. It is deterministic while that context is unchanged,
not a separately persisted random nonce. Another workspace's token cannot authorize a
write even if the numeric revisions match.

## Submit one reviewed batch

Use `POST /api/v1/kennel-map/moves` with `Content-Type: application/json`, the existing
HttpOnly cookie, and the current snapshot's precondition. A non-secret example shape:

```json
{
  "effective_date": "2026-03-31",
  "precondition": "COPY_THE_EXACT_CURRENT_SNAPSHOT_PRECONDITION",
  "moves": [
    {
      "dog_id": "COPY_THE_DOG_PUBLIC_UUID_FROM_THE_SNAPSHOT",
      "destination_code": "PUPPY-A"
    }
  ]
}
```

The two `COPY_…` strings are documentation placeholders, not valid request values.
Use a bounded, nonempty list of at most 60 moves with unique dog UUIDs. The body
accepts only these fields and cannot supply a workspace identity. A born,
lifecycle-active dog can move to any existing active location. Injured, Rest,
Restricted, or Retired availability does not prohibit a move. An occupied destination,
adult/puppy location type, or nominal capacity is not a rejection reason. Prior residents
remain there. Capacity can inform a message without treating it as a safety assessment.

The transaction locks the workspace, rechecks expiry/precondition, validates the
entire batch, then changes only this workspace's overrides. It does not materialize
a plan/work day. A changed batch increases revision once; a true no-op keeps the
revision/token. Returning to a baseline location removes a redundant override.
The response is the complete committed Map snapshot with the next editing context.
Replace the displayed committed snapshot with that response; do not merge optimistic
occupancy into a response assembled from an older revision.

## Errors and recovery

Service errors use `detail: {"code": "…", "message": "…"}`. Schema-invalid requests
also use HTTP 422 through normal API validation.

| HTTP | Code | Handling |
|---|---|---|
| 401 | `housing_session_required` | The cookie is missing, invalid, expired, or lost during a lock wait. Reinitialize through the existing session flow, discard old preconditions, and reload. Never replay the old batch automatically. |
| 409 | `housing_changed` | The token is stale or belongs to another workspace/date. Reload the snapshot and let the user review a new draft. |
| 422 | `housing_date_read_only` | Select the demo reference date; do not silently convert a historical action into a current move. |
| 422 | `housing_duplicate_dog` | Deduplicate the draft before review. |
| 422 | `housing_unknown_dog` | Reload and verify the selected dog. |
| 422 | `housing_dog_inactive` | Archived or not-yet-born dogs cannot be moved. |
| 422 | `housing_invalid_destination` | Choose an existing active location. |
| 403 | Existing Origin guard | The production mutation did not originate from the configured public origin. Preserve that guard. |

Do not show success or update committed placement after any failure. Do not log tokens,
cookies, or move bodies. The production API remains `Cache-Control: no-store`.

## Draft versus committed state

P13C should retain one server snapshot and a separate local draft. Dropping/selecting
a destination only stages the draft. Review must show current versus proposed locations
and all resulting residents, including over-capacity occupancy. Confirm sends one
batch; Cancel sends nothing. Use accessible keyboard and touch alternatives and the
existing focus-managed dialog pattern. Do not hide residents as `+N` or truncate the
list at nominal capacity. Switching a date, expiry, reset, or stale response must not
leave a draft that can be silently applied under another editing context.

Reset uses the same workspace lock, deletes its overrides and existing mutable rows,
and increases housing revision even when already empty. Every pre-reset confirmation
is invalid. Expiration deletes overrides by FK cascade. A replacement session has a
different identity and rejects old tokens. Other visitors remain independent.

## Shared reads and rollback

Map, Registry/profile, Daily Plan, Team Builder candidates, Daily Entry groupings,
Analytics housing labels/distributions, and Dashboard share the bounded request-scoped
`HousingContext` with `EffectiveDogState`. Historical gaps stay gaps. Profile history
exposes temporary current housing separately as `workspace_housing`; canonical periods
and archived last-known placement are not rewritten. Moves do not change eligibility
policy, selected participants, saved teams, actual positions, starts, kilometres, or
past ledger records. Future team generation can use current soft home-pair preference.

Migration `b7e13a9d4c20` is additive, but an older binary neither reads overlays nor
deletes them during its old Reset implementation. Before rolling back application code,
drain/invalidate temporary workspaces and pending confirmations using compatible code
in a controlled maintenance step. Rehearse the exact sequence in disposable PostgreSQL;
otherwise stale overlays can reappear on re-upgrade. Do not treat a destructive schema
downgrade as routine production rollback. No migration, seed, reset, or deployment is
performed automatically by application startup.
