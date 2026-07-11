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
- Frontend-agnostic result serialization and visualization-hint normalization.
- Public-alpha documentation drafts and deterministic evaluation fixtures.
- Multi-tenant API security tests covering base-queryset scoping, permission-gated fields, route permission gates, and permission-scoped catalog/planner metadata.
- OpenAI-compatible provider using Python stdlib HTTP.
- Mocked and opt-in live provider tests.
- Private real-project integration checklist and templates for multi-tenant validation.
- Configurable request-permission getter for projects with role-based or staff permission systems outside Django's default `user.get_all_permissions()`.
- Runnable complex test project with admin-enabled demo settings, synthetic tenant-scoped grants, and complex member/subscription/billing/payment/session resources.
- Dedicated Django admin AskLens query page that runs validated queries, displays result rows, and reuses existing successful audit records for repeated questions.
- Demo seed command creates a local admin superuser, staff users with varied synthetic tenant/reporting grants, and richer per-facility synthetic data.
- Demo-only AskLens frontend page that calls the catalog/query APIs and displays returned data with switchable client-side views.
- Tenant-scoped demo permission tokens for complex test-project grants, including regression coverage for facility-level row separation.
- Resource-level permission scoping for catalog visibility and plan validation, plus permission-filtered demo questions.
- Environment-driven live OpenAI-compatible planner mode for the runnable complex demo project.
- Permission-scoped capabilities endpoint, semantic capability-question routing, LLM-generated query suggestions from visible capabilities, and demo guidance for "what can I query?" UX.
- Planner guidance and validation normalization for date-bucket visualization aliases such as `start_date_month`.
- Opt-in demo validation management command for live LLM smoke checks across seeded users/questions.
- Size profiles for the complex demo seed command, including medium/large bulk-generated tenant/member/billing datasets.
- Additional realistic demo tables and AskLens resources for marketing campaigns, leads, bookings/attendance, staff shifts, and support tickets.
- Sanitized capability scope guidance and validation so query-help suggestions do not imply multi-tenant access for single-scope users.
- Suppressed single-scope entity examples such as plural facility-list suggestions for users scoped to one facility.
- Added schema-agnostic `scope_resource` and `scope_dimension` registration metadata so scope-aware help does not depend on tenant/facility/account naming.
- Seeded demo role groups, user full names, explicit owner grants, and an owner-only facility owners resource for owner lookup questions.
- Added a regression-tested demo permission/resource matrix; owners see all resources, mixed member reporters no longer receive billing resources, and owner email requires a staff-PII grant.
- Added `examples_enabled=False` for queryable helper resources that should not dominate deterministic “what can I query?” suggestions, clarified LLM-vs-fallback help labels in the demo UI, allowed help requests such as “give me 10 examples” to return up to 10 validated suggestions, canonicalized provider resource/field/metric labels, and surfaced safe fallback reasons when live QueryHelp fails validation.

### Security

- No raw SQL execution path in the MVP.
- No write/update/delete query intents.
- No sample database rows sent to providers by default.
- Sensitive and hidden fields excluded from default planner catalog serialization.
- Crafted provider plans cannot use permission-gated tenant fields without the required configured permission string.
- Catalog and planner prompt metadata are scoped to configured request permissions.
- Complex tenant tests prove resource base querysets restrict rows to facilities where the user has the required synthetic reporting grant.
- Live provider errors avoid exposing API keys or raw credentials.
