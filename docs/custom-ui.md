# Building a custom AskLens UI

AskLens does not require the packaged browser UI. Treat the packaged page as a demo shell around the public API. Production projects can build their own React, Vue, HTMX, Django-template, mobile, Slack, or internal dashboard UI and render AskLens results however they want.

## Endpoints to call

Mount the API routes:

```python
from django.urls import include, path

urlpatterns = [
    path("", include("django_asklens.api.urls")),
]
```

Then call the same permission-gated endpoints your UI needs:

```text
GET  /asklens/capabilities/
POST /asklens/query/
GET  /asklens/runs/<id>/
```

The endpoints use your normal Django/DRF authentication and the configured AskLens API permission classes. Resource visibility, field visibility, row scope, sensitive fields, and suggested examples are all scoped to the current request.

## Discover visible capabilities

Use capabilities to show the current user what they can ask about before they query anything:

```http
GET /asklens/capabilities/
Accept: application/json
```

The response is metadata only. It contains visible resources, their server-owned timezones, fields, metrics, date fields, supported query patterns, limitations, and example questions. It does **not** include database rows or sample values.

```json
{
  "summary": "You can ask read-only list and aggregate questions over 2 resources.",
  "resources": [
    {
      "name": "orders",
      "label": "Orders",
      "fields": [
        {"name": "status", "label": "Status", "can_group": true},
        {"name": "created_at", "label": "Created date", "can_date_bucket": true}
      ],
      "metrics": [
        {"name": "order_count", "label": "Orders", "result_type": "integer"}
      ],
      "examples": ["Show count of Orders by Status"]
    }
  ],
  "examples": ["Show count of Orders by Status"]
}
```

Common UI uses:

- show starter questions from `examples`
- display visible resources/fields in a help panel
- hide the query composer when no resources are visible
- explain why a user cannot ask about a field or resource

## Ask a question

Send natural-language questions to `/asklens/query/`:

```http
POST /asklens/query/
Content-Type: application/json

{"question": "Show orders by status"}
```

A data-query response includes `response_type: "query"`, normalized rows, column metadata, and result limit metadata:

```json
{
  "run_id": 42,
  "question": "Show orders by status",
  "response_type": "query",
  "plan": {"resource": "orders", "intent": "aggregate", "limit": 10},
  "columns": [
    {"key": "status", "label": "Status", "type": "string", "nullable": false},
    {
      "key": "order_count",
      "label": "Orders",
      "type": "integer",
      "nullable": false
    }
  ],
  "data": [
    {"status": "paid", "order_count": 120},
    {"status": "pending", "order_count": 34}
  ],
  "row_count": 2,
  "result_metadata": {
    "limit": 10,
    "limit_scope": "groups",
    "truncated": false
  },
  "duration_ms": 18,
  "visualization": {"type": "bar", "x": {"field": "status"}, "y": {"field": "order_count"}}
}
```

For grouped aggregate/chart responses, `result_metadata.limit` caps returned groups or slices. For list/table responses, it caps returned rows. If `result_metadata.truncated` is true, another matching row/group exists beyond the returned limit; show a message such as “Showing the first N results. Refine filters or increase the limit.” Ungrouped aggregates have effective limit one and are never truncated. AskLens does not provide cursor pagination.

Use each column's canonical `type` and `nullable` metadata rather than inferring types from the first row. Decimal values are strings to preserve precision. Empty ungrouped aggregates contain one row (`count=0`, other aggregate values `null`); empty grouped aggregates contain no rows.

Render tables by iterating `columns` for headers and `data` for row values:

```js
function renderTable(response) {
  const table = document.createElement("table");
  const thead = table.createTHead();
  const header = thead.insertRow();
  response.columns.forEach((column) => {
    const th = document.createElement("th");
    th.textContent = column.label || column.key;
    header.appendChild(th);
  });

  const tbody = table.createTBody();
  response.data.forEach((row) => {
    const tr = tbody.insertRow();
    response.columns.forEach((column) => {
      const td = tr.insertCell();
      td.textContent = row[column.key] ?? "";
    });
  });
  return table;
}
```

