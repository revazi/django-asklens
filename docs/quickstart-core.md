# Core-only executable quickstart

This is the shortest complete path from an exact core wheel to two reviewed
Django resources and trusted Python execution. It uses no Django REST Framework,
provider call, frontend, or MCP integration.

## Artifact boundary

> [!IMPORTANT]
> This guide is for unreleased current source or a separately verified exact
> candidate wheel. It is not the published PyPI `0.1.0a1`, and it is not a
> release or upgrade claim. PyPI users must install `django-asklens==0.1.0a1`
> and use the immutable
> [`v0.1.0a1` documentation](https://github.com/revazi/django-asklens/blob/v0.1.0a1/README.md).
> Do not combine those published bytes with this unreleased-main contract.

For a maintainer-supplied candidate, verify its immutable commit, exact wheel
filename, and SHA-256 digest before installation as described in
[Installation](installation.md#maintainer-supplied-private-candidate-evaluation).
The disposable smoke at the end instead builds one wheel from the current local
source, installs that exact file, and reports its digest.

## 1. Install the exact core artifact

Create an isolated environment and install the verified wheel by path, without
an optional extra:

```bash
mkdir asklens-core-quickstart
cd asklens-core-quickstart
python -m venv .venv-asklens-core
.venv-asklens-core/bin/python -m pip install --no-cache-dir \
  /absolute/path/to/django_asklens-0.1.0a1-py3-none-any.whl
.venv-asklens-core/bin/django-admin startproject quickstart .
.venv-asklens-core/bin/python manage.py startapp shop
```

The unchanged `0.1.0a1` filename can identify either published or unreleased
bytes, so the absolute path and separately verified SHA-256 digest matter. A
same-version local replacement is not a resolver upgrade or public release.

Add the core package and the project-owned app config to
`quickstart/settings.py`:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_asklens",
    "shop.apps.ShopConfig",
]

DJANGO_ASKLENS = {
    "LLM_BACKEND": "dummy",  # No live provider call.
    "AUDIT_INCLUDE_CONTENT": False,
}
```

AskLens audit migrations depend on Django's user model, so keep the applicable
authentication app in the project. The default database audit stores operational
metadata, not raw questions or complete plans, with the content setting above.

## 2. Create the models

Use synthetic models while evaluating the integration. `GlobalFact` represents
non-sensitive shared lookup data deliberately reviewed as visible across every
request. `ScopedFact.scope_key` is private Django policy data and will not be a
registered semantic field.

```python
# shop/models.py
from django.db import models


class GlobalFact(models.Model):
    code = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=100)


class ScopedFact(models.Model):
    scope_key = models.CharField(max_length=150)
    label = models.CharField(max_length=100)
```

Replace the synthetic `scope_key` rule with your reviewed membership policy.
Never accept identity, permissions, a tenant ID, or a scope token from the
query plan or other client input.

## 3. Register the reviewed resources

Create exactly one project-owned registration module:

```python
# shop/asklens_registration.py
from django_asklens import register

from .models import GlobalFact, ScopedFact


