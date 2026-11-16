# Public-API consumer typing baseline

The source/candidate for issue [#190](https://github.com/revazi/django-asklens/issues/190)
ships inline annotations and a PEP 561 `django_asklens/py.typed` marker. Mypy can
therefore inspect a normal installed wheel instead of treating all AskLens
imports as untyped. This is **a bounded consumer baseline**, not a strict check
of every package implementation module, a new runtime contract, or evidence
about immutable public `0.3.2` artifacts. No stub package, runtime typing
dependency, Django plugin, or new public helper is introduced.

## Import inventory and boundary

The [0.3.x compatibility policy](compatibility.md) remains authoritative.
Importability or an annotation does not promote a provisional/internal surface.

| Imports/access | Policy and selected static coverage |
| --- | --- |
| `django_asklens.Metric`, `SemanticResource`, `register`, `get_resource` | **Governed** documented registration calls. Metric operation literals, private-binding argument types, resource return types and common registration keyword mistakes are covered. Undocumented dataclass construction/fields are not governed. |
| `django_asklens.catalog.Metric`, `SemanticResource`, `CatalogRegistry`, `default_registry`, `register`, `get_resource` | **Governed** documented registration imports; the two registry names are in `catalog`, not the package root. Fixtures cover both import locations, registry registration and resource lookup. |
| `django_asklens.execution.execute_plan`, `QueryResult` | **Governed** facade call and documented result access: `rows`, `row_count`, `duration_ms`, `limit`, `limit_scope`, `truncated`, `to_dict()`. Required request, registry/plan argument types, result metadata types, immutable containers and wrong result use are checked. Successful execution returns a `QueryResult`; construction, `columns`, compiler/prepared/private state are excluded. |
| `django_asklens.exceptions.PublicAskLensError`, `public_error_payload` | **Governed** safe public failure handling, ten canonical code literals, message and optional pointer types. Catch the public exception; diagnostic subclass constructors, causes and internal messages remain excluded. The fixture's local expected-code alias is an assertion, not a new package API. |
| `django_asklens.observability.ObservabilityEvent` | **Governed** all eight fields: event-name/status/code literals, optional resource/intent/count/truncation and integer duration. The documented callback remains default-off; settings resolution and delivery are runtime concerns. |
| Catalog serialization/capability helpers, `FieldSpec`, `FieldConfig`, `ScopeProvider` and other implementation/helper imports | **Provisional or internal**, not additional governed imports. Existing annotations can reference helper types without making their construction or serialization stable. Private bindings, Django paths and querysets stay internal. |
| `django_asklens.planning`, `django_asklens.results` helpers/models | **Provisional** as packages, including `QueryPlan` construction, preview validation, presentation and serialization helpers. The governed `QueryResult` access above is imported from `execution`, not a promise for the `results` package. |
| Compiler/context/prepared objects; five JSON documents/schemas | **Internal, draft**. No wire/schema typing, schema negotiation or alternative execution path is promised. |
| HTTP/DRF, MCP/FastMCP, admin/frontend, querying/providers, other settings/audit surfaces | **Optional and/or provisional** per the policy, not selected consumer typing APIs. |

## Reproduce against an installed candidate

From the source checkout, with Python 3.12+ and `uv`:

```bash
uv sync --locked --group dev
artifacts="$(mktemp -d)"
uv run --no-sync python -m build --outdir "$artifacts"
uv run --no-sync python scripts/check-consumer-types.py \
  "$artifacts/django_asklens-0.3.2-py3-none-any.whl"
```

The runner exports only core dependencies and the development-only `typing`
group from `uv.lock` (mypy **2.4.0**). It creates a fresh virtual environment and
copies `tests/installed_consumer/typing/{positive.py,negative.py,mypy.ini}` into
a temporary directory **outside the checkout**. It installs the supplied wheel
without extras or an editable project, checks installed provenance and the
marker, and verifies DRF/FastMCP are absent. It clears Python/mypy/Django/uv
configuration environment variables and runs Python in isolated mode. This
prevents `PYTHONPATH`, `MYPYPATH`, user site packages or checkout-local imports
from making the consumer green accidentally. Package implementation imports are
followed normally, not replaced with `Any` via `follow_imports=skip`.

The bounded mypy invocation is equivalent to the following **inside that isolated
environment**, not from a repository checkout:

```bash
python -I -m mypy --config-file mypy.ini \
  --no-error-summary --no-pretty --no-color-output positive.py
python -I -m mypy --config-file mypy.ini \
  --no-error-summary --no-pretty --no-color-output negative.py
```

The positive fixture uses precise `assert_type` checks to detect loss of useful
AskLens types. The negative fixture must fail at exactly **24** marked
line/error-code pairs: incorrect registration arguments, facade calls, result
use, public errors and event access. Any missing, extra, duplicate or relocated
error fails the runner; a merely nonzero exit is insufficient. The matcher has
offline unit tests, including false-success and unexpected-output cases.

CI enforces this command once in the existing Python 3.12 / Django 5.2 job after
building the wheel. Its **isolated typing environment uses lock-selected Django**
(currently 6.1), not the runtime matrix's Django override. Static checking targets
Python 3.12. Runtime tests and installed examples still cover the supported
Python/Django matrix; the typing baseline is not a Django-stubs matrix. The
marker, fixtures, config, runner and lock are included in the sdist, and the
marker in the wheel; CI checks packaging and that typing tools do not become
runtime requirements.

## Deliberate limits and the one exclusion

- `mypy.ini` enables strict **consumer** checking. Mypy's normal installed-library
  behavior does not report all implementation errors in site-packages. This is
  not a repository-wide clean-mypy claim. There is no global `ignore_errors`,
  AskLens import exclusion, repository-wide suppression or blanket replacement
  of public types with `Any`. Inline annotations were sufficient for this
  surface; duplicate narrow stubs would create a second contract to maintain.
- The sole `ignore_missing_imports` override is **`django.db.models`**, the
  fixture's only Django import, because core Django has no PEP 561 marker.
  Without separately configured Django typing, `Model`/`QuerySet` are untyped:
  this suite cannot reject a non-model class or prove a scope callback returns
  the correct queryset/model. It passes a model class into the examples instead
  of suppressing untyped-base errors for a synthetic model subclass. Hosts may
  adopt Django stubs/plugins separately; no stubs/plugin dependency is required
  at runtime or asserted compatible by this baseline.
- DRF has no baseline here: no request serializer, view, response, permission or
  adapter typing promise is made. Core does not import DRF or FastMCP. Request
  identity/scope objects and callback internals remain host-specific/dynamic.
- Existing field configuration is `Mapping[str, object]`; arbitrary nested
  configuration keys/values are not statically validated. Metric `result_type`
  and order-direction strings also still need runtime validation. The fixture
  does not claim to reject all invalid registration input.
- Result cells and `to_dict()` envelope contents retain existing dynamic
  annotations. Container/metadata typing does **not** establish JSON value types,
  selected-column names, presentation shape, or any governed serialized schema.
  Plan mapping contents are likewise not statically authorized or validated.
- Event name and status literals are individually typed; allowed combinations,
  nonnegative durations/counts, safe pointers/messages and permissions are still
  checked at runtime. Static success never authorizes execution or bypasses
  validation, serialization, registration trust, scope, budgets or the facade.

The fixtures are synthetic local/CI evidence only, not production wire
acceptance, live-provider evidence, independent security certification, or a
release/publication action.
