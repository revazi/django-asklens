# Building a custom AskLens UI

Use the [troubleshooting decision path](troubleshooting.md) to distinguish safe
caller recovery from privileged host diagnosis. Never explain protected-member
existence or turn a successful empty result into an access error.

## Minimal columns/data consumer

Start with the [installed-package quickstart](quickstart-app.md), then enable
the [session API recipe](usage.md#authenticated-normal-user-api-quickstart).
The **API extra is required** for both this custom browser consumer and the
packaged reference frontend. Native Django admin query/audit pages do not
require it. The HTTP/frontend shapes are [optional and provisional](compatibility.md),
not governed wire contracts.

The one minimal, framework-free consumer lives in the copied host application:

- [table template](https://github.com/revazi/django-asklens/blob/main/examples/quickstart/shop/templates/shop/table.html)
- [plain JavaScript renderer and request handler](https://github.com/revazi/django-asklens/blob/main/examples/quickstart/shop/static/shop/table.js)
- [host routes](https://github.com/revazi/django-asklens/blob/main/examples/quickstart/quickstart/api_urls.py)

These are new **source-only examples**, not files shipped inside immutable
public `0.3.2`. They consume existing published capabilities. They are neither
a dashboard/chart builder nor a production-ready UI product. Reuse/adapt this
small consumer in any host UI rather than copying the complex test project.

`quickstart.api_urls` mounts `/table/` behind Django `login_required`, Django's
host-owned `LoginView` at `/accounts/login/`, and `django_asklens.api.urls`.
Django supplies the CSRF token through `{% csrf_token %}`. The script POSTs
JSON with `credentials: "same-origin"`, `mode: "same-origin"`, and
`X-CSRFToken`; redirects are rejected rather than interpreted as data. It sends
only `question` and `include_presentation: false`, never a user, permission,
tenant, or scope claim. The API independently authenticates and revalidates the
current request; a protected HTML page is not a substitute for route permission
and trusted row scope. Exact dependencies/settings/authentication and executable
CSRF checks belong to the [API recipe](usage.md), not a second setup here.

The synthetic seed has no usable login passwords. Run the recipe tests for the
ready-to-execute path; a real host supplies its existing account lifecycle.
If trying the template in a local browser, first configure an authenticated
host account and static serving appropriate to that disposable host. The
example's `DEBUG=False` settings deliberately do not promise a `runserver`
static-file deployment. Never copy its local secret/settings into production.

### Render only the declared projection

For a successful `response_type: "query"`, the HTTP payload has one complete
`result` child:

```json
{
  "result": {
    "columns": [
      {"key": "product", "label": "Product", "type": "string", "nullable": false},
      {"key": "total_cents", "label": "Total (cents)", "type": "integer", "nullable": false}
    ],
    "data": [{"product": "North class", "total_cents": 2000}],
    "row_count": 1,
    "result_metadata": {"limit": 10, "limit_scope": "rows", "truncated": false}
  }
}
```

This abbreviated single-row shape illustrates rendering; the exact paid-order
fixture returns **two** rows as documented in the minimal quickstart. Do not
infer column names or types from the first row. The implementation:

1. Iterates `result.columns` for headers and cell lookup; ignores any other row
   keys. It uses canonical `type`/`nullable` metadata as the type contract, not
   JavaScript numeric inference. Decimal values remain strings (no precision
   loss); null/missing cells display `—`.
2. Creates DOM nodes and assigns `textContent` for labels and values. It never
   uses `innerHTML`, evaluates presentation metadata, creates returned links,
   or renders raw error bodies. Django autoescaping remains enabled.
3. Adds a table caption and `<th scope="col">`, a real form label, keyboard
   submit controls, `role="status"`/polite live status, and `aria-busy` during
   requests. The submit button is disabled during execution and restored on
   every outcome, keeping keyboard controls available for recovery.
4. Clears previous results **before every request and on failure**. Old rows
   must not remain visible after session expiry, permission revocation, or a
   malformed response.

The custom consumer intentionally ignores optional `presentation`. It does not
render charts or turn display hints into query policy.

### Empty, limited, help, and failure states

- `Show my paid orders` returns the current authorized owner's paid rows.
- `Show my refunded orders` returns `HTTP 200`, the same typed columns and
  `data: []`. Show “No matching rows in your current authorized scope,” not
  “no data exists” or “permission denied.” Empty grouped aggregates likewise
  have no rows; an empty ungrouped aggregate instead has one row (count zero,
  other values null).
- `result.result_metadata.truncated: true` means another matching row/group
  exists beyond the execution limit. Explain that the result is limited and
  invite a narrower question. This is **not pagination**; no cursor is provided.
- A help response has `response_type: "capabilities"` rather than `result`.
  This minimal UI asks for an exact configured data question instead. A richer
  host may safely render `help.content.suggestions` as text; replayed plans
  remain untrusted and must be revalidated on the current request.
- Unknown and unauthorized members both yield `asklens.member.unavailable`.
  Keep that opacity. Refresh the visible catalog or ask the host administrator
  to review access; never reveal protected fields, permissions, tenant
  existence, raw errors, or audit content to explain a denial.
- `401`/`403`: sign in again or request a host access review. An HTML CSRF or
  login response is not result JSON; never display its raw body.
- `429`: wait and follow the host retry policy/`Retry-After`. Do not loop retries
  automatically. A network error or unexpected response gets a fixed safe
  message, not `exception.message` or provider diagnostics. Use the exact
  configured dummy question or retry later; do not broaden scope.

Handled AskLens API failures use `{ "error": { "code": "asklens.…",
"message": "…" } }`, with an optional audit `run_id`. Do not look for legacy
`detail`, echoed question, or a result on failure. The renderer uses stable
codes/statuses and fixed UI recovery messages; it does not inspect or display
server diagnostics. Full provisional API and audit visibility rules remain in
the [usage guide](usage.md#4-query-through-the-optional-api).

## Discovery and host-owned extensions

Use `GET /asklens/catalog/` for current-request visible resources/fields and
`GET /asklens/capabilities/` for machine features/limits. Neither contains rows
or sample values. Keep both authenticated. Do not use catalog absence to
confirm that a hidden resource or tenant exists.

A host may save questions/plans in its own storage, but AskLens alpha does not
ship a saved-query model. Avoid persisting result rows, provider bodies, or
sensitive questions by default. Submit saved/provider/client-produced plans
back to AskLens for current permission, scope, and budget validation. Audit
records are not a result cache and must not be used as an access workaround.

## Verification and evidence limits

The API recipe exercises real Django login/session/CSRF and installed candidate
bytes with a disposable database. The standalone Chromium check uses the actual
template/script with **synthetic intercepted HTTP responses** to check safe DOM
rendering (including HTML-like values), empty/error/recovery/loading states,
keyboard submission, and request credentials/CSRF shape:

```bash
uv run --no-sync playwright install chromium
uv run --no-sync python tests/e2e/quickstart_table.py
```

That default mode is a browser DOM regression, **not** installed-artifact or
production wire acceptance. To additionally exercise the actual copied host
and installed candidate API over local HTTP, reuse the same installer after
building the wheel (the separate dev interpreter supplies only Playwright):

```bash
uv run --no-sync python -m build --wheel
ASKLENS_ADAPTER_SMOKE=1 ASKLENS_BROWSER_PYTHON="$PWD/.venv/bin/python" \
  uv run --no-sync bash .github/scripts/wheel-smoke.sh api 'Django>=5.2,<5.3' '5.2.'
```

The optional `shop.browser_recipe` uses Django's disposable static live test
server in the isolated API-wheel environment. Chromium submits the real host
login form, loads the actual static script, demonstrates scoped table/empty/
opaque-denied states, and verifies authenticated requests without CSRF fail.
The browser driver imports no AskLens checkout; the server retains the wheel
byte/import checks and outbound-network block, and browser traffic is limited
to that owned local server. Test-only credentials and response bodies are not
printed. No live LLM or external account is involved. This is **local synthetic
HTTP evidence**, not production wire acceptance. Neither browser mode proves
independent adoption, production readiness, or security certification.
