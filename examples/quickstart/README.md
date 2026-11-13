# Minimal installed-package consumer

This synthetic Django app asks an exact configured question about the current
user's orders using an installed AskLens artifact, not `tests.test_project` or
an editable package checkout. It has no server, login passwords, API/MCP extras,
Docker, or live LLM calls.

Follow [Your first scoped question](../../docs/quickstart-app.md) for the complete
fresh-directory setup, public artifact authentication, expected success/empty/
denial results, host-model transition, tests, and cleanup. Do not run this seed
command against a real application's database or copy the trusted `--as-user`
selector into a public request handler.

These example files are new mutable source material, not part of immutable
public `v0.3.2`. They use existing public `django-asklens==0.3.2` behavior. The
package remains alpha; dummy mode matches exact questions and the records are
synthetic, not evidence of natural-language reliability or production readiness.
