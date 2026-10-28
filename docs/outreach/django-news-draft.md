# Draft — Django News submission

**Status (refreshed 2026-10-27):** Prepared for Revaz Zakalashvili to review,
but **not ready to submit** while the mutable public documentation still
contains pre-publication `0.3.2`/current-`0.3.1` wording. No submission has been
made. The `v0.3.2` GitHub Release, PyPI record, documentation endpoints, and
showcase endpoints linked below were rechecked; HTTP availability does not cure
the stale release labels. The submitter is the project's creator and
maintainer. This draft was prepared with AI assistance and requires the
maintainer's final review after the documentation closeout.

## Suggested fields

**Title**

Django AskLens: validated read-only questions over registered Django models

**URL**

<https://github.com/revazi/django-asklens>

**Summary**

Django AskLens `0.3.2` is a BSD-licensed public alpha that asks a provider for a
structured query plan, validates it against an explicit host-registered catalog
and the current request's permissions, and compiles a read-only Django ORM query
rather than executing LLM-generated SQL. Its immutable source release includes
a seeded synthetic browser demo that runs offline with deterministic exact
questions and no API key, plus a 36-second captioned walkthrough and text
alternative. It is not evidence for arbitrary natural-language wording or a
production certification; host applications still own authentication, trusted
row scope, timeouts, and rate limits.

**Release and demo links**

- Release: <https://github.com/revazi/django-asklens/releases/tag/v0.3.2>
- PyPI: <https://pypi.org/project/django-asklens/0.3.2/>
- Showcase: <https://revazi.github.io/django-asklens/showcase/>
- Security checklist: <https://revazi.github.io/django-asklens/security-checklist/>

**Reproducible demo note**

Check out the immutable `v0.3.2` tag, run `uv sync --locked --group dev`, migrate
and seed with `DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings`, then
start the server with `DJANGO_ASKLENS_DEMO_LIVE_LLM=0`. Sign in using the
documented synthetic `facility-owner` account and click **Show paid billing
revenue by product**. Full commands, expected North-only output,
troubleshooting, and cleanup are in the
[source demo guide](https://github.com/revazi/django-asklens/blob/v0.3.2/docs/test-project-demo.md#sqlite-frontend-and-admin-first-run-start-to-reset).
The offline dummy provider recognizes the displayed exact questions only.

**Feedback request**

The maintainer is looking for feedback about integrating explicit semantic
registration and request-derived tenant scope into existing Django projects,
plus the minimum result/error contract a host-owned UI needs.

**Affiliation and AI disclosure**

Submitted by Revaz Zakalashvili, the project's author and maintainer. The
submission text was prepared with AI assistance and reviewed by the author.
The demo contains synthetic data and makes no live provider call.

## Maintainer review before submission

- Complete and deploy the post-release documentation closeout, then verify that
  the linked public pages no longer call `0.3.2` unpublished or `0.3.1` current.
- Check Django News' current submission form and field limits rather than
  assuming this packet matches a future form unchanged.
- Re-read and edit the summary in the submitter's own voice.
- Recheck every public link while signed out and confirm that `0.3.2` is still
  the intended current alpha.
- Keep the alpha, exact-dummy-question, synthetic-data, affiliation, and AI
  disclosures in any shortened version.
- Submit only through the maintainer's own browser/account. Do not automate
  login or submission, and do not treat acceptance or publication as an
  endorsement.
