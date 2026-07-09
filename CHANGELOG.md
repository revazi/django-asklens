# Changelog

All notable changes to Django AskLens will be documented here.

The project is pre-alpha and APIs may change before the first public alpha.

## 0.1.0a0 — Unreleased

### Added

- Minimal Django reusable app scaffold and test harness.
- Explicit semantic catalog registration with field and metric metadata.
- Strict Pydantic QueryPlan schema and catalog validation.
- ORM-only compiler and executor for read-only list and aggregate queries.
- Deterministic planner/provider flow with `DummyProvider`.
- DRF catalog/query/run endpoints and `SemanticQueryRun` audit model.
- Frontend-agnostic table renderer and chart-spec normalization.
- Public-alpha documentation drafts and deterministic evaluation fixtures.
- Multi-tenant API security tests covering base-queryset scoping, permission-gated fields, route permission gates, and permission-scoped catalog/planner metadata.
- OpenAI-compatible provider using Python stdlib HTTP.
- Mocked and opt-in live provider tests.
- Private real-project integration checklist and templates for multi-tenant validation.
- Configurable request-permission getter for projects with role-based or staff permission systems outside Django's default `user.get_all_permissions()`.
- Runnable complex test project with admin-enabled demo settings, synthetic tenant-scoped grants, and complex member/subscription/billing/payment/session resources.
- Dedicated Django admin AskLens query page that runs validated queries, displays result rows, and reuses existing successful audit records for repeated questions.
- Demo seed command creates a local admin superuser, staff users with varied synthetic tenant/reporting grants, and richer per-facility synthetic data.
- Demo-only AskLens frontend page that calls the catalog/query APIs and renders table/chart-ready responses with vanilla JavaScript.
- Tenant-scoped demo permission tokens for complex test-project grants, including regression coverage for facility-level row separation.

### Security

- No raw SQL execution path in the MVP.
- No write/update/delete query intents.
- No sample database rows sent to providers by default.
- Sensitive and hidden fields excluded from default planner catalog serialization.
- Crafted provider plans cannot use permission-gated tenant fields without the required configured permission string.
- Catalog and planner prompt metadata are scoped to configured request permissions.
- Complex tenant tests prove resource base querysets restrict rows to facilities where the user has the required synthetic reporting grant.
- Live provider errors avoid exposing API keys or raw credentials.
