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

## Initial replay results

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

## Remaining verification and closeout gates

Final full/focused checks, package contents/Twine, locked audit and strict
rendered docs results will be appended after the complete prose/navigation
revision is checked. Hosted checks and mandatory independent review of the
exact eventual PR head remain separate gates; no approval is claimed here.
The parent may perform authorized merge/exact-merge CI/docs/CodeQL checks and
#196/#183 closeout afterward. No #198 or later task is started by this record.

## External-action and evidence limits

The [maintainer-only sharing plan](https://github.com/revazi/django-asklens/blob/main/docs/outreach/sharing-plan-196.md)
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
