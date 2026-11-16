# Minimal installed-package consumer

This synthetic Django app asks an exact configured question about the current
user's orders using an installed AskLens artifact, not `tests.test_project` or
an editable package checkout. Its default core path has no server, login
passwords, API/MCP extras, Docker, or live LLM calls.

Follow [Your first scoped question](../../docs/quickstart-app.md) for the complete
fresh-directory setup, public artifact authentication, expected success/empty/
denial results, host-model transition, tests, and cleanup. Do not run this seed
command against a real application's database or copy the trusted `--as-user`
selector into a public request handler.

After that minimal path, choose the canonical [API/admin recipe](../../docs/usage.md),
[table consumer](../../docs/custom-ui.md), or [MCP recipe](../../docs/mcp-integration.md).
The opt-in settings/URLs/tools and `shop/*_recipe.py` tests share this model,
registration and fixtures; they do not change the base CLI/seed behavior.
Native admin is Django-only, the browser table requires the API extra, and the
FastMCP bridge needs only the MCP extra. Recipe tests use disposable databases,
real session/CSRF checks where applicable, and synthetic server-owned MCP
context, never a public user selector. No production authentication is supplied.

These example files are new mutable source material, not part of immutable
public `v0.3.2`. They use existing public `django-asklens==0.3.2` behavior. The
package remains alpha; dummy mode matches exact questions and the records are
synthetic, not evidence of natural-language reliability or production readiness.
