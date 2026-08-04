# Private Candidate Pilot Intake Worksheet

**Status:** Blank Evaluation Template

This worksheet is a privacy-safe structural template for private candidate evaluation. Evaluators and maintainers use this format to record scope, expectations, and evaluation outcomes outside of this repository.

> **Privacy Warning:** Do not commit completed forms, real metrics, real question corpora, or any application-specific details to Git, GitHub PRs, or public issues. Store completed worksheets in participant- or maintainer-approved private storage only.
>
> **Never include:** participant names, application names, exact schema/model/binding paths, database rows or sample values, questions containing private facts, tenant or user identifiers, permission strings, credentials, secrets, `.env` files, scope-provider code, full sensitive plan or filter values, provider payloads, provider logs, or full audit content.

---

## 1. Environment & Compatibility

Record safe participant-class and major-version data only.

- **Participant Class:** (e.g., SYNTHETIC_B2B_SaaS, SYNTHETIC_INTERNAL_TOOL)
- **Python Version:** (e.g., 3.12, 3.13)
- **Django Version:** (e.g., 5.2, 6.0)
- **Database Engine & Major Version:** (e.g., PostgreSQL 15, PostgreSQL 18; SQLite is acceptable only for fast compatibility testing, not primary pilot/evaluation data)
- **Primary AskLens Surface:** (e.g., Python Facade, API, MCP)

---

## 2. Public Semantic Registration Inventory

List the explicitly registered semantic resources, fields, and metrics.

> **Prohibited:** Django model labels, ORM paths, private bindings, QuerySets, scope-provider code, permission-token formats, actual tenant/user IDs, and exact system clocks.

**Resource 1:** `SYNTHETIC_RESOURCE_NAME`
- **Scope Mode:** `context_scoped` | `global`
- **Semantic Fields:**
  - `synthetic_field_1` (Type, Nullable)
  - `synthetic_field_2` (Type, Nullable)
- **Semantic Metrics:**
  - `synthetic_metric_1` (Type, distinctness/cardinality rules)
  - `synthetic_metric_2` (Type, distinctness/cardinality rules)
- **Timezone Configuration:** (e.g., `UTC`, `America/New_York`)

*(Duplicate for additional resources)*

---

## 3. High-Level Permission & Scope Rules

Define the expected security boundaries structurally. Do not include actual permission strings or tenant identifiers.

- **Role/Membership Condition:** (e.g., "Request user must have synthetic role A to access resource B")
- **Tenant Isolation:** (e.g., "Results strictly bounded to the synthetic tenant associated with the request context")
- **Allowed Expectations:** (e.g., "Role A can aggregate synthetic metric 1")
- **Denial Expectations:** (e.g., "Role C receives empty sets or authorization errors for resource B")

---

## 4. Question Cases & Expectations

Prepare at least 25 de-identified query scenarios covering expected usage and edge cases. Keep this corpus in private external storage.

For each case, record the intent, shape, and outcome structurally (avoiding rows or sensitive values):

1. **Question:** "List recent synthetic events."
   - **Intent/Mode:** `list`
   - **Expected Status:** Supported
   - **Expected Shape/Count:** Up to N items, matching standard structural limits.
2. **Question:** "Total amount per synthetic category."
   - **Intent/Mode:** `aggregate`
   - **Expected Status:** Supported
   - **Expected Shape/Count:** N categories, scalar outputs.
3. **Question:** "Cross-reference synthetic resource A with resource B."
   - **Intent/Mode:** Cross-resource
   - **Expected Status:** Unsupported (No executable single-resource plan; planner/client classifies unsupported.)
   - **Expected Result:** If malformed transport input is later submitted, record its actual safe stable error separately.

*(Continue to at least 25 structured synthetic cases)*

---

## 5. Adversarial & Boundary Testing

Verify fail-closed behavior across these structural categories. Record the expected result/error and confirm zero-application-query expectations where applicable.

- **Cross-Scope Attempt:** Requesting synthetic tenant B's data using the exact same otherwise-valid plan under synthetic tenant A's server-owned context. Expected: A correctly scoped application-data query may execute, using the server-owned scoped QuerySet, and evidence must prove no out-of-scope rows or aggregate influence from tenant B.
- **Hidden/Filter-Only/Result-Excluded/Unknown Member:** Requesting a filter, metric, or field not in the public semantic catalog or deliberately omitted. Expected: `asklens.member.unavailable`; zero application-data SQL.
- **Client-Supplied Policy Claims:** Attempting to pass tenant IDs, permission tokens, or scope claims in the query payload. Expected: This never changes trusted identity/permissions/tenant/scope. Strict extra plan keys may cause `asklens.parse.invalid` and unavailable semantic members `asklens.member.unavailable`; record actual stable error. Zero application-data SQL.
- **Missing Context:** Executing a `context_scoped` resource query without a request context. Expected: `asklens.scope.unavailable`; zero application-data SQL.
- **Structural Budget Exceeded:** Requesting limits above `MAX_ROWS`. Expected: Hard rejection `asklens.budget.exceeded` before application-data SQL (truncation applies only within an accepted limit).
- **MCP Row-Return Default:** Returning rows via MCP without explicit host + request opt-in. Expected: Returned query data/rows are omitted unless host+request opt in; execution/result metadata may remain. Validation/budgets/execution/audit still run and omission is not a query-cost control.
- **Provider Metadata Boundary:** Inspect the permission-scoped catalog and pre-provider request, requiring private metadata never be included or transmitted. Expected: Stop and report before provider transmission if inspection detects bindings, model labels, QuerySets, scope, or tenant IDs.

---

## 6. Audit, Log, & Provider Data-Handling

Define the data-handling policy for the evaluation environment.

- **Audit Policy Mode:** (e.g., database, disabled, custom)
- **Storage Owner:** (e.g., Participant-owned private audit store/database)
- **Retention & Deletion Policy:** (e.g., Ephemeral session only, wiped daily)
- **Prohibited Artifacts:** Full result rows in logs, provider responses stored in application traces, actual `.env` secrets in telemetry.

---

## 7. Integration & Effort Metrics

Record the operational effort required to stand up the evaluation environment.

- **Provider/Client Planning Mode:** (e.g., explicit MCP integration, direct Python execution)
- **Initial Smoke Test:** Confirmed provider-off initial execution (deterministic local testing without live AI).
- **Time to Integration:** (e.g., Hours to configure ASGI and sync models)
- **Time to First Correctly Scoped Query:** (e.g., Minutes/Hours from setup)
- **Maintainer Intervention Required:** (Yes/No, with structural reasons)
- **Registration Effort:** (e.g., Approximate time to register the synthetic inventory)
- **Baseline Custom-Report Effort:** (e.g., Estimated hours it would normally take to manually code the same 25 cases as Django API endpoints)
