# Django AskLens docs

Django AskLens is the Django implementation of the [AskLens specification](asklens-specification.md): a read-only semantic query contract over explicitly registered models, with optional Django REST Framework and MCP adapters.

Django AskLens was created by [Revaz Zakalashvili](https://github.com/revazi) ([revaz.zakalashvili@gmail.com](mailto:revaz.zakalashvili@gmail.com)).

## Package provenance

> [!IMPORTANT]
> These docs describe `django-asklens==0.2.0`. Install that exact release and use
> the immutable [documentation tagged `v0.2.0`](https://github.com/revazi/django-asklens/blob/v0.2.0/README.md).
>
> The historical `0.1.0a1` package was a testing artifact and is not a supported
> upgrade origin. Do not mix its bytes or tagged docs with `0.2.0`. See
> [Installation](installation.md) before using the guides below.

## Guides

- [AskLens specification](asklens-specification.md)
- [Installation](installation.md)
- [Support lifecycle](support-lifecycle.md)
- [Current Django AskLens surface](alpha-surface-inventory.md)
- [Core-only executable quickstart](quickstart-core.md)
- [Usage guide](usage.md)
- [Core Python API](core-python-api.md)
- [Draft internal contract schemas](internal-contracts.md)
- [Internal semantic decision index](internal-semantic-decision-index.md)
- [Internal metadata, result, and error leakage audit](internal-surface-leakage-audit.md)
- [Issue #84 failure-mode and host-control matrix](internal-failure-mode-matrix.md)
- [Draft internal conformance corpus](conformance.md)
- [Custom UI guide](custom-ui.md)
- [Registration API](registration.md)
- [Provider configuration](providers.md)
- [Bounded MCP quickstart and integration notes](mcp-integration.md) — exact local extra, trusted context mapping, compact discovery, and safe row defaults
- [Security checklist](security-checklist.md)
- [Production checklist](production-checklist.md)
- [Host throttling and audit controls](host-throttle-and-audit-controls.md)
- [Multi-tenant security](multitenancy-security.md)
- [Evaluation fixtures](evaluation.md)
- [Synthetic performance baseline](performance-baseline.md)
- [Test coverage baseline and critical-boundary map](test-coverage.md)
- [Example Django AskLens integration](test-project-demo.md)
- [Demo query ideas](demo-queries.md)

## Current scope

AskLens is a read-only semantic query specification. Django AskLens is the first implementation. Callers supply an untrusted `query-plan`; the implementation resolves current identity, catalog, and row scope, compiles a read-only query, and returns typed result JSON. Optional DRF, MCP, admin, frontend, and provider adapters must use the same execution path.

AskLens does not execute LLM-generated SQL, mutate data, auto-expose Django models, send sample rows to providers, or require a frontend framework. See the [AskLens specification](asklens-specification.md).
