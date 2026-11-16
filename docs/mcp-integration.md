# MCP integration notes

MCP is an **optional, provisional** adapter under the [compatibility policy](compatibility.md).
It does not supply production authentication, tenant resolution, or transport
protection. All execution still converges on the trusted facade, with explicit
registration, current permissions, fail-closed scope, bounded read-only ORM, and
metadata-only audit. See [Host controls](host-throttle-and-audit-controls.md)
for rate/concurrency limits and timeouts; omitting rows does not reduce query cost.

## Bounded MCP quickstart

Start after [Your first scoped question](quickstart-app.md), using its copied
consumer, model/migration, single `ShopConfig.ready()` registration import,
`requires_permission`, and trusted `visible_orders(request)` ownership scope.
The default permission resolver calls the current `request.user.get_all_permissions()`;
permission assignment and tenant membership are server-owned, never plan/tool
arguments. Invalid/anonymous scope never broadens to the model manager.

The dependency-free helpers/toolset need only core `django-asklens==0.3.2`
(`Django>=5.2,<7.0`, `pydantic>=2,<3`). For the optional FastMCP bridge, install
**only** the `mcp` extra, which adds `fastmcp>=3.4,<5` and no DRF:

```bash
# Reuse the authenticated public wheel from the minimal quickstart.
uv pip install --python .venv/bin/python 'artifacts/django_asklens-0.3.2-py3-none-any.whl[mcp]'
.venv/bin/python manage.py migrate --settings=quickstart.mcp_settings
.venv/bin/python manage.py check --settings=quickstart.mcp_settings
.venv/bin/python manage.py check_asklens --fail-on-empty --settings=quickstart.mcp_settings
```

Authenticate immutable public `0.3.2` against [Installation](installation.md).
A same-version local rebuild is separate evidence, not the public wheel.
`0.1.0a1` is not a supported upgrade origin. The new `examples/quickstart` MCP
files are **source-only additions**, not files in immutable public `0.3.2`;
they use already-published capabilities. The older generic sketch in
[`examples/mcp/`](../examples/mcp/) links here rather than defining another recipe.

### Settings and server-owned request wiring

`quickstart.mcp_settings` extends core settings (not the web/API settings),
retains exact dummy questions and metadata-only database audit, and adds:

```python
# After importing core settings; no API URLs, DRF, or web middleware.
DJANGO_ASKLENS = {
    **DJANGO_ASKLENS,
    "API_PERMISSION_CLASSES": ["django_asklens.access.IsAuthenticated"],
    "REQUEST_PERMISSIONS_GETTER": None,
    "MCP_ALLOW_ROW_RETURN": False,
    "MCP_MAX_RETURNED_ROWS": 1,
}
```

