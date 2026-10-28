# Draft — Django Forum Show & Tell

**Status (refreshed 2026-10-27):** Prepared for Revaz Zakalashvili to review,
but **not ready to post** while the mutable public documentation still contains
pre-publication `0.3.2`/current-`0.3.1` wording. No post or submission has been
made. The `v0.3.2` GitHub Release, PyPI files, documentation endpoints, and
showcase endpoints linked below were rechecked; HTTP availability does not cure
the stale release labels. The author is the creator and maintainer of Django
AskLens. This draft was prepared with AI assistance and requires the author's
final review after the documentation closeout.

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

The immutable [`v0.3.2`](https://github.com/revazi/django-asklens/releases/tag/v0.3.2)
source includes a small demo that needs no API key or provider network call:

```bash
git clone --branch v0.3.2 --depth 1 \
  https://github.com/revazi/django-asklens.git
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
rows. The `DummyProvider` is deterministic and matches only the displayed exact
questions; this is not evidence that arbitrary natural-language wording works.
After stopping the server, remove only `.asklens-test-project.sqlite3` if you
want to reset the synthetic demo.

The current published version is
[`django-asklens==0.3.2`](https://pypi.org/project/django-asklens/0.3.2/), an
alpha rather than a stable or production-certified release. The
[showcase](https://revazi.github.io/django-asklens/showcase/) includes a
36-second browser walkthrough with captions and a text alternative. Its data,
accounts, and credentials are local synthetic fixtures, and the recording makes
no live provider call. Please review the
[security checklist](https://revazi.github.io/django-asklens/security-checklist/)
and authenticate the exact
[PyPI `0.3.2` record](https://pypi.org/project/django-asklens/0.3.2/)
before evaluating AskLens outside a disposable synthetic setup.

I would especially value feedback from maintainers who have integrated
reporting into an existing Django permission and tenant model:

- Does explicit model/field/metric registration fit your application boundary?
- Is a request-derived `scope_provider` practical in your project?
- Which result metadata and safe error states would your own UI need?
- Where is the setup or security guidance still ambiguous?

Affiliation/disclosure: I am the author and maintainer of Django AskLens. This
post was drafted with AI assistance and reviewed by me before posting. The demo
uses synthetic data only.

## Maintainer review before posting

- Re-read the final text in the author's own voice; remove anything the author
  cannot personally support.
- Complete and deploy the post-release documentation closeout, then verify that
  the linked public pages no longer call `0.3.2` unpublished or `0.3.1` current.
- Recheck the GitHub Release, PyPI version, documentation, showcase, and security
  links while signed out.
- Confirm that `0.3.2` is still the intended version to describe and retain the
  alpha, exact-dummy-question, synthetic-data, affiliation, and AI disclosures.
- Preview the post in Django Forum and check code-block and link rendering.
- Post only through the maintainer's own account. Do not automate login or
  submission. After posting, record the public URL separately rather than
  changing this draft to imply community adoption or endorsement.
