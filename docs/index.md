# Django AskLens docs

Django AskLens is a pre-alpha reusable Django + DRF package for safe natural-language querying over explicitly registered Django models.

## Guides

- [Installation](installation.md)
- [Usage guide](usage.md)
- [Custom UI guide](custom-ui.md)
- [Registration API](registration.md)
- [Provider configuration](providers.md)
- [Security checklist](security-checklist.md)
- [Production checklist](production-checklist.md)
- [Multi-tenant security](multitenancy-security.md)
- [Evaluation fixtures](evaluation.md)
- [Runnable complex test project](test-project-demo.md)
- [Test matrix plan](test-matrix.md)
- [Demo query ideas](demo-queries.md)

## Current scope

AskLens exposes permission-scoped catalog and capabilities metadata, accepts a natural-language question, asks a deterministic or configured provider for structured `QueryPlan` JSON, validates the plan against the semantic catalog, compiles safe read-only Django ORM queries, executes with limits, and returns table/chart-ready JSON.

AskLens does not execute LLM-generated SQL, mutate data, auto-expose Django models, send sample rows to providers, or require a frontend framework.
