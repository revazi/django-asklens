# AskLens MCP wrapper examples

These examples show how to register AskLens' dependency-free MCP tool wrappers
with a host project's MCP server implementation. They are synthetic integration
evidence, not a production authentication or transport template.

## Bounded current-artifact checklist

This `main`-branch example requires unreleased current source or a
maintainer-supplied private candidate. Verify the candidate's immutable commit,
exact filename, and SHA-256 using the
[private-candidate instructions](../../docs/installation.md#maintainer-supplied-private-candidate-evaluation),
then install that exact local wheel in a fresh environment:

```bash
export ASKLENS_CANDIDATE_WHEEL=/verified/path/django_asklens-0.1.0a1-py3-none-any.whl
python -m pip install "${ASKLENS_CANDIDATE_WHEEL}[mcp]"
```

Do not replace the wheel path with an unpinned package name. Current and
published bytes share the `0.1.0a1` filename; this is same-version replacement,
not a public release or normal upgrade.

### Register the trusted context mapping

AskLens intentionally does not depend on a generic Django MCP package or Django
REST Framework for MCP support. The host must authenticate the MCP connection
and map its trusted server-owned context to a Django request-like object:

```python
from types import SimpleNamespace

from django_asklens.mcp import AskLensMCPToolSet, create_fastmcp_server


def request_from_context(context):
    principal = authenticated_principal_from_context(context)  # Host-owned.
    return SimpleNamespace(
        user=principal.user,
        reporting_tenant=principal.reporting_tenant,
    )


toolset = AskLensMCPToolSet(request_factory=request_from_context)
server = create_fastmcp_server(toolset)
```

`authenticated_principal_from_context()` is host code and must reject an
unauthenticated or invalid session. Project-specific permissions and row scope
come from `request.user`, `REQUEST_PERMISSIONS_GETTER`, and registered
`scope_provider(request)` callables. They never come from client tool arguments.

The default tool schemas must not accept `username`, `user`, `permissions`,
`tenant`, or `scope`. FastMCP injects its server context rather than exposing it
as an argument.

### Run the compact synthetic flow

1. Call `asklens_capabilities()` and inspect permission-scoped
   `resource_summaries`; this compact discovery returns no rows or samples.
2. Fetch `asklens_query_plan_schema()` and
   `asklens_describe_resource(resource="orders")` only when needed.
3. Submit a synthetic semantic plan to `asklens_validate_plan(plan=...)`.
   Validation reports `executed: false`; it is not reusable authorization.
4. Submit the returned plan to
   `asklens_execute_plan(plan=..., include_rows=False)`. Execution revalidates
   the current principal and scope through AskLens' trusted facade.
5. Confirm `data` is empty and `rows_omitted: true`. Then request
   `include_rows=True` while the host default remains off and confirm
   `row_return_denied: true`; never treat row omission as query-cost control.

The five default tools are `asklens_capabilities`,
`asklens_query_plan_schema`, `asklens_describe_resource`,
`asklens_validate_plan`, and `asklens_execute_plan`. The provider-backed
`asklens_query` tool stays disabled unless the host deliberately opts in.

The concrete implementation in `tests/test_project/mcp.py` uses an in-memory
fake MCP server to prove registration, server-derived permissions, detailed
metadata lookup, synthetic validation/execution, tenant isolation, and safe row
omission. The FastMCP bridge tests prove compact discovery and that every tool
input schema excludes client identity, permission, tenant, and scope selectors:

```bash
uv run pytest tests/test_project/test_mcp_example.py \
  tests/test_project/test_mcp_server.py
```

See the full [MCP integration guide](../../docs/mcp-integration.md) for audit,
row-cap, adapter, and host-operations details.

## Runnable local endpoint

For a real local MCP endpoint in this repository, start the synthetic demo ASGI
app with MCP enabled. This is only a local one-port convenience; production
hosts must supply real authentication, transport protection, route gates,
timeouts, and rate/concurrency controls.

```bash
DJANGO_ASKLENS_MCP_ENABLED=1 \
DJANGO_ASKLENS_MCP_USERNAME=facility-owner \
uv run uvicorn tests.test_project.demo_asgi:application --reload --port 8000
```

Then point an MCP client at `http://127.0.0.1:8000/mcp` using Streamable HTTP.
The demo chooses `facility-owner` on the server and keeps row return disabled by
default. If you are only testing the Django admin or demo frontend, use the
normal Django `runserver` flow instead.
