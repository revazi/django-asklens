# Django AskLens docs

Django AskLens is the Django implementation of the [AskLens specification](asklens-specification.md): a read-only semantic query contract over explicitly registered models, with optional Django REST Framework and MCP adapters.

Django AskLens was created by [Revaz Zakalashvili](https://github.com/revazi) ([revaz.zakalashvili@gmail.com](mailto:revaz.zakalashvili@gmail.com)).

## Package provenance

> [!IMPORTANT]
> `django-asklens==0.3.0` is the current published alpha, not a stable or
> production-certified release. Install its exact public surfaces with
> `python -m pip install 'django-asklens==0.3.0'`,
> `python -m pip install 'django-asklens[api]==0.3.0'`, or
> `python -m pip install 'django-asklens[mcp]==0.3.0'`.
>
> Use the immutable
> [`v0.3.0` documentation](https://github.com/revazi/django-asklens/blob/v0.3.0/README.md)
> and [GitHub Release](https://github.com/revazi/django-asklens/releases/tag/v0.3.0).
> They identify commit `36570eb702c7e3a885ff6aca65a07200e8fedcf9`, tree
> `35a525ea1d969833dc1a5b1abce14f6631e34f57`, wheel
> `django_asklens-0.3.0-py3-none-any.whl` with SHA-256
> `d7f7159cfdbb3d9755d9b3542f9cda4280f0e72939f81aca4d3a2cd8d8921e8b`,
> and source distribution `django_asklens-0.3.0.tar.gz` with SHA-256
> `a7717736c07b93d66e1326dc43a438aa0918c17b4512ddb2391257de5887c5c9`.
> Same-version local builds remain separate local evidence.
>
> The immutable `django-asklens==0.2.0` release remains the prior supported
> `0.2.x` upgrade origin; use its
> [documentation tagged `v0.2.0`](https://github.com/revazi/django-asklens/blob/v0.2.0/README.md).
> The historical `0.1.0a1` package was an unsupported testing artifact and is not
> an upgrade origin. See [Installation](installation.md) for authentication and
> evidence limits before using the guides below.

## Guides

- [AskLens specification](asklens-specification.md)
- [Installation](installation.md)
- [Support lifecycle](support-lifecycle.md)
- [0.3.x compatibility boundary](compatibility.md)
- [Release process and Trusted Publishing setup](releasing.md)
- [0.3.x maintenance roadmap](maintenance-roadmap.md)
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
- [Host throttling, audit, and observability controls](host-throttle-and-audit-controls.md)
- [Multi-tenant security](multitenancy-security.md)
- [Evaluation fixtures](evaluation.md)
- [Synthetic performance baseline](performance-baseline.md)
- [Test coverage baseline and critical-boundary map](test-coverage.md)
- [Example Django AskLens integration](test-project-demo.md)
- [Demo query ideas](demo-queries.md)

## Current scope

AskLens is a read-only semantic query specification. Django AskLens is the first implementation. Callers supply an untrusted `query-plan`; the implementation resolves current identity, catalog, and row scope, compiles a read-only query, and returns typed result JSON. Optional DRF, MCP, admin, frontend, and provider adapters must use the same execution path.

AskLens does not execute LLM-generated SQL, mutate data, auto-expose Django models, send sample rows to providers, or require a frontend framework. See the [AskLens specification](asklens-specification.md).
