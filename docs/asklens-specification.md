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

AskLens does not execute LLM-generated SQL, mutate data, auto-expose models, or
accept client-owned identity, permissions, tenant IDs, or scope.

## Documents

The specification has five unversioned JSON documents:

- `catalog`
- `query-plan`
- `capabilities`
- `result`
- `error`

Machine-readable Draft 2020-12 schemas ship with the Django implementation under
`django_asklens/contracts/schemas/`. Language-neutral fixtures live in
`conformance/`.

A schema-valid plan remains untrusted. Execution must still apply current
authorization, scope, and budgets.

## Query core

- Read-only.
- One resource per plan.
- `list` and `aggregate` intents.
- Implicit-AND filters.
- Registered fields and metrics only.
- Bounded, deterministic results.
- Public semantic keys are not backend traversal paths.

Optional HTTP, MCP, admin, frontend, and provider adapters are implementation
surfaces. They must not weaken the query core.

## Trust model

Every plan is untrusted, including provider output, HTTP/MCP clients, saved
plans, and Python callers.

The implementation owns:

- current identity and permissions;
- catalog and resource registration;
- row scope;
- request clock and resource timezone;
- audit policy.

Clients cannot supply trusted permission strings, tenant IDs, scope tokens, or
prepared execution state.

## Non-goals

- Raw SQL
- Mutations
- Arbitrary joins and expressions
- Automatic model or schema exposure
- Client-owned identity, permissions, tenant, or scope
- Dashboard builders
- Schema versioning

## Django implementation

`django-asklens` is the Django implementation of this specification.

- Public execution: `execute_plan(plan, *, request, registry=...)`
- Private Django bindings stay off the public documents
- Optional DRF and MCP extras
- Optional admin, reference frontend, and providers
- ORM-only reads

See [Draft internal contract schemas](internal-contracts.md) for schema
accessors and [Draft internal conformance corpus](conformance.md) for fixtures.
