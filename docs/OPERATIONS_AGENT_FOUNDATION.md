# Operations Agent — P14A foundation and P14B review

> Historical B-stage status (superseded for current scope by the P14C section below).
P14A was accepted as a local, disabled foundation, **not a live AI feature**. It supplies strict
contracts, a frozen operational projection, six read tools, deterministic checks,
provider-specific request/response adapters and a bounded routing state machine.
P14A itself introduced no route/UI/loop/network transport. P14B now adds one bounded
server loop, default-disabled selected-day API and a feature-local Operations review
block in Daily Plan. It adds no chat, conversation persistence, table/migration, model
runtime or infrastructure service. Existing screens work without AI. Fake HTTP tests
are contract evidence, not model-quality or live-provider compatibility evidence.
P14B is **LIVE QA INCOMPLETE / BLOCKED on the reserve**, not full live PASS.
The owner supplied private project keys and confirmed the required Free/privacy
conditions. A genuine Groq tool→final run passed protocol/tool/reference checks
through the UI; its prose is not factually accepted and showed observed inaccuracies.
The free reserve never completed its loop under the required filters. The bounded campaign stopped
at 11/12 actual attempts. Nothing here changes production; P14C and publication still
require separate acceptance/authorization.



## Current first-demo scope — P14C, 22 November 2026

The owner's explicit scope decision makes Groq Free `openai/gpt-oss-20b` the sole
active provider for the first demo. OpenRouter reserve is **DEFERRED**, not a passed
historical two-provider gate. `AGENT_OPENROUTER_RESERVE_ENABLED=false` by default
independently of retained keys, and the feature itself remains disabled by default.
The optional adapter and meaningful opt-in tests retain all exact-free price/privacy
filters. Capabilities and Privacy derive the same active provider list. No OpenRouter
metadata/inference/account changes were made in C. Groq-only429 preserves known
Retry-After; temporary failure is503, auth/configuration stays distinct. No retry or
switch occurs in this mode.

Known exact snapshot entities become typed escaped text/link segments after strict
model reference validation. UUIDs remain internal identities/routes; no extra dog
names/free text are sent to the model for presentation. A narrow verified-ID-list
formatter removes only its technical IDs marker, not factual assertions. Unknown,
malformed, embedded or wrong-kind IDs make the explanation unresolved; checked facts
remain. Duplicate/long/Cyrillic/HTML-like names remain real names with correct local
links. One frozen summary separately shows plan presence, activity/distance, selected
names/counts (unique versus participations), saved teams, recording status and actual
sessions/starts/dog-km. Other snapshot dogs have their own finding counts/details/links.
There is no second profile fetch, mutable identity source, HTML trust or reference repair.

Offline fixtures and real UI at1440/768/390 prove readable names, links, explicit
teams/actual, secondary archive grouping, safe unavailable states and no page overflow.
Targeted backend172 and frontend47 tests, Ruff/mypy and Node24 build pass. These are
not evidence that free model prose is true. The old UUID-heavy Groq explanation is
used as a deterministic presentation fixture, not regenerated for style.

**P14C LIVE QUALITY INCOMPLETE / FREE QUOTA BLOCKED.** The separately authorized
Groq-only campaign closed at2/8: one HTTP200 requested mandatory validate_day, then
HTTP429 prevented the final. The API preserved429/Retry-After1 and made no reserve
switch. Safe headers observed1000RPD and8000TPM; they do not prove daily exhaustion
or an invoice. No raw upstream error body or precise unobserved cause is claimed.
No further generation was used to wait for a lucky pass. Empty-plan and actual-only
expected cases were fixed before inference (Mar31 actual2sessions/16starts/120dog-km),
but not run after the rate-limit failure. Three genuine quality outcomes remain
NOT VERIFIED. A fake quota UI fixture separately verifies copy/Retry-After/no replay.

Old11/12 and2/6 ledgers/closures are immutable; new2/8 makes cumulative15/21 ceiling.
Unused slots do not transfer. New known tokens1148prompt/39completion cover only
HTTP200;429 usage is unknown. Free account/privacy attestation is reused, not a measured
billing guarantee. No new payment, model, account relaxation, deployment or P14D.
The historical sections below describe their original stage; they grant no live budget.


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
  `particle-ai/particle-1:free`. Never strip :free, use auto/random routing, model fallback
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

### Observed Groq tool/output-mode compatibility

The limited live probe returned HTTP400 `invalid_request_error`, with the safe
parameter classification `response_format` / tool-JSON-mode conflict and no failed
model generation. Groq tool-capable requests therefore omit the provider's
`response_format` option, on the initial required tool and later auto-tool turns.
The tool registry remains present and later reads remain model-selected: this is not
a forced final immediately after `validate_day`. OpenRouter keeps its JSON object
mode. Final model content still must pass the unchanged strict JSON and evidence
validation; malformed output is terminal and cannot trigger a safety-bypassing
reserve. The compatibility change alone is not proof of a completed live loop.

