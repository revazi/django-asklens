# AskLens MCP wrapper examples

These examples show how to register AskLens' dependency-free MCP tool wrappers with a host project's MCP server implementation.

AskLens intentionally does not depend on a generic Django MCP package or Django REST Framework for MCP support. The host project remains responsible for:

- choosing/running the MCP transport;
- authenticating the MCP caller;
- mapping the caller to a Django user or request-like object;
- deriving any tenant/role permission strings from trusted server-side context; and
- deciding whether row return should be enabled with `DJANGO_ASKLENS["MCP_ALLOW_ROW_RETURN"]`.

Use `AskLensMCPToolSet` when your MCP library can register existing Python callables. Use the lower-level functions in `django_asklens.mcp` when your MCP framework has a different calling convention.

For a runnable repository example, see `tests/test_project/mcp.py` and `tests/test_project/test_mcp_example.py`. They use an in-memory fake MCP server to show registration, context-to-request mapping, server-derived permissions, plan validation, execution, row omission, and the opt-in `asklens_query` tool.
