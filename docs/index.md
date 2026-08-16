# Django AskLens docs

Django AskLens is an alpha reusable Django package for safe natural-language querying over explicitly registered Django models, with an optional Django REST Framework API integration.

Django AskLens was created by [Revaz Zakalashvili](https://github.com/revazi) ([revaz.zakalashvili@gmail.com](mailto:revaz.zakalashvili@gmail.com)).

## Package provenance: choose documentation by artifact

> [!IMPORTANT]
> PyPI currently serves `django-asklens==0.1.0a1`; install that exact version and use the immutable [documentation tagged `v0.1.0a1`](https://github.com/revazi/django-asklens/blob/v0.1.0a1/README.md). This `main` branch documents an unreleased, incompatible 0.2 target whose examples do not match the published alpha. No public 0.2 package is being released by this documentation change.
>
> Do not combine published-alpha packages with unreleased-main instructions or mix those artifacts across workers or clients. [Choose the matching published, source-checkout, or maintainer-supplied private-candidate instructions](installation.md) before using the guides below.

## Guides

- [Installation](installation.md)
- [Core-only executable quickstart](quickstart-core.md)
- [Private candidate evaluation and onboarding](private-candidate-evaluation.md)
- [Privacy-Safe Pilot Intake Worksheet](pilot-intake-worksheet.md)
- [Usage guide](usage.md)
- [Migrating from 0.1 alpha to 0.2 alpha](migrating-0.1-to-0.2.md)
- [Core Python API](core-python-api.md)
- [Draft internal contract schemas](internal-contracts.md)
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
- [PR7 deterministic hardening evidence](hardening-pr7-deterministic-evidence.md)
- [PR8 locked dependency vulnerability audit evidence](hardening-pr8-locked-dependency-vulnerability-audit.md)
- [Runnable complex test project](test-project-demo.md)
- [Demo query ideas](demo-queries.md)

## Current scope

AskLens exposes permission-scoped catalog metadata and separate machine capabilities, accepts a natural-language question through Python helpers or the optional DRF API, asks a deterministic or configured provider for an executable `query_plan` plus optional separate `presentation`, validates the plan against the semantic catalog, compiles safe read-only Django ORM queries, executes with limits, and returns typed result JSON.

AskLens does not execute LLM-generated SQL, mutate data, auto-expose Django models, send sample rows to providers, or require a frontend framework.
