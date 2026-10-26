# Django AskLens docs

Django AskLens is the Django implementation of the [AskLens specification](asklens-specification.md): a read-only semantic query contract over explicitly registered models, with optional Django REST Framework and MCP adapters.

Django AskLens was created by [Revaz Zakalashvili](https://github.com/revazi) ([revaz.zakalashvili@gmail.com](mailto:revaz.zakalashvili@gmail.com)).

## See it

[![The synthetic AskLens source demo showing the exact paid-revenue question, North Studio current-user scope, and grouped North-only output.](https://raw.githubusercontent.com/revazi/django-asklens/main/docs/assets/showcase/scoped-revenue.png)](showcase.md)

See the [36-second browser showcase](showcase.md) for the exact offline question,
scoped grouped result, successful empty result, and neutral denial. The capture
uses seeded synthetic data and the deterministic `DummyProvider`; it is not
live-LLM, arbitrary-language, customer-data, or production evidence.

## Run it

- [Try the current synthetic source demo locally—no API key](test-project-demo.md#sqlite-frontend-and-admin-first-run-start-to-reset)
- [Install an authenticated public artifact](installation.md)
- [Core-only executable quickstart](quickstart-core.md)

The source demo keeps Django authentication, CSRF, the explicit catalog,
current-request permissions, trusted row scope, and query limits active. Its
configured offline questions match exact text only.

## Integrate it

- [Register host-owned models](registration.md)
- [Configure providers](providers.md)
- [Use the authenticated API](usage.md)
- [Build a custom UI](custom-ui.md)
- [Bounded MCP quickstart and integration notes](mcp-integration.md) — public `0.3.1` `[mcp]` extra, trusted context mapping, compact discovery, and safe row defaults

## Package provenance

> [!IMPORTANT]
> `django-asklens==0.3.1` is the current published alpha, not a stable or
> production-certified release. Current source documentation and the synthetic
> source demo may be newer than the immutable public wheel. Authenticate the
> artifact you install and review the exact public hashes, tag/commit/tree,
> Python/Django ranges, historical release evidence, and supported upgrade
> origins in [Installation](installation.md). The immutable
> [`v0.3.1` source snapshot](https://github.com/revazi/django-asklens/blob/v0.3.1/README.md)
> and [GitHub Release](https://github.com/revazi/django-asklens/releases/tag/v0.3.1)
> remain the public `0.3.1` references; same-version local rebuilds are separate
> local evidence.

## Security and operations

- [Security checklist](security-checklist.md)
- [Multi-tenant security](multitenancy-security.md)
- [Production checklist](production-checklist.md)
- [Host throttling, audit, and observability controls](host-throttle-and-audit-controls.md)
- [Support lifecycle](support-lifecycle.md)
- [0.3.x compatibility boundary](compatibility.md)

## Guides and reference

- [AskLens specification](asklens-specification.md)
- [Core Python API](core-python-api.md)
- [Draft internal conformance corpus](conformance.md)
- [Evaluation fixtures](evaluation.md)
- [Demo query ideas](demo-queries.md)
- [Example Django AskLens integration](test-project-demo.md)
- [Synthetic performance baseline](performance-baseline.md)

## Maintainer evidence

These internal and release-process records are useful for review, but are
secondary to the runnable integration and safety guides above.

- [Current Django AskLens surface](alpha-surface-inventory.md)
- [0.3.x maintenance roadmap](maintenance-roadmap.md)
- [Test coverage baseline and critical-boundary map](test-coverage.md)
- [Draft internal contract schemas](internal-contracts.md)
- [Internal semantic decision index](internal-semantic-decision-index.md)
- [Internal metadata, result, and error leakage audit](internal-surface-leakage-audit.md)
- [Issue #84 failure-mode and host-control matrix](internal-failure-mode-matrix.md)
- [Release process and Trusted Publishing setup](releasing.md)
- [Static docs build and operator-only Pages activation](pages-deployment.md)

## Current scope

AskLens is a read-only semantic query specification. Django AskLens is the first implementation. Callers supply an untrusted `query-plan`; the implementation resolves current identity, catalog, and row scope, compiles a read-only query, and returns typed result JSON. Optional DRF, MCP, admin, frontend, and provider adapters must use the same execution path.

AskLens does not execute LLM-generated SQL, mutate data, auto-expose Django models, send sample rows to providers, or require a frontend framework. See the [AskLens specification](asklens-specification.md).
