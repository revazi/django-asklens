# Installation

`django-asklens==0.3.0` is the current published alpha. Alpha does not mean
stable, production-certified, independently security-certified, or suitable for
a particular deployment. Authenticate public artifacts against the immutable
release identities below; a matching version string alone is not provenance.
Current source metadata identifies the reviewed `0.3.1` release source, but
that version and local artifacts do not establish publication or final public
identities. Public `0.3.0` remains the immediate supported upgrade origin until
a separate publication succeeds. The immutable `0.2.0` release remains the
supported older `0.2.x` origin. The historical `0.1.0a1` package was an
unsupported testing artifact and is not an upgrade origin.

## Current published alpha: 0.3.0

Install the exact public core package:

```bash
python -m pip install 'django-asklens==0.3.0'
```

Install the optional provisional DRF API and packaged reference frontend:

```bash
python -m pip install 'django-asklens[api]==0.3.0'
```

Install the optional provisional FastMCP bridge:

```bash
python -m pip install 'django-asklens[mcp]==0.3.0'
```

Use the immutable
[`v0.3.0` README](https://github.com/revazi/django-asklens/blob/v0.3.0/README.md)
and
[`v0.3.0` installation guide](https://github.com/revazi/django-asklens/blob/v0.3.0/docs/installation.md),
and retain the
[`v0.3.0` GitHub Release](https://github.com/revazi/django-asklens/releases/tag/v0.3.0)
as the release record. The authoritative source identity is:

- commit: `36570eb702c7e3a885ff6aca65a07200e8fedcf9`
- tree: `35a525ea1d969833dc1a5b1abce14f6631e34f57`

The authenticated public distributions are exactly:

- wheel `django_asklens-0.3.0-py3-none-any.whl`: SHA-256
  `d7f7159cfdbb3d9755d9b3542f9cda4280f0e72939f81aca4d3a2cd8d8921e8b`
- source distribution `django_asklens-0.3.0.tar.gz`: SHA-256
  `a7717736c07b93d66e1326dc43a438aa0918c17b4512ddb2391257de5887c5c9`

Maintainers can independently re-download and authenticate those public bytes,
then exercise each artifact's core, API, and MCP installations outside the
checkout:

```bash
bash scripts/published-package-smoke.sh \
  --version 0.3.0 \
  --wheel-sha256 d7f7159cfdbb3d9755d9b3542f9cda4280f0e72939f81aca4d3a2cd8d8921e8b \
  --sdist-sha256 a7717736c07b93d66e1326dc43a438aa0918c17b4512ddb2391257de5887c5c9 \
  --django-package 'Django>=6.1,<6.2' \
  --django-version-prefix '6.1.'
```

Supply digests from this independent immutable release record, not values copied
from the same PyPI response being authenticated. The verifier requires fixed
PyPI hosts, exact filenames, one non-yanked wheel and one non-yanked source
distribution, matching metadata/download digests, isolated installs, and Django
migration checks. This proves only the bounded public package properties it
checks. It is not production, live-provider, deployment, adoption, or
independent-security evidence.

## Prior PyPI release and upgrade origin: 0.2.0

Core package:

```bash
python -m pip install 'django-asklens==0.2.0'
```

Optional DRF API and packaged reference frontend:

```bash
python -m pip install 'django-asklens[api]==0.2.0'
```

Optional FastMCP bridge:

```bash
python -m pip install 'django-asklens[mcp]==0.2.0'
```

Use the immutable [documentation tagged `v0.2.0`](https://github.com/revazi/django-asklens/blob/v0.2.0/README.md). Do not combine `0.2.0` instructions with the historical `0.1.0a1` testing artifact.

The published `0.2.0` files have these independently recorded SHA-256 values:

- wheel: `af0881945d5f5f227332aac8bb13df10d4cf5bd3e54a038acd6545db5640d1d8`
- source distribution: `11af90303fd2d23123e4caa98c6e6cb660b7b8f32d6fba0c57a4554c8d39e022`

Maintainers can re-download, authenticate, and exercise both public artifacts
with `scripts/published-package-smoke.sh`; see the
[release process](releasing.md#rechecking-a-published-release-locally). The
probe removes checkout import shadowing and uses separate core, API, and MCP
environments. This does not make PyPI installation an independent security or
production certification.

## Source checkout and exact local artifacts

Use `uv` when developing in this repository:

```bash
uv sync --group dev
uv run pytest
```

A locally built wheel reports `0.3.1`, but it is not a public or final artifact.
Record the local source commit and locally produced digest as separate candidate
evidence; never attach the immutable public `0.3.0` identities above to it. The
immediate supported origin for this maintenance source is authenticated public
`0.3.0`; published `0.2.0` remains a separately checked older supported
`0.2.x` origin. No upgrade from the `0.1.0a1` testing artifact is claimed.

### Exact local release-source package evidence

The opt-in package smoke validates an exact committed local `0.3.1` source:

```bash
bash scripts/alpha-candidate-package-smoke.sh
```

The command requires Python 3.12+, `uv`, Git, `tar`, and a clean source tree. It
exports the exact `HEAD` commit into a temporary build tree, builds exactly one
`0.3.1` wheel and one source distribution, runs Twine and package-content
checks, reports their local-only SHA-256 digests, and runs installed-wheel
checks outside the repository root. It verifies that release notes remain
excluded and that development tools did not leak into runtime requirements or
extras, then installs the core, API, and MCP wheel surfaces in separate
temporary environments.

The primary upgrade probe authenticates the exact public `0.3.0` wheel and
source distribution against the immutable SHA-256 values above, installs the
wheel in a disposable environment, applies the existing AskLens migrations
(`0001_initial` and `0002_add_admin_query_proxy`), and creates one synthetic
`SemanticQueryRun` row. It then upgrades to the local `0.3.1` wheel, runs
`migrate --plan`, `migrate`, `showmigrations`, `check`, and
`makemigrations --check --dry-run`, and verifies the unchanged graph, preserved
row, proxy model, table shape, and absence of checkout source shadowing.

A separate probe authenticates published `0.2.0` and repeats the same bounded
checks because it remains the supported older `0.2.x` origin; it is not
substituted for the immediate public `0.3.0` maintenance hop. This is bounded
SQLite package evidence, not PostgreSQL or production upgrade certification. It
does not test or replace the `0.1.0a1` testing artifact. The script removes its temporary environments and
artifacts and does not upload, tag, publish, or release anything.

## Authenticated API prerequisites for an exact 0.3.1 source artifact

These prerequisites document the optional provisional DRF adapter in a
separately verified local `0.3.1` wheel. Public users must continue to use the
authenticated `0.3.0` wheel and immutable `v0.3.0` docs above until a separate
`0.3.1` publication succeeds; users remaining on `0.2.0` must use the immutable
`v0.2.0` docs. Keep every local source identity and digest separate from public
release identities:

```bash
python -m pip install '/verified/local/path/django_asklens-0.3.1-py3-none-any.whl[api]'
```

The `[api]` extra installs the existing DRF dependency within the bounds in `pyproject.toml`; it does not install FastMCP or make DRF a core dependency. Add the host authentication/session apps, DRF, AskLens, and the project app that owns registration:

```python
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "django_asklens",
    "shop.apps.ShopConfig",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
```

Mount the current API routes:

```python
from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
]
```

Apply the normal host auth/contenttypes/session migrations, the host model permissions, and AskLens audit migrations, then check startup registration:

```bash
python -m django migrate
python -m django check
```

Use existing host authentication to create and authenticate normal users and assign Django permissions server-side. AskLens does not add an authentication backend or token endpoint. The default API route gate requires an authenticated request; a host may configure stronger existing DRF-compatible permission classes. Row identity and scope still come only from the current server-owned request and the registered `scope_provider(request)`.

For a disposable source-tree verification that performs these steps with synthetic users, session middleware, `testserver` as the only `ALLOWED_HOSTS` entry, deterministic dummy planning, and metadata-only database audit, run:

```bash
bash scripts/quickstart-core-smoke.sh --api
```

The default command without `--api` remains the U2 core-only exact-wheel smoke. Both modes create one `mktemp`-owned root and remove it on success or failure; neither deletes a caller-owned path. Build and dependency installation may use configured package indexes. The smoke is local current-artifact evidence only—not PostgreSQL, release, upgrade, production, external-usability, or security-certification evidence.

Continue with the [authenticated normal-user API quickstart](usage.md#authenticated-normal-user-api-quickstart) for registration, host permission assignment, catalog-first verification, the current query/denial statuses, and audit expectations.

## Django setup

For core-only use, add AskLens to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "django_asklens",
]
```

For Python-only usage without DRF, see the [Core Python API](core-python-api.md) guide.

For the optional API integration, add DRF and AskLens to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "rest_framework",
    "django_asklens",
]
```

Include the API URLs:

```python
from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
]
```

Optionally mount the packaged reference frontend:

```python
urlpatterns = [
    path("", include("django_asklens.api.urls")),
    path("", include("django_asklens.frontend.urls")),  # /asklens/ui/
]
```

The packaged frontend is optional and calls the AskLens API routes, so it also requires the `api` extra and API URLs. Production projects can build custom UIs directly on the API; see [Building a custom AskLens UI](custom-ui.md).

Run migrations for AskLens-owned audit models, then verify that startup populated the process-local registry:

```bash
python -m django migrate asklens
python manage.py check_asklens --fail-on-empty
```

`check_asklens` prints only aggregate resource, scope-mode, field, and metric counts. It performs no application-data queries and does not invoke scope providers. Django initializes every installed host app before the command runs, so host `AppConfig.ready()` side effects remain the host's responsibility.

## Minimal settings

```python
DJANGO_ASKLENS = {
    # Optional safe default; global resources must still opt in individually.
    "DEFAULT_SCOPE_MODE": "context_scoped",
    "LLM_BACKEND": "dummy",
    "LLM_MODEL": None,
    "LLM_BASE_URL": "https://api.openai.com/v1",
    "LLM_API_KEY": None,
    "LLM_TIMEOUT_SECONDS": 30,
    "LLM_TEMPERATURE": 0,
    "MAX_ROWS": 500,
    "DEFAULT_LIMIT": 100,
    "MAX_PLAN_BYTES": 65_536,
    "MAX_FILTERS": 20,
    "MAX_SELECTED_FIELDS": 25,
    "MAX_ORDER_BY": 5,
    "MAX_JOINS": 2,  # maximum relationship-hop depth
    "MAX_RELATIONSHIP_EDGES": 8,
    "MAX_IN_VALUES": 100,
    "MAX_FILTER_VALUES": 200,
    "MAX_METRICS": 5,
    "MAX_GROUP_BY": 3,
    "PROMPT_RESOURCE_SHORTLIST_LIMIT": 0,
    "OBSERVABILITY_SINK": None,  # optional content-free host callback
    "MCP_ALLOW_ROW_RETURN": False,
    "MCP_MAX_RETURNED_ROWS": 100,
}
```

The default permission gate is `django_asklens.access.IsAuthenticated`, a lightweight class compatible with DRF's `has_permission(request, view)` interface. API projects may set `API_PERMISSION_CLASSES` to DRF permission classes or other DRF-compatible classes. Review the [production checklist](production-checklist.md) before enabling AskLens outside local development.

## Compatibility

The [support lifecycle](support-lifecycle.md) defines how a Python, Django,
PostgreSQL, or optional-adapter line enters or leaves the tested list. It keeps
resolver eligibility and exact-artifact CI evidence separate from the
[narrow governed 0.3.x core boundary](compatibility.md). That boundary is not a
1.0 stability claim and does not govern optional adapter or document shapes.

Current development target:

- Python 3.12+
- Django 5.2 LTS, Django 6.0, or Django 6.1
- Pydantic v2
- Optional API extra: Django REST Framework 3.18+
- Optional MCP extra: FastMCP 3.4+

Installation metadata remains `Django>=5.2,<7.0`, but current CI support evidence is deliberately limited to Django 5.2 LTS, 6.0, and 6.1.
