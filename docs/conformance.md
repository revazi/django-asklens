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

PostgreSQL replay runs in required CI on these representative stacks:

| PostgreSQL | Python | Django |
| --- | --- | --- |
| 15 | 3.12 | 5.2 |
| 15 | 3.13 | 6.0 |
| 18 | 3.13 | 6.1 |

The [CI workflow](../.github/workflows/ci.yml) configures a disposable PostgreSQL
service, PostgreSQL test settings, and the expected server major for each stack.
After installing and checking the selected Django version, it runs:

```bash
uv run --no-sync pytest --strict-config --strict-markers -m postgresql tests/conformance/test_replay.py
```

This command relies on that CI setup; it is not a standalone local PostgreSQL
bootstrap command. The [replay harness](../tests/conformance/test_replay.py)
includes a server-major guard that rejects the wrong backend or major version.
CI also runs the complete PostgreSQL-marked database-sensitive suite separately;
those tests supplement, rather than replace, the language-neutral corpus.

These are representative stacks, not a Cartesian matrix or evidence for every
PostgreSQL version. Passing the SQLite corpus does not provide PostgreSQL
evidence. Passing PostgreSQL replay is not production certification, backend
neutrality, or an independent security review.

Generated cases may supplement this corpus, but they must not replace explicit
security and semantic cases. Contract conflicts are resolved in normative-prose,
schema, fixture, then implementation order as described in
[Draft internal contract schemas](internal-contracts.md).
