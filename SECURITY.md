# Security policy

Django AskLens is an LLM-assisted data access package. Treat it like a reporting, analytics, or admin surface.

## Supported versions

Until the first stable release, security fixes are handled on the latest unreleased/pre-alpha code line only.

| Version | Supported |
| --- | --- |
| `0.1.0a0` / `main` | Yes |
| Older snapshots | No |

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
- query execution starts from each resource's `base_queryset(request)`,
- DRF/API permissions and request-scoped field permissions must be enforced,
- limits such as `MAX_ROWS`, `MAX_JOINS`, `MAX_METRICS`, and `MAX_GROUP_BY` must remain active.

See also:

- [Security checklist](docs/security-checklist.md)
- [Production checklist](docs/production-checklist.md)
- [Multi-tenant security](docs/multitenancy-security.md)

## Disclosure expectations

Please allow time for validation and a fix before public disclosure. Security fixes should include tests when practical and should avoid introducing live-provider or sensitive-data dependencies.
