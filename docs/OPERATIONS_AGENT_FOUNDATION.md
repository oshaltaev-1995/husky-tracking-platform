# Operations Agent — P14A foundation and P14B handoff

P14A is local, disabled by default, and **not a live AI feature**. It supplies strict
contracts, a frozen operational projection, six read tools, deterministic checks,
provider-specific request/response adapters and a bounded routing state machine.
There is no API route, UI button/chat, automatic loop, real network transport,
conversation persistence, new table/migration or infrastructure service. Existing
screens work without AI. Fake HTTP tests are contract evidence, not model-quality or
live provider compatibility evidence. P14B and publication require separate approval.

## Context and consistency

`operations.snapshot.SnapshotReader.capture(cookie, selected_date)` owns its Session
and short transaction. It requires an existing valid backend-issued cookie; missing,
expired or replaced identities never initialize a session or fall back to baseline.
Dates must lie in DemoClock's 2025-12-01…2026-03-31 season, not machine today.

The existing workspace-row lock is acquired before reading domain data; this is the
same first lock used by Plan/Team/Actual, housing and Reset. Every participating
reader receives one `HousingContext`. Ordinary PostgreSQL read/write transactions
are intentional: SELECT FOR UPDATE cannot be combined with PostgreSQL READ ONLY.
The operation adds no domain objects, flushes, date materialization or reset writes.
It closes the transaction **and Session before returning**. Provider callbacks never
retain a DB connection or lock, including while waiting, switching or validating.

The resulting Pydantic graph is frozen, extra-forbidden and detached, including nested
tuples; it contains no ORM handles. Public identity is a random snapshot UUID plus
contract version, captured-at UTC and selected date. Private workspace/expiry/reset
binding stays in the non-serializable server RunContext. `check` re-resolves the
current cookie and locks/rechecks expiry/schema/generation before a provider step,
reserve restart, tool completion and final result. Cancellation/attempt generations
discard late results. Reset/session replacement cannot resurrect old work.

`housing_revision` detects Reset and conservatively housing moves; it is **not** a
global plan/actual version. Ordinary edits after capture are allowed: results describe
the snapshot at its capture time. The recorded plan revision identifies its source;
no claim is made to detect all later edits. Historical housing never receives the
March31 override. Canonical data is immutable throughout a normal run.

Bounds: at most60 canonical dog states,32 activities,64 actual sessions,32 locations,
512 evidence/check items and192KB serialized local snapshot; oversize is a typed
failure, not silent truncation. A model receives only the small run envelope and
explicit bounded tool results, not the full local snapshot. Detail selections are
validated against that exact snapshot. `validate_day` returns rule/status counts and
up to32 attention/violation/unverified details with an explicit omitted-detail count.
Tool result and provider input caps may reject an excessive selection; they are not
tokenizer estimates and never trigger paid fallback.

## Read registry, evidence and rules

`FrozenTools` has no Session, URL client or writer. Closed tool names:

| Tool | Facts |
| --- | --- |
| get_day_plan | Saved activities, selected pool, distances/revision; no notes/title text |
| get_saved_teams | Only persisted teams/slots and selected pool, never solver execution |
| get_dog_states | Explicitly selected UUIDs, dated born/lifecycle/class/availability/capabilities |
| get_workload | Selected dogs' actual7d/14d/season strictly **before** date, with actual on date separately labelled |
| get_housing | Dated location/provenance and informational nominal occupancy |
| validate_day | Compact deterministic checks, counts, evidence and qualified conclusions |

Arguments are strict bounded JSON objects (duplicate keys/nonfinite numbers rejected),
season/snapshot date and known public UUID/activity identities; no workspace ID, SQL,
URL, Python, shell, provider config, arbitrary tool or browser capability is accepted.
All tools in a run use the same frozen data, even after switching providers.

Existing `DailyPlanService` eligibility, `EffectiveDogState`, Team Builder workload
queries and saved-lineup validator supply facts. Canonical workload arithmetic uses
`domain.workload.validate_daily_dog_distances`:5/10km,30km per dog/day, planned and
actual **separate**. A recorded plan is not counted twice. Canonical actual
WorkSession/WorkParticipation remains the only work ledger. Saved roles/pool/geometry
and uniqueness reuse Team Builder validation; hard_conflict prohibits a **harness
pair**, not a whole team. No medical/fitness recommendation or new eligibility policy
is introduced. Missing saved teams or not-recorded actual are attention/incomplete
states, not proof of a completed training. No plan is an explicit empty state.
Missing dated facts are unverified. Unborn dogs are explicitly identified rather than
treated as unavailable workers. Occupancy above nominal capacity is not a violation.

