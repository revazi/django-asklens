# Draft — Django Forum Show & Tell

**Status (refreshed 2026-11-12):** Content-ready for Revaz Zakalashvili's
final review and manual posting if he chooses. No post or submission has been
made. The `v0.3.2` GitHub Release, PyPI files, public documentation, showcase,
and security guidance linked below were rechecked after the successful Pages
deployment from commit `80128e2784ae2fdbdbb5ca29efea3e01aa2d147a`; the checked
pages identify `0.3.2` as the current published alpha. The author is the creator
and maintainer of Django AskLens. This draft was prepared with AI assistance and
must be edited into the author's own voice before posting.

**Intended location:** Django Forum's public
[Show & Tell category](https://forum.djangoproject.com/c/projects/11), which was
available signed out and describes itself as a place to show projects and ask
for feedback. Posting requires the maintainer's own authenticated account.

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
- Recheck the GitHub Release, PyPI version, documentation, showcase, and security
  links while signed out.
- Confirm that `0.3.2` is still the intended version to describe and retain the
  alpha, exact-dummy-question, synthetic-data, affiliation, and AI disclosures.
- Open the signed-out Show & Tell category above, then preview the post through
  the maintainer's own account and check code-block and link rendering.
- Post only through the maintainer's own account. Do not automate login or
  submission. After posting, record the public URL separately rather than
  changing this draft to imply community adoption or endorsement.
