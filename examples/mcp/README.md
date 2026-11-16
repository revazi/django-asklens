# AskLens MCP wrapper examples

The canonical progressive recipe is the
[MCP integration guide](../../docs/mcp-integration.md#bounded-mcp-quickstart).
Start with the [minimal installed-package consumer](../../docs/quickstart-app.md),
then use its opt-in `quickstart.mcp_settings` and `quickstart.mcp.make_server`.
The guide owns exact dependencies, registration/settings, server-derived identity,
current-request authorization and row scope, default row omission, explicit
host-and-request row gates/caps, and installed-candidate verification commands.

`generic_toolset.py` remains a dependency-free registration sketch for hosts
using another MCP framework. Its unimplemented request factory is intentional:
there is no default authenticated identity, public username selector, transport,
or production authentication implementation. Do not register its `context`
parameter as a client tool argument; bind trusted server-injected context using
the host framework. For FastMCP use AskLens' `create_fastmcp_server()` bridge,
which omits context from the generated client schema.

These helpers already exist in immutable public `django-asklens==0.3.2`;
the quickstart adapter files are newer **source-only** examples, not retroactive
changes to published artifacts. All MCP adapter shapes are optional and
provisional under the [compatibility policy](../../docs/compatibility.md).
A candidate wheel and its digest are separate from public-artifact evidence.

For the larger synthetic ASGI endpoint and its limitations, follow
[Runnable test-project MCP endpoint](../../docs/mcp-integration.md#runnable-test-project-mcp-endpoint).
It is a source demo, not the minimal adoption recipe or production-auth guidance.