def visible_scoped_facts(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return ScopedFact.objects.none()
    return ScopedFact.objects.filter(scope_key=user.get_username())


register(
    timezone="UTC",
    model=GlobalFact,
    name="global_facts",
    label="Reviewed global facts",
    description="Non-sensitive shared facts reviewed for global row access.",
    fields={
        "code": {
            "binding": "code",
            "type": "string",
            "nullable": False,
            "label": "Code",
        },
        "label": {
            "binding": "label",
            "type": "string",
            "nullable": False,
            "label": "Label",
        },
    },
    default_order=(("code", "asc"),),
    scope_mode="global",
)

register(
    timezone="UTC",
    model=ScopedFact,
    name="scoped_facts",
    label="Scoped facts",
    description="Facts visible in the current server-owned user scope.",
    fields={
        "label": {
            "binding": "label",
            "type": "string",
            "nullable": False,
            "label": "Label",
        },
    },
    default_order=(("label", "asc"),),
    requires_permission="shop.view_scopedfact",
    scope_mode="context_scoped",
    scope_provider=visible_scoped_facts,
)
```

`global` is explicit per resource and should be used only after reviewing every
row as intentionally unrestricted. A `context_scoped` resource always requires
a trusted `scope_provider(request)`. Missing request context, invalid provider
output, and provider failure reject; context scope never falls back to the
model manager.

## 4. Import registration once from `AppConfig.ready()`

Use one controlled startup import owned by the host app:

```python
# shop/apps.py
from django.apps import AppConfig


class ShopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shop"

    def ready(self):
        from . import asklens_registration  # noqa: F401
```

AskLens does not autodiscover host registration modules or models. Import the
registration module through this one path only. Do not also import it through
URLs, models, admin modules, multiple `AppConfig` classes, or manually invoke a
registration function from autoreloader code. Duplicate process-local
registration raises an error; do not hide it with a broad exception or weaken
the explicit registry.

A module import is naturally cached in one Python process. If a test deliberately
rebuilds Django's app registry, make that test's registry lifecycle explicit
rather than adding production autoreload guards that can conceal missing or
duplicate registration.

## 5. Migrate and check

Create the synthetic app migration, apply Django and AskLens migrations, and run
Django's system checks:

```bash
.venv-asklens-core/bin/python manage.py makemigrations shop
.venv-asklens-core/bin/python manage.py migrate
.venv-asklens-core/bin/python manage.py check
```

Registration happens during Django startup. An invalid scope declaration or
private binding therefore fails the command rather than silently exposing a
broader queryset. A successful `check` alone does not prove that another app's
registration module was imported; keep the single `AppConfig.ready()` path in
code review and execute a current-request query.

## 6. Execute untrusted list plans with current requests

Plans select fields by string semantic name. They never contain Django bindings,
permissions, identities, or scope selectors:

```python
from django_asklens.execution import execute_plan


global_plan = {
    "resource": "global_facts",
    "intent": "list",
    "select": ["code", "label"],
    "limit": 20,
}

scoped_plan = {
    "resource": "scoped_facts",
    "intent": "list",
    "select": ["label"],
    "limit": 20,
}


def run_current_request(request):
    global_result = execute_plan(global_plan, request=request)
    scoped_result = execute_plan(scoped_plan, request=request)
    return global_result.to_dict(), scoped_result.to_dict()
```

Treat every plan as untrusted, including a saved plan or an existing
`QueryPlan`. Always call `django_asklens.execution.execute_plan(plan,
request=request)` with the current server-owned Django request. The host owns
authentication, permission assignment, and scope resolution; clients do not.

A user without `shop.view_scopedfact` receives the same stable opaque
`asklens.member.unavailable` code as an unknown member. That rejection occurs
with zero registered application-data SQL. Do not replace the safe public error
with permission, membership, model, or scope diagnostics.

## 7. Run the disposable wheel smoke

From the unreleased source checkout:

```bash
bash scripts/quickstart-core-smoke.sh
```

The script copies only the local wheel inputs into a `mktemp`-owned root, builds
one source wheel, reports its SHA-256 digest, installs core only in a fresh
virtual environment, and creates a fresh Django project and app outside the
repository. It runs migrations and `check`, then proves:

- repeated global and scoped list results have stable projections;
- two current authenticated requests receive different synthetic scopes;
- a user without the registered permission receives
  `asklens.member.unavailable` with zero registered application-data SQL; and
- the exact disposable root is removed on success or failure.

Retained output contains only synthetic row counts, hashes, status/error codes,
and artifact/cleanup statuses—not result rows. The smoke makes no provider,
container, frontend, DRF, or MCP call. Network access may still be needed for
normal build and core dependency installation.

This local smoke is repository-operated technical evidence. It is not a release,
production-readiness claim, external usability result, or security audit.
