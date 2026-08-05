# Django AskLens docs

Django AskLens is an alpha reusable Django package for safe natural-language querying over explicitly registered Django models, with an optional Django REST Framework API integration.

## Guides

- [Installation](installation.md)
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
- [MCP integration notes](mcp-integration.md) — framework-neutral adapter helpers and wrapper
- [Security checklist](security-checklist.md)
- [Production checklist](production-checklist.md)
- [Host throttling and audit controls](host-throttle-and-audit-controls.md)
- [Multi-tenant security](multitenancy-security.md)
- [Evaluation fixtures](evaluation.md)
- [Synthetic performance baseline](performance-baseline.md)
- [Runnable complex test project](test-project-demo.md)
- [Demo query ideas](demo-queries.md)

## Current scope

AskLens exposes permission-scoped catalog metadata and separate machine capabilities, accepts a natural-language question through Python helpers or the optional DRF API, asks a deterministic or configured provider for an executable `query_plan` plus optional separate `presentation`, validates the plan against the semantic catalog, compiles safe read-only Django ORM queries, executes with limits, and returns typed result JSON.

AskLens does not execute LLM-generated SQL, mutate data, auto-expose Django models, send sample rows to providers, or require a frontend framework.