Server-created evidence holds selected date, entity references, measured values/units
and rule IDs. `validate_references` checks snapshot ID, evidence existence, exact date
and entity membership. Local deep links are built by trusted code from known routes
and identities, never supplied HTML or external URLs. A model's arbitrary prose is
**not** automatically truth-verified: only its structured references can be validated
in A. Future UI must render explanations as text and distinguish them from facts.

## Programmatic interface, not an agent loop

`foundation.prepare_review` requires current-cookie/cancellation/admission callbacks
and an injected transport. It captures once and returns `PreparedReview`. The caller
may explicitly call `review.run.call()`, `review.execute_tool(response)` and
`review.finish(response)`; A does not iterate automatically or expose these over HTTP.
Each tool executes only after pending-attempt, context and budget preflight. Rejection
is terminal; another provider is never asked to bypass it. Required admission is an
application boundary, not a misleading process-local rate limiter. P14B must wire
real deployment admission/rate limiting before exposing a route. A false admission
result reaches neither provider, even if reserve capacity remains.

`ProviderRun` permits one Groq→OpenRouter switch, never a cycle. Upstream429 means
rate/quota restriction, not necessarily exhausted daily tokens. Valid Retry-After is
propagated; no same-provider retry, sleeping loop or hidden HTTP retries. Transport
failure/timeout/5xx can switch within the common deadline. After a tool followed by
Groq429, reserve restarts the original task/contracts/same snapshot; primary raw
transcript/reasoning/partial text is not transferred. Final output is withheld until
structured evidence/context checks pass. Total caps are6 HTTP calls,8 tool executions,
45s including preparation and failures,1024 output tokens/call. Input bytes and tool
result caps are real byte bounds, not promised token counts. Groq's completion cap
includes reasoning; low effort and hidden reasoning are requested; no CoT is kept.

| Outcome | Future API contract (no endpoint in A) |
| --- | --- |
| application limit | 429 app_rate_limited, no provider |
| both attempted routes quota-limited | 429 ai_quota_exhausted |
| network/temporary/no compatible free route | 503 ai_temporarily_unavailable |
| 401 /403 /402 | distinct authentication/access/payment configuration failure; no safety-bypassing fallback |
| bad request/tool/JSON/evidence/policy refusal | distinct terminal failure |
| no remaining budget/time | run_budget_exhausted /timeout; do not claim untried reserve quota exhaustion |
| Reset/expiry/replacement/cancel | context_changed /session_expired /cancelled; no result |

No global cross-worker quota accounting/cooldown is claimed. State is only this run;
PostgreSQL, not process memory, remains the authority for workspace lifecycle.

## Provider contract and zero-cost boundary

Server-only `ProviderSettings` uses `AGENT_*`; `.env.example` has blank keys and
`AGENT_ENABLED=false`. No implicit .env load or outgoing HTTP transport is installed.
Tests explicitly inject fake transports regardless of ambient keys. SecretStr values,
Authorization and raw bodies are excluded from DTO repr. No raw prompts/responses,
notes, hidden reasoning, keys or cookie values are written to logs or review outputs.
`run.metadata()` exposes random run ID, provider/model, switches, time, counts, safe
error code and usage; rule codes can be attached from deterministic results. There is
no persistent conversation store.

- Groq fixed endpoint: `https://api.groq.com/openai/v1/chat/completions`, exact
  `openai/gpt-oss-20b`. Free-account status is an explicit operator prerequisite;
  `AGENT_GROQ_FREE_ACCOUNT_CONFIRMED` is an attestation, not automatic billing proof.
  Model identity alone does not make a paid Groq account safe for a €0 budget.
- OpenRouter fixed endpoint: `https://openrouter.ai/api/v1/chat/completions`, exact
  `openai/gpt-oss-20b:free`. Never strip :free, use auto/random routing, model fallback
  lists, BYOK, paid plugins/search/server tools or purchase/rotate credits/accounts.
  `provider.max_price={prompt:0,completion:0,request:0}`, `require_parameters:true`,
  `data_collection:"deny"` are mandatory. `allow_fallbacks:true` permits endpoints
  **of that same exact model under all these filters**; the flag alone is not a price
  guarantee. No compatible endpoint means unavailable, not filter relaxation.
