# Troubleshooting setup and query failures

Use this decision path with [Your first scoped question](quickstart-app.md) or
an existing host integration. Start with the synthetic, offline `dummy` backend
and an **exact configured question**. Do not switch to a live provider, enable
content logging, increase privileges, or widen row scope to make a failure pass.

There are two audiences:

- **Query users / UI authors:** use the safe outcome and recovery guidance below.
  An unavailable member must not reveal whether it exists or is forbidden.
- **Authorized host maintainers:** review startup wiring, migration state and
  server-owned configuration privately, using existing host access. Query access
  is not audit or configuration access. Never return private bindings, permission
  lists, tenant identities, questions, provider bodies, credentials or raw
  exceptions as troubleshooting hints. Do not paste raw logs into support tickets.

This guide adds no diagnostic endpoint, catalog dump, permission, or error code.
The [0.3.x compatibility boundary](compatibility.md) governs canonical public
errors; adapter envelopes/statuses remain provisional.

## 1. Can Django start?

Run the ordinary host checks with the **same environment and settings module**
as the failing process. In the copied quickstart, for example:

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py check_asklens --fail-on-empty
.venv/bin/python manage.py migrate --check
```

These are separate checks, not an all-in-one readiness test. In another host,
use its normal interpreter, settings and authorized deployment procedure. For
API/admin/MCP example settings, select the module used by that adapter, not only
the base quickstart settings.

| Observation | What it establishes | Safe host next step |
| --- | --- | --- |
| Django startup raises a duplicate-registration error before any summary | Registration was attempted twice in this process; the command did not run | Keep the host app config in `INSTALLED_APPS` and one registration import from `AppConfig.ready()`. Remove duplicate execution/import paths; do not swallow the exception or clear the registry to hide it. |
| Startup rejects a resource definition | Registration validation failed, not a provider or data-query failure | Review the explicit resource definition privately: approved field/metric bindings, declared IANA timezone, scope mode and required trusted scope provider. Follow [registration](registration.md). |
| `check_asklens` reports `Status: EMPTY` | No resources are in this process's default registry | Verify the correct app config/settings, the single startup import, and use of the default registry by the integration. A resource in a separate custom registry does not populate the default one. |
| `--fail-on-empty` exits nonzero after the empty summary | The optional empty-registry deployment gate worked | Fix registration wiring, not permissions or provider configuration. Without this flag, an empty registry exits successfully. |
| `Status: OK` but the intended registration is missing | At least one resource was registered, not necessarily the intended set | Review the expected registration wiring in host code; counts are not a named inventory. Do not add a default full-catalog dump. |
| `migrate --check` exits nonzero | The selected database has unapplied migrations | Apply the host's reviewed migrations through its normal deployment process, then rerun the check. Do not suppress errors, fake migrations, or delete a host database. |

### What the checks do **not** promise

Django's `check` does not provide an AskLens-specific configuration/readiness
check. It can pass while migrations are unapplied or AskLens settings are
invalid. `makemigrations --check --dry-run` detects model/migration drift; it does
**not** establish that migrations were applied to the selected database.

`check_asklens` reports only aggregate resource, scope-mode, field and metric
counts from the in-memory default registry. It owns **zero application-data
SQL**, does not invoke scope providers or live providers, and does not resolve
request permissions. It does not test tables, audit persistence, provider
configuration, every AskLens setting, or whether a particular user can query.
`Status: OK` is not authorization or production readiness. If a new diagnostic
would need more data, privilege, or output detail, stop for a separately reviewed
output/permission contract rather than extending this counts-only command.

**Startup limitation:** Django loads settings, app imports and `AppConfig.ready()`
before command handling. Arbitrary host startup code (including other apps or
host checks) is outside the command's guarantee; it can perform SQL, call
providers, fail, or have other side effects. Keep registration startup
metadata-only. Do not claim that running the whole Django process is SQL- or
network-free just because the command's own handler is.

With database audit enabled, apply AskLens and authentication migrations on the
host-selected audit database too. Audit routing/aliases are server-owned; follow
[host audit controls](host-throttle-and-audit-controls.md). Audit sink writes are
best-effort: a missing audit table can leave a successful query without a stored
run. Conversely, a missing registered application table can fail execution.
Neither symptom proves that `check_asklens` is broken. Verify audit readiness
through existing authorized host operations and synthetic integration tests,
not by exposing audit storage or raw database errors to query users. Do not
turn off audit or enable `AUDIT_INCLUDE_CONTENT` to work around setup mistakes.

## 2. Did the request reach query execution?

First verify the chosen adapter's existing authentication, CSRF and route
permissions: [API/admin](usage.md#authenticated-normal-user-api-quickstart),
[custom UI](custom-ui.md), or [MCP](mcp-integration.md#bounded-mcp-quickstart).
A route-gate denial can happen before orchestration and create **no query audit
row**. HTTP status alone is not a core execution category: the API also uses
safe authorization errors for route/CSRF failures and budget errors for
throttling. Do not require an audit row or retry the same unauthorized request
indefinitely.

After a host changes a user's permissions, use a fresh authenticated request
(and refresh host-side user permission caches as appropriate). Never accept
permissions, identity or tenant scope from question text, headers chosen by a
client, or a client-supplied plan. Native admin staff access and MCP connection
access do not independently authorize resource members or rows.

## 3. Is the outcome an error, help, or a successful result?

Inspect the safe `error.code`, not raw diagnostic text or guessed member names.
Python callers catch `PublicAskLensError` and serialize it with
`public_error_payload()`; see [stable execution errors](core-python-api.md#stable-execution-errors).
The ten canonical categories and fixed execution messages remain unchanged:

| Code / fixed execution message | Safe next step for the caller | Authorized host diagnosis (never client detail) |
| --- | --- | --- |
| `asklens.parse.invalid` — The query plan could not be parsed. | Use a supported plan shape or a reviewed exact dummy question. | Check the untrusted plan/envelope shape against the current integration; reject extra keys, invalid types and malformed JSON. Do not display parser input or exceptions. |
| `asklens.plan.invalid` — The query plan is invalid. | Simplify the question using supported operations. | Review semantic constraints and supported types/operators in a synthetic fixture. A shape-valid plan is not execution authorization. |
| `asklens.provider.failed` — The query provider could not produce a usable response. | In dummy mode, choose an exact configured starter question; otherwise retry only under the host's bounded retry policy or contact the host. | Check exact dummy wording first. Privately review backend configuration and approved provider health/timeout controls; do not return provider bodies, endpoints, keys or raw errors. |
| `asklens.member.unavailable` — A requested query member is unavailable. | Choose another approved question or contact the host. | Verify intended registration and current server-derived access privately. Unknown and denied resources, fields and metrics are deliberately indistinguishable. Do not disclose whether a protected member exists or tell the user which permission is missing. |
| `asklens.authorization.denied` — The current request is not authorized to execute this query. | Sign in through the host's normal flow or contact the host; do not supply alternate identity claims. | Verify trusted current-request identity/permission resolution and adapter route gates. Do not grant superuser access to diagnose a query. |
| `asklens.scope.unavailable` — A safe query scope is unavailable for this request. | Contact the host if a fresh authenticated request still fails. | Review the trusted scope provider's lazy queryset and registered model. Never fall back to an unrestricted manager or reveal tenant existence. |
| `asklens.budget.exceeded` — The query plan exceeds an execution limit. | Narrow approved filters/selections or reduce the requested limit; respect any adapter retry delay. | Review structural limits or host throttling without raising limits blindly. Limits do not replace statement/request timeouts. |
| `asklens.binding.invalid` — The query plan could not be bound safely. | Contact the host; changing identity or guessing fields is not recovery. | Review resource bindings and relevant settings, including audit mode/content/sink types. Invalid audit configuration can reject execution before application SQL even when both startup checks pass. |
| `asklens.compile.failed` — The query plan could not be compiled. | Contact the host with the safe category. | Reproduce using a reviewed synthetic plan and the supported Django/database combination. Keep ORM paths and compiler causes private. |
| `asklens.execute.failed` — The query could not be executed. | Retry only if the host advises it; otherwise contact the host. | Check migrations, database availability, timeouts and result-type declarations through approved host operations. Do not reflect SQL or database exceptions. |

An optional safe JSON `pointer` identifies a plan location, not a permission
hint. Do not append diagnostic text to these messages. Route-level adapters may
use their own fixed safe wording within the same category; do not parse messages
to infer policy. The [API error envelope](usage.md#4-query-through-the-optional-api)
and core exception are different surfaces.

### Dummy mismatch versus malformed plan versus provider failure

`DummyProvider` does not interpret arbitrary natural language. With the default
`DUMMY_DEFAULT_PLAN=None`, an unmatched string returns `asklens.provider.failed`;
this is not evidence of a network outage or denial. Compare the exact configured
question privately, including case and punctuation, or use a host-approved
starter. Do not enumerate private question mappings in an error response or
configure a catch-all plan to hide a mismatch.

An **exact** configured question can still map to an invalid envelope or plan.
Malformed provider envelopes may return `asklens.plan.invalid`; structural
untrusted-plan failures at the execution facade use `asklens.parse.invalid`.
Semantic validation and access checks can return other canonical categories.
Fix the reviewed fixture, not the validation. A real provider transport/response
failure also maps to `asklens.provider.failed`; the public code intentionally does
not expose its underlying body or cause. Default verification needs no live call.
See [providers](providers.md) for the existing configuration contract.

### Separately authorized synthetic provider preflight

The new source/candidate [standalone preflight](providers.md#standalone-fixed-synthetic-preflight)
can reject missing/invalid configuration offline. An actual provider request
requires a separate explicit `--allow-network-and-charges` invocation after the
network/charge disclosure and operator authorization. Do not run it from
`manage.py` or a bootstrapped host: the standalone path avoids Django setup,
settings resolution, registry access, scopes, rows, application SQL and audit
writes. It uses only a fixed synthetic prompt/schema, no private questions or
catalog. Its output is fixed safe categories and, on success, non-sensitive
configuration/date metadata, not raw causes or bodies. It bypasses provider-I/O
logging even if that host setting is enabled.

**Live path UNVERIFIED; actual acceptance INCOMPLETE.** A tiny synthetic pass
would not validate the current full AskLens strict schema, authorize a user,
prove scope/audit readiness, or establish production acceptance. The
[source/candidate offline schema gate](providers.md#offline-strict-schema-gate-resolved-live-acceptance-still-incomplete)
is now repaired at the OpenAI-compatible boundary, not by changing application
QueryPlan contracts: optional non-nullable values use null omission markers on
the strict wire and normalize back before existing validation. All actual
emitted planner/unified objects were already closed; unused raw model schemas
were the source of the earlier open-map report. Open maps are not silently
truncated or accepted. Actual live application acceptance and the deprecated
snapshot's lifecycle/model-selection gates remain unresolved in #188. A later
HTTP 400/422 still does not identify schema rejection rather than another
request rejection. Do not disable strict mode, weaken validation/permissions,
substitute a model silently, or enable provider I/O logging to bypass a failure.
`check_asklens` remains counts-only and never invokes this probe.

### Empty is success, not denial

A successful list or grouped query can return typed `columns`, `data: []` and
`row_count: 0`. Display “No rows” within the current authorized scope; do not
convert it to an error, retry as a more privileged user, widen scope, or claim
there are no rows anywhere. An ungrouped aggregate instead returns one row:
count metrics are `0`, other aggregates are `null`. Respect truncation metadata
on nonempty results. A capabilities/help response is not a data result and must
not be rendered as an empty table.

The existing quickstart has exact success and empty questions plus opaque
permission denial. Its [consumer/adapter tests](usage.md#4-audit-and-safe-recovery)
exercise the real app, including metadata-only audit and zero unauthorized
application-data execution. Keep `AUDIT_INCLUDE_CONTENT=False`; successful
responses can contain authorized question/plan/data content, but troubleshooting
and default audit storage must not copy it. Browser consumers should use safe
text rendering and bounded generic recovery, never raw response bodies; see
[the minimal UI](custom-ui.md).