The concrete [host wiring](https://github.com/revazi/django-asklens/blob/main/examples/quickstart/quickstart/mcp.py)
exposes `make_toolset(authenticated_user_id)` and
`make_server(authenticated_user_id)`. The required host callback authenticates
and resolves a verified **server-side session** on every tool invocation. It
must reject invalid/expired sessions and return the server-mapped Django user
PK, not a claim from tool arguments, headers supplied as identity, question
text, or a client-selected username. There is no default identity or public
user selector. The factory refetches an active Django user each call, avoiding
stale permission caches, applies `can_access_asklens(request)`, and passes a
server-created request to the toolset. Use a uniform host-owned safe transport
error for rejected authentication; never serialize exception text or user
existence. The example deliberately does **not** implement a production login
or transport authentication layer.

```python
# Host startup AFTER Django setup; supply your already-verified session lookup.
from quickstart.mcp import make_server

server = make_server(resolve_authenticated_user_id)  # Required host function.
# Mount/run this server only behind the host's authenticated MCP transport.
```

Internally it constructs `AskLensMCPToolSet(request_factory=...,
expose_query_tool=False, default_include_rows=False)` and passes it to
`create_fastmcp_server()`. FastMCP injects server context; the five tools' input
schemas omit `user`, `username`, `permissions`, `tenant`, `scope`, and context.
The provider-backed `asklens_query` tool stays disabled. For a tenant-aware
host, resolve membership server-side and attach the trusted attributes required
by its permission getter and `scope_provider`; do not copy this synthetic
single-owner policy as a production tenancy model.

### Validate, execute, and test both row gates

Discover compact metadata with `asklens_capabilities()`, then request
`asklens_query_plan_schema()` and `asklens_describe_resource(resource="orders")`
as needed. Submit this untrusted synthetic plan to `asklens_validate_plan` and
then `asklens_execute_plan`:

```python
plan = {
    "resource": "orders",
    "intent": "list",
    "select": ["product", "total_cents"],
    "filters": [{"field": "status", "op": "eq", "value": "paid"}],
    "limit": 10,
}
```

Validation reports `executed: false` and is not reusable authorization. Execution
refetches identity, revalidates current permission and trusted scope, and audits.
The adapter currently flattens the core `result` into top-level `columns`,
`data`, `row_count`, and `result_metadata`; do not assume the HTTP envelope.

| Host setting / request | Expected for Alice's two paid orders |
| --- | --- |
| Default host off, default request | `rows_omitted: true`, `data: []`, `row_count: 2` |
| Host off, `include_rows=True` | Still omitted; `row_return_denied: true` |
| Host on, default request | Still omitted — host approval alone is insufficient |
| Explicit host `MCP_ALLOW_ROW_RETURN=True`, request `include_rows=True`, cap 1 | First authorized row only; `mcp_returned_row_count: 1`, `mcp_row_limit: 1`, `mcp_rows_truncated: true`, executed `row_count: 2` |

Row return is a deliberate data-disclosure decision: MCP clients may place tool
output into an LLM context. The recipe enables it **only inside a test override**,
not by default. `MCP_MAX_RETURNED_ROWS` caps the tool payload, not execution;
`MAX_ROWS`/plan limits still bound execution. `result_metadata.truncated` is
false here because the database result fits the plan limit; the separate
`mcp_rows_truncated` flag means the transport cap removed an already-executed row.
Neither is a cursor. Narrow the query rather than inventing pagination.

Run the installed recipe:

<!-- asklens-adapter:mcp -->
```bash
.venv/bin/python manage.py test shop.mcp_recipe --settings=quickstart.mcp_settings
```

It uses a synthetic host-owned session map (not a real transport), tests both
gates/cap, active-user/session rejection, and revokes permission between
validation and execution to prove current-request denial with zero order SQL.
It verifies actual FastMCP-generated schemas and metadata-only audit. No rows,
protected fields, permission tokens, tenant existence, raw errors, or audit
content are printed for diagnosis. There are no live LLM calls or credentials.

From a current checkout, reuse the existing isolated candidate installer:

```bash
uv run --no-sync python -m build --wheel
ASKLENS_ADAPTER_SMOKE=1 uv run --no-sync bash .github/scripts/wheel-smoke.sh mcp 'Django>=5.2,<5.3' '5.2.'
```

The runner reads the marked command above, copies the actual consumer outside
the checkout, checks installed candidate bytes and MCP-only dependency/import
isolation, and blocks execution-time network calls. It does not authenticate
the public wheel or prove production wire acceptance, independent adoption,
production readiness, or security certification. Installation may use network
access; recipe execution does not. For real-transport **synthetic source-demo**
evidence only, see [Runnable test-project MCP endpoint](#runnable-test-project-mcp-endpoint).

## Why AskLens still matters with MCP

MCP can provide a transport layer between an AI client and application tools. A Django-aware MCP server can also authenticate a caller and map the caller to a Django user.

That does not replace AskLens' core responsibilities:

- defining which Django models are exposed as semantic resources;
- exposing only permission-scoped resources, fields, metrics, and examples;
- hiding sensitive fields unless permissions allow them;
- validating every `QueryPlan` as untrusted input;
- enforcing resource and field permissions;
- starting execution from each resource's explicit global or context-scoped policy;
- compiling to Django ORM only, not LLM-generated SQL;
- applying configured limits;
- returning table/chart-ready JSON; and
- auditing query execution.

A useful framing is:

```text
MCP = transport and tool invocation
AskLens = semantic catalog, policy validation, safe ORM execution, and audit
```

Without AskLens, an MCP server that supports ad hoc analytics would still need to implement those safety and semantic layers itself, or it would risk exposing raw database access, broad model introspection, or hand-written report tools only.

## Package/dependency approach

AskLens intentionally does not depend on a generic Django MCP package. Some generic implementations expose broad model/admin/DRF surfaces or depend on Django REST Framework, which conflicts with AskLens' optional-DRF core design and explicit semantic registration model.

The dependency-free helpers live in the main `django-asklens` package. The optional FastMCP bridge is available through the `mcp` extra. For local release verification, install only the exact verified wheel shown below:

```bash
export ASKLENS_RELEASE_WHEEL=/verified/path/django_asklens-0.3.2-py3-none-any.whl
python -m pip install "${ASKLENS_RELEASE_WHEEL}[mcp]"
```

A separate package such as `django-asklens-mcp` may make sense later if AskLens grows a larger transport/server integration with its own dependency cadence. It is not needed for the current bridge layer.

## Adapter helpers

AskLens provides lower-level helpers that can be wrapped as MCP tools:

```python
from django_asklens.mcp import (
    asklens_capabilities,
    asklens_describe_resource,
    asklens_execute_plan,
    asklens_query,
    asklens_query_plan_schema,
    asklens_validate_plan,
)
```

Suggested MCP tool mapping:

```text
asklens_capabilities(include_query_plan_schema=false, resource_detail="summary")
asklens_query_plan_schema()
asklens_describe_resource(resource)
asklens_validate_plan(plan)
asklens_execute_plan(plan, presentation=null, include_rows=false)
asklens_query(question, presentation=null, include_rows=false)  # optional convenience tool
```

`asklens_capabilities(request)` returns machine capabilities separately from
permission-scoped resource metadata. With `resource_detail="full"`, the payload
contains sibling `capabilities` and `catalog` documents. With
`resource_detail="summary"`, it contains machine `capabilities` plus adapter-
level `resource_summaries`; the summary is not the strict catalog document.
Machine capabilities contain no labels, descriptions, examples, scope guidance,
or resources. The helper does not return rows/sample values, execute a query, or
call a provider. For MCP transports, prefer summary detail and
`include_query_plan_schema=False` during discovery.

`asklens_query_plan_schema(request)` returns the QueryPlan JSON schema without
repeating machine capabilities or catalog metadata.

`asklens_describe_resource(request, resource)` returns full permission-scoped metadata for one visible resource. Use this after compact discovery and before constructing a QueryPlan for a specific resource.

`asklens_validate_plan(request, plan)` validates a client-produced plan against the current catalog, permissions, settings, and safety rules without executing a database query or creating an audit row.

`asklens_execute_plan(request, plan, presentation=None, include_rows=False)` revalidates the plan, resolves the resource's explicit global/context scope, compiles it to Django ORM, and applies the configured audit mode. Optional presentation is a separate envelope and cannot affect execution. Database audit mode also returns a run id. Default audit records omit the MCP question and complete plan; they retain operational resource/intent/status/error/row-count/duration metadata only.

`asklens_query(request, question, include_rows=False)` is a convenience wrapper around AskLens' existing query orchestration for deployments that still want AskLens to call its configured provider.

These helpers do not import Django REST Framework or an MCP SDK.

MCP failures use the same stable error object as core Python and the API:

```json
{
  "error": {
    "code": "asklens.member.unavailable",
    "message": "A requested query member is unavailable."
  }
}
```

The object contains only a namespaced `code`, safe `message`, and optional safe JSON `pointer`. Unknown and unauthorized resources, fields, and metrics are intentionally indistinguishable. Older transport-specific `error_category` values are removed.

## AskLens toolset wrapper

When an MCP server can register existing Python callables, use `AskLensMCPToolSet`:

```python
from django_asklens.mcp import AskLensMCPToolSet


def build_request_from_mcp_context(context):
    # Host-project code: map the authenticated MCP context/session to a
    # Django request-like object with request.user and any tenant attributes
    # used by REQUEST_PERMISSIONS_GETTER or scope_provider(request).
    ...


toolset = AskLensMCPToolSet(
    request_factory=build_request_from_mcp_context,
    expose_query_tool=False,
)

# Register these callables with your MCP server implementation.
tools = toolset.tools()
```

`toolset.tools()` returns:

```text
asklens_capabilities
asklens_query_plan_schema
asklens_describe_resource
asklens_validate_plan
asklens_execute_plan
```

If `expose_query_tool=True`, it also returns `asklens_query`. Keep this disabled unless you intentionally want a tool that may call the configured AskLens provider in non-dummy deployments.

The optional FastMCP bridge exposes compact discovery by default:
`asklens_capabilities()` omits the QueryPlan schema, returns the machine
capability document, and places compact resource metadata in separate
`resource_summaries`. MCP clients can then call `asklens_query_plan_schema()` and
`asklens_describe_resource(resource)` only when they need those details.

When using `create_fastmcp_server(toolset)`, FastMCP's injected `Context` is passed to `toolset.request_factory(context)`. Host projects can use that trusted server-side context to derive the Django user, tenant scope, or session metadata. Do not accept usernames or permission strings from client-controlled tool arguments.

See [`examples/mcp/`](../examples/mcp/) for a generic registration sketch. The repository also includes a concrete, tested example in `tests/test_project/mcp.py` with coverage in `tests/test_project/test_mcp_example.py`; it uses an in-memory fake MCP server to demonstrate tool registration and calls without choosing a real transport dependency.

## Runnable test-project MCP endpoint

The runnable test project can expose a real FastMCP Streamable HTTP endpoint for local testing with clients such as pi-codemcp. This ASGI/Uvicorn setup is a local one-port demo convenience: `/mcp` is served by FastMCP and normal Django routes, including admin, are mounted beside it.

For the committed PostgreSQL 18 and Playwright HTTP evidence, use `bash scripts/reference-demo-smoke.sh` from a source checkout after the setup in [the runnable demo guide](test-project-demo.md). That smoke starts with a server-owned `facility-owner` identity, keeps `DJANGO_ASKLENS_MCP_ALLOW_ROWS=0`, proves the tool schema has no client identity/permission/scope arguments, requests rows and observes safe denial, and tears down its isolated Compose project. It is synthetic internal alpha release-source evidence, not production authentication or transport-security guidance.

AskLens core does not require ASGI, Uvicorn, or FastMCP. Host projects may run their normal Django app/admin through `runserver`, WSGI, or their existing ASGI stack and expose MCP from a separate process or port. In this repository, FastMCP and Uvicorn are development dependencies installed by `uv sync --group dev`.

Seed the demo database first:

```bash
uv run python -m django migrate --settings=tests.test_project.demo_settings
uv run python -m django seed_complex_test_project --settings=tests.test_project.demo_settings
```

Start the local ASGI demo app with MCP enabled:

```bash
DJANGO_ASKLENS_MCP_ENABLED=1 \
DJANGO_ASKLENS_MCP_USERNAME=facility-owner \
uv run uvicorn tests.test_project.demo_asgi:application --reload --port 8000
```

The MCP endpoint is:

```text
http://127.0.0.1:8000/mcp
```

The endpoint is mounted only when `DJANGO_ASKLENS_MCP_ENABLED=1` is set. If MCP is not enabled, use the normal Django development server described in the test-project demo guide.

The demo MCP user is selected server-side by `DJANGO_ASKLENS_MCP_USERNAME`. Do not expose username or permission selection as MCP tool arguments. To expose the optional AskLens-managed question tool, set:

```bash
DJANGO_ASKLENS_MCP_EXPOSE_QUERY=1
```

To allow row return through MCP, set:

```bash
DJANGO_ASKLENS_MCP_ALLOW_ROWS=1
```

Rows remain omitted unless both the tool call asks for rows and this environment flag enables `DJANGO_ASKLENS["MCP_ALLOW_ROW_RETURN"]`.

For pi-codemcp, add a server like this to `~/.pi/agent/mcp.json`:

```json
{
  "mcpServers": {
    "asklens": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

Then reload CodeMCP in Pi with `/codemcp`, discover the `asklens` server, and search for AskLens tools.

## Planning modes

### 1. AskLens-managed planning

In this mode, the MCP client passes a natural-language question to AskLens:

```text
MCP client
  -> asklens_query(question)
  -> AskLens provider creates QueryPlan
  -> AskLens validates QueryPlan
  -> AskLens executes safe ORM query
```

This keeps behavior close to the optional DRF `/asklens/query/` endpoint. It is useful when the deployment wants consistent server-side planning or when the MCP client is not expected to produce a structured plan itself.

This mode may call the configured AskLens provider. The default `dummy` backend makes no network calls; live providers remain opt-in.

### 2. MCP/client-managed planning

In a more MCP-native flow, the client LLM can act as the planner and AskLens does not need to call an external LLM:

```text
MCP client LLM
  -> asklens_capabilities()
  -> produce QueryPlan JSON as tool arguments
  -> asklens_validate_plan(plan)
  -> asklens_execute_plan(plan, include_rows=false)
  -> AskLens validates and executes safe ORM query
```

This mode uses the MCP client's model for planning. AskLens remains the trust boundary: it treats the client-produced plan as untrusted, validates it, enforces permissions and tenant scope, compiles Django ORM only, applies limits, and audits execution.

This is the preferred design when the goal is to avoid server-side LLM calls from AskLens while still preventing the MCP client from becoming direct database access.

## Row-return defaults

MCP clients often place tool results into an LLM context. For that reason, the adapter defaults to returning metadata rather than rows:

```json
{
  "response_type": "query",
  "run_id": 42,
  "columns": [
    {"key": "status", "label": "Status", "type": "string", "nullable": false}
  ],
  "data": [],
  "row_count": 2,
  "rows_omitted": true,
  "presentation": {"kind": "bar"}
}
```

There are two gates for row return:

1. The tool call must pass `include_rows=True`.
2. The Django project must explicitly enable row return:

```python
DJANGO_ASKLENS = {
    "MCP_ALLOW_ROW_RETURN": True,
    "MCP_MAX_RETURNED_ROWS": 100,
}
```

If `include_rows=True` is requested while `MCP_ALLOW_ROW_RETURN` is false, AskLens still omits rows and returns `row_return_denied: true`.

When rows are allowed, `MCP_MAX_RETURNED_ROWS` caps only the MCP tool payload. AskLens still executes the validated query through its normal row limits and audit path, and `row_count` still describes the executed result. Core `result_metadata.truncated` reports whether another database row/group exists beyond the plan limit; the separate `mcp_rows_truncated` flag reports whether the already-executed result was additionally capped for the MCP payload. If the MCP payload is capped, the response also includes `mcp_row_limit` and `mcp_returned_row_count`.

`MCP_MAX_RETURNED_ROWS` is not pagination. Today, an MCP client that needs more rows should ask a narrower follow-up query, use exposed fields for stable filters such as “after this id/date” where appropriate, or the host project must intentionally raise the MCP row cap. First-class “next page” behavior should be added after AskLens core has safe pagination/cursor semantics.

## Request and permission mapping

The adapter expects a Django request-like context so existing AskLens hooks behave the same way as API/admin/core usage:

- `request.user` for authentication and default Django permissions;
- `REQUEST_PERMISSIONS_GETTER` for project-specific role or tenant permission strings;
- trusted resource `scope_provider(request)` callables for context scope; and
- configured project gates around the MCP server/tool route.

The MCP layer should map its authenticated principal to a real Django user or a request-like object with equivalent attributes before calling AskLens. It should not expose permission strings as client-controlled tool arguments, and it should not bypass AskLens permission, validation, or row-scope checks.

## Non-goals for the adapter

The adapter does not add:

- raw SQL generation or execution;
- mutation/write tools;
- automatic exposure of all Django models;
- sample database rows in capabilities output;
- permission bypasses for MCP clients;
- a mandatory MCP SDK dependency;
- a dependency on Django REST Framework; or
- mandatory server-side LLM calls.

The intended integration is a transport adapter over AskLens core, not a replacement for AskLens' safety model.
