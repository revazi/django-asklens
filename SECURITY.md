# Security policy

Django AskLens is an LLM-assisted data access package. Treat it like a reporting, analytics, or admin surface.

## Supported versions

Until the first stable release, security fixes are handled on the latest unreleased/pre-alpha code line only.

| Version | Supported |
| --- | --- |
| `main` (unreleased alpha work) | Yes |
| `0.1.0a1` (published alpha) | Yes |
| `0.1.0a0` and older snapshots | No |

## Reporting a vulnerability

Please do **not** report security vulnerabilities in public issues.

Use GitHub private vulnerability reporting for this repository if it is enabled. If private vulnerability reporting is not available, contact the maintainer through a private channel and include only the minimum details needed to reproduce the issue.

Do not include:

- real API keys or credentials,
- `.env` contents,
- production database rows,
- PII or customer data,
- raw provider payload logs containing sensitive schema or user questions.

Helpful report details:

- affected version or commit,
- affected configuration/settings,
- minimal reproduction steps using synthetic data,
- expected versus actual behavior,
- whether the issue can bypass catalog, permission, tenant, or row-level controls.

## Security model summary

AskLens should fail closed:

- no LLM-generated SQL execution,
- no data mutation actions,
- no sample database rows sent to providers by default,
- only explicitly registered resources and fields are queryable,
- provider output is untrusted and must be validated before execution,
- every resource resolves to explicit `global` or trusted request-aware `context_scoped` policy, with no unrestricted manager fallback,
- context-scoped execution starts from a lazy exact-model `scope_provider(request)` queryset and fails closed when current scope is unavailable,
- DRF/API/MCP permissions and request-scoped field permissions must be enforced through the trusted facade,
- client input cannot select identity, permission, tenant, or scope policy,
- structural limits must remain active, while hosts additionally enforce statement/request timeouts, rate/concurrency limits, read-only database defense, and monitoring, and
- default audit storage remains metadata-only; full content requires explicit retention, access, redaction, and deletion policy.

See also:

- [Security checklist](docs/security-checklist.md)
- [Production checklist](docs/production-checklist.md)
- [Multi-tenant security](docs/multitenancy-security.md)

## Disclosure expectations

Please allow time for validation and a fix before public disclosure. Security fixes should include tests when practical and should avoid introducing live-provider or sensitive-data dependencies.
