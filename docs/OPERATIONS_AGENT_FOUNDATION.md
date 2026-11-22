# Operations Agent — P14A foundation and P14B review

P14A was accepted as a local, disabled foundation, **not a live AI feature**. It supplies strict
contracts, a frozen operational projection, six read tools, deterministic checks,
provider-specific request/response adapters and a bounded routing state machine.
P14A itself introduced no route/UI/loop/network transport. P14B now adds one bounded
server loop, default-disabled selected-day API and a feature-local Operations review
block in Daily Plan. It adds no chat, conversation persistence, table/migration, model
runtime or infrastructure service. Existing screens work without AI. Fake HTTP tests
are contract evidence, not model-quality or live-provider compatibility evidence.
P14B implementation is **READY FOR LIVE QA**, not full live PASS: project keys/account
verification and completed real primary/reserve runs remain gated. Nothing here changes
production; P14C and publication require separate acceptance/authorization.

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

Each tool publishes its own JSON argument contract. `get_dog_states` and `get_workload`
require nonempty `dog_ids`; descriptions direct the model to IDs in this snapshot and
the selected date. Other tools accept only their supported date/activity/dog
selectors. Required fields, minItems and additional-property rejection agree with
runtime validation; snapshot membership remains a server check, not a dynamic schema.
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
in A. P14B renders explanations as ordinary escaped text and distinguishes them from
server facts/findings, including values/units, missing data and omitted-detail counts.

## Foundation interface and P14B serial loop

`foundation.prepare_review` requires current-cookie/cancellation/admission callbacks
and an injected transport. It captures once and returns `PreparedReview`. The caller
may explicitly call `review.run.call()`, `review.execute_tool(response)` and
`review.finish(response)`; A does not iterate automatically or expose these over HTTP.
Each tool executes only after pending-attempt, context and budget preflight. Rejection
is terminal; another provider is never asked to bypass it. Required admission is an
application boundary, not a misleading process-local rate limiter. P14B wires the
specific ingress and backend concurrency guards below. A false admission
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
includes reasoning; GPT-OSS uses `reasoning_effort:"low"` and
`include_reasoning:false`, never the unsupported `reasoning_format:"hidden"`.
No CoT is retained. A deadline is checked before constructing a request and again
after payload preparation, before dispatch. `tool_calls` finish requires exactly one
allowed call; `stop` requires a final content object without calls. Inconsistent,
missing or empty call structures terminate without fallback.

| Outcome | P14B API contract (A had no endpoint) |
| --- | --- |
| application limit | 429 at ingress, classified as app_rate_limited by UI; no provider |
| both attempted routes quota-limited | 429 ai_quota_exhausted |
| network/temporary/no compatible free route | 503 ai_temporarily_unavailable |
| 401 /403 /402 | distinct authentication/access/payment configuration failure; no safety-bypassing fallback |
| bad request/tool/JSON/evidence/policy refusal | distinct terminal failure |
| no remaining budget/time | run_budget_exhausted /timeout; do not claim untried reserve quota exhaustion |
| Reset/expiry/replacement/cancel | context_changed /session_expired /cancelled; no result |

A generic429 without a valid retry hint receives a30-second component-local UI
courtesy wait; valid header/body hints (including zero) take precedence. This wait
is not global/account accounting, and navigating/reloading cannot bypass the
authoritative ingress limit.

No global cross-worker quota accounting/cooldown is claimed. State is only this run;
PostgreSQL, not process memory, remains the authority for workspace lifecycle.

`OperationsReviewService` owns one serial model→validated tool→frozen result→model
loop. On each provider attempt its first model request requires `validate_day`;
acceptance refuses an otherwise final answer until that model-requested tool has
completed for this attempt. Other reads are selected by the model from the closed
registry; the loop does not automatically dump every tool or the database. Reserve
restarts on the same snapshot without resetting counters/deadline or transferring
primary transcript. There is no partial explanation streaming.

The response separates two core server facts (saved plan and actual ledger), up to32
non-pass findings, their evidence and trusted operational links from the model's short
explanation. It includes selected date/capture UTC, provider/model/reserve flag, bounded
successful tool steps, and known run token usage. Known usage sums reported successful
responses across providers; missing/lost responses mark it incomplete rather than zero.
Last-response and per-provider usage remain distinct internal metadata. No UI claims
to measure account quota, remaining credits or billing.

