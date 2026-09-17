# AskLens specification

Status: **draft, unversioned**. This is the AskLens specification. Django AskLens in this repository is the first implementation.

There is one current document shape. Do not add schema versions, revisions,
negotiation fields, or previous-shape compatibility.

This is not an NDC profile, not a published multi-implementation standard, and
not proof of a second backend. A later independent implementation should reuse
these documents and the language-neutral conformance corpus.

## What AskLens is

AskLens is a read-only semantic query contract over explicitly registered
application data.

A caller supplies an untrusted plan. A trusted implementation:

1. parses the plan;
2. resolves current identity, permissions, catalog, resource, and row scope;
3. validates semantics and budgets;
4. compiles a read-only query from private bindings;
5. executes;
6. serializes a deterministic result;
7. writes privacy-aware audit metadata.

A schema-valid plan remains untrusted. Parsing establishes structure only.
Execution always repeats current authorization, catalog, scope, and budgets.

AskLens does not execute LLM-generated SQL, mutate data, auto-expose models, or
accept client-owned identity, permissions, tenant IDs, or scope.

## Documents

The specification has five unversioned JSON documents:

- `catalog` — permission-scoped resources, fields, and metrics
- `query-plan` — untrusted list or aggregate request
- `capabilities` — machine-readable types, operators, intents, and limits
- `result` — deterministic columns, rows or groups, and truncation metadata
- `error` — safe code, message, and optional JSON Pointer

Machine-readable Draft 2020-12 schemas ship with the Django implementation under
`django_asklens/contracts/schemas/`. Language-neutral fixtures live in
`conformance/`.

HTTP, MCP, admin, and UI envelopes may wrap these documents. Wrappers are
implementation surfaces. They must not add a second query contract.

## Query core

- Read-only.
- One resource per plan.
- `list` and `aggregate` intents.
- Implicit-AND filters.
- Registered fields and metrics only.
- Bounded, deterministic results.
- Public semantic keys are not backend traversal paths.

Plans name metrics by registered semantic name only:

```json
{"metric": "revenue"}
```

The plan does not choose the aggregate function, backing field, distinct
behavior, or permission policy. Those are trusted registration.

Presentation, if any, is a separate envelope after execution. Presentation cannot change authorization, compilation, ordering, limits, or returned values.

## Query plan

Required members are `resource` and `intent`. Optional members are `filters`,
`select`, `group_by`, `metrics`, `order_by`, and `limit`. Additional properties
are rejected.

Illustrative aggregate plan:

```json
{
  "resource": "orders",
  "intent": "aggregate",
  "filters": [
    {"field": "created_at", "op": "last_n_days", "value": 30}
  ],
  "group_by": [{"field": "status"}],
  "metrics": [{"metric": "revenue"}],
  "order_by": [{"metric": "revenue", "direction": "desc"}],
  "limit": 100
}
```

A `list` plan selects semantic fields. An `aggregate` plan groups and/or
references registered metrics. Visualization is not a plan member.

## Catalog and capabilities

The catalog is permission-scoped. Unknown and unauthorized members are publicly
indistinguishable.

Machine capabilities declare supported intents, types, operators, time grains,
and structural limits. They omit resources, labels, examples, permission tokens,
tenant identifiers, and backend bindings.

Human help may include labels, descriptions, and examples. Help is not
authorization.

Public catalogs omit private bindings, ORM paths, expressions, QuerySets, scope
providers, and tenant identifiers.

## Trust model

Every plan is untrusted, including provider output, HTTP/MCP clients, saved
plans, UI edits, Python callers, and previously validated payloads.

Server-owned context includes:

- current identity and permissions;
- catalog and resource registration;
- row scope;
- request clock and resource timezone;
- audit policy.

Clients cannot supply trusted permission strings, tenant IDs, scope tokens, or
prepared execution state. Preview validation is not an execution token.
Prepared/bound state is internal, short-lived, and bound to the current request.

Rejected plans issue no registered application-data queries. Database audit mode
may write at most one metadata-only insert. Audit failure must never trigger
execution.

## Scope

Every resource is `global` or `context_scoped`. There is no unrestricted
manager fallback.

- `context_scoped` requires a trusted server-side scope mapping from the current
  request to that resource's rows.
- `global` is an explicit reviewed decision that the resource is not
  request-scoped.
- Missing, invalid, or failed scope rejects before application-data SQL.

Row scope and field/resource permissions are complementary. Neither replaces
the other.

## Types and operators

