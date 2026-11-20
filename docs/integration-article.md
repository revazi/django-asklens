# Ask a scoped Django question without executing model-generated SQL

**Draft integration article — not submitted or externally posted.** Prepared
for [#196](https://github.com/revazi/django-asklens/issues/196) on 2026-11-20.
Django AskLens is **alpha**. The prospective author, Revaz Zakalashvili, is its
creator and maintainer; this draft and its verification were prepared with
substantial **AI assistance** and still require independent review. All data
below is **synthetic**. The offline dummy provider recognizes **exact configured
questions**, not arbitrary natural language. No live provider is called.

## The integration problem

Suppose your Django application already knows which orders a person may see.
You want that person to ask for a small paid-order report, not hand a language
model a database connection or execute its proposed SQL. Authentication and
ownership policy should remain in the application, where they already belong.

AskLens separates a proposed query from authority to run it:

1. The host explicitly registers a model, semantic fields and any metrics.
   Private Django bindings remain in host code, not in the planner's field list.
2. Planning uses catalog metadata filtered by server-derived permissions, not
   database rows or sample values by default. Host-written descriptions and
   enum values are still disclosures: review them before sending metadata to
   a provider. Never put private data into supposedly helpful catalog prose.
3. An untrusted JSON plan names semantic members and supported operations. It
   cannot supply SQL, an ORM path, a user, tenant, permission grant or scope
   provider. A valid-looking schema is not permission to execute.
4. `execute_plan(plan, request=request)` builds fresh execution state, reparses
   and revalidates against the current catalog, request permissions and budgets,
   then obtains the host's lazy scoped queryset and compiles read-only ORM
   operations. A previously validated or cached plan is not an access token.
5. The result contains typed columns, bounded rows and explicit truncation
   metadata, suitable for a small table. Empty results and denials are different
   outcomes; neither should cause the host to retry with broader scope.

See the [trusted facade](core-python-api.md),
[current-request revalidation assertions](https://github.com/revazi/django-asklens/blob/6d0d15d9017749547eb8cc6bfdc59883561ff077/tests/execution/test_adapter_revalidation.py)
and [threat-model checklist](security-checklist.md). These mechanisms constrain
queries; they do not certify a deployment's security or a model's answer quality.

## Start with an inspectable host, not a production database

Reuse [Your first scoped question](quickstart-app.md), including its fresh-directory
copy, installation, migration, check and synthetic seed steps. It supplies one
ordinary `shop.Order` model, an owner relationship, three non-login users and
four fixture orders. No DRF, MCP, server, Docker or API key is required for this
CLI integration. Python 3.12+, a POSIX shell and `uv` are the documented setup.
Use only the disposable copy; do not point its settings at another database.

**Choose the artifact deliberately.** The quickstart authenticates the immutable
public [`django-asklens==0.3.2` alpha](https://pypi.org/project/django-asklens/0.3.2/)
and its [release source](https://github.com/revazi/django-asklens/tree/v0.3.2).
The recorded public wheel SHA-256 is
`739d5411cd0b0ab63ac8dae9e9a0a4f2cf396cb2e0f0ef5bbfac9a2c4607b050`;
see [installation and artifact identities](installation.md) before installing.
The quickstart host, this article and its failure fixture are **newer source
additions**, not files inside that release. The replays reported here used a
freshly built, same-version **candidate wheel**, byte-checked in isolated
installed environments, not the authenticated public wheel. That is not evidence
that candidate-only provider fixes shipped in public `0.3.2`.
[Exact source/candidate evidence and commands](article-evidence-196.md) identify
what was actually tested. Current [public documentation](https://revazi.github.io/django-asklens/)
is mutable and may lag source; the repository links in that record pin the
examples used here. No new release or docs-site deployment is part of this work.

## Register only what this report needs

This is the quickstart's existing
[`shop/asklens_registration.py`](https://github.com/revazi/django-asklens/blob/main/examples/quickstart/shop/asklens_registration.py),
imported once by `ShopConfig.ready()`. It is host code, not a provider response:

<!-- asklens-article-source:registration -->
```python
"""Public semantic fields stay separate from private host bindings and scope."""

from django_asklens import register

from .models import Order


def visible_orders(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return Order.objects.none()
    return Order.objects.filter(owner_id=user.pk)


register(
    model=Order,
    name="orders",
    label="My orders",
    description="Synthetic orders owned by the current authenticated user.",
    timezone="UTC",
    fields={
        "product": {"binding": "product", "type": "string", "nullable": False},
        "status": {"binding": "status", "type": "string", "nullable": False},
        "total_cents": {
            "binding": "total_cents",
            "type": "integer",
            "nullable": False,
            "label": "Total (cents)",
        },
    },
    default_order=(("product", "asc"),),
    requires_permission="shop.view_order",
    scope_mode="context_scoped",
    scope_provider=visible_orders,
)
```

Here `product`, `status` and `total_cents` are public semantic keys. They happen
to resemble their bindings; that is not automatic field exposure. `owner` and
`owner_id` are **not** queryable fields. `scope_provider` can use the private
owner binding without exposing it to the planner. Resource permission and row
ownership are separate: `shop.view_order` permits querying the resource, while
`visible_orders(request)` restricts the rows. Anonymous scope is `none()`, not
an unrestricted manager fallback. More complex membership policies and safe
relationship/metric cardinality require explicit [registration](registration.md).

In this fixture, Alice's permitted catalog contains `orders` with just those
three fields; the `no-report` user's catalog has no resources. Catalog output
omits the private bindings and permission requirement. Permission-filtered
metadata reduces what planning sees, but execution still validates the plan:
hiding something in a UI is not an authorization check.

The local `ask_orders` command loads an actual synthetic Django user, attaches
it to a server-created `HttpRequest`, and calls the **provisional**
`execute_asklens_query_request` orchestrator with a question and **no**
`provided_plan`. Dummy planning proposes a configured plan; data execution then
converges on the governed `execute_plan` facade. In a web host use the genuine
middleware-authenticated `request.user`. **Never expose `--as-user` or any
client-supplied identity/scope selector as an HTTP or MCP argument.** See the
[compatibility boundary](compatibility.md): orchestration/adapters and the five
JSON documents remain provisional/draft, not a frozen wire protocol.

## Four outcomes you can replay

Run these from the disposable quickstart copy after setup/seed. Each JSON block
is the command's complete stdout document **except `result.duration_ms`**, a
variable non-negative measurement omitted for comparison. Error commands exit
**1**, emit the safe JSON to stdout and a fixed CLI summary to stderr. Do not
paste raw diagnostics into a user interface.

### 1. Useful, bounded success

<!-- asklens-article:success -->
```bash
.venv/bin/python manage.py ask_orders 'Show my paid orders' --as-user alice
```

<!-- asklens-article:success-response -->
```json
{
  "response_type": "query",
  "result": {
    "columns": [
      {"key": "product", "label": "Product", "type": "string", "nullable": false},
      {"key": "total_cents", "label": "Total (cents)", "type": "integer", "nullable": false}
    ],
    "data": [
      {"product": "North class", "total_cents": 2000},
      {"product": "North membership", "total_cents": 1200}
    ],
    "row_count": 2,
    "result_metadata": {"limit": 10, "limit_scope": "rows", "truncated": false}
  }
}
```

The paid-order plan selects two registered fields and filters registered
`status` to `paid`. Alice gets her two paid orders, not her draft or Bob's South
order. `row_count` counts returned rows, not all possible matches; the explicit
limit is 10. List/group execution fetches at most the validated limit plus one
to detect truncation. If `truncated` is true, label the table as partial and ask
for a narrower query—do not display the count as an exact total.

### 2. A successful empty result

<!-- asklens-article:empty -->
```bash
.venv/bin/python manage.py ask_orders 'Show my refunded orders' --as-user alice
```

<!-- asklens-article:empty-response -->
```json
{
  "response_type": "query",
  "result": {
    "columns": [
      {"key": "product", "label": "Product", "type": "string", "nullable": false},
      {"key": "total_cents", "label": "Total (cents)", "type": "integer", "nullable": false}
    ],
    "data": [],
    "row_count": 0,
    "empty": true,
    "result_metadata": {"limit": 10, "limit_scope": "rows", "truncated": false}
  }
}
```

Exit status **0** means the permitted query ran; no scoped row matched
`refunded`. Keep the column headers and display “No matching rows.” Do not call
this a permission failure or broaden ownership scope to find an answer.

### 3. Opaque denial, not an empty table

<!-- asklens-article:denied -->
```bash
.venv/bin/python manage.py ask_orders 'Show my paid orders' --as-user no-report
```

<!-- asklens-article:denied-response -->
```json
{
  "response_type": "error",
  "error": {
    "code": "asklens.member.unavailable",
    "message": "A requested query member is unavailable."
  }
}
```

This user lacks the resource permission. The caller receives neither permission
names nor evidence that a particular hidden resource exists: unavailable and
unknown members share a public category. The replay asserts **zero queries to
the Order table** for this path; user/permission queries and an AskLens audit
write are distinct and may still occur. A real host can offer neutral account
recovery, not a policy explanation, a superuser retry or a false empty success.

### 4. A provider-produced plan that is not usable

Use the copied, article-only
[`quickstart/invalid_plan_settings.py`](https://github.com/revazi/django-asklens/blob/main/examples/quickstart/quickstart/invalid_plan_settings.py).
It retains the dummy backend and metadata-only audit, but makes the exact paid
question return this intentionally invalid envelope:

<!-- asklens-article-source:invalid-envelope -->
```json
{
  "query_plan": {
    "resource": "orders",
    "intent": "list",
    "select": ["product", "total_cents"],
    "limit": "ten"
  }
}
```

<!-- asklens-article:invalid -->
```bash
.venv/bin/python manage.py ask_orders 'Show my paid orders' --as-user alice --settings=quickstart.invalid_plan_settings
```

<!-- asklens-article:invalid-response -->
```json
{
  "response_type": "error",
  "error": {
    "code": "asklens.plan.invalid",
    "message": "The query plan is invalid."
  }
}
```

`limit` must be an integer. The actual dummy provider returns the bad plan; the
planner rejects its envelope before compilation, with no Order-table query.
This is **not** the unmatched-question/provider-transport failure from the
quickstart and is not a simulated live-model success. Remove `--settings=...`
to return to the reviewed paid-order fixture; do not coerce arbitrary provider
output or disable validation to repair a real failure. Other boundaries can
produce different safe [error categories](core-python-api.md#stable-execution-errors).

## What the host still owns

Treat questions, provider plans, cached plans and display values as untrusted.
The provider may misunderstand the request, suggest unavailable fields or
produce invalid JSON. Keeping SQL/code execution out of the design does not
make every accepted report meaningful, affordable or safe to disclose.

- **Authentication and policy:** trusted user/tenant membership, permissions,
  permission-cache invalidation, reviewed resource/field grants and a correct
  lazy exact-model scope provider. Revalidation invokes current host policy; it
  cannot repair stale permissions cached by the host or a scope provider that
  accidentally returns every row. Never reuse internal compiled/prepared state.
- **Operational bounds:** AskLens validates plan bytes, field/filter/metric/
  relationship counts and result limits. The host still needs indexes,
  statement/request/provider timeouts, rate/concurrency controls and read-only
  database defense. A ten-row output cap does not cap a full-table scan's cost.
- **Data handling:** by default the provider receives questions and permitted
  semantic metadata, not database rows. Choose provider retention and network
  policy deliberately; questions themselves may contain sensitive content.
  Leave provider I/O logging off. Metadata-only audit still contains operational
  identifiers; secure its access and retention. Full-content audit needs
  explicit policy, and audit delivery failure must be monitored. Observability
  is best effort, not an audit replacement.
- **Adapters and presentation:** authenticate/gate the actual API/MCP route, not
  just the page. Keep CSRF where applicable, render values as text and use
  typed columns. MCP omits rows by default because client tools may send them
  onward to a model; omission does not mean no database query occurred. Start
  with one verified [API/admin](usage.md) or [MCP](mcp-integration.md) recipe.

The existing [browser showcase](showcase.md) offers approved synthetic captures,
a captioned 36-second video and a text walkthrough of the **different complex
source demo**. It is not a screenshot of these CLI outputs or a live-provider
result. This article reuses that media by reference; it invents no new capture.

## What this evidence does—and does not—show

The [replay record](article-evidence-196.md) documents these four outcomes from an
installed candidate, with network guards and metadata-only audit assertions.
The [package-review index](package-review-196.md) records broader source scope
and limitations; it is not a security clearance. [#188 live application/model
acceptance](https://github.com/revazi/django-asklens/issues/188) remains open.
No [#193 human sessions](https://github.com/revazi/django-asklens/issues/193) or
[#194 representative application](https://github.com/revazi/django-asklens/issues/194)
exists. There are no consented usability findings or external adoption results
to quote, and internal tests/AI roleplay would not substitute for them. This is
not a production-readiness, stability, endorsement or security-certification claim.

If you evaluate the integration later, useful feedback is a specific confusing
step or a minimal synthetic reproduction, with exact artifact/version and
expected versus actual behavior—not production rows or provider dumps. Use the
[contributor feedback routes](https://github.com/revazi/django-asklens/blob/main/CONTRIBUTING.md#feedback-and-triage); suspected
vulnerabilities go privately through the [security policy](https://github.com/revazi/django-asklens/security/policy).
Posting, contact and distribution remain unperformed and require separate
operator authorization.
