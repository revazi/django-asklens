# Contributing to Django AskLens

Thanks for your interest in Django AskLens.

Django AskLens 0.3.2 is the current public alpha. APIs may change; keep
contributions safe, small and deterministic.

- **Integrating the package?** Start with [Your first scoped question](docs/quickstart-app.md),
  not the internal test project. [Installation](docs/installation.md) distinguishes
  authenticated public artifacts from same-version source/candidate builds.
- **Changing this repository?** Follow the setup below, then choose a focused test.
- **Looking for a small task?** See [confirmed task scopes and current availability](docs/contributing.md#small-tasks-and-availability).
- **Reporting feedback?** Use [the issue chooser](https://github.com/revazi/django-asklens/issues/new/choose)
  and the [routing/triage guidance](#feedback-and-triage) below.
- **Suspected vulnerability?** Never open a public issue; follow [SECURITY.md](SECURITY.md).

## Development setup

Use Python 3.12+ and [`uv`](https://docs.astral.sh/uv/). The checkout's
`.python-version` selects Python 3.12.9; `uv` can install it if needed. From a
fresh checkout, run:

```bash
git clone https://github.com/revazi/django-asklens.git
cd django-asklens
export DJANGO_ASKLENS_LIVE_LLM=0
export DJANGO_ASKLENS_DEMO_LIVE_LLM=0
uv sync --locked --group dev
uv run --no-sync pytest tests/test_scaffold.py
```

Expect **5 passed**: package import, Django app setup, settings and dummy-provider
checks. This is a smoke check, not full behavior or security evidence. Setup may
download Python/dependencies; the default tests themselves are offline, use
synthetic data and SQLite, and require no API key, Docker, browser or external
service. Do not copy production settings or credentials into the checkout.
The dev group includes optional adapter/testing dependencies; they are not core
package runtime requirements. `--locked` preserves the reviewed dependency graph;
`--no-sync` reuses that environment for checks without changing it.

## Choose the smallest relevant test

Run from the repository root after setup. Narrow further with a test node or
`-k` when appropriate; focused checks do not replace the full suite before a PR.

| Change | First relevant command |
| --- | --- |
| Contributor forms, routing or task navigation | `uv run --no-sync pytest tests/test_contributor_entry_points.py` |
| General docs navigation/build tooling | `uv run --no-sync pytest tests/test_showcase_and_docs_artifacts.py` plus the strict docs build below |
| Minimal Django consumer example | `uv run --no-sync pytest tests/test_installed_quickstart_example.py` (source-level; not installed-artifact proof) |
| Registration declarations | `uv run --no-sync pytest tests/catalog` |
| Provider handling/strict-schema mapping | `uv run --no-sync pytest tests/llms/test_openai_compatible.py tests/llms/test_openai_strict_schema.py` (mocked, no live requests) |
| Consumer typing runner | `uv run --no-sync pytest tests/test_consumer_typing_harness.py`, then the installed-wheel command below |

For other runtime work, start with the matching `tests/` directory and consult the
[critical-boundary map](docs/test-coverage.md). Run the default checks before a PR:

```bash
uv run --no-sync pytest
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync python -m django check --settings=tests.test_project.settings
uv run --no-sync python -m django makemigrations asklens --check --dry-run --settings=tests.test_project.settings
artifacts="$(mktemp -d)"
uv run --no-sync python -m build --outdir "$artifacts"
uv run --no-sync twine check "$artifacts"/*
```

Run `bash scripts/coverage-baseline.sh` separately for critical-boundary changes.
It has no percentage threshold: inspect missing branches in the affected boundary,
not the aggregate as proof of correctness or security.

### Optional integration checks

Default pytest skips live-provider tests and PostgreSQL-service tests when not
configured. Do not enable them to fix an unrelated documentation change.

- PostgreSQL checks need a disposable local service and synthetic database; see
  [the database-sensitive checks](docs/test-project-demo.md).
- Browser checks need Playwright's Chromium and the synthetic demo; Docker is
  needed only for the separate container/reference stack. See the
  [demo guide](docs/test-project-demo.md) and [showcase capture](docs/showcase.md).
- Installed core/API/MCP checks build a **candidate** and create disposable
  environments; see [local package evidence](docs/installation.md#exact-local-source-package-evidence).
  Some harnesses download dependencies/authenticate public upgrade artifacts.
- Live providers require separate explicit network/charge authorization and
  bounded consent. Keep them disabled here. [Provider limits](docs/providers.md)
  and [#188](https://github.com/revazi/django-asklens/issues/188) explain why mocks
  and the tiny preflight are not live application acceptance.

## Feedback and triage

**All public reports must contain no secrets or customer data.** Use minimal
synthetic names/models/rows/questions. Never paste `.env` contents, credentials,
private endpoints, raw exceptions, provider payloads or full logs. Review text,
attachments and reproduction repositories before submitting. Do not work around
permissions, tenant/row scope or validation to make a reproduction easier.

- **Bug:** reproducible incorrect existing behavior → [Bug report](https://github.com/revazi/django-asklens/issues/new?template=bug_report.yml).
- **Integration friction:** an unclear installation/example/host-integration step,
  whether or not it is a defect → [Integration friction](https://github.com/revazi/django-asklens/issues/new?template=integration_friction.yml).
- **Provider compatibility:** a structured-output/configuration mismatch →
  [Provider compatibility](https://github.com/revazi/django-asklens/issues/new?template=provider_compatibility.yml).
  State the exact model, version/artifact and offline/live evidence boundary;
  no new live request is required.
- **Feature or support question:** use the guidance below, not a bug by default.
- **Security:** suspected authorization, tenant, scope or other vulnerability →
  [private security policy](SECURITY.md), **never a public issue**. Use GitHub
  private reporting if enabled; otherwise use an established private maintainer
  channel. Do not publish details while seeking a private route.

### Feature requests

Search [existing issues](https://github.com/revazi/django-asklens/issues) first.
For genuinely new behavior, [open a feature request](https://github.com/revazi/django-asklens/issues/new?labels=enhancement&title=%5BFeature%5D%20).
Describe the concrete user outcome, current limitation, relevant version/artifact,
synthetic example, expected behavior and why existing options do not suffice.
Do not include secrets or customer data. Discuss larger designs before coding;
a request does not authorize implementation or promise support/stability.

### Support questions

Start with [troubleshooting](docs/troubleshooting.md) and the relevant guide.
If still blocked, [ask a bounded support question](https://github.com/revazi/django-asklens/issues/new?labels=question&title=%5BQuestion%5D%20)
with exact artifact/version/platform, guide step, expected/actual outcome and a
minimal synthetic reproduction. Include no secrets or customer data. Use the
integration form if the confusing step itself is useful feedback. GitHub
Discussions is not enabled; there is no separate support forum or response SLA.

### Where usability feedback goes

Maintainers triage public reports in [GitHub Issues](https://github.com/revazi/django-asklens/issues),
not in private provider logs or a parallel backlog. Ask only for missing safe
reproduction/version evidence; redirect suspected vulnerabilities privately.
Reproduce offline when possible and distinguish code bugs (`bug`), guide gaps
(`documentation`), new behavior (`enhancement`) and questions (`question`).
Link related issues and close duplicates with the canonical link rather than
splitting the same symptom into multiple tasks. Keep labels to those needed for
the next action; forms reuse existing labels and create none. Do not apply
`good first issue` until a maintainer confirms paths, expected result, bounded
scope and verification with no unresolved trust/design gate. Remove it if scope
expands. No label mutation or new issue is needed just to keep a beginner queue full.
Confirmed blockers may inform [#195](https://github.com/revazi/django-asklens/issues/195);
a public friction report is not an independent study session under
[#193](https://github.com/revazi/django-asklens/issues/193).

## Pull request expectations

- Keep changes focused; link the existing issue and explain the observed gap,
  expected result and relevant compatibility/safety boundary.
- Add/update behavior tests and docs together. Keep tests offline and deterministic.
- Record exact source SHA (and candidate artifact/digest if used), platform and
  dependency versions, commands, outcomes and skips. Separate source/candidate,
  authenticated public-artifact, mocked and authorized live evidence.
- Give a minimal synthetic before/after reproduction or rendered-doc check when
  relevant. State what was **not** verified; green tests are not production,
  adoption or independent-security evidence.
- Do not commit `.env`, API keys, provider dumps, local SQLite files or sensitive
  data. Review the diff for accidental disclosure; summarize sanitized evidence,
  not raw external errors. Disclose substantial AI assistance and verify its output.
- Independent review and hosted checks are required before merge. A contributor
  PR is not approval to merge, release or operate external services.

## Safety and maintainer-only actions

Provider output is untrusted JSON and must pass AskLens validation before ORM
execution. Do not weaken read-only execution, explicit model/field registration,
request-time Django/DRF permissions, trusted `scope_provider(request)`, query
budgets or metadata-only audit defaults. Never execute provider SQL, mutate
application data or send database rows/sample values by default.

Contributors must **not** merge their own work, manage labels/backlog or dependency
PRs for this task, change protected settings/secrets, move immutable tags/artifacts,
release/tag/upload to PyPI, deploy/activate Pages, or dispatch workflows. These
are separately authorized maintainer/operator actions, not setup steps. Do not
contact/recruit users, automate accounts, use production applications/data or run
live providers without separate explicit authorization. Normal PR-triggered CI
is not a manual workflow dispatch. See the [maintenance boundaries](docs/maintenance-roadmap.md).

## Documentation

Build/validate locally with the isolated docs group; this does **not** deploy:

```bash
uv sync --locked --group docs
uv run --no-sync mkdocs build --strict --clean
uv run --no-sync python scripts/verify-docs-site.py site
```

This sync changes the local environment's selected groups. Re-run
`uv sync --locked --group dev` before returning to pytest/build tools.
[Pages activation](docs/pages-deployment.md) remains a manual operator action.
Useful references: [contributor hub](docs/contributing.md),
[registration](docs/registration.md), [providers](docs/providers.md),
[security checklist](docs/security-checklist.md) and [release runbook](docs/releasing.md)
(the latter is reference, not permission to publish).

## Bounded consumer typing

This is an installed-wheel public-API alpha gate, not a repository-wide mypy check.
After the dev setup, reproduce against a freshly built candidate:

```bash
artifacts="$(mktemp -d)"
uv run --no-sync python -m build --outdir "$artifacts"
uv run --no-sync python scripts/check-consumer-types.py \
  "$artifacts/django_asklens-0.3.2-py3-none-any.whl"
```

See [exact coverage and Django/DRF limits](docs/typing.md). Keep annotations useful
without blanket `Any`, global ignore-errors, broad suppressions, runtime typing
dependencies or a whole-repository rewrite.
