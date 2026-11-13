# Your first scoped question

Install the published package in a normal, minimal Django application and ask
one configured question about the current user's orders. This is a CLI-first
integration: no web server, API key, Docker, DRF, or MCP dependency is needed.

**Django AskLens is alpha.** The example and all records are synthetic and local
only. Dummy mode maps exact configured questions to reviewed plans; it is
**not arbitrary natural language**. Ten minutes is an onboarding target, not a
measured independent usability claim.

## Why this example exists

The [core-only quickstart](quickstart-core.md) teaches explicit registration and
direct `execute_plan()` calls. The [complex source demo](test-project-demo.md)
adds a browser, many resources, and adapters. Neither supplies this small,
inspectable **question → current-request scope → answer** consumer application.

The new [example source](https://github.com/revazi/django-asklens/tree/main/examples/quickstart)
reuses the existing registration, permissions, and query orchestrator. It does
not introduce a package API or another complex demo. Its files are ordinary
Django application code, outside `tests.test_project`:

| File | Host responsibility |
| --- | --- |
| `quickstart/settings.py` | Core apps, SQLite, two reviewed dummy plans, metadata-only audit |
| `shop/models.py` and `shop/migrations/` | One host-owned `Order` model and migration |
| `shop/apps.py` | One `AppConfig.ready()` registration import |
| `shop/asklens_registration.py` | Explicit fields, permission, and `scope_provider` |
| `shop/management/commands/seed_quickstart.py` | Synthetic local fixture setup only |
| `shop/management/commands/ask_orders.py` | Trusted operator identity selection and question execution |
| `shop/tests.py` | Django-only example regressions |

## 1. Copy the example to a fresh directory

These commands use a POSIX shell on macOS/Linux, Python 3.12 or newer, Git, and
[uv](https://docs.astral.sh/uv/). Internet access may be needed to obtain the
source, Python, public artifacts, and normal dependencies. Query execution is
offline. This is not Windows-shell verification or a deployment template.

From an existing current source checkout:

```bash
# If necessary, first: git clone https://github.com/revazi/django-asklens.git
# Then: cd django-asklens
source_dir="$PWD"
quickstart_dir="$(mktemp -d "${TMPDIR:-/tmp}/asklens-first-question.XXXXXX")"
cp "$source_dir/examples/quickstart/manage.py" "$quickstart_dir/"
cp -R "$source_dir/examples/quickstart/quickstart" \
  "$source_dir/examples/quickstart/shop" "$quickstart_dir/"
cd "$quickstart_dir"
uv venv --python 3.12 .venv
```

Only consumer application files are copied, not the package or repository test
project. `quickstart_dir` is outside the checkout; do not run the example against
a real application's database. Keep these shell variables for the next steps.

The example is new source material on mutable `main`, **not a file shipped in
the immutable `v0.3.2` release**. It uses existing public `0.3.2` behavior. The
installed package below is the authenticated published wheel, not an editable
checkout or a same-version local rebuild. Record the checkout SHA if you need
to reproduce the example files exactly:

```bash
git -C "$source_dir" rev-parse HEAD
```

## 2. Authenticate and install the public core wheel

The existing downloader uses only Python's standard library. It checks fixed
PyPI hosts, filenames, non-yanked status, metadata digests, and downloaded bytes
against the independently recorded [public artifact identities](installation.md).
It also downloads the source distribution as evidence; install only the wheel.

```bash
mkdir artifacts
.venv/bin/python "$source_dir/scripts/download_pypi_artifacts.py" \
  --version 0.3.2 \
  --wheel-sha256 739d5411cd0b0ab63ac8dae9e9a0a4f2cf396cb2e0f0ef5bbfac9a2c4607b050 \
  --sdist-sha256 e522055e3b34eac434cabff6db8bb4c278e210591bcd95027956f2449daee177 \
  --output-dir artifacts
uv pip install --python .venv/bin/python \
  artifacts/django_asklens-0.3.2-py3-none-any.whl
.venv/bin/python - <<'PY'
from importlib import metadata, util
from pathlib import Path
import sys
import django_asklens

package = Path(django_asklens.__file__).resolve()
assert package.is_relative_to(Path(sys.prefix).resolve())
assert metadata.version("django-asklens") == "0.3.2"
assert util.find_spec("rest_framework") is None
assert util.find_spec("fastmcp") is None
print("Installed public version:", metadata.version("django-asklens"))
print("Import path:", package)
PY
```

The import path must be inside this example's `.venv`, not the source checkout.
Do not use `pip install -e`, install optional extras, or add the checkout to the
module search path. Hash verification authenticates the public artifact, not
its fitness for a particular deployment; dependency resolutions remain
host-owned and should be audited separately.

## 3. Migrate, check, and seed synthetic records

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check
.venv/bin/python manage.py check_asklens --fail-on-empty
.venv/bin/python manage.py seed_quickstart
```

The committed host migration creates `shop.Order`; Django migrations create
users/permissions and AskLens audit tables. No host `makemigrations` step is
missing. `ShopConfig.ready()` imports the registration module once at startup;
do not also import it from models or URLs. `check_asklens` reports counts only;
it does not execute data queries or prove a user's scope.

The seed creates three ordinary Django users with **unusable passwords** (no
login credentials), no staff/superuser flags, and four synthetic orders:

| CLI selector | Django username | `shop.view_order` | Owned orders |
| --- | --- | --- | --- |
| `alice` | `asklens-alice` | Granted | Two paid North products and one draft |
| `bob` | `asklens-bob` | Granted | One paid South product |
| `no-report` | `asklens-no-report` | Not granted | None |

Seeding is repeatable without duplicate rows. It refuses to repurpose a seeded
username that now has a usable password or a privileged role. It does not reset
arbitrary changes to fixture data or user permissions; use a fresh disposable
project to restore the original state.

## 4. Ask an exact question

```bash
.venv/bin/python manage.py ask_orders 'Show my paid orders' --as-user alice
```

The response has `response_type: "query"`. Its `result` contains typed `columns`,
`data`, and `result_metadata` (including `truncated: false`). The exact `data` is:

```json
[
  {"product": "North class", "total_cents": 2000},
  {"product": "North membership", "total_cents": 1200}
]
```

The draft order and Bob's South order must not appear. Try the same question as
Bob:

```bash
.venv/bin/python manage.py ask_orders 'Show my paid orders' --as-user bob
```

Its `data` is exactly:

```json
[{"product": "South membership", "total_cents": 9900}]
```

This is question orchestration, not a direct hand-written-plan execution call:
`ask_orders` calls `execute_asklens_query_request(request, question=...)` without
`provided_plan`. The dummy provider selects a reviewed configured plan, and the
trusted facade revalidates the current permissions and row scope before ORM
execution. The shared question orchestrator is currently a **provisional**
integration surface; it is not a newly frozen API.

**Identity boundary:** `--as-user` is an explicitly trusted, local management
command selector, not an authentication mechanism. It loads actual Django users
and their permissions and attaches the selected user to a server-created
`HttpRequest`. Do not expose this selector as a public API or accept a username,
permission, or tenant from a query plan. In a web application, use the real
`request.user` supplied by your authentication middleware.

## 5. Distinguish empty, denied, and unmatched questions

A permitted query can legitimately return no rows:

```bash
.venv/bin/python manage.py ask_orders 'Show my refunded orders' --as-user alice
```

Expected: `response_type: "query"`, `result.data: []`,
`result.result_metadata.truncated: false`, exit status zero. This is not a provider or permission error.

The same paid-order question without the resource permission is denied:

```bash
.venv/bin/python manage.py ask_orders 'Show my paid orders' --as-user no-report
```

Expected: `response_type: "error"`, safe error code
`asklens.member.unavailable`, and nonzero command exit. Do not turn the denial
into a successful empty response, print permission/tenant details, grant
superuser, or broaden the queryset to make it work.

Unconfigured wording also fails safely with a nonzero exit:

```bash
.venv/bin/python manage.py ask_orders 'Find every order please' --as-user alice
```

Dummy mode does not interpret that sentence. Use the exact two configured
questions above. [Live provider configuration](providers.md) is a separate,
explicitly opted-in path that may send questions and permitted catalog metadata
to a provider and incur charges; none of these commands enables it.

## 6. Inspect registration and audit, then use your model

Read `shop/asklens_registration.py`. `product`, `status`, and `total_cents` are
explicit semantic keys with private Django `binding` values. Neither `owner`
nor `owner_id` is registered as a queryable field. `visible_orders(request)`
returns a lazy queryset filtered by the current authenticated user's primary
key; anonymous requests get `Order.objects.none()`. Registration also requires
`shop.view_order`: resource permission and row ownership are separate checks.
There is no unrestricted-manager fallback.

For a real application:

1. Install the authenticated package in the host's environment; do not copy this
   example's settings, database, secret key, seed command, or `--as-user` CLI.
2. Register the actual host model and only approved fields. Keep semantic names
   stable while mapping private bindings deliberately. See [registration](registration.md)
   for explicitly registered metrics and relationship/cardinality rules.
3. Replace `visible_orders` with a reviewed membership policy returning a lazy
   queryset of the registered model. Derive identity and tenant membership from
   trusted server state, never from question text or client-selected scope.
4. Set the real resource/field permissions; import registration once from the
   host app's `AppConfig.ready()`. Keep request-time checks and query budgets.
5. First exercise reviewed dummy questions with real authenticated requests in
   a non-production environment. For direct untrusted plans use the
   [governed `execute_plan()` path](quickstart-core.md); for HTTP/MCP use the
   existing [API](usage.md) or [MCP](mcp-integration.md) integration guides.
6. Review timeouts, rate/concurrency limits, indexes, provider data handling,
   audit retention, and the [production checklist](production-checklist.md).
   This synthetic example establishes none of those deployment guarantees.

By default each accepted query attempt writes metadata-only `SemanticQueryRun`
audit data. The example tests assert blank stored questions and no full plan
filters/selections, including the denial path's zero `Order` queries. The trusted
seed command writes application fixtures intentionally; it is not an AskLens
query or a production data-loading tool.

Run the example's Django-only regression tests:

```bash
.venv/bin/python manage.py test shop
.venv/bin/python manage.py makemigrations --check --dry-run
```

These tests use a disposable test database. They cover both user scopes, empty
results, opaque denial with zero order-table queries, unmatched wording, audit
privacy, seed repeatability/refusal, and CLI selector validation.

## Troubleshooting

| Symptom | Safe next step |
| --- | --- |
| Missing `examples/quickstart` | Use current source containing this new example, not the immutable release-source tag. The package installed in step 2 is still public `0.3.2`. |
| Python/uv missing | Install Python 3.12+ and uv; the commands explicitly select a consumer interpreter rather than relying on the repository's `.python-version`. |
| Artifact digest/lookup fails | Stop. Recheck the published installation record and connectivity; never substitute a local rebuild under the same public identity. |
| Import path points to checkout or extras appear | Recreate the fresh environment, remove inherited module-path overrides, and install only the authenticated core wheel. |
| Missing table or permission | Run `migrate` in the copied project and then `seed_quickstart`. Do not suppress migration errors. |
| Empty registry / duplicate registration | Check `shop.apps.ShopConfig` and the single `AppConfig.ready()` import. Do not add duplicate URL/model imports or swallow registration errors. |
| No synthetic user | Run `seed_quickstart` in this disposable project. |
| Expected denial / unmatched wording | Nonzero exit is deliberate; use the permissioned selector and exact question for the success case. Do not loosen scope or permissions. |
| Fixture changed after seeding | Create a new disposable copy; repeat seeding does not override changed records or reset roles. |

## Cleanup and evidence boundary

After inspecting results, remove only the explicitly named example-generated
files from the **copied** project (this resets both synthetic data and audit):

```bash
# Confirm this is the copied directory printed in step 1, not the checkout.
printf '%s\n' "$quickstart_dir"
cd "$quickstart_dir"
rm -f -- db.sqlite3
rm -r -- .venv artifacts
```

The example source remains for inspection. Alternatively, delete the exact
`asklens-first-question.*` directory you created using your file manager. Do not
run broad database deletion commands against a host project.

Manual maintainer execution against an authenticated installed artifact is
technical evidence, not independent onboarding, adoption, production-readiness,
or security certification. Automated consumer CI following this public path is
the separate follow-up [#185](https://github.com/revazi/django-asklens/issues/185).
The existing [candidate-wheel smoke](quickstart-core.md#7-run-the-disposable-wheel-smoke)
continues separately; it does not authenticate a rebuilt wheel as the public
artifact. No package release, live provider call, deployment, or external
submission is performed by this guide.
