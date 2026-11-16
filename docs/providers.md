# Provider configuration

AskLens treats provider output as untrusted data. A provider returns an envelope containing an executable `query_plan` and optional separate `presentation`; AskLens validates the plan before compilation or execution. Presentation metadata cannot alter authorization, scope, compilation, ordering, limits, or returned values. Metric requests contain only a registered semantic name; providers never choose or receive the operation, private Django binding, distinct key, or permission token.

## Default backend: dummy

The default backend is deterministic and local:

```python
DJANGO_ASKLENS = {
    "LLM_BACKEND": "dummy",
    "DUMMY_PLANS": {
        "Show orders by status": {
            "query_plan": {
                "resource": "orders",
                "intent": "aggregate",
                "group_by": [{"field": "status"}],
                "metrics": [{"metric": "order_count"}],
                "limit": 100,
            },
            "presentation": {
                "kind": "bar",
                "x": "status",
                "y": "order_count",
            },
        }
    },
    "DUMMY_DEFAULT_PLAN": None,
}
```

`DummyProvider` makes no network calls and requires no API keys. It matches the
question string exactly; unless `DUMMY_DEFAULT_PLAN` is explicitly configured,
arbitrary rewordings fail safely rather than being interpreted as natural
language. Tests and evaluation fixtures should use it by default. To try the
existing synthetic source demo with reviewed success, empty, denial, and error
paths, follow [Example Django AskLens integration](test-project-demo.md#sqlite-frontend-and-admin-first-run-start-to-reset).

For exact-question mismatches, malformed plans and provider failures, use the
[troubleshooting decision path](troubleshooting.md#dummy-mismatch-versus-malformed-plan-versus-provider-failure).
The public provider error does not reveal private questions or provider causes;
do not enable provider I/O logging merely to complete onboarding.

## One OpenAI onboarding path — UNVERIFIED

**Actual live acceptance is INCOMPLETE.** No provider API call or billed test was
performed for this change. Public documentation and deterministic mocks are not
live transport evidence, model-quality evidence, or production acceptance.

The existing stdlib HTTP backend is reused; no provider SDK is required. This
path pins the dated snapshot of the previously documented GPT-4.1 mini model:

```python
import os

DJANGO_ASKLENS = {
    "LLM_BACKEND": "openai_compatible",
    "LLM_BASE_URL": "https://api.openai.com/v1",
    "LLM_API_KEY": os.environ["OPENAI_API_KEY"],
    "LLM_MODEL": "gpt-4.1-mini-2025-04-14",
    "LLM_TIMEOUT_SECONDS": 30,
    "LLM_TEMPERATURE": 0,
    "LOG_LLM_IO": False,
    "AUDIT_INCLUDE_CONTENT": False,
}
```

Supply keys through an approved secret manager or protected process environment,
not command-line values, committed files, examples, logs, tickets, or test
fixtures. The example reads the key only when the host loads these settings;
never use real keys in offline tests. Use a clean standalone interpreter for the
probe below, not `manage.py`, a host shell, or a wrapper that bootstraps Django.

### Public configuration evidence (checked 2026-11-16)

- OpenAI's [GPT-4.1 mini model reference](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
  lists the `gpt-4.1-mini-2025-04-14` snapshot, Chat Completions
  (`/v1/chat/completions`), and Structured Outputs support. This is support for
  the stated API features, not an evaluation of AskLens or of model quality.
- **Deprecation warning:** OpenAI's [deprecations reference](https://developers.openai.com/api/docs/deprecations)
  lists this snapshot as deprecated on **2026-10-14**, with shutdown on
  **2027-01-14**. This bounded recipe retains and pins the existing documented
  model family, not a long-term recommendation. Recheck the public availability
  before seeking live authorization; after shutdown this recipe cannot pass.
  A replacement needs its own verified configuration and acceptance, not a
  silent model substitution.
- The [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)
  documents `response_format.type="json_schema"` with `strict: true`, its
  supported JSON Schema subset, all properties required (nullable unions for
  optional values), and `additionalProperties: false` for every object.
  JSON mode (`json_object`), function calling alone, and merely returning JSON
  are not equivalent. An OpenAI-compatible URL does **not** establish these
  features; other compatible services, including the previously illustrated
  Gemini endpoint, are not validated onboarding paths here.

### Offline strict-schema gate resolved; live acceptance still incomplete

The source/candidate OpenAI-compatible boundary now copies the requested schema
into a strict wire representation: every declared object property is required,
originally optional non-nullable properties gain a nullable union, and Pydantic
`default` annotations are removed from the wire copy. Local references are
retained. Objects must already have `additionalProperties: false`; open maps
are rejected before transport, never closed by deleting meaningful keys.
This is a narrow adaptation of the schemas AskLens actually emits, not a general
JSON Schema compiler or a guarantee for arbitrary compatible services/models.

The reproduced mismatch is precise:

| Emitted application schema | Properties previously outside `required` |
| --- | --- |
| Planner envelope | `presentation` |
| Planner `QueryPlan` / compact unified `query_plan` | `filters`, `group_by`, `metrics`, `select`, `order_by`, `limit` |
| Planner `GroupBySpec` / compact unified grouping item | `date_trunc` |
| Planner `OrderBySpec` / compact unified ordering item | `field`, `metric`, `direction` |
| Planner `PresentationSpec` | `kind`, `x`, `y` |
| Compact unified envelope | `query_plan`, `presentation`, `query_help` |
| Compact unified presentation | `x`, `y` |
| Compact unified help / suggestion item | `suggestions`, `notes` / `fields`, `metrics`, `date_fields`, `why` |

**Correction to the earlier gate description:** these actual emitted schemas
already close every object. Open maps occur in the unused full
`AskLensProviderResponse.model_json_schema()` (raw plan/suggestion-plan fields),
not the compact unified request. Standalone help removes the suggestion-plan
property before emission; its optional fields and the intent schema receive
the same boundary adaptation.

On return, only null markers introduced for originally non-nullable optional
properties become omissions. An originally nullable null remains a value.
False, zero, empty strings/collections, explicit limits, filter values, order,
help references and meaningful inactive branches are not discarded. In
particular, a null limit marker leaves the limit **unset**, so the current host
default applies; an explicit limit is retained and budget-checked. These wire
markers do not make null a new valid value in an application QueryPlan. Unknown
keys and invalid required values remain available for normal rejection. The
existing application parsers, catalog/permission checks and trusted execution
facade still validate all provider output; strict mode remains enabled, with no
permissive fallback. Dummy/custom providers and application schema accessors
are unchanged. See the [compatibility boundary](compatibility.md).

Deterministic synthetic-credential tests inspect the actual mocked transport
request and validate synthetic responses against its adapted schema, then test
normalization and existing application validation/execution. This resolves only
issue #188's **offline required/closed-object schema gate**. It is not provider
wire acceptance, model-quality evidence or production readiness. The tiny
preflight below still cannot establish full application-schema acceptance.
Actual authorized application-provider acceptance and the pinned snapshot's
lifecycle/model-selection gates remain unresolved; **#188 stays open**. Do not
disable strict mode or weaken validation if a later authorized call is rejected.

### Limits and retry semantics

| Path | Request/concurrency bound | Timeout and retries |
| --- | --- | --- |
| Standalone synthetic preflight | At most **one** POST per invocation, one choice, serial, `max_completion_tokens=32`; reads at most 16 KiB + 1 byte | Default 30 seconds; explicitly configurable from 1 to 30 finite seconds; no retries, redirects, failover, proxies, cookies or SDK |
| Opt-in tests below | At most **seven** POSTs per serial pytest session and **one** per test; `max_completion_tokens=2048` | 30 seconds per call; no retries, redirects, proxy inheritance or failover; parallel workers rejected |
| Normal application provider | One initial POST per `complete_json()` invocation; stdlib redirects may add requests; no package-wide request, concurrency or financial limit | Configured `LLM_TIMEOUT_SECONDS` (example: 30); no AskLens automatic retries or failover; stdlib default redirect/proxy behavior is unchanged |

The timeout is a stdlib network/socket-operation timeout, **not a guaranteed
wall-clock deadline** (DNS, connect phases and slow reads can extend elapsed
time). The preflight also bounds response bytes, not just output tokens. A token
or request cap is **not a guaranteed financial cap**. Repeated processes/runs can
incur additional charges. The application does not add this probe's token or
response-byte caps to normal queries. Host retries, parallelism and financial
controls require separate operator policy; there is no invented spending limit.

## Standalone fixed-synthetic preflight

This is a new **source/candidate** module, not part of immutable public `0.3.2`
artifacts. From this checkout (or a wheel built from it), the default is offline:

```bash
uv run python -m django_asklens.provider_preflight
```

It prints a prior network/charge disclosure and
`{"code": "consent_required", "status": "not_passed"}` (exit 2). It does not
read any key without the explicit flag. `--help` is also offline. Neither an
ambient `OPENAI_API_KEY`, Django provider settings nor live-test flags grant
consent. Unsupported options, invalid/absent keys and nonfinite/out-of-range
timeouts fail safely before transport; supplied values are never echoed.

**Only after separate operator authorization for network use and possible
charges**, supply `DJANGO_ASKLENS_PREFLIGHT_API_KEY` through the approved secret
source and run this deliberately opted-in command. No live request is authorized
by this guide or by issue creation:

```bash
uv run python -m django_asklens.provider_preflight --allow-network-and-charges
```

Optional `--timeout-seconds 10` lowers the socket-operation timeout. Endpoint,
model, prompt and schema overrides are deliberately unavailable. The only user
message is the fixed synthetic request `Return {"probe":"ok"}.`; the strict
schema is a closed object with the single required enum property `probe="ok"`.
There is no application question, catalog/guidance, registry inspection, row
sample, permission resolution, scope callback, audit write or application SQL.

The module imports package/provider definitions (including creation of the
package's empty default-registry object); it **does not read or populate that
registry**, load Django settings, call `django.setup()`, or import host apps.
It composes the existing stdlib provider's request builder and JSON parsers,
not `complete_json()` or its settings-backed provider-I/O logger. The isolated
transport never reads HTTP error bodies, follows redirects or uses ambient
proxies/global installed openers. There are no content logs or artifact files.
An arbitrary Python startup hook, interpreter wrapper, malicious local package,
or a host that calls this function after its own startup is outside this
standalone guarantee; use a clean process. This is not a privileged Django
management command and does not change counts-only `check_asklens`.

Exit 0 means **synthetic exchange only**. Output records fixed non-sensitive
configured provider, endpoint and snapshot (not server-attested model identity),
UTC observation time, timeout, temperature,
request/concurrency/token bounds and zero retries, with application acceptance
still `incomplete`. This metadata can be retained for a later **authorized** live
observation; never retain payloads, authorization, URLs with secrets or raw
exceptions. Exit 2 returns only a fixed failure category, not provider advice:

| Category | Private operator action; no automatic retry |
| --- | --- |
| `consent_required` | Obtain separate authorization before opting in. |
| `invalid_arguments` / `invalid_configuration` | Review the supported flag, finite timeout and dedicated protected key source; no transport occurred. |
| `schema_or_request_rejected` | HTTP 400/422 can indicate schema **or another request** rejection; it is not proof of which one. Review documented strict support privately. |
| `authentication_rejected` | HTTP 401/403; privately check key validity/access without echoing it. |
| `timed_out` / `network_failed` | Review approved connectivity/timeout policy; do not add blind retries. |
| `rate_limited` | HTTP 429; respect provider policy and obtain approval before another invocation. |
| `redirect_rejected` | Do not forward credentials to a different endpoint. |
| `invalid_output` | Refusal, truncation, oversized/malformed content or a mismatched synthetic object; no compatibility acceptance. |
| `provider_failed` / `probe_failed` / `interrupted` | Stop and investigate through approved private operations; no raw provider exception is emitted. |

Do not enable `LOG_LLM_IO` to complete onboarding. For ordinary application
calls that opt-in setting logs request URLs/bodies, provider response/error
bodies and parsed content. Even though authorization headers are filtered,
URLs with secret parameters and arbitrary provider-echoed secrets can leak.
The probe avoids this logger entirely, even when host logging is enabled.

## Provider interface

Providers implement the `LLMProvider` protocol:

```python
class LLMProvider(Protocol):
    def complete_json(
        self, *, messages: Sequence[LLMMessage], schema: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...
```

AskLens sends:

- permission-scoped provider guidance derived from safe catalog metadata and machine capabilities,
- the user's question,
- a strict JSON schema for the response being requested.

AskLens must not send sample database rows, secrets, credentials, `.env` content, or unregistered/unauthorized sensitive fields by default.

## Prompt-size optimization

Live `/asklens/query/` calls use internal permission-scoped query guidance for
provider prompts. This guidance is derived from the separate catalog and
machine capability facts; it is not the public machine capability document. By
default, AskLens sends all visible resources in a compact provider-facing shape
so the provider can choose among the user's full allowed catalog. Compact
resource metadata retains the server-owned timezone, and compact field metadata
retains canonical type, nullability, supported operators, and explicitly
registered enum values/aliases; it still omits Django bindings, model labels,
permission tokens, and database values. The provider cannot override the
resource timezone in a plan.

Resource shortlisting is available as an opt-in prompt-size optimization for larger catalogs. When enabled, likely data questions send only the top matching visible resources before the provider call. This can reduce prompt size and cost, but it is not an authorization decision: every returned plan is still validated against the full catalog, request permissions, and limits before execution.

Explicit help questions such as `show me example queries` keep full visible
provider guidance so users can discover everything available to them. Human
examples and guidance never become fields in the machine capability document.

The alpha default is `0`, which disables resource shortlisting:

```python
DJANGO_ASKLENS = {
    "PROMPT_RESOURCE_SHORTLIST_LIMIT": 0,
}
```

To opt into data-question resource shortlisting, set a positive value such as `4` after validating representative questions against your catalog.

## Testing live providers — separate authorization required

Default tests/diagnostics/CI stay offline, require no keys and do not run the
probe. The existing two opt-in evaluation modules now require **both**
`DJANGO_ASKLENS_LIVE_LLM=1` and
`DJANGO_ASKLENS_LIVE_LLM_CONSENT=network-and-charges`. Enabling just one flag
cannot invoke their transport. They are not the no-bootstrap synthetic probe:
they start the repository test Django app, create synthetic database fixtures,
send fixed test questions and permission-scoped synthetic guidance, execute
validated plans and test tenant denial/audit behavior. Never substitute a real
host settings module, catalog, rows or user questions.

**UNVERIFIED / actual live acceptance INCOMPLETE.** No live evaluation was run
for this change. Only the offline schema gate above is resolved; actual
application-provider acceptance and lifecycle/model-selection gates remain open.
Only after separate network/charge authorization, supply the protected
`DJANGO_ASKLENS_LIVE_LLM_API_KEY` variable and run serially, with no xdist,
`--showlocals`, content logging, recording/capture plugins or payload artifacts:

```bash
DJANGO_ASKLENS_LIVE_LLM=1 \
DJANGO_ASKLENS_LIVE_LLM_CONSENT=network-and-charges \
uv run pytest --tb=no -q tests/evaluation/test_live_openai_compatible.py \
  tests/evaluation/test_live_api_openai_compatible.py
```

Endpoint and model default to the exact fixed configuration above. If explicitly
supplied, `DJANGO_ASKLENS_LIVE_LLM_BASE_URL` and
`DJANGO_ASKLENS_LIVE_LLM_MODEL` must match it; missing/invalid configuration skips
without transport. The shared fixture disables provider I/O logging, checks
consent again at transport, enforces one request/test and seven/session, rejects
concurrent calls/parallel workers, and isolates redirects/proxies. Multiple
sessions are not a global quota. Existing parsing, catalog, permission, trusted
fail-closed scope and structural-budget validation remain mandatory; every data
plan still converges on `execute_plan()`. The probe grants none of these rights.

If an authorized result is obtained later, record exact non-sensitive provider,
snapshot, endpoint, temperature, timeout, request/token/concurrency configuration,
UTC observation date, test selection, pass/fail category and actual request
count. Never record credentials, request/response payloads, raw exceptions or
secret-bearing URLs. A synthetic result is not application authorization,
audit readiness, full-schema support, reliability, production readiness, or a
substitute for that later application acceptance. Leave #188's live-evidence
gate open until resolved by the owner.

The source demo's separate `DJANGO_ASKLENS_DEMO_LIVE_LLM=1` path is not this
probe or its bounded test harness; do not enable it during offline onboarding.

## Safety notes

- Provider output is untrusted.
- QueryPlan validation remains mandatory.
- Never execute provider-generated SQL.
- Do not send sample rows to providers by default.
- Keep provider I/O logging off; authorization filtering alone cannot sanitize arbitrary URLs or provider bodies.
