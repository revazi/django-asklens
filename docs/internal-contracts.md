# Draft internal contract schemas

AskLens packages five machine-readable JSON Schemas for its one current internal
shape:

- `catalog`
- `query-plan`
- `capabilities`
- `result`
- `error`

They use JSON Schema Draft 2020-12 and are available from Python:

```python
from django_asklens import get_contract_schema, list_contract_schemas

assert list_contract_schemas() == (
    "catalog",
    "query-plan",
    "capabilities",
    "result",
    "error",
)

query_plan_schema = get_contract_schema("query-plan")
```

Each call to `get_contract_schema()` returns a fresh mapping loaded from the
installed package. The source files are under
`django_asklens/contracts/schemas/`.

## Status and precedence

These schemas are **internal, draft, and unfrozen**. They document the current
Django 0.2 target and support conformance work; they are not a published
specification, a compatibility promise, an NDC profile, or evidence of a
backend-neutral implementation.

The documents do not contain embedded AskLens contract versions, revisions, or
negotiation fields. During the alpha, package SemVer, strict parsing, the
changelog, and the migration guide govern intentional shape replacement.

When an internal contract conflict is found, use this order:

1. accepted normative prose defines semantics;
2. JSON Schema defines wire shape;
3. language-neutral fixtures provide executable cases;
4. Django must conform to those sources.

A separate top-level `conformance/` corpus provides explicit synthetic positive, negative, security, budget, semantic, ordering, truncation, and serialization cases. The current Django implementation replays it on SQLite and on the required PostgreSQL 15/18 CI jobs. The source-checkout PostgreSQL 18 Compose/Playwright reference workflow adds demo-path evidence; it does not freeze these contracts or establish production, backend-neutral, public-specification, pilot, or independent-security evidence.

## Boundaries

Fixed structural objects reject additional properties. Public catalogs omit
private Django bindings, expressions, permission tokens, scope providers,
QuerySets, and tenant identifiers. Machine capabilities omit resources, labels,
descriptions, examples, and human scope guidance. Public errors contain only a
stable code, safe message, and optional bounded JSON Pointer.

The result `data` member retains the approved list of row maps. Row keys are
dynamic result-column names, so that one map allows additional properties only
when each value is a JSON cell (`string`, `integer`, finite JSON number,
`boolean`, or `null`). Fixed result envelopes, columns, and metadata remain
closed. Column/row key agreement and canonical type-specific value semantics
are enforced by execution and will also be covered by conformance fixtures;
they cannot be expressed completely by the standalone shape schema.

Schema validation is not authorization. A syntactically valid plan still must
enter `execute_plan()`, which resolves current server-owned identity,
permissions, catalog, row scope, limits, bindings, execution, serialization,
and audit policy.