### Endpoint-declared optional controls

The chosen Particle endpoint's public `supported_parameters` includes tools,
tool_choice, JSON response_format, reasoning and max_tokens, but not the optional
parallel_tool_calls hint. Because `require_parameters:true` excludes endpoints that
do not support requested controls, the OpenRouter serializer omits only that hint.
Groq still sends `parallel_tool_calls:false`. Both providers remain subject to the
unchanged parser requirement of exactly one tool call per response; a multi-call
reserve reply is terminally rejected before any tool executes.

The observed reserve HTTP 404 did not provide a safely classified error body, so its
precise cause is not established. This declared-parameter correction is justified by
the published contract; the final attempt after omission still returned 404. It does
not establish that the hint caused the prior failures or that privacy caused them.
All zero-price/privacy filters, require_parameters, JSON mode, the selected exact
model and the common campaign counter remain unchanged.

### Evidence/entity binding clarified after a live rejection

A limited live response used real snapshot/date/evidence IDs but attached a day
entity to activity-scoped evidence. The unchanged validator rejected it. The trusted
outgoing contract now explicitly requires each reference entity to be copied exactly
from the entities array of the same evidence entry selected by evidence_id; a day
entity is not a default, and an activity ID is its UUID rather than the selected date.
The example uses issued-kind/issued-ID placeholders rather than suggesting every
reference is day-scoped. There is no server repair, reference rewriting or looser
acceptance. This clarification alone does not establish a successful live loop.

### One manual reserve replacement during limited live preparation

On 22 Nov 2026 the public OpenRouter catalog no longer listed the accepted A/B
`openai/gpt-oss-20b:free`, and its exact model endpoints projection returned zero
endpoints. Its historical model page is not evidence of current route availability.
The separately authorized live continuation therefore makes one development-time
replacement: **`particle-ai/particle-1:free`**. Groq remains `openai/gpt-oss-20b`.
The server allowlist, defaults and tests accept only this exact reserve, not the
retired model, paid Particle ID, model lists or random routing.

