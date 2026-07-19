# MCP integration notes

Status: AskLens ships dependency-free MCP adapter helpers, an `AskLensMCPToolSet` wrapper, and an optional FastMCP bridge under `django_asklens.mcp`. The repository also includes an opt-in ASGI/Uvicorn MCP endpoint for the runnable local test project. Django AskLens does not provide a production authentication layer; host projects remain responsible for authenticating MCP callers and mapping trusted server-side context to a Django request-like object.

## Why AskLens still matters with MCP

MCP can provide a transport layer between an AI client and application tools. A Django-aware MCP server can also authenticate a caller and map the caller to a Django user.

That does not replace AskLens' core responsibilities:

- defining which Django models are exposed as semantic resources;
- exposing only permission-scoped resources, fields, metrics, and examples;
- hiding sensitive fields unless permissions allow them;
- validating every `QueryPlan` as untrusted input;
- enforcing resource and field permissions;
- starting execution from each resource's `base_queryset(request)` tenant/row-scope hook;
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

The dependency-free helpers live in the main `django-asklens` package. The optional FastMCP bridge is available through the `mcp` extra:

```bash
python -m pip install 'django-asklens[mcp]'
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
asklens_execute_plan(plan, include_rows=false)
asklens_query(question, include_rows=false)  # optional convenience tool
```

`asklens_capabilities(request)` returns permission-scoped metadata only: visible resources, fields, metrics, supported patterns, limitations, example questions, and optionally the `QueryPlan` JSON schema. It does not return database rows or sample values, execute a query, or call an LLM provider. For MCP transports, prefer `resource_detail="summary"` and `include_query_plan_schema=False` during discovery to keep tool output compact.

`asklens_query_plan_schema(request)` returns the QueryPlan JSON schema without repeating catalog capabilities.

`asklens_describe_resource(request, resource)` returns full permission-scoped metadata for one visible resource. Use this after compact discovery and before constructing a QueryPlan for a specific resource.

`asklens_validate_plan(request, plan)` validates a client-produced plan against the current catalog, permissions, settings, and safety rules without executing a database query or creating an audit row.

`asklens_execute_plan(request, plan, include_rows=False)` revalidates the plan, compiles it to Django ORM, executes it through the resource `base_queryset(request)`, creates the normal AskLens audit record, and returns metadata such as columns, row count, visualization hints, and run id.

`asklens_query(request, question, include_rows=False)` is a convenience wrapper around AskLens' existing query orchestration for deployments that still want AskLens to call its configured provider.

These helpers do not import Django REST Framework or an MCP SDK.

## AskLens toolset wrapper

When an MCP server can register existing Python callables, use `AskLensMCPToolSet`:

```python
from django_asklens.mcp import AskLensMCPToolSet


def build_request_from_mcp_context(context):
    # Host-project code: map the authenticated MCP context/session to a
    # Django request-like object with request.user and any tenant attributes
    # used by REQUEST_PERMISSIONS_GETTER or base_queryset(request).
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

The optional FastMCP bridge exposes compact capabilities by default: `asklens_capabilities()` omits the QueryPlan schema and summarizes each resource. MCP clients can then call `asklens_query_plan_schema()` and `asklens_describe_resource(resource)` only when they need those details.

When using `create_fastmcp_server(toolset)`, FastMCP's injected `Context` is passed to `toolset.request_factory(context)`. Host projects can use that trusted server-side context to derive the Django user, tenant scope, or session metadata. Do not accept usernames or permission strings from client-controlled tool arguments.

See [`examples/mcp/`](../examples/mcp/) for a generic registration sketch. The repository also includes a concrete, tested example in `tests/test_project/mcp.py` with coverage in `tests/test_project/test_mcp_example.py`; it uses an in-memory fake MCP server to demonstrate tool registration and calls without choosing a real transport dependency.

## Runnable test-project MCP endpoint

The runnable test project can expose a real FastMCP Streamable HTTP endpoint for local testing with clients such as pi-codemcp. This ASGI/Uvicorn setup is a local one-port demo convenience: `/mcp` is served by FastMCP and normal Django routes, including admin, are mounted beside it.

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

The endpoint is mounted only when `DJANGO_ASKLENS_MCP_ENABLED=1` is set. The earlier local alias `DJANGO_ASKLENS_DEMO_MCP=1` is also accepted for compatibility. If MCP is not enabled, use the normal Django development server described in the test-project demo guide.

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
  "columns": [{"key": "status", "label": "Status", "type": "string"}],
  "data": [],
  "row_count": 2,
  "rows_omitted": true,
  "visualization": {"type": "bar"}
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

When rows are allowed, `MCP_MAX_RETURNED_ROWS` caps only the MCP tool payload. AskLens still executes the validated query through its normal row limits and audit path, and `row_count` still describes the executed result. If the MCP payload is capped, the response includes `mcp_rows_truncated: true`, `mcp_row_limit`, and `mcp_returned_row_count`.

`MCP_MAX_RETURNED_ROWS` is not pagination. Today, an MCP client that needs more rows should ask a narrower follow-up query, use exposed fields for stable filters such as “after this id/date” where appropriate, or the host project must intentionally raise the MCP row cap. First-class “next page” behavior should be added after AskLens core has safe pagination/cursor semantics.

## Request and permission mapping

The adapter expects a Django request-like context so existing AskLens hooks behave the same way as API/admin/core usage:

- `request.user` for authentication and default Django permissions;
- `REQUEST_PERMISSIONS_GETTER` for project-specific role or tenant permission strings;
- resource `base_queryset(request)` hooks for tenant/row scope; and
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
