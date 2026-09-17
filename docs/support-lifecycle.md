# Support lifecycle

## Status and provenance

This is the support admission and retirement policy for Django AskLens. It
records what repository evidence is required before a Python, Django,
PostgreSQL, or optional-adapter line is described as tested. It does not freeze
an API or create a SemVer-stable compatibility guarantee.

Artifact provenance remains part of every support statement:

- PyPI currently publishes `django-asklens==0.1.0a1`; use its immutable tagged
  documentation. That package was a testing artifact only.
- `main` contains an incompatible, unreleased 0.2-era target while still
  reporting version `0.1.0a1`.

Do not combine packages, workers, clients, documentation, or persisted plans
from those contexts. An installation requirement tells a resolver which
versions it may install. Rule: resolver eligibility is not support evidence.
Classifiers, documentation, and release notes must describe evidence for the
matching artifact rather than silently promoting unreleased `main` behavior to
the published alpha.

## Current evidence

The current unreleased source tree has the following repository-operated
evidence:

- Python 3.12 and 3.13 run the full SQLite/unit/integration CI.
- Django 5.2, 6.0, and 6.1 each run on both tested Python lines.
- Installed-wheel checks exercise the core package and the optional API and MCP
  extras on each Python/Django matrix job.
- Database-sensitive and conformance checks run these representative stacks:
  - PG15 / Python 3.12 / Django 5.2;
  - PG15 / Python 3.13 / Django 6.0;
  - PG18 / Python 3.13 / Django 6.1.
- The reference browser/API/MCP smoke runs on PostgreSQL 18, Python 3.13, and
  Django 6.1.
- Current source metadata requires Python `>=3.12`, Django `>=5.2,<7.0`, and
  Pydantic v2. The optional API extra requires DRF `>=3.18,<4`; the optional MCP
  extra requires FastMCP `>=3.4,<4`.

This is not a Cartesian PostgreSQL matrix, a claim about every future Python or
Django release accepted by broad metadata, or production-capacity evidence.
SQLite is fast compatibility evidence; PostgreSQL is the required
representative database-sensitive evidence for the named tuples. Optional
adapter evidence applies only when the corresponding extra is installed.

The tested list belongs to the exact source commit or released artifact named by
the evidence. It must be rechecked for each candidate. Repository tests and
maintainer-operated CI are not external adoption, an independent security
review, or production certification.

## Admission policy

A version line is admitted to public tested-support documentation only through a
tracked issue and review. The evidence change comes before the support claim;
resolver success or an upstream compatibility statement alone is insufficient.

### Python

Admit a Python minor only after:

1. its final upstream release is available and still receives upstream security
   fixes;
2. every required runtime and selected optional dependency resolves without
   widening an unrelated major-version bound;
3. the full default suite passes across every currently tested Django line;
4. source and installed-wheel core/API/MCP checks pass;
5. at least one applicable representative PostgreSQL stack passes; and
6. metadata, classifiers, installation guidance, and release notes are updated
   together after the evidence is green.

A preview, release candidate, or development interpreter can provide advisory
signal but cannot enter the tested list.

### Django

Admit a Django feature line only after:

1. its final upstream release is available and within upstream security support;
2. core requirements plus selected DRF/FastMCP combinations are compatible;
3. the full suite passes on every currently tested Python line;
4. source/wheel core, API, and MCP isolation and behavior checks pass;
5. one named representative PostgreSQL tuple passes the unchanged conformance
   and database-sensitive suites; and
6. the latest-stack reference browser/API/MCP smoke passes before public docs,
   classifiers, bounds, or release notes call the line tested.

“Latest” is never a floating support promise. Documentation names the exact
Django feature line evidenced by CI. A new line does not automatically retire an
older line.

### PostgreSQL

Add a PostgreSQL major to the tested list only after a named Python/Django tuple
passes the unchanged conformance corpus, database-sensitive suite, Django
checks, and migration-drift checks on that major. The selected tuple and the
absence of Cartesian coverage must remain explicit. The reference smoke moves
to a new major only after its API/MCP/browser and disposable-cleanup evidence
also passes.

### Optional adapters and tooling

DRF and FastMCP remain optional and must not enter core imports or mandatory
runtime requirements. Their bounds are admitted or widened only after core-only
installation still succeeds and the relevant source/wheel adapter checks pass.
Contributor tools such as `uv`, psycopg, Docker, Playwright, and coverage do not
become host runtime requirements merely because they produce evidence.

## Retirement policy

A tested line may be proposed for retirement when at least one of these applies:

- upstream security support has ended or an unpatched vulnerability makes
  continued use unsafe;
- a required runtime or selected optional dependency no longer supports the
  combination;
- the combination cannot run on maintained CI or test infrastructure without a
  disproportionate project-specific fork;
- repeated evidence shows the line blocks a required security/correctness fix;
  or
- the maintainer records a bounded maintenance decision based on demonstrated
  cost and available alternatives.

Age alone, a newer release, or lack of known users is not sufficient. Retirement
uses this process:

1. open a tracked issue with upstream status, failing evidence, affected package
   surfaces, dependency and migration impact, and alternatives;
2. keep the line in CI until the decision is accepted, unless running it is
   itself unsafe or impossible;
3. provide **one planned release notice** before removal where safe and feasible;
4. update CI, metadata/classifiers, installation guidance, security support
   tables, and release notes in the accepted removal change; and
5. retain migration or replacement guidance appropriate to the affected alpha
   surface.

Security and trust-boundary behavior must fail closed. A vulnerable or unsafe
behavior does not receive a compatibility shim merely to preserve a notice
window. Emergency retirement or a security-driven break may be immediate, but
must still be recorded with scope, rationale, mitigation, and affected versions
without publishing sensitive exploit or credential details.

## Ownership and exceptions

The repository maintainer owns admission, retirement, and temporary-exception
decisions. CI success can supply evidence but cannot approve a support line.
Dependency bots, resolver output, downloads, examples, and issue interest do not
make a support decision.

A temporary exception must identify its owner, exact combination, reason,
security/correctness impact, mitigation, and review or expiry date. It must not
silently skip required jobs, add blanket suppressions, weaken trust-boundary
tests, or broaden package claims. Changes to required status checks, dependency
majors, or public support bounds remain separately reviewed decisions.

## Current release posture

The [current Django AskLens surface](alpha-surface-inventory.md) maps exposed,
optional, internal, and unsupported areas without accepting any stable surface.
See the [AskLens specification](asklens-specification.md).

`0.1.0a1` was a testing artifact only and is not a supported upgrade origin.
There is no deprecation window. Host-owned responsibilities are accepted. The
five packaged JSON Schemas stay internal, draft, unfrozen, and unversioned.
Do not add schema versions or handle previous-shape compatibility. This tree is
not a 0.2.0 release.

Do not add document versions or extension negotiation. Do not record or handle schema changes.
Current first-install migrations, changelog entries, and source/wheel checks are
evidence of the current tree; they do not make this commit a release. A version
bump, tag, or upload still requires explicit maintainer authorization.
