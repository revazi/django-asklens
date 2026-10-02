# Host throttle, concurrency, and AskLens observability controls

AskLens intentionally delegates transport and volume controls to the host project.
This guide shows host-owned, non-package controls for the optional DRF API and
other entry points.

## 1) Authenticated principal + DRF/proxy rate controls

For API routes, keep principal-based controls in host configuration:

- Enforce route permissions with `DJANGO_ASKLENS["API_PERMISSION_CLASSES"]`.
- Add DRF throttles on the AskLens query route.
- Use `UserRateThrottle` (or equivalent) for authenticated principal-bound
  limits; authenticated user identity comes from host auth and request principal,
  not headers.
- Apply proxy/IP extraction (for example `X-Forwarded-For`) only for IP-based
  anonymous or secondary controls after explicit trusted-proxy configuration.
  Do not let spoofed proxy headers choose authenticated identity.

Example route-level pattern:

```python
from rest_framework.throttling import UserRateThrottle
from django_asklens.api.views import QueryView


class AuthenticatedQueryThrottle(UserRateThrottle):
    rate = "60/min"


urlpatterns = [
    path(
        "asklens/query/",
        QueryView.as_view(
            throttle_classes=[AuthenticatedQueryThrottle],
        ),
        name="asklens-query",
    ),
]
```

A focused regression test in this repository proves that this transport-stage
throttle can return `429` before `execute_asklens_query_request` runs, before any
application-table SQL, and without creating a query audit event.

## 2) MCP, Python, and provider entry points still require host guards

AskLens does not own all transport controls for non-API entry points.
Host projects must keep equivalent controls before calling into AskLens
helpers:

- authenticate and bind trusted context (`request.user` / request-like principal);
- authorize tool calls at the host boundary;
- enforce rate limiting and quotas where requests can flood the host;
- enforce timeout budgets and bounded concurrency per host worker;
- enforce host transport and payload-size limits before facade call.
- keep every provider/client output as untrusted until it is validated by
  AskLens facade parsing and semantic checks.

Equivalent guarding is especially important when using:

- `django_asklens.querying.execute_asklens_query_request` from custom Python paths;
- MCP tool wrappers (`django_asklens.mcp` wrappers or custom servers).

## 3) Concurrency and timeout coordination

AskLens structural budgets are not traffic/concurrency controls.
Coordinate host limits so the transport layer rejects overload before ORM work:

- apply request-level timeouts (ASGI/WSGI/proxy) and keep them coordinated with
  DB statement timeouts;
- keep database roles and statement policies read-focused where possible;
- limit concurrent in-flight query handlers by process semaphore/worker budget;
- test cancellation, saturation, and cleanup behavior at the host layer.

## 4) Throttle denial and AskLens audit behavior

When DRF throttling or proxy rate decisions reject a request, execution does not
reach AskLens request orchestration in this package.
Expected result:

- HTTP `429`; AskLens DRF views use the fixed `asklens.budget.exceeded` error envelope and preserve DRF's `Retry-After` header when supplied, while an upstream proxy owns its response;
- no call to `execute_asklens_query_request`;
- no AskLens query audit event for that request;
- independent host logs for rate-limit denial decisions can be kept distinct from
  execution/audit event streams.

If a request passes host controls, AskLens executes normally and applies
`AUDIT_MODE` as configured.

## 5) Privacy-safe host observability callback

`DJANGO_ASKLENS["OBSERVABILITY_SINK"]` is `None` by default. A host may set a
callable or dotted callable path. It receives one immutable
`django_asklens.observability.ObservabilityEvent` at a time and requires no
telemetry dependency:

```python
from django_asklens.observability import ObservabilityEvent


def observe_asklens(event: ObservabilityEvent) -> None:
    # Keep these bounded dimensions as labels.
    labels = {
        "name": event.name,
        "status": event.status,
        "resource": event.resource or "none",
        "intent": event.intent or "none",
        "error_code": event.error_code or "none",
    }
    # Record these as measurements, never labels.
    record_metrics(
        labels=labels,
        duration_ms=event.duration_ms,
        result_count=event.result_count,
        truncated=event.truncated,
    )


DJANGO_ASKLENS["OBSERVABILITY_SINK"] = observe_asklens
```

The callback contract has exactly eight fields: `name`, `status`, `resource`,
`intent`, `error_code`, `duration_ms`, `result_count`, and `truncated`. Valid
outcomes are:

