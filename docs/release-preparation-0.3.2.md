# 0.3.2 release preparation record

**Status: published 2026-10-27.** `django-asklens==0.3.2` is the current
published alpha. The immutable [`v0.3.2` GitHub Release](https://github.com/revazi/django-asklens/releases/tag/v0.3.2),
[PyPI record](https://pypi.org/project/django-asklens/0.3.2/), and exact public
identities in [Installation](installation.md) establish the release—not this
mutable preparation document. The sections below preserve the pre-publication
candidate rationale, evidence, and gates as historical context; their future
or candidate tense is not current release status.

## Why a patch release

The preparation baseline is `fec40ba8e76e643e81f920b0f99d042cbe7a14d7`.
Comparison with immutable `v0.3.1` found no changes to package Python execution
code, governed registration/execution/error/observability interfaces, packaged
schemas, or migrations. The package frontend is provisional and gains clearer
offline, empty, help, and error states without changing execution routing.
Release operations gain a fail-closed artifact-handoff verifier. Documentation,
showcase media, synthetic fixtures, tests, and development tools are updated.
The runtime dependency bounds and supported lines are unchanged.

This supports a proposed `0.3.2` patch under the
[0.3.x compatibility policy](compatibility.md), not a new stability guarantee.
The package remains alpha. No migration, data transformation, public API
expansion, live-provider certification, or production certification is claimed.

## What users receive

- A clearer no-API-key source-demo journey, with exact offline questions and
  explicit current-user scope, plus scoped successful empty and safe error states.
- A README/PyPI description with synthetic screenshots and a short recording,
  captions, and a text walkthrough. Media links target repository `main`;
  source showcase tooling/media are intentionally excluded from distributions.
- Navigable local docs, build-only CI, and a separately operator-triggered
  Pages deployment workflow. The documentation URL stays on GitHub: prepared
  deployment source and a configured site URL are not evidence of a live site.
- More defensive release artifact handoff before protected publication.

The source demo remains a full-checkout evaluation path, not a second packaged
application. The offline planner matches configured questions exactly; it does
not demonstrate arbitrary natural-language interpretation.

## Security and dependency limits

The development lock contains certifi `2026.10.19`, Django REST Framework
`3.18.2`, FastMCP/fastmcp-slim `4.1.2`, OpenTelemetry API `1.45.1`, and
resolver-required dependencies. These updates address the advisories found
while preparing the source. They do not force every host to use those versions:
Python package runtime bounds remain unchanged, and hosts must audit and patch
their own resolved environments. An advisory lookup is point-in-time evidence,
not independent security review.

## Candidate installation and upgrades

Build the reviewed candidate into an owned temporary directory, authenticate
its local digest, and install that exact wheel into a fresh environment. Do not
reuse immutable public `0.3.1` hashes for a local `0.3.2` build.

The opt-in `scripts/alpha-candidate-package-smoke.sh` requires a clean committed
snapshot, exports that exact snapshot, and builds one wheel and one source
distribution. It checks core/API/MCP installation outside the checkout and
upgrades separately authenticated public `0.3.1`, `0.3.0`, and `0.2.0` wheels.
`0.3.1` is the immediate candidate upgrade origin; the older-origin probes
remain separate assertions. The synthetic SQLite probes check exact migration
state, preserved audit data, proxy/table shape, and import provenance.
They are not PostgreSQL or production upgrade certification. `0.1.0a1` remains
an unsupported testing artifact.

For a real host, back up according to host policy and run its own system,
migration-drift, application, authorization, and enabled-adapter checks. Stored
or provider-produced plans still require current-request `execute_plan()`
validation. No migration is not a rollback or mixed-version guarantee.

## Local preparation evidence

On the uncommitted candidate based on the source baseline above:

- Full local suite: **1,262 passed, 11 skipped**. The skips are not passes or
  live-provider/hosted release evidence.
- Ruff lint/format, Django system checks, and migration-drift checks passed.
- Locked audit: no known vulnerabilities or adverse project statuses in the
  120 audited dependencies, a point-in-time result only.
- Strict MkDocs build and rendered-output validation passed for **35 pages**,
  including navigation, links, fragments, and showcase assets.
- A disposable Git test snapshot passed the exact-source package smoke:
  Twine/content/metadata checks, isolated core/API/MCP installs, and all three
  authenticated public-origin SQLite upgrade probes with preserved audit data.
  Its local artifact digests are not public hashes or final-release identities.
- PostgreSQL **15** and **18** each passed **297** database-sensitive tests,
  system checks, and migration-drift checks in owned disposable containers.
- PostgreSQL 18 passed the real Playwright/API/FastMCP reference demo smoke,
  including scoped rows, empty states, safe denial, and recovery.

These results are bounded local preparation evidence, not final hosted approval,
public artifact verification, production certification, or independent review.
No real-project commit, push, tag, upload, deployment, or outreach was performed.

## Historical release gates (subsequently completed)

1. Review the final diff, package metadata, changelog, and candidate notes.
2. Verify the full local suite, dependency audit, docs rendering, candidate
   package installation/upgrades, and relevant PostgreSQL/browser/API/MCP checks.
   A disposable test snapshot can exercise uncommitted candidate bytes, but
   cannot replace exact-final-commit evidence.
3. Commit/push only with authorization; require green hosted checks on the exact
   proposed release commit. Local preparation does not satisfy this gate.
4. Obtain explicit authorization for an exact version/tag/commit and operator
   confirmation of publisher configuration. Existing tags/releases/files stay
   immutable. Protected-environment approval remains operator-only.
5. Publish through the reviewed Trusted Publishing workflow, authenticate the
   downloaded public wheel/sdist, and verify the post-publication matrix before
   updating current-release status and public hash records.

At preparation time, none of these steps deployed Pages, requested OIDC,
approved an environment, changed publisher settings, posted outreach, or
published Python artifacts. The later authorized Pages deployment and `0.3.2`
Trusted Publishing run are separate records. See the
[release runbook](releasing.md) for publication and incident boundaries.
