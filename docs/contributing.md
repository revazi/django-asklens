# Contribute and give feedback

You do not need a provider account, customer data or Docker to start. AskLens is
an alpha; keep changes small, explicit and safe.

## Choose an entry point

- **Try a normal Django integration:** [Your first scoped question](quickstart-app.md)
  uses the authenticated public `0.3.2` core artifact and synthetic data. This is
  different from developing against a same-version source/candidate checkout.
- **Make a repository change:** [CONTRIBUTING — development setup](../CONTRIBUTING.md#development-setup)
  is the canonical locked setup and five-test offline smoke path. Continue with
  the [smallest relevant test](../CONTRIBUTING.md#choose-the-smallest-relevant-test)
  and [PR evidence expectations](../CONTRIBUTING.md#pull-request-expectations).
- **Report a bug, integration friction or provider mismatch:** use the
  [issue chooser](https://github.com/revazi/django-asklens/issues/new/choose).
  Record the exact artifact/version, platform, expected/actual behavior and a
  minimal **synthetic** reproduction. **No secrets or customer data:** no keys,
  private endpoints, real questions/rows, raw provider bodies or logs.
- **Request a feature or ask for help:** read the distinct
  [feature](../CONTRIBUTING.md#feature-requests) and
  [support](../CONTRIBUTING.md#support-questions) routes. Discussions is disabled.
- **Report a suspected vulnerability:** follow [SECURITY.md](../SECURITY.md)
  privately, never through a public issue. Private reporting may not be enabled;
  use an established private maintainer channel if it is unavailable.

Default tests are offline, with no provider credentials. Dependency setup can
use the network; optional PostgreSQL/browser/installed-artifact checks have
[separate prerequisites](../CONTRIBUTING.md#optional-integration-checks).
Live-provider requests/spend, external recruitment, dependency-PR management,
merge/release/tag/upload, deployment/Pages and workflow dispatch are **not**
contributor setup steps; see [maintainer-only boundaries](../CONTRIBUTING.md#safety-and-maintainer-only-actions).

## Small tasks and availability

**Reviewed 2026-11-18 for [#197](https://github.com/revazi/django-asklens/issues/197):**
there is no currently available, fully scoped `good first issue` in the open
backlog. Do not mistake a `help wanted` label or a roadmap item for beginner-safe
work. Check the [current beginner queue](https://github.com/revazi/django-asklens/issues?q=is%3Aissue%20is%3Aopen%20label%3A%22good%20first%20issue%22)
and confirm scope with a maintainer before starting; an empty queue is intentional.

These three genuine bounded **documentation** gaps are addressed by this #197
change, not advertised as still-open assignments. They show useful newcomer-sized
work with paths, expected results and verification without manufacturing duplicate
issues or expanding runtime/typing policy:

| Existing issue and confirmed gap | Paths and expected result | Verification |
| --- | --- | --- |
| [#197](https://github.com/revazi/django-asklens/issues/197), connected to shipped [#184](https://github.com/revazi/django-asklens/issues/184): contributor setup used unlocked sync and jumped straight to the full suite; no first smoke or focused-test map | `CONTRIBUTING.md`, `docs/installation.md`: one locked setup, five-test smoke and source-example/typing/provider test selectors; keep the installed public tutorial separate | Fresh `uv sync --locked --group dev`; `uv run --no-sync pytest tests/test_scaffold.py`; run the relevant selector from CONTRIBUTING |
| [#197](https://github.com/revazi/django-asklens/issues/197): live docs had no contributor/feedback entry point | `docs/contributing.md`, `docs/index.md`, `mkdocs.yml`, `README.md`: reach setup, safe report routes and task availability without traversing maintainer release records | `uv run --no-sync pytest tests/test_contributor_entry_points.py`; strict docs build and `scripts/verify-docs-site.py site` after docs sync |
| Shipped [#189](https://github.com/revazi/django-asklens/issues/189): roadmap still instructed keeping the closed registration-guidance issue open | `docs/maintenance-roadmap.md`: replace only the stale status with [merged PR #214](https://github.com/revazi/django-asklens/pull/214) and its exact merge SHA; preserve historical measurements and the no-new-helper decision | Check linked issue is CLOSED/PR is MERGED; `uv run --no-sync pytest tests/test_contributor_entry_points.py`; strict docs/link checks |

No additional typing task was confirmed: [#190](https://github.com/revazi/django-asklens/issues/190)
already delivered the [bounded installed-wheel typing baseline](typing.md).
Its documented Django/dynamic-value limits are not unclaimed beginner work.
Authorization/scope design, provider lifecycle/live acceptance in
[#188](https://github.com/revazi/django-asklens/issues/188), dependency management,
external recruitment in [#193](https://github.com/revazi/django-asklens/issues/193)
and representative-app selection in [#194](https://github.com/revazi/django-asklens/issues/194)
require separate expertise, evidence or authorization. They are not beginner tasks.

For the next real gap, report the confusing step first. Maintainers should reuse
the existing issue where possible and confirm one narrow path/result/check before
applying `good first issue`; do not create filler to populate this page. Public
usability feedback is [triaged in GitHub Issues](../CONTRIBUTING.md#where-usability-feedback-goes),
with duplicates linked and only the labels needed for the next action. A report
or synthetic maintainer rehearsal is not an independent usability session.