| `name` | `status` | Other field semantics |
| --- | --- | --- |
| `asklens.plan.accepted` | `accepted` | `resource` and `intent` are safe names from a currently validated plan; no error or result metadata. |
| `asklens.plan.rejected` | `rejected` | `resource` and `intent` are always `None`, so unknown or unauthorized caller names cannot become labels; `error_code` is canonical. |
| `asklens.execution.succeeded` | `succeeded` | Safe resolved resource/intent plus `result_count` and `truncated`; no error code. |
| `asklens.execution.failed` | `failed` | Safe resolved resource/intent and canonical `error_code`; no partial result metadata. |

`duration_ms` is a non-negative integer measured with the process monotonic
clock, rounded to the nearest millisecond. A facade `plan.accepted` or
validation `plan.rejected` duration covers current plan parsing and validation.
A direct pre-plan rejection also covers facade context resolution up to that
rejection. A shared-orchestration pre-facade rejection instead covers the
interval from orchestration entry through its final rejection, which can
include permission resolution, presentation parsing, intent routing, and
provider planning as applicable. Execution duration covers scope preparation,
ORM compilation/evaluation, and trusted serialization; it excludes audit and
callback delivery. These are operational observations, not SLA or billing
clocks, and durations from different event categories are not interchangeable.
`result_count` is the number of returned rows or groups after the AskLens limit
and is bounded by the current trusted row/group budget; `truncated` says whether
AskLens detected more rows/groups. Both occur only on successful execution.

Delivery is best effort. Once the trusted facade has built its audit context,
it completes the authoritative audit attempt before scheduling one callback
attempt for each applicable event. Outside an initialized Django transaction,
callback delivery is synchronous. For every initialized database connection in
an `atomic()` block at emission time, AskLens registers the immutable lifecycle
batch with `on_commit()` and delivers only after all of those callbacks run. A
rollback on any one of those connections discards its callback, so the whole
batch is dropped rather than partially delivered. A facade called inside a
host-owned `atomic()` block can therefore return before deferred delivery.

Django has no public `on_commit()` facility while autocommit is disabled through
manual transaction management outside `atomic()`. If any initialized connection
is in that state, AskLens conservatively drops the batch. It does not invoke the
sink before commit or depend on backend transaction internals. These rules keep
the sink out of every transaction active at emission time: an ordinary sink
database error cannot mark such a caller transaction rollback-only, and a
built-in audit row in such an `atomic()` transaction commits before delivery.
Observability remains best effort and must not be used to infer commit or audit
persistence.

A validated execution attempts `plan.accepted` followed by one execution
outcome; a validation rejection attempts only `plan.rejected`. If a direct
facade call is rejected while resolving its request, permissions, or audit
context, no facade audit context exists and one opaque `plan.rejected` is
scheduled without creating or changing an audit outcome. The untrusted plan is
not parsed. For the same pre-plan failure under shared orchestration,
observation is deferred so the shared external audit attempt remains first and
only one rejection event is scheduled. Other final provider/orchestration
failures that occur before the facade likewise schedule one opaque
`plan.rejected` after external audit. Capability/help responses and transport
denials do not claim plan/execution events. Repeated facade calls are separate
lifecycles.

An invalid setting or failed dotted import disables delivery. A scheduling or
callback exception is suppressed and stops the remaining events for that
lifecycle. There is no retry or fallback sink. AskLens does not consult callback
return values and its delivery path does not authorize requests, execute
rejected plans, rerun queries, replace public errors, alter result bytes, or
change/conceal the authoritative audit attempt. Recursive delivery triggered
inside a sink is suppressed in that context; concurrent request contexts remain
independent. The callback is ordinary trusted host process code, not a sandbox:
hosts remain responsible for its latency, database/network operations, and
other side effects.

Use `name`, `status`, resolved `resource`, `intent`, and canonical `error_code`
only as bounded dimensions. Resource cardinality is bounded by the host's
explicit registration set. Do not use durations or counts as labels. Hosts must
not enrich events with request content merely because an external telemetry
SDK supports arbitrary attributes.

The event cannot contain questions; complete or partial plans; field, metric,
filter, order, or group names/values; rows/groups or result values; identity,
user, tenant, permission, or scope data; credentials; provider/client payloads;
private bindings; raw exceptions, diagnostics, or messages; database aliases;
SQL; or arbitrary client-supplied unknown names. Inspecting those values in
host closure/request state would violate the contract even though the package
did not pass them.

Observability is not audit. `AUDIT_MODE`, `AUDIT_SINK`, built-in audit storage,
and `AUDIT_INCLUDE_CONTENT` retain their existing separate semantics. An
observability callback must not be used as proof that an audit record was
persisted, and an audit sink should not be repurposed as this typed event API.

## 6) Built-in database audit routing and read privacy