## Endpoint, transport and lifecycle boundary

- `GET /api/v1/operations/capabilities` is public and read-only; it returns only feature
  state, provider names, fixed scenario and demo-season bounds, without creating a cookie.
- `POST /api/v1/operations/review` accepts only `selected_date`, requires an existing
  valid cookie workspace and exact configured Origin, and never silently replaces a
  missing/expired session with baseline. Both endpoints use shared API `no-store`.
- Production Nginx maps only this exact POST method/URI to independent client-IP zones:
  2 requests/minute with burst 1, plus one concurrent review per IP. Its existing narrow
  trusted-proxy real-IP setup supplies the key; query strings and new workspace cookies
  cannot reset it. The shared proxy's safe generic 429 body is normalized by the UI;
  backend failures have typed codes. No upstream POST replay. Backend remains private; raw development
  access without Nginx does not provide that public admission guarantee.
- Backend concurrency is one in-flight review per worker, not a persistent/global
  limiter. With N workers, up to N reviews may run across different clients. A slot
  remains occupied until its worker actually exits, including after an HTTP waiter
  disconnects/times out. No new queue, Redis or cross-worker account counter is claimed.
- The synchronous stdlib HTTPS transport runs in a worker thread, verifies TLS against
  one of two fixed hosts, follows no redirect and performs no retry. It rejects oversized
  Content-Length and reads at most the response cap plus one byte; it never loads an
  unbounded body first. Error bodies are not needed and are closed without logging.
  Remaining whole-call timeout applies at blocking phases and a socket watchdog also
  interrupts slow header/body reads. The API applies its separate whole-run watchdog.
- System DNS resolution cannot be forcibly interrupted by the synchronous Python
  resolver. A late DNS/TLS completion is checked against deadline/cancellation before
  HTTP dispatch. Disconnect/Cancel stops subsequent work and final acceptance, but an
  already sent remote request may still complete and consume quota. No refund is promised.
- Capture/context checks use remaining-budget database statement/lock timeouts, with
  configured pool/connect bounds; provider waits never retain a Session or workspace lock.

The Daily Plan block displays the selected demo day and the external-processing notice
before the explicit Review operations action. It sends one POST, disables duplicates,
offers Cancel and distinguishes quota/rate/unavailable/timeout/invalid/session errors.
Retry-After blocks a new explicit attempt until the shown time; no automatic replay.
Date/session replacement, Reset review/open/start, route departure, known expiry and
Cancel clear the active request/result. A local generation plus immediate date/session
comparison rejects late responses even before an Angular cleanup effect runs.
Ordinary saved edits after capture are not claimed to invalidate the snapshot: its UTC
capture time and that limitation are visible. Escaped text, semantic buttons/statuses,
focus return and local route links preserve keyboard and narrow-screen use.

## Provider contract and zero-cost boundary

Server-only `ProviderSettings` uses `AGENT_*`; `.env.example` has blank keys and
`AGENT_ENABLED=false`. There is no implicit provider `.env` search. Runtime environment
or an explicitly selected private `AGENT_ENV_FILE` configures native startup; the file
must contain only AGENT settings and deny group/other permissions (for example 0600).
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
  max_completion_tokens, low effort and `include_reasoning:false`; OpenRouter uses
  max_tokens and `reasoning:{exclude:true,effort:"low"}`. Model
  JSON/tool-option compatibility remains a bounded live gate in B, not assumed from
  generic OpenAI API compatibility. The transport contract prohibits redirects;
  P14B enforces fixed host, TLS verification, response bound,
  timeout and no retries. A historically had no live transport with which keys could be sent.

## Data handling and Free-only setup — not activated in production

This local package does not enable the public production site. Privacy's optional AI
section is shown only when this environment's public metadata reports the feature
enabled, so disabled production does not imply active Groq/OpenRouter processing.
No live account controls or provider inference are claimed verified by fake tests.
Both providers may receive the selected date, snapshot UUID/time, small
synthetic plan/actual counts, bounded dog identities/states/capabilities, roles/housing,
actual workload numbers and evidence returned by explicitly used tools. Reserve gets
the same initial envelope and can request those tools again, never the Groq transcript.

