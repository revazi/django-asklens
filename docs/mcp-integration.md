# MCP integration notes

Status: framework-neutral adapter helpers are available under `django_asklens.mcp`. Django AskLens does not currently ship a full MCP SDK server, HTTP transport, or authentication layer. Host projects can wrap these helpers with whichever Django-aware MCP server they use.

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

## Adapter helpers

AskLens provides dependency-free helpers that can be wrapped as MCP tools:

```python
from django_asklens.mcp import (
    asklens_capabilities,
    asklens_execute_plan,
    asklens_query,
    asklens_validate_plan,
)
```

Suggested MCP tool mapping:

```text
asklens_capabilities()
asklens_validate_plan(plan)
asklens_execute_plan(plan, include_rows=false)
asklens_query(question, include_rows=false)  # optional convenience tool
```

`asklens_capabilities(request)` returns permission-scoped metadata only: visible resources, fields, metrics, supported patterns, limitations, example questions, and the `QueryPlan` JSON schema. It does not return database rows or sample values, execute a query, or call an LLM provider.

`asklens_validate_plan(request, plan)` validates a client-produced plan against the current catalog, permissions, settings, and safety rules without executing a database query or creating an audit row.

`asklens_execute_plan(request, plan, include_rows=False)` revalidates the plan, compiles it to Django ORM, executes it through the resource `base_queryset(request)`, creates the normal AskLens audit record, and returns metadata such as columns, row count, visualization hints, and run id. Returning rows is explicit because many MCP clients feed tool results back into an LLM context.

`asklens_query(request, question, include_rows=False)` is a convenience wrapper around AskLens' existing query orchestration for deployments that still want AskLens to call its configured provider.

These helpers do not import Django REST Framework or an MCP SDK.

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

Projects can call `asklens_execute_plan(..., include_rows=True)` or `asklens_query(..., include_rows=True)` for trusted deployments or user-approved actions, but row return is not the silent default.

## Request and permission mapping

The adapter expects a Django request-like context so existing AskLens hooks behave the same way as API/admin/core usage:

- `request.user` for authentication and default Django permissions;
- `REQUEST_PERMISSIONS_GETTER` for project-specific role or tenant permission strings;
- resource `base_queryset(request)` hooks for tenant/row scope; and
- configured project gates around the MCP server/tool route.

The MCP layer should map its authenticated principal to a real Django user or a request-like object with equivalent attributes before calling AskLens. It should not expose permission strings as client-controlled tool arguments, and it should not bypass AskLens permission, validation, or row-scope checks.

Example wrapper shape:

```python
def asklens_execute_plan_tool(context, plan, include_rows=False):
    request = build_django_request_from_mcp_context(context)
    return asklens_execute_plan(
        request,
        plan,
        include_rows=include_rows,
    )
```

## Non-goals for the adapter

The adapter does not add:

- raw SQL generation or execution;
- mutation/write tools;
- automatic exposure of all Django models;
- sample database rows in capabilities output;
- permission bypasses for MCP clients;
- a mandatory MCP SDK dependency; or
- mandatory server-side LLM calls.

The intended integration is a transport adapter over AskLens core, not a replacement for AskLens' safety model.