The [official model page](https://openrouter.ai/particle-ai/particle-1:free) documents
zero prompt/completion pricing, tools/tool_choice and structured response_format.
Its public endpoints metadata reports one Particle AI endpoint with the required
capabilities. [Particle's terms §5](https://particle.ai/terms/) state that customer
content is not used for training/model improvement without affirmative opt-in.
The [standard-inference retention policy](https://particle.ai/legal/zero-data-retention)
has scope and operational-metadata/legal/abuse exceptions; this does not establish a
universal zero-retention or EEA-only guarantee for OpenRouter and every intermediary.

All existing `max_price` fields remain zero, including per-request price, with
`require_parameters:true` and `data_collection:"deny"`. Published metadata and policy
support this one manual trial choice, but do not prove an endpoint accepts the
complete tools/JSON/reasoning/price/privacy combination. Only the bounded genuine
reserve smoke can verify that. Incompatible filters must return unavailable, never
be relaxed. The campaign's 12-total-attempt counter is not reset by this source change.

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

### Limited live outcome — 22 November 2026

The owner supplied project-only keys privately and confirmed Groq Free/model/Limits,
OpenRouter no-purchase/top-up and disabled optional logging/training controls,
including free models. Effective settings were checked without printing secrets.
This is owner attestation, not automated access to every account control.

One persisted campaign ledger reserved each actual attempt before dispatch and did
not refund failures or reset across backend restarts/source corrections. It stopped
at **11 of 12 actual inference HTTP attempts**: eight Groq and three OpenRouter.
Three private fake primary 429 events admitted the reserve scenarios; they made no
outbound Groq request and are explicitly separate from the actual attempt count.
No automatic retry, parallel load, paid route or additional model was introduced.

- **Groq protocol/tool/evidence PASS:** actual attempts 7–8 completed a model-requested
  `validate_day`, its frozen tool result, and a validated final/reference response
  through the existing UI. Server facts matched the snapshot (one planned activity,
  zero actual sessions), and the agent made no domain writes. This does **not** mean
  the explanation is factually accepted: its empty-pool/archive generalizations were
  inaccurate for the plan's four selected working dogs. References existing and
  matching evidence do not validate every prose statement. That campaign left this
  quality limitation unresolved; separately authorized P14C model-quality evaluation
  has not started. Earlier failed/rejected attempts remain spent in the ledger.
- **OpenRouter reserve FAIL / INCOMPLETE:** attempts 9–11 reached the fixed Particle
  free route with all price/privacy/parameter filters intact and returned HTTP 404.
  No reserve tool call or accepted final occurred. The application returned
  `503 ai_temporarily_unavailable`; it did not claim exhausted free quota.
  Omitting the unadvertised optional parallel-call hint did not resolve the failure.
  No usable typed upstream reason was safely observed, so its cause is **UNKNOWN**.
- **Usage/billing:** observed OpenRouter key metadata before/after reported
  `is_free_tier:true` and usage 0. This is key-scoped metadata, potentially delayed,
  not an account-wide invoice or universal measured-€0 guarantee. Groq billing
  measurement is unavailable here; its Free status is the owner's attestation.

The permitted source changes are one explicit reserve-model selection and narrow
serialization/reference instructions; parser/evidence, one-call execution, deadlines,
call caps and zero-price/privacy controls remain enforced. Accepted 500 backend/323
frontend gates remain baseline evidence, supplemented by the affected-path checks
bound to these source changes; fake responses are not substitute reserve proof.
No production feature or configuration was changed. The campaign is stopped, with
one unused slot; missing keys are not its blocker. The unresolved required result is
a genuine compatible free-reserve tool→result→final loop. P14C remains unstarted.

### Context and diagnostic follow-up — 22 November 2026

The mandatory `validate_day` projection previously retained only non-pass detail.
Four selected working dogs disappeared while ten unrelated archived states remained.
It now includes activity kind/distance, selected UUID pool and counts, eligibility
counts/reasons, selected dated states, saved-team counts, recording state and a
separate actual ledger summary. Unique dogs and activity participations are distinct.
Findings carry explicit selected/activity/actual/other-dog/housing/day scope; selected
invalid dogs take priority. Every detail carries unchanged issued frozen evidence.
Counts cover the full snapshot, and omitted activities/states/findings are counted.
The whole serialized result remains at most 16,384 bytes. No names/titles/notes/history
are added to this mandatory projection, and canonical checks/eligibility are unchanged.
The representative probe grows from 10,857 to 15,564 bytes; it retains all four selected
states and truthfully omits one unrelated archived detail, while counting all ten.

QA-only diagnostics now read fragmented/chunked/EOF error responses up to a byte cap
and deadline, retain numeric error codes and finite routing stage/count/type values,
and preserve original HTTP status on observer failure. They discard raw messages,
metadata/raw bodies, prompts/outputs, identifiers and secrets. Only the private QA
adapter opts in to [OpenRouter router metadata](https://openrouter.ai/docs/guides/routing/routers/router-metadata),
including its documented top-level error envelope; no public debug feature is added.

The authenticated [account-filtered model catalog](https://openrouter.ai/docs/api/api-reference/models/list-models-filtered-by-user-provider-preferences-privacy-settings-and-guardrails)
returned HTTP 200 with a complete validated body, but exact Particle free is **ABSENT**;
the public catalog/endpoints list it. This establishes a current account/public
availability mismatch, not the precise reason for old 404s. Missing request pricing
is not proof of zero; ZDR is not equivalent to `data_collection:deny`. The request's
zero-price/required-parameter/privacy filters remain unchanged. No reserve POST or
model substitution was attempted after this metadata result; failures or invalid
catalog bodies would instead be UNKNOWN.

A separate durable cap-six campaign was explicitly authorized for this follow-up.
It closed at **2/6**: two genuine Groq HTTP 200 turns, one model-requested `validate_day`,
and accepted final/reference JSON through the existing UI. Stated facts match one
5 km plan, four eligible active/available dogs, and zero actual sessions/dog-km; the
old empty-pool/archive generalization is gone. The prose distinguishes pool from teams
but does not explicitly state numeric zero saved teams or discuss unselected archives.
This is one bounded example, not a general quality guarantee. No further generation
was used to polish wording. All 21 domain/workspace table counts **and values** had
matching pre/post hashes. UI Reset removed the temporary plan before guarded cleanup.

The old 11/12 ledger/closure remain byte-identical; combined actual attempts are
**13/17**, with no transferred slots or new fake events. New known usage is 7,004 prompt
and 432 completion tokens; historical failed/lost usage stays unknown. OpenRouter key
metadata remained Free with reported usage zero, which may lag and is not an invoice.
P14B remains **LIVE QA INCOMPLETE / BLOCKED** until a compatible genuine reserve loop
is proved under separately authorized scope. No account settings were relaxed, no
paid route was used, and no production activation or P14C work occurred.

Targeted checks: 188 tools/providers/transport tests, 55 snapshot/API tests, 31 QA
diagnostic fixtures, 25 counter tests, four metadata/admission fixtures, Ruff and mypy.
Frontend 323 tests/build and unchanged architecture gates are reused with source
hash bindings; the full suites/build were deliberately not repeated in this scope.

### Private configuration and historical B live gate

The owner supplies a project-only private file, never credentials from another project:

```dotenv
AGENT_ENABLED=true
AGENT_OPENROUTER_RESERVE_ENABLED=false
AGENT_GROQ_FREE_ACCOUNT_CONFIRMED=true
AGENT_GROQ_API_KEY=<set privately>
AGENT_OPENROUTER_API_KEY=<set privately>
AGENT_GROQ_MODEL=openai/gpt-oss-20b
AGENT_OPENROUTER_MODEL=particle-ai/particle-1:free
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

The historical B live smoke was at most **12 inference HTTP requests total**, including
failed requests, fallback and every model turn, sequentially across the campaign.
Verify one completed Groq tool→result→final run and one completed free-reserve run;
the latter may use an isolated server-side fake primary 429, never a public selector.
Preserve exact free model/price/privacy filters and record only safe provider/model,
request/tool/count/code/timing/known-usage/evidence metadata. Stop at the cap even if
cost remains zero. Do not deliberately exhaust quotas, purchase credits or weaken
filters. Current model catalog/parameter/account compatibility and actual usage/billing
must be checked; unknown usage is not evidence of zero spend.

The required owner setup and genuine primary run are now present. A completed real
reserve run under all filters is still missing, so the honest status at that B stage was
**LIVE QA INCOMPLETE / BLOCKED on the reserve**, not P14B fully PASS. The 11-request
campaign is stopped; no script restart/source fix may reset its total or create an
unannounced budget. P14C quality/adversarial evaluation does not begin as part of B.
No production enablement, push, tag or merge is authorized here.

Published limits are guidance, not application constants or permanent free-service
guarantees: Groq model table lists30RPM/1000RPD/8000TPM/200000TPD; organisation Limits
is authoritative. OpenRouter zero-purchase :free guidance is20RPM/50RPD, including
failed attempts. A run can spend multiple requests. Current account Limits remain
authoritative; no quota was consumed in A. B now has owner account attestation and a
completed genuine primary protocol/tool/reference loop, while model prose quality,
reserve completion and exact Groq billing are not established.
OpenRouter deny filters and required account logging/training controls
do not prove universal provider retention or region; abuse/legal exceptions apply.

Official references inspected for A (21 Nov2026; recheck in B):
[Groq tool use](https://console.groq.com/docs/tool-use/overview),
[API fields](https://console.groq.com/docs/api-reference),
[limits](https://console.groq.com/docs/rate-limits),
[billing](https://console.groq.com/docs/billing-faqs),
[deprecations](https://console.groq.com/docs/deprecations),
[Historical OpenRouter GPT-OSS free model](https://openrouter.ai/openai/gpt-oss-20b:free),
[provider/price filters](https://openrouter.ai/docs/guides/routing/provider-selection),
[limits](https://openrouter.ai/docs/api/reference/limits),
[data collection](https://openrouter.ai/docs/guides/privacy/data-collection).

## Evaluation and scope

`python -m app.operations.evals` runs12 small deterministic fixtures with expected
rule/status/value/evidence checks, no model or provider request. Pure-tool tests cover
strict arguments and evidence; real disposable PostgreSQL covers shared locks,
snapshot/no-write/isolation, historical/future bounds and lifecycle; fake HTTP/state
tests cover serial turns, mid-run restart, rejection, deadlines and budget. These
are not 12 model-quality evaluations. The current P14C scope replaces that earlier20–30-model-scenario expectation with a
12-row mixed-method matrix and three prespecified Groq cases within a separate cap8;
its genuine quality outcomes remain NOT VERIFIED after a rate-limit failure.

G-DOC-01 clarification: P13G's pre/post-Apply comparison establishes unchanged
**Work.summary / actual-work metrics for all16 dogs**. It does not establish equality
of complete Work DTOs including history/weekly arrays. No historical accepted archive
was rewritten. G-PRIVACY-01 names ht_demo_session and notes/housing use, keeps TTL
runtime-driven, and describes Reset accurately: deletes mutable workspace data, does
not delete the cookie and does not extend its existing expiry. Privacy GET never
creates a workspace or optional browser storage.

### B live-smoke model-quality limitation

The accepted Groq result is a protocol/tool/reference PASS, not a claim of accurate
free prose. Its screenshot contains an observed prose error: it calls the selected
four-dog pool empty and generalizes archived-dog findings. Server facts correctly
show one saved activity and zero actual work, and references passed strict binding.
No validator or facts were changed to accept the wording. This limitation is recorded
for later review at that time. The subsequent accepted context fix removed that
observed loss; current C scope/outcome are stated at the top of this document.