Render charts with any charting library by mapping `visualization.x.field` and `visualization.y.field` to values in `data`:

```js
function toBarSeries(response) {
  const x = response.visualization?.x?.field;
  const y = response.visualization?.y?.field;
  if (!x || !y) return null;
  return response.data.map((row) => ({
    label: row[x],
    value: row[y],
  }));
}
```

## Visualization is only a hint

`visualization` is a display hint, not a required renderer contract. Your UI can:

- ignore it and always render a table
- use it to choose a chart type
- replace it with your own chart rules
- request no visualization hint when you only need serialized data

```http
POST /asklens/query/
Content-Type: application/json

{"question": "Show orders by status", "include_visualization": false}
```

When `include_visualization` is false, the response still includes `columns`, `data`, `row_count`, and audit metadata.

## Handle help responses

Questions such as `show me example queries` or `what can I ask?` return `response_type: "capabilities"` and do not execute a database query:

```json
{
  "response_type": "capabilities",
  "query_help_source": "deterministic",
  "capabilities": {"summary": "You can ask read-only questions over 1 resource."},
  "query_help": {
    "answer": "Try these examples.",
    "suggestions": [
      {
        "question": "Show count of Orders by Status",
        "resource_name": "orders",
        "plan": {"resource": "orders", "intent": "aggregate"}
      }
    ]
  }
}
```

Your UI should branch on `response_type`:

```js
if (response.response_type === "capabilities") {
  renderSuggestions(response.query_help.suggestions);
} else {
  renderTable(response);
}
```

## Saving queries

A custom UI can save useful questions in local storage, bookmarks, a project-owned database table, or another application-owned model. AskLens does not ship a first-class server-side saved-query model in alpha. A saved item can store:

```json
{
  "question": "Show count of Orders by Status",
  "plan": {"resource": "orders", "intent": "aggregate"}
}
```

When replaying a saved suggestion, send both fields back to `/asklens/query/`:

```http
POST /asklens/query/
Content-Type: application/json

{
  "question": "Show count of Orders by Status",
  "plan": {"resource": "orders", "intent": "aggregate"}
}
```

The normal AskLens API revalidates submitted plans against the current request's permissions, resource catalog, field rules, and current plan limits before execution. Execution then resolves the resource's fail-closed scope policy: deliberately reviewed per-resource `global` scope or a trusted current-request `scope_provider` under `context_scoped`, which may be configured once as the safe project default. Missing or invalid scope rejects without falling back to the model manager. This applies to clicked suggestions, browser-saved plans, server-saved plans, and UI-edited plans with changed filters, date intervals, ordering, or limits. A saved plan is an optimization and UX convenience, not a permission bypass.

If you build server-side saved queries, keep them project-owned until AskLens grows a first-class saved-query model after alpha. Suggested fields are:

- owner/user or team
- title
- original question
- optional saved plan JSON
- created/updated timestamps
- last run id or last run summary

## Audit runs

For successful data queries and safe failures, AskLens writes `SemanticQueryRun` audit records. Retrieve one through:

```http
GET /asklens/runs/42/
```

Use this for “view previous run” screens or audit links. The run endpoint still checks whether the current user may view the run.

## Safety reminders for custom UIs

- Do not send database rows or sample values to LLM providers from your UI.
- Do not turn AskLens plans into SQL execution; AskLens is designed for validated Django ORM queries.
- Handle API failures through `error.code` and display only `error.message`. Unknown and unauthorized members intentionally share `asklens.member.unavailable`; do not attempt to infer hidden catalog membership.
- Do not trust saved plans from the browser; submit them back to AskLens for revalidation.
- Keep route permissions on the API even if the UI page has its own access gate.
