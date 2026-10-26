# Draft — Django News submission

**Status (refreshed 2026-10-26):** Draft for Revaz Zakalashvili to review and
submit manually. No submission has been made. Use only after the referenced
source demo, showcase assets, and guide are publicly available at the reviewed
commit; this local packet does not publish them. The author is the creator and
maintainer of Django AskLens. This draft was prepared with AI assistance.

## Suggested fields

**Title**

Django AskLens: validated read-only questions over registered Django models

**URL**

<https://github.com/revazi/django-asklens>

**Summary**

Django AskLens is a BSD-licensed public alpha that asks a provider for a
structured query plan, validates it against an explicit host-registered catalog
and the current request's permissions, and compiles a read-only Django ORM
query rather than executing LLM-generated SQL. Its source checkout includes a
seeded synthetic browser demo that runs offline with deterministic exact
questions and no API key, plus a 36-second captioned walkthrough and text
alternative. It is not arbitrary natural-language evidence or a production
certification; host applications still own authentication, trusted row scope,
timeouts, and rate limits.

**Reproducible demo note**

From a source checkout, run `uv sync --locked --group dev`, migrate and seed
with `DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings`, then start the
server with `DJANGO_ASKLENS_DEMO_LIVE_LLM=0`. Sign in using the documented
synthetic `facility-owner` account and click **Show paid billing revenue by
product**. Full commands, expected North-only output, troubleshooting, and
cleanup are in the
[source demo guide](https://github.com/revazi/django-asklens/blob/main/docs/test-project-demo.md#sqlite-frontend-and-admin-first-run-start-to-reset).

**Feedback request**

The maintainer is looking for feedback about integrating explicit semantic
registration and request-derived tenant scope into existing Django projects,
plus the minimum result/error contract a host-owned UI needs.

**Affiliation and AI disclosure**

Submitted by Revaz Zakalashvili, the project's author and maintainer. The
submission text was prepared with AI assistance and reviewed by the author.
The demo contains synthetic data and makes no live provider call.