Exclude free notes, activity titles/labels, Contact content, visitor personal data,
IP/client headers, cookies, HMAC/preconditions, internal workspace IDs, credentials,
DB URLs, images/PDFs and whole histories. Dog names/strings are untrusted data, not
instructions; an injection fixture cannot change registry/provider/budget policy.
The provider sees only the HTTP connection of the server transport, not a
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
3. Supply keys only through private server runtime settings. No key is needed for
   offline B implementation. Execute a few explicitly authorised live requests with limits above,
   validate actual billing/usage, errors, tool schema, zero-price and privacy-filter
   compatibility. If filters yield no route, show failure; do not upgrade/relax.
4. Use the implemented cancellation/current-session guards, real ingress admission,
   UI evidence/trace and conditional notice. Before live QA verify the current account
   Limits/remaining quota through normal provider controls, without logging account IDs.

### Private configuration and remaining live gate

The owner supplies a project-only private file, never credentials from another project:

```dotenv
AGENT_ENABLED=true
AGENT_GROQ_FREE_ACCOUNT_CONFIRMED=true
AGENT_GROQ_API_KEY=<set privately>
AGENT_OPENROUTER_API_KEY=<set privately>
AGENT_GROQ_MODEL=openai/gpt-oss-20b
AGENT_OPENROUTER_MODEL=openai/gpt-oss-20b:free
AGENT_MAX_HTTP_CALLS=6
AGENT_MAX_TOOL_CALLS=8
AGENT_DEADLINE_SECONDS=45
AGENT_HTTP_TIMEOUT_SECONDS=12
AGENT_MAX_OUTPUT_TOKENS=1024
```

These are placeholders, not usable keys. `AGENT_GROQ_FREE_ACCOUNT_CONFIRMED` is the
operator's attestation, not automatic billing verification. OpenRouter no-purchase,
logging/training and free-route controls require separate account inspection; there
is no invented automatic attestation or billing guarantee. Keep flags false until
the prerequisites are met; absent keys/flags do not enable the feature.

For a native backend, set `PRIVATE_AGENT_ENV` to the owner's private AGENT-only file,
make it 0600, then explicitly pass `AGENT_ENV_FILE="$PRIVATE_AGENT_ENV"` to the existing
backend startup command. Application/database settings remain separate. For Compose,
use `--env-file .env --env-file "$PRIVATE_AGENT_ENV"` before the existing project/file
arguments: declared AGENT variables are forwarded to the backend in development and
production Compose. Do **not** pass host `AGENT_ENV_FILE` into a container whose file
does not exist there. Use `config --quiet` for validation so resolved secrets are not
printed. `PUBLIC_BASE_URL` must equal the actual browser origin (including local QA
port); the review endpoint checks Origin in development too. Native/dev-server-only
tests do not substitute for the required real Nginx admission-path QA.

The permitted live smoke is at most **12 inference HTTP requests total**, including
failed requests, fallback and every model turn, sequentially across the campaign.
Verify one completed Groq tool→result→final run and one completed free-reserve run;
the latter may use an isolated server-side fake primary429, never a public selector.
Preserve exact free model/price/privacy filters and record only safe provider/model,
request/tool/count/code/timing/known-usage/evidence metadata. Stop at the cap even if
cost remains zero. Do not deliberately exhaust quotas, purchase credits or weaken
filters. Current model catalog/parameter/account compatibility and actual usage/billing
must be checked; unknown usage is not evidence of zero spend.

Until owner keys/account checks and both real completed runs exist, the honest status
is **READY FOR LIVE QA / LIVE QA BLOCKED**, not P14B fully PASS. Unavailable routes or
insufficient smoke budget remain explicit gates. P14C quality/adversarial evaluation
does not begin as part of B. No production, push, tag or merge is authorized here.

Published limits are guidance, not application constants or permanent free-service
guarantees: Groq model table lists30RPM/1000RPD/8000TPM/200000TPD; organisation Limits
is authoritative. OpenRouter zero-purchase :free guidance is20RPM/50RPD, including
failed attempts. A run can spend multiple requests. B must recheck them; no quota was
consumed in A. B has not yet established a completed live run or account proof.
OpenRouter deny filters and required account logging/training controls
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
