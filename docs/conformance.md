# Draft internal conformance corpus

The source distribution includes a language-neutral JSON corpus under
`conformance/`. It exercises the one current internal catalog, capabilities,
query-plan, result, and error shapes without making those shapes a public
specification or compatibility promise.

## Case shape

Every case contains:

- a permission-scoped catalog snapshot;
- an implementation capability snapshot;
- an untrusted plan;
- an expected canonical result or stable public error;
- an expected application-data query count; and
- a synthetic execution scenario identifier.

Cases contain only synthetic values. They do not contain private bindings,
permission tokens, tenant identifiers, QuerySets, scope providers, or trusted
clock values.

The scenario identifier does not grant authority. The implementation replay
harness maps it to server-owned identity, permissions, semantic registration,
row scope, settings, and clock behavior. A fixture therefore cannot choose its
own authorization or scope.

## Coverage

Explicit fixture categories cover:

- positive scoped list and aggregate execution;
- structural rejection;
- unavailable members, denied resources, missing scope, and cross-scope
  isolation;
- structural budgets and zero-application-query rejection;
- canonical decimal, trusted-clock relative-time, and empty-aggregate semantics;
- deterministic ordering and accurate truncation; and
- canonical decimal, datetime, and enum serialization.

The current replay harness runs these cases against SQLite in the normal test
suite:

```bash
uv run pytest tests/conformance/test_replay.py
```

PostgreSQL replay is a later R4 slice. Passing the SQLite corpus does not provide
PostgreSQL evidence, production certification, backend neutrality, or an
independent security review.

Generated cases may supplement this corpus, but they must not replace explicit
security and semantic cases. Contract conflicts are resolved in normative-prose,
schema, fixture, then implementation order as described in
[Draft internal contract schemas](internal-contracts.md).