- Serial local tool calls only, no parallel call assumption. Groq uses
  max_completion_tokens and low/hidden reasoning; OpenRouter uses max_tokens. Model
  JSON/tool-option compatibility remains a bounded live gate in B, not assumed from
  generic OpenAI API compatibility. Redirect following is prohibited by transport
  contract; future transport must enforce fixed host, TLS verification, response bound,
  timeout and no retries. A has no live transport with which keys could be sent.

## Data handling and Free-only setup for B — NOT active public processing

The present public site does not send operational data to these providers. Do not add
a premature processing statement to public Privacy. Before B activation, update the
notice and technical data map to match the actual account controls and selected
providers. Both providers may receive the selected date, snapshot UUID/time, small
synthetic plan/actual counts, bounded dog identities/states/capabilities, roles/housing,
actual workload numbers and evidence returned by explicitly used tools. Reserve gets
the same initial envelope and can request those tools again, never the Groq transcript.

Exclude free notes, activity titles/labels, Contact content, visitor personal data,
IP/client headers, cookies, HMAC/preconditions, internal workspace IDs, credentials,
DB URLs, images/PDFs and whole histories. Dog names/strings are untrusted data, not
instructions; an injection fixture cannot change registry/provider/budget policy.
The provider sees only the HTTP connection of the future server transport, not a
forwarded visitor identity. Do not promise universal zero retention, EEA-only routing,
certification or legal transfer guarantees: none is automatically verified by A.

Before limited B live QA, owner must:
1. Create/use only a Groq Free account; verify organisation plan, Limits and data-use
   controls. Do not activate paid service, card, upgrade or credits. Generate a
   server-side key privately; confirm model/tool support is still available.
2. Create/use a no-purchase OpenRouter account; verify exact :free catalog entry,
   tool support and current zero-purchase quotas. Keep prompt/completion logging and
   training/data opt-ins off; inspect account/provider privacy controls. Do not weaken
   data_collection deny for a free endpoint. $0 key credit limit alone is not a
   demonstrated promise that every free request will work.
3. Supply keys only through private server runtime settings. No key is needed to
   finish A. Execute a few explicitly authorised live requests with limits above,
   validate actual billing/usage, errors, tool schema, zero-price and privacy-filter
   compatibility. If filters yield no route, show failure; do not upgrade/relax.
4. Wire cancellation/current-session guards, real admission, UI tool trace/evidence,
   plain-text explanations, no partial streaming and public notice before exposure.

Published limits are guidance, not application constants or permanent free-service
guarantees: Groq model table lists30RPM/1000RPD/8000TPM/200000TPD; organisation Limits
is authoritative. OpenRouter zero-purchase :free guidance is20RPM/50RPD, including
failed attempts. A run can spend multiple requests. B must recheck them; no quota was
consumed in A. OpenRouter deny filters and default account logging/training controls
do not prove universal provider retention or region; abuse/legal exceptions apply.

Official references inspected for A (21 Nov2026; recheck in B):
[Groq tool use](https://console.groq.com/docs/tool-use/overview),
[API fields](https://console.groq.com/docs/api-reference),
[limits](https://console.groq.com/docs/rate-limits),
[billing](https://console.groq.com/docs/billing-faqs),
[deprecations](https://console.groq.com/docs/deprecations),
[OpenRouter exact free model](https://openrouter.ai/openai/gpt-oss-20b:free),
[provider/price filters](https://openrouter.ai/docs/guides/routing/provider-selection),
[limits](https://openrouter.ai/docs/api/reference/limits),
[data collection](https://openrouter.ai/docs/guides/privacy/data-collection).

## Evaluation and scope

`python -m app.operations.evals` runs12 small deterministic fixtures with expected
rule/status/value/evidence checks, no model or provider request. Pure-tool tests cover
strict arguments and evidence; real disposable PostgreSQL covers shared locks,
snapshot/no-write/isolation, historical/future bounds and lifecycle; fake HTTP/state
tests cover serial turns, mid-run restart, rejection, deadlines and budget. These
are not 12 model-quality evaluations. P14C will assess approximately20–30 real-model
and adversarial scenarios after B's separately authorised live interface.

G-DOC-01 clarification: P13G's pre/post-Apply comparison establishes unchanged
**Work.summary / actual-work metrics for all16 dogs**. It does not establish equality
of complete Work DTOs including history/weekly arrays. No historical accepted archive
was rewritten. G-PRIVACY-01 names ht_demo_session and notes/housing use, keeps TTL
runtime-driven, and describes Reset accurately: deletes mutable workspace data, does
not delete the cookie and does not extend its existing expiry. Privacy GET never
creates a workspace or optional browser storage.
