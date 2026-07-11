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

The response is metadata only. It contains visible resources, fields, metrics, date fields, supported query patterns, limitations, and example questions. It does **not** include database rows or sample values.

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
        {"name": "order_count", "label": "Orders", "op": "count", "field": "id"}
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

A data-query response includes normalized rows and column metadata:

```json
{
  "run_id": 42,
  "question": "Show orders by status",
  "plan": {"resource": "orders", "intent": "aggregate"},
  "columns": [
    {"key": "status", "label": "Status", "type": "string"},
    {"key": "order_count", "label": "Orders", "type": "number"}
  ],
  "data": [
    {"status": "paid", "order_count": 120},
    {"status": "pending", "order_count": 34}
  ],
  "row_count": 2,
  "duration_ms": 18,
  "visualization": {"type": "bar", "x": {"field": "status"}, "y": {"field": "order_count"}}
}
```

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

A custom UI can save useful questions in a database, local storage, bookmarks, or a project-owned saved-query model. A saved item can store:

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

AskLens always revalidates submitted plans against the current request's permissions, resource catalog, field rules, limits, and row scope before execution. A saved plan is an optimization and UX convenience, not a permission bypass.

If you build server-side saved queries, keep them project-owned until AskLens grows a first-class saved-query model. Suggested fields are:

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
- Do not build a raw SQL mode around AskLens plans.
- Do not hide API errors that indicate permission or validation failures.
- Do not trust saved plans from the browser; submit them back to AskLens for revalidation.
- Keep route permissions on the API even if the UI page has its own access gate.
