# Django AskLens docs

Django AskLens is an alpha reusable Django package for safe natural-language querying over explicitly registered Django models, with an optional Django REST Framework API integration.

## Guides

- [Installation](installation.md)
- [Usage guide](usage.md)
- [Core Python API](core-python-api.md)
- [Custom UI guide](custom-ui.md)
- [Registration API](registration.md)
- [Provider configuration](providers.md)
- [Security checklist](security-checklist.md)
- [Production checklist](production-checklist.md)
- [Multi-tenant security](multitenancy-security.md)
- [Evaluation fixtures](evaluation.md)
- [Runnable complex test project](test-project-demo.md)
- [Demo query ideas](demo-queries.md)

## Current scope

AskLens exposes permission-scoped catalog and capabilities metadata, accepts a natural-language question through Python helpers or the optional DRF API, asks a deterministic or configured provider for structured `QueryPlan` JSON, validates the plan against the semantic catalog, compiles safe read-only Django ORM queries, executes with limits, and returns table/chart-ready JSON.

AskLens does not execute LLM-generated SQL, mutate data, auto-expose Django models, send sample rows to providers, or require a frontend framework.
