# #196 article replay evidence

**Date:** 2026-11-20 UTC. This is local synthetic evidence for the
[draft integration article](integration-article.md), not publication, an
independent usability study, production security assurance or live-provider
acceptance. The [package review](package-review-196.md) is a separate
source/assertion review; it must not be reduced to a test count.

## Source and artifact identities

- Review baseline: `6d0d15d9017749547eb8cc6bfdc59883561ff077`.
- Article/examples/runner implementation:
  [`66705194d480a98983bf153e5170b7528bc00f99`](https://github.com/revazi/django-asklens/commit/66705194d480a98983bf153e5170b7528bc00f99).
  Runtime package source is unchanged from the baseline.
- Complete article/prose/navigation snapshot and final verification source:
  [`9f6317690632ab82573a1b52d71774ceab2282ea`](https://github.com/revazi/django-asklens/commit/9f6317690632ab82573a1b52d71774ceab2282ea).
  The later evidence/link-only follow-up does not change runtime, examples or
  executable article blocks.
- Final replay candidate, built from a clean `git archive` of that snapshot with
  `SOURCE_DATE_EPOCH=1795192916`: wheel SHA-256
  `c6ac182f510fa3d796ce29d1da540a4143375f0df28ae3b6043188bcb410fc3a`;
  sdist SHA-256
  `1e4ef2f082c495bdb76fd1353d438537cb0f02c1bd9df6a6aee039346bc055d0`.
  Names remain `django_asklens-0.3.2-py3-none-any.whl` and
  `django_asklens-0.3.2.tar.gz`; same-version candidates are not public artifacts.
- Initial candidate: `django_asklens-0.3.2-py3-none-any.whl`, SHA-256
  `3653507b5c753b23508e80e315ac472535c696ae1b370a533adb1a1fa03db8f8`.
  This was a local build of unchanged runtime bytes, **not** a public artifact.
- Public artifact, **not installed/authenticated again by this task**:
  [`django-asklens==0.3.2`](https://pypi.org/project/django-asklens/0.3.2/), wheel
  SHA-256 `739d5411cd0b0ab63ac8dae9e9a0a4f2cf396cb2e0f0ef5bbfac9a2c4607b050`.
  See the [immutable release and sdist identities](installation.md). Candidate
  provider fixes and these new host/article files do not alter that artifact.

Environment: macOS arm64, Python 3.12.9, Django 6.1.2, SQLite 3.47.1. Optional API
recipe resolved DRF 3.18.3. The bounded typing consumer uses the locked mypy
2.4.0 tooling group. These local versions do not stand in for the hosted
Python/Django/PostgreSQL matrix.

## Reproduction using existing infrastructure

Use a full checkout containing this article and the locked development group.
The following opt-ins reuse the existing installer, byte-for-byte installed
package checks, outside-checkout consumer copy, network/import guards, tutorial
setup and cleanup. They do not replace the critical-boundary or conformance
infrastructure and default off for historical published-artifact probes.
Build/install/audit tools may fetch ordinary packages/advisories; query execution
uses dummy fixtures only.

Before all test/build/smoke commands, remove key variables **without reading
values** and turn consent/logging off, for example in a disposable subshell:

```bash
unset OPENAI_API_KEY GEMINI_API_KEY GOOGLE_API_KEY ANTHROPIC_API_KEY
unset DJANGO_ASKLENS_LIVE_LLM_API_KEY DJANGO_ASKLENS_LLM_API_KEY
unset DJANGO_ASKLENS_PREFLIGHT_API_KEY
export DJANGO_ASKLENS_LIVE_LLM=0
export DJANGO_ASKLENS_LIVE_LLM_CONSENT=0
export DJANGO_ASKLENS_DEMO_LIVE_LLM=0
export DJANGO_ASKLENS_LIVE_LLM_LOG_IO=0
uv sync --locked --group dev
artifacts="$(mktemp -d)"
uv run --no-sync python -m build --outdir "$artifacts"
wheel="$artifacts/django_asklens-0.3.2-py3-none-any.whl"
ASKLENS_TUTORIAL_SMOKE=1 ASKLENS_ARTICLE_SMOKE=1 ASKLENS_ADAPTER_SMOKE=1 \
  uv run --no-sync bash .github/scripts/wheel-smoke.sh \
  core 'Django==6.1.2' '6.1.' "$wheel"
ASKLENS_ADAPTER_SMOKE=1 uv run --no-sync bash .github/scripts/wheel-smoke.sh \
  api 'Django==6.1.2' '6.1.' "$wheel"
ASKLENS_ADAPTER_SMOKE=1 uv run --no-sync bash .github/scripts/wheel-smoke.sh \
  mcp 'Django==6.1.2' '6.1.' "$wheel"
uv run --no-sync python scripts/check-consumer-types.py "$wheel"
```

The article commands and expected JSON are read from its marked blocks, not
regenerated in the runner. Full CLI documents are compared, omitting only the
variable non-negative `duration_ms` measurement. The registration snippet is
checked against the actual imported consumer file; the bad envelope is checked
against the article-only settings fixture. Missing/duplicate steps, altered
commands, wrong exits, unexpected response fields, invalid duration, guard
failures and expected-output drift have negative regression tests in
[`test_integration_article.py`](../tests/test_integration_article.py).

## Replayed outcomes

All four outcomes below passed on both the initial and final replay candidates.
The final core tutorial/admin, API and MCP recipes and bounded typing checks
also passed again; source/wheel API-route snapshots matched exactly.

| Outcome | Observed / asserted |
| --- | --- |
| Success | Exit 0; exactly two Alice-owned paid orders, exact typed columns, `row_count: 2`, limit 10/rows, `truncated: false`. The existing tutorial separately asserts Bob's different scope. |
| Empty | Exit 0; query response with the same columns, `data: []`, `empty: true`, `row_count: 0`, not truncated. |
| Opaque denial | Exit 1; exact fixed `asklens.member.unavailable` code/message; zero Order-table queries. Not a successful empty response. |
| Invalid provider plan | Exit 1; actual dummy provider's string limit fails planner-envelope validation with exact `asklens.plan.invalid` code/message; zero Order-table queries. No live provider or direct-plan substitution. |
| Policy/audit | Allowed/denied catalogs checked with real synthetic users; no private bindings/permission requirement in this fixture's catalog. Four attempts produce two success/two failed metadata-only audit rows with blank questions and no full plan/filters/selections. |
| Isolation/cleanup | Imported package bytes match the candidate wheel; core has neither DRF nor FastMCP/test-project imports; socket/HTTP connections forbidden during example commands; only owned temporary consumer/environment removed. |
| Existing consumers | Core tutorial, native admin, API and MCP installed recipes pass; adapter tests remain synthetic/in-process, not remote wire or live-provider proof. |
| Bounded typing | Installed `py.typed`, positive fixture and exactly 24 negative diagnostics pass without optional adapters. |
| Focused article/tutorial/source consumer tests | 54 passed. Source-level tests alone are not installed-artifact evidence. |

## Final local verification

Executed against `9f6317690632ab82573a1b52d71774ceab2282ea`, with live consent
and logging off and key variables removed unread as above:

| Check | Local result and scope |
| --- | --- |
| `bash scripts/coverage-baseline.sh` with `PYTEST_ADDOPTS=-rs` | **1555 passed, 11 skipped**. Seven skips require live network/charge consent; three are PostgreSQL timeout/role checks and one is the PostgreSQL server-major guard. Informational branch measurement has no percentage gate and is not security/correctness proof. |
| Focused registry/catalog/compiler/planning/facade/results/schema/conformance/compatibility/export/import/optional-dependency/typing-harness/article/tutorial subset | **878 passed, 4 skipped** (the same PostgreSQL-only checks). Existing composition/generative/conformance infrastructure was reused. |
| Ruff lint / format; `compileall` | Pass; 287 Python files already formatted. |
| Django `check`; `makemigrations asklens --check --dry-run` | No issues; no migration drift. Runtime, migrations, dependency graph and conformance fixtures are unchanged from the review baseline. |
| Strict MkDocs build and `scripts/verify-docs-site.py site` | Pass: 44 HTML pages; rendered local links/fragments/navigation/assets checked. Sharing drafts/plan absent from rendered files and search; no deployment. |
| Local rendered article in Chromium | Pass at 1280px and 390px viewport widths: one title, four outcome headings, disclosures present, no horizontal page overflow; external HTTP(S) requests blocked and JavaScript disabled. No new screenshot/video capture; not a full accessibility audit. |
| Final evidence/link-only follow-up | 51 article/tutorial/docs regression tests pass; strict docs and lint/format pass again. No executable article block, example, runner or runtime source changes. |
| Exact-source build / Twine / archive inspection | Wheel and sdist pass; schemas, `py.typed`, runner, article and invalid-plan host fixture included where expected; dev dependencies, outreach, media, generated site and local-only artifacts excluded. |
| `scripts/alpha-candidate-package-smoke.sh` | Pass against exact committed source: core/API/MCP installs, schema/metadata/exclusions, authenticated public **0.3.1 / 0.3.0 / 0.2.0** origins upgraded to a separate candidate while preserving synthetic migration state/audit row. This does **not** authenticate public `0.3.2` or establish a live integration. |
| `uv audit --locked --preview-features audit-command` | No known vulnerabilities or adverse project statuses in 120 audited packages (121 resolved). Point-in-time advisory lookup, not proof of dependency safety. |
| Installed final candidate | All four article outcomes, core tutorial/admin, API and MCP recipes, source/wheel API-route parity, and positive/24-negative typing consumers pass with byte/import/network guards. |

To reproduce the focused subset, use `pytest -q -rs` with `tests/catalog`,
`tests/compiler`, `tests/planning`, `tests/execution`, `tests/results`,
`tests/contracts`, `tests/conformance`, `tests/test_compatibility_contract.py`,
`tests/test_export_surface.py`, `tests/test_import_boundaries.py`,
`tests/test_optional_drf.py`, `tests/test_consumer_typing_harness.py`,
`tests/test_quickstart_wheel_smoke.py` and `tests/test_integration_article.py`.
Docs use the locked docs group, `mkdocs build --strict --clean` and the rendered
validator, then restore the locked dev group before further tests.

The package-evidence script builds its **own** ephemeral candidate from the same
source (wheel `c4124d964c7499be3894701f724b311eae60b619869eebd7b060d720c4740a02`,
sdist `07692f8c9d4a8583071b64613b62e7b3555bf384e4b0432e3bbd14bd69f8afb4`).
It is not the deterministic final replay artifact named above; do not combine
their digests. The script cleans only its owned temporary resources.

## Remaining closeout gates

Hosted checks, private maintainer triage and mandatory independent review of the
exact eventual PR head remain separate gates; no approval is claimed here.
The parent may perform authorized merge/exact-merge CI/docs/CodeQL checks and
#196/#183 closeout afterward. No #198 or later task is started by this record.

## External-action and evidence limits

The [maintainer-only sharing plan](https://github.com/revazi/django-asklens/blob/9f6317690632ab82573a1b52d71774ceab2282ea/docs/outreach/sharing-plan-196.md)
records dated signed-out public rules/route observations and channel blocks.
It and the refreshed existing drafts are excluded from rendered docs/search
and Python distributions. They are not published submissions or approval to
contact anyone. The article is a repository draft; no new Pages deployment was
performed. Existing approved showcase media are referenced, not recaptured.

No live requests, provider keys, production rows/private applications, recruitment,
human sessions (#193), separate representative app (#194), external adoption,
model-quality claims, new backend, schema versioning, dependency-PR management,
release/tag/upload or external publication occurred. Live/PostgreSQL skips must
be recorded as such, not as acceptance. SQLite/mock/internal evidence does not
establish exhaustive correctness/security, production capacity, portability or
community endorsement. Creator affiliation, alpha and AI-assistance disclosures
remain mandatory in any future owner-edited version.