`DJANGO_ASKLENS["AUDIT_DATABASE_ALIAS"]` is optional and server-owned. `None`
preserves ordinary Django write/read routing. A configured non-empty alias is
used explicitly for built-in `SemanticQueryRun` writes and
`GET /asklens/runs/<id>/` reads; client payloads cannot override it and failures
do not fall back to `default`. Malformed, nonexistent, unavailable, or missing-
table aliases use normal sink-failure behavior on write and one fixed safe
`asklens.execute.failed` envelope on read without reflecting alias/database
diagnostics.
Lifecycle command `--database` selection remains an independent explicit
operator choice.

Configured API permission classes still gate run detail before lookup. The
owner may read a row; cross-user review requires Django's global
`asklens.view_semanticqueryrun` permission. `is_staff` alone is not enough, while
active superusers follow normal Django permission behavior. Authorization is
part of the queryset, so missing and inaccessible IDs share an opaque `404` and
a read creates no new audit event.

Run-detail serialization reapplies the current content policy. Unless
`AUDIT_INCLUDE_CONTENT` is exactly boolean `True`, questions are blank and plans
are reduced to safe resource/intent metadata even for legacy rows. Stored free-
form error text is never reflected: recognized AskLens codes receive canonical
safe messages, unknown/malformed text receives a fixed generic safe error, and
success/blank errors become `null`. Full-content hosts own retention, access,
redaction, deletion, backups, replicas, and every alternate display/export
surface. Never place bindings, permission strings, tenant IDs, credentials,
rows, provider payloads, or raw rejected input into host audit views.

## 7) Sink failures and control boundaries

`AUDIT_SINK` failures must be logged and ignored for execution flow.
A sink error must not trigger query re-run, nor become an authorization or rate
limiter gate.

## 8) Manual built-in database-audit lifecycle commands

AskLens provides manual, preview-by-default redaction and irreversible purge for
built-in `SemanticQueryRun` rows:

```bash
python manage.py redact_asklens_audit \
  --before 2026-08-01T00:00:00Z \
  --database default \
  --batch-size 1000

python manage.py purge_asklens_audit \
  --before 2026-08-01T00:00:00Z \
  --database default \
  --batch-size 1000
```

Both cutoffs must be strict uppercase, offset-aware RFC 3339 timestamps in the
past; batch size is bounded from 1 through 10000. Preview counts eligible rows
at one point in time and performs no writes. Only trusted operators should add
`--execute`. Output contains no high-water/row IDs or stored content.

Redaction execution needs update permission and only updates `question` and
`plan` on selected built-in rows, retaining each audit row and its operational
fields. Redaction does not capture a primary-key high-water boundary: it selects
batches until no eligible content remains. Concurrent deletes or rewrites can
make its count differ from preview, while later eligible inserts, including
higher-PK rows, can be included in the same run and prolong it. Each redaction
batch commits independently; a failing batch rolls back its updates while rows
handled by earlier committed batches remain redacted. Rerun preview and
reconcile before retrying.

Purge execution needs delete and related-object permissions and targets eligible
`SemanticQueryRun` rows through its initial primary-key high-water boundary.
Ordinary later higher-PK inserts wait for another run. Manually inserted or
reused lower PKs and concurrent changes are not covered by a snapshot guarantee;
actual deleted-row counts may differ from preview.

Before purge, establish and test a backup/restore plan. Normal Django delete
signals run, and collector relationships may cascade, update, protect, restrict,
or otherwise block related host rows. Each batch commits independently. A
failing batch rolls back, but earlier committed batches remain deleted if a
later batch or signal fails. Rerun preview and reconcile before retrying.
External effects performed by host signal handlers cannot be rolled back.

The command code does not resolve or invoke configured `AUDIT_SINK` callables.
Host delete signals and relationships may perform their own effects. Custom-sink
storage, backups, and replicas remain host-owned. AskLens does not schedule
these commands or choose an automatic retention policy, and they do not
complete host user/tenant access or deletion-request workflows.

The packaged `SemanticQueryRun` admin preserves inherited Django view semantics
for its list and detail pages but denies add, change, and delete for every
principal, including superusers. Its action filtering removes
`delete_selected`. Redaction and purge remain separate AskLens-provided operator
workflows; they are not universal host authorization or mutation controls and
do not prevent ORM, direct database, custom-sink, or host-defined administrative
writes. Restrict command execution and every other storage path separately.

## 9) No mandatory telemetry or queueing dependencies

The callback adds no OpenTelemetry, Prometheus, logging, network, background
queue, cache, or service-mesh dependency. Hosts may adapt the typed events to
those systems under their own privacy, cardinality, availability, and retention
policy; those transports and dashboards are not package requirements or
production acceptance evidence.
