# Django AskLens docs

Django AskLens is an alpha reusable Django package for safe natural-language querying over explicitly registered Django models, with an optional Django REST Framework API integration.

Django AskLens was created by [Revaz Zakalashvili](https://github.com/revazi) ([revaz.zakalashvili@gmail.com](mailto:revaz.zakalashvili@gmail.com)).

## Package provenance: choose documentation by artifact

> [!IMPORTANT]
> PyPI currently serves `django-asklens==0.1.0a1`; install that exact version and use the immutable [documentation tagged `v0.1.0a1`](https://github.com/revazi/django-asklens/blob/v0.1.0a1/README.md). This `main` branch documents an unreleased, incompatible 0.2 target whose examples do not match the published alpha. No public 0.2 package is being released by this documentation change.
>
> Do not combine published-alpha packages with unreleased-main instructions or mix those artifacts across workers or clients. [Choose the matching published or source-checkout instructions](installation.md) before using the guides below.

## Guides

- [AskLens specification](asklens-specification.md)
- [Installation](installation.md)
- [Support lifecycle](support-lifecycle.md)
- [Alpha surface inventory](alpha-surface-inventory.md)
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
