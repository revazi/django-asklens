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

- HTTP `429` from DRF/proxy response handling;
- no call to `execute_asklens_query_request`;
- no AskLens query audit event for that request;
- independent host logs for rate-limit denial decisions can be kept distinct from
  execution/audit event streams.

If a request passes host controls, AskLens executes normally and applies
`AUDIT_MODE` as configured.

## 5) Audit sink guidance

For this pre-0.2 alpha-candidate scope, the current operational audit sink for
custom integrations is:

- `DJANGO_ASKLENS["AUDIT_MODE"] = "custom"` with `AUDIT_SINK`
- `DJANGO_ASKLENS["AUDIT_INCLUDE_CONTENT"] = False` by default.

This repository does **not** define a frozen external event schema.
Treat sink payloads as package-internal operational metadata and avoid expanding
publicly visible fields without explicit agreement.

For a host-observed metric model, keep metadata low-cardinality:

- `status`;
- `resource` (when present);
- `intent` (when present);
- `error_code`.

Use numeric observations for:

- `duration_ms`;
- `row_count`.

`error_code` may be a stable label; do not use free-form `error_message` in
metric labels. Keep human-readable error messages in controlled logs where
retention, access, and redaction are enforced.

Do **not** include, export, or index these request-level values by default:

- question text;
- full validated/supplied plan payload;
- filter values or rendered SQL;
- row contents/rows returned;
- credentials or permission strings;
- tenant IDs or raw user identifiers;
- provider payloads.

## 6) Sink failures and control boundaries

`AUDIT_SINK` failures must be logged and ignored for execution flow.
A sink error must not trigger query re-run, nor become an authorization or rate
limiter gate.

## 7) Manual built-in database-audit redaction

AskLens provides one manual, preview-by-default lifecycle command for built-in
`SemanticQueryRun` rows:

```bash
python manage.py redact_asklens_audit \
  --before 2026-08-01T00:00:00Z \
  --database default \
  --batch-size 1000
```

The cutoff must be a strict uppercase, offset-aware RFC 3339 timestamp in the
past. Preview counts eligible rows at one point in time and performs no writes.
Only a trusted operator should add `--execute`; the selected alias then needs
update permission. Execution clears `question` and `plan` only, in bounded
batches, while retaining the audit row and operational fields. Output contains
no audit row IDs or stored content.

The command acts on the selected built-in database table regardless of current
`AUDIT_MODE`; it does not call custom sinks. Custom-sink storage, backups, and
replicas remain host-owned. AskLens does not schedule this command, choose a
retention policy, purge rows, or complete host deletion-request workflows.

## 8) No mandatory telemetry or queueing dependencies

AskLens does not require OpenTelemetry, Prometheus, background queues, a cache,
or service mesh to satisfy this hardening slice.
Host projects can add them later if needed for operations, but they are not
package requirements.
