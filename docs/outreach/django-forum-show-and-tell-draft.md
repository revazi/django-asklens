# Draft — Django Forum Show & Tell

**Status (refreshed 2026-10-26):** Draft for Revaz Zakalashvili to review and
post manually. Do not post as automation. Use only after the referenced source
demo, showcase assets, and guide are publicly available at the reviewed commit;
this local draft does not make them published. The author is the creator and
maintainer of Django AskLens. This draft was prepared with AI assistance and
should be edited into the author's own voice before submission.

## Proposed title

Django AskLens: scoped read-only questions over registered Django models (alpha)

## Proposed post

Hi Django community — I maintain
[Django AskLens](https://github.com/revazi/django-asklens), a BSD-licensed public
alpha for turning a question into a validated, read-only Django ORM query over
models and semantic fields that the host explicitly registers.

The design difference I am exploring is that the provider does not write or
execute SQL. It proposes structured JSON; AskLens validates that plan against
the current request's permission-filtered catalog and structural limits, then a
trusted host path compiles a read-only QuerySet. Context-scoped resources start
from a host-owned `scope_provider(request)`. Authentication, permission grants,
row-scope correctness, timeouts, and rate limits remain the host application's
responsibility.

There is now a small source-checkout demo that needs no API key or provider
network call:

```bash
git clone https://github.com/revazi/django-asklens.git
cd django-asklens
uv sync --locked --group dev
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
  uv run python -m django migrate --run-syncdb
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
  uv run python -m django seed_complex_test_project --size small
DJANGO_ASKLENS_DEMO_LIVE_LLM=0 \
DJANGO_SETTINGS_MODULE=tests.test_project.demo_settings \
  uv run python -m django runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000/>, use the synthetic local-only account
`facility-owner` / `12admin34`, and click the exact configured question **Show
paid billing revenue by product**. The expected result is a grouped table/chart
containing North-scoped products such as `North membership`, with no South
rows. The `DummyProvider` is deterministic and matches only displayed exact
questions; this is not arbitrary natural-language or live-LLM evidence. Remove
only `.asklens-test-project.sqlite3` after stopping the server.

The current published version is `0.3.1`, an alpha rather than a stable or
production-certified release. The polished browser journey above describes
current source and may be newer than that immutable wheel. Its captured
36-second walkthrough has a caption track and text alternative, and its data,
accounts, and credentials are local synthetic fixtures. Please review the
[installation provenance](https://github.com/revazi/django-asklens/blob/main/docs/installation.md)
and [security checklist](https://github.com/revazi/django-asklens/blob/main/docs/security-checklist.md)
before evaluating it outside a synthetic local setup.

I would especially value feedback from maintainers who have integrated
reporting into an existing Django permission and tenant model:

- Does explicit model/field/metric registration fit your application boundary?
- Is a request-derived `scope_provider` practical in your project?
- Which result metadata and safe error states would your own UI need?
- Where is the setup or security guidance still ambiguous?

Affiliation/disclosure: I am the author and maintainer of Django AskLens. This
post was drafted with AI assistance and reviewed by me before posting. The demo
uses synthetic data only.