Canonical field types are `string`, `boolean`, `integer`, `decimal`, `float`,
`date`, `datetime`, `time`, `uuid`, and `enum`.

Operators are type-specific:

| Type | Operators |
| --- | --- |
| `string` | `eq`, `neq`, `contains`, `icontains`, `in`, `isnull` |
| `boolean` | `eq`, `neq`, `in`, `isnull` |
| `integer`, `decimal`, `float`, `time` | `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `isnull` |
| `date`, `datetime` | `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `isnull`, `date_range`, `last_n_days`, `last_n_months` |
| `uuid`, `enum` | `eq`, `neq`, `in`, `isnull` |

Rules:

- Every filter has a non-null `value`.
- `isnull` takes a boolean.
- `neq` excludes null rows.
- `contains` / `icontains` require nonempty strings.
- Relative time uses the injected aware request clock and an explicit
  server-owned IANA resource timezone. Clients cannot choose the timezone.
- `last_n_days` is a rolling duration. `last_n_months` is calendar subtraction
  in the resource timezone. Both exclude `now` as an exclusive upper bound.

## Results

Successful results are typed columns plus `data` rows or groups.

- List and grouped queries fetch `limit + 1` and set `truncated` from the extra
  row.
- Ungrouped aggregates return one row and `truncated: false`.
- Empty ungrouped `count` is `0`; empty `sum` / `avg` / `min` / `max` are `null`.
- Empty grouped aggregates return no rows.
- Decimal aggregates use canonical minimal plain-decimal strings.
- Datetimes include an offset. UUIDs are canonical strings.
- Unsupported runtime objects fail rather than being stringified.

## Errors

Public failures expose only:

- a stable namespaced `code`
- a safe `message`
- an optional JSON Pointer

Current codes:

- `asklens.parse.invalid`
- `asklens.member.unavailable`
- `asklens.plan.invalid`
- `asklens.authorization.denied`
- `asklens.scope.unavailable`
- `asklens.budget.exceeded`
- `asklens.binding.invalid`
- `asklens.compile.failed`
- `asklens.execute.failed`
- `asklens.provider.failed`

Unknown and unauthorized members use `asklens.member.unavailable`. Tracebacks,
bindings, tenant identifiers, and raw provider payloads are not public error
content.

## Budgets

Implementations enforce structural bounds before compilation. Django AskLens
defaults:

| Budget | Default |
| --- | ---: |
| Plan payload | 64 KiB UTF-8 |
| Filters | 20 |
| Selected fields | 25 |
| Order terms | 5 |
| Group terms | 3 |
| Metrics | 5 |
| Relationship hops | 2 |
| Unique relationship edges | 8 |
| Values per `in` | 100 |
| Total scalar filter values | 200 |
| Returned rows/groups | 500 |
| Default result limit | 100 |

Above-bound plans reject with `asklens.budget.exceeded` and zero
application-data SQL. Omitting rows from an MCP response does not make the
query cheap; budgets still apply.

Hosts still own statement timeout, request timeout, rate/concurrency limits,
read-only credentials, indexes, and capacity.

## Conformance

The `conformance/` corpus is the language-neutral executable spec. Each case
has a catalog snapshot, capabilities, untrusted plan, expected result or error,
and expected application-data query count.

Fixtures cannot choose authorization or scope. The implementation harness maps
a scenario identifier to server-owned context.

Django AskLens replays the corpus on SQLite and on required PostgreSQL 15/18 CI
stacks. Passing fixtures is not production certification or a second-backend
proof.

Conflict order:

1. this specification's normative prose
2. JSON Schema wire shape
3. language-neutral fixtures
4. Django implementation

## Django implementation

`django-asklens` is the Django implementation of this specification.

- Public execution: `execute_plan(plan, *, request, registry=...)`
- Every adapter (Python, DRF, MCP, admin, frontend, provider) converges on that
  function.
- Private Django bindings stay off the public documents.
- `context_scoped` resources use a trusted `scope_provider` that returns a lazy
  QuerySet for the registered model.
- Compilation is ORM-only reads.
- Optional extras: DRF routes, MCP helpers/FastMCP bridge, admin, reference
  frontend, dummy and OpenAI-compatible providers.

See [document schemas](internal-contracts.md) and
[conformance corpus](conformance.md).

## Non-goals

- Raw SQL
- Mutations
- Arbitrary joins and expressions
- Automatic model or schema exposure
- Client-owned identity, permissions, tenant, or scope
- Dashboard builders
- Schema versioning
- Saved-query storage as a core contract (callers may persist plans; replay is
  still untrusted and must revalidate)
