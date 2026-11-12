# Draft — Django News submission

**Status (refreshed 2026-11-12):** Content-ready for Revaz Zakalashvili's
final review and manual submission if he chooses. No submission has been made.
The `v0.3.2` GitHub Release, PyPI record, public documentation, showcase, and
security guidance linked below were rechecked after the successful Pages
deployment from commit `80128e2784ae2fdbdbb5ca29efea3e01aa2d147a`; the checked
pages identify `0.3.2` as the current published alpha. The submitter is the
project's creator and maintainer. This draft was prepared with AI assistance and
must be edited into the maintainer's own voice before submission.

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

## Public submission-route observation

A signed-out read-only check on 2026-11-12 found that
<https://django-news.com/> is currently served as the Django News Newsletter on
Buttondown. The homepage exposed subscription, archive, sponsorship, jobs, and
podcast links, but no public content-submission or suggestion link. The guessed
`https://django-news.com/submit/` route returned HTTP 404. The public Google
Document linked from “Sponsor Us” is sponsorship guidance, not a content
submission form.

This does not prove that Django News accepts no community submissions. It means
the current public submission route was not discoverable in the bounded
signed-out check. The maintainer must confirm an editor-approved channel from a
trusted current source rather than guessing a form, automating contact, or
sending this packet unsolicited.

## Maintainer review before submission

- Confirm the current editor-approved submission/contact channel and any field
  limits. If no channel can be verified, retain this as a draft and do not send
  it.
- Re-read and edit the summary in the submitter's own voice.
- Recheck every public link while signed out and confirm that `0.3.2` is still
  the intended current alpha.
- Keep the alpha, exact-dummy-question, synthetic-data, affiliation, and AI
  disclosures in any shortened version.
- Submit only through the maintainer's own browser/account. Do not automate
  login or submission, and do not treat acceptance or publication as an
  endorsement.
