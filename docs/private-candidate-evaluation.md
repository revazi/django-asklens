# Private candidate evaluation and onboarding

This guide is for a maintainer-invited, private technical evaluation of an exact Django AskLens source-built wheel. It does not require or imply a public PyPI release. It is not a normal `0.1.0a1` to `0.2.0a*` upgrade, a pilot result, beta-readiness evidence, or production approval.

Use only a maintainer-supplied candidate manifest that binds all three of these values:

- an immutable 40-character Git commit;
- the source-built wheel filename;
- the wheel's SHA-256 digest.

The current repository and wheel still report version `0.1.0a1`. Use a clean evaluation environment so pip cannot silently retain or confuse the published same-version package. The existing [source-checkout package smoke](installation.md#source-checkout-alpha-candidate-package-evidence) proves exact same-version replacement only; it is not a resolver-selected upgrade.

## Evaluation boundary

Run the evaluation in participant-owned, isolated staging with a disposable or restorable PostgreSQL database containing only synthetic or properly de-identified data. Do not connect this candidate to production data or a shared production database. Keep live providers off until a separate provider evaluation is approved.

Current package metadata supports Python 3.12+ and Django 5.2 LTS or Django 6.x. The broad compatibility matrix currently exercises Python 3.12/3.13 and Django 5.2/6.x on SQLite. PostgreSQL semantic/conformance CI is narrower: Python 3.13 with Django 6.x on PostgreSQL 15 and 18. The PostgreSQL 18 reference app also has separate browser/API/MCP smoke evidence. Record the exact evaluation combination and this limitation rather than implying that every Python/Django/PostgreSQL combination has been tested together.

The optional Django REST Framework API and FastMCP integrations are installed only when they are part of the agreed evaluation.

Before starting, assign an evaluation owner and record where the staging environment, candidate manifest, dependency lock, database snapshot, and rollback instructions are held. Keep completed evaluation forms and evidence outside this repository.

## 1. Verify candidate provenance before installation

Obtain the commit, wheel, and checksum through the maintainer-approved channel. Set local values without pasting participant or environment identifiers into a shell history shared with others:

```bash
export ASKLENS_CANDIDATE_COMMIT='<40-character commit>'
export ASKLENS_CANDIDATE_WHEEL='/absolute/path/django_asklens-0.1.0a1-py3-none-any.whl'
export ASKLENS_CANDIDATE_SHA256='<64-character lowercase SHA-256>'
```

Verify the commit in a clean source checkout and require an exact immutable match:

```bash
git fetch origin "$ASKLENS_CANDIDATE_COMMIT"
test "$(git rev-parse "$ASKLENS_CANDIDATE_COMMIT^{commit}")" = \
  "$ASKLENS_CANDIDATE_COMMIT"
git switch --detach "$ASKLENS_CANDIDATE_COMMIT"
test "$(git rev-parse HEAD)" = "$ASKLENS_CANDIDATE_COMMIT"
test -z "$(git status --porcelain --untracked-files=no)"
```

Stop if the commit differs, the tracked checkout is dirty, or the wheel/checksum does not match the maintainer-supplied manifest. Verify the wheel bytes and package metadata without installing it:

```bash
python - "$ASKLENS_CANDIDATE_WHEEL" "$ASKLENS_CANDIDATE_SHA256" <<'PY'
from email.parser import Parser
from hashlib import sha256
from pathlib import Path
import hmac
import sys
import zipfile

wheel = Path(sys.argv[1]).resolve()
expected = sys.argv[2]
if len(expected) != 64 or expected.lower() != expected:
    raise SystemExit("Expected one lowercase SHA-256 digest")
actual = sha256(wheel.read_bytes()).hexdigest()
if not hmac.compare_digest(actual, expected):
    raise SystemExit(f"Candidate checksum mismatch: {actual}")

with zipfile.ZipFile(wheel) as archive:
    metadata_names = [
        name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
    ]
    if len(metadata_names) != 1:
        raise SystemExit("Expected exactly one wheel METADATA file")
    metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
if metadata["Name"] != "django-asklens" or metadata["Version"] != "0.1.0a1":
    raise SystemExit("Unexpected candidate name or unchanged source version")
print(f"Verified {wheel.name} sha256={actual}")
PY
```

A matching checksum proves that the evaluated bytes match the candidate manifest. It is not a reproducible-build claim or an independent security signature. Retain the manifest and checksum outside the repository with the evaluation record.

## 2. Create an isolated environment and install one surface

Create a fresh virtual environment. Install dependencies from the participant's approved package index or wheelhouse; the candidate itself is always the verified local wheel and is not resolved from PyPI.

Select an approved Python 3.12 or 3.13 interpreter and confirm its version before creating the environment. In this example, `python3` must resolve to that approved interpreter:

```bash
python3 --version
python3 -m venv .venv-asklens-evaluation
. .venv-asklens-evaluation/bin/activate
python -m pip install --upgrade pip
```

Install only the surface under evaluation:

```bash
# Core only:
python -m pip install "$ASKLENS_CANDIDATE_WHEEL"

# Or core plus the optional DRF API/frontend:
python -m pip install "${ASKLENS_CANDIDATE_WHEEL}[api]"

# Or core plus the optional FastMCP bridge:
python -m pip install "${ASKLENS_CANDIDATE_WHEEL}[mcp]"

# Or both optional surfaces when both are in the agreed evaluation:
python -m pip install "${ASKLENS_CANDIDATE_WHEEL}[api,mcp]"
```

Use only one of those commands in a fresh environment. If an approved index is unavailable, stop rather than substituting an unverified `django-asklens` package. Confirm the installed distribution and supported framework versions:

```bash
python - <<'PY'
from importlib.metadata import version

import django

print("django-asklens", version("django-asklens"))
print("Django", django.get_version())
PY
```

Seeing `django-asklens 0.1.0a1` is expected for this private candidate. It is not evidence that pip performed an upgrade from the published alpha.

## 3. Prepare participant-owned staging

Use a dedicated PostgreSQL 15 or 18 database that can be recreated or restored. Keep database administration/migration credentials separate from the runtime query role.

Before installing into the staging application:

1. Record Python, Django, PostgreSQL major version, selected core/API/MCP surface, candidate commit, wheel filename, and checksum.
2. Take the participant's normal disposable-database snapshot or confirm recreation steps.
3. Pin the application dependency lock so rollback restores the complete prior environment, not only AskLens.
4. Use synthetic or de-identified records and confirm provider/log/audit pipelines cannot export sensitive content.
5. Configure a statement timeout on the actual PostgreSQL role/connection, a coordinated ASGI/WSGI or proxy request timeout, authenticated-principal rate limits, and a bounded concurrency limit.
6. Prefer a runtime database role that can read only the intended schemas/tables. Run migrations with a separate deployment role. Because database audit mode writes an AskLens-owned row, use an approved custom/separately routed audit sink when the query role is strictly read-only; never grant application-data writes merely to make auditing work.

See the [production checklist](production-checklist.md) for host controls and the [multi-tenant security guide](multitenancy-security.md) for request-owned scope requirements. The repository Compose app is synthetic test evidence, not the participant's staging topology or credential pattern.

## 4. Configure safe defaults and migrate

Keep planning deterministic and offline for the initial technical smoke:

```python
DJANGO_ASKLENS = {
    # Optional project default; every global resource remains explicit.
    "DEFAULT_SCOPE_MODE": "context_scoped",
    "LLM_BACKEND": "dummy",
    "LOG_LLM_IO": False,
    "ALLOW_RAW_SQL": False,
    "SEND_SAMPLE_ROWS_TO_LLM": False,
    "MCP_ALLOW_ROW_RETURN": False,
    "AUDIT_INCLUDE_CONTENT": False,
    # Choose database, disabled, or an approved custom sink deliberately.
    "AUDIT_MODE": "custom",
    "AUDIT_SINK": "project.audit.write_safe_asklens_event",
}
```

Do not copy that custom sink path unless the participant owns an equivalent implementation. Database or disabled mode may be more appropriate for an isolated smoke. Review the complete [installation settings](installation.md#minimal-settings), set conservative structural budgets, and leave provider credentials unset.

Run migration planning, migrations, and Django's system check using the staging project's normal settings:

```bash
python manage.py showmigrations asklens
python manage.py migrate --plan
python manage.py migrate
python manage.py check
```

Register one deliberately narrow resource in participant-owned application code by following the [registration guide](registration.md) and [core execution guide](core-python-api.md). Every field needs a public semantic key plus private binding/type/nullability. Every resource needs an explicit IANA timezone and an effective `global` or `context_scoped` policy. Context scope requires a server-owned `scope_provider(request)` that returns a lazy queryset for the registered model; global scope must be an explicit per-resource review.

Trusted identity, permissions, tenant identifiers, QuerySets, private bindings, scope providers, audit policy, and injected clocks belong only in participant-owned server configuration/code. Never put them in candidate manifests, portable fixtures, intake templates, prompts, or evaluation evidence.

## 5. Run a bounded technical smoke

Define expected outcomes before execution, then use the participant application's normal test command to prove all agreed paths. Keep live providers disabled and do not print or attach returned rows.

Minimum smoke:

- catalog/capabilities are accessible only to an authorized synthetic/de-identified user and omit private bindings, model labels, permission formats, tenant identifiers, QuerySets, and scope implementation;
- one supported list or aggregate plan executes through the public trusted facade for the current request and returns only the expected scoped row count/column types;
- the same plan cannot cross to a second synthetic/de-identified scope;
- missing scope, hidden field, unknown member, client-supplied policy/tenant input, and one over-budget plan fail safely before application-data SQL;
- audit remains metadata-only, or the approved custom/disabled mode behaves as configured;
- optional API/MCP paths are exercised only if their extras are in scope; MCP identity remains server-owned and row return stays disabled by default;
- statement/request timeout, rate, concurrency, and read-only-role controls are verified using the participant's host tooling, not inferred from AskLens structural limits.

The repository's [synthetic PostgreSQL/Playwright smoke](test-project-demo.md#one-command-postgresql-18--playwright-reference) can be run separately from a source checkout to understand the reference behavior. It must not replace participant-owned registration, scope, and host-control checks.

## 6. Measure time to first correctly scoped query safely

Start the measurement when the evaluator begins candidate installation/configuration. Stop only when a predefined synthetic/de-identified query returns the expected scoped result **and** its paired cross-scope/hidden-member case denies safely.

Record outside this repository:

- candidate commit and wheel checksum;
- Python/Django/PostgreSQL major versions and core/API/MCP surface;
- elapsed engineering minutes;
- pass/fail for correctly scoped query and adversarial denial;
- count and category of maintainer interventions;
- safe error codes and documentation gaps.

Do not record questions containing private business facts, database rows or values, participant/user names, tenant identifiers, permission strings, credentials, environment content, model/binding paths, QuerySets, scope-provider logic, full plans with sensitive filters, provider payloads, or full audit content. A repository test or author-operated demo is technical evidence only, not external continued-use evidence.

## 7. Roll back or uninstall

For a disposable environment, deactivate and remove the evaluation virtual environment using the participant's normal workspace cleanup process. Restore the prior application dependency lock and recreate/restore the disposable database snapshot.

If the candidate was installed into a retained staging environment:

```bash
python -m pip uninstall django-asklens
```

Uninstalling the package does not reverse database migrations, application registrations, saved plans, API/MCP clients, or host audit data. Do not run `migrate asklens zero` blindly. Restore the complete tested snapshot/configuration together, following the strict [0.1-to-0.2 rollback guidance](migrating-0.1-to-0.2.md).

## 8. Report issues without leaking evaluation data

For ordinary defects, provide the candidate commit/checksum, Python/Django/PostgreSQL versions, selected surface, a synthetic minimal reproduction, expected/actual safe behavior, and stable `asklens.*` error code. Do not attach database dumps, screenshots with rows, completed intake/evaluation forms, private schemas, tenant IDs, permissions, environment files, or raw provider/audit logs.

Report suspected security vulnerabilities through the private process in [SECURITY.md](../SECURITY.md), never a public issue. Stop evaluation if a case suggests cross-scope or hidden-field disclosure, mutation, generated-SQL execution, or provider/audit leakage. Only the maintainer may record verified external evidence, and no completed participant data belongs in this repository.
