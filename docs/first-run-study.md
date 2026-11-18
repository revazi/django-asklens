# External first-run study protocol — preparation only

Prepared for [#192](https://github.com/revazi/django-asklens/issues/192), with
session execution in [#193](https://github.com/revazi/django-asklens/issues/193).
**No sessions, recruitment, external contact or independent usability results
are established by this document.**

## Maintainer approval — #192 only

On **2026-11-18 UTC**, the maintainer explicitly **approved** the exact merged
protocol at commit
[`27a1e3e1f1b2286f8b079fecdfb10363b4da17d9`](https://github.com/revazi/django-asklens/blob/27a1e3e1f1b2286f8b079fecdfb10363b4da17d9/docs/first-run-study.md).
This dated decision satisfies #192's maintainer-review criterion for protocol
preparation only; worker review and green CI are not substitutes for it.

Approval does **not** authorize #193 execution. A specific recruitment route,
participant contact, consent process, recording, custodian/storage setup and
actual sessions remain separately unauthorized and incomplete. The approved
protocol's consent, privacy, artifact, timing, storage and recruitment
requirements below remain unchanged; any artifact or task revision requires
new maintainer review.

## Question, participants and stopping rule

Hypothesis: a Django developer can install, register this one model and obtain a
first correctly scoped dummy answer **unassisted within ten minutes**. Ten
minutes is neither a promise nor a result. This is a small formative study, not
a benchmark, adoption survey, production/security review or revived pilot gate.

#193 aims for 3–5 consenting independent human Django developers. Independent
means not a maintainer/contributor who designed this journey, not a worker on
these issues and not previously rehearsed/coached on this exact task. Record
prior Django/AskLens familiarity in coarse bands and any relationship/conflict;
exclude ineligible sessions from the independent count, not from an honest
limitations note. Maintainer rehearsals, AI simulations, synthetic fixtures,
installed-wheel CI and security reviews are useful **separate** evidence, never
participants. Do not claim population representativeness or continued adoption.

Allow up to **25 minutes of task time**, excluding explicitly timed breaks.
At ten minutes, silently mark the hypothesis outcome; do not interrupt or imply
failure. Stop earlier at completion, participant request, suspected sensitive
data exposure or an unsafe action. Ask once at the start whether neutral
think-aloud is comfortable; silence is allowed. Do not repeatedly prompt them.
If they request help, offer to continue unassisted or accept help. Log each
intervention and its time/content category; never count later success as
unassisted. Safety intervention always takes priority over completion.

## Fixed artifact and facilitator preparation

Use this selected artifact pair, not floating `main` or `pip install latest`:

<!-- asklens-study:identity -->
```json
{
  "package_version": "0.3.2",
  "wheel": "django_asklens-0.3.2-py3-none-any.whl",
  "wheel_sha256": "739d5411cd0b0ab63ac8dae9e9a0a4f2cf396cb2e0f0ef5bbfac9a2c4607b050",
  "sdist_sha256": "e522055e3b34eac434cabff6db8bb4c278e210591bcd95027956f2449daee177",
  "example_source_commit": "1188e981b5fb4fba468f7ecfcf97e0886aa22874",
  "question": "Show my paid orders",
  "failure_selector": "no-report"
}
```

The wheel is the immutable **public** core `0.3.2` artifact authenticated by
[Installation](installation.md). The source-only example at that exact commit
is **not shipped in the public wheel/sdist**. A same-version local rebuild is a
different artifact and must not be substituted. Record the protocol commit
separately; changing either artifact or task requires a new study revision and
maintainer review, not a silent substitution mid-series.

Facilitator preparation, before participant task time:

1. Use an owned disposable directory outside the source checkout, never a host
   application/database. On a POSIX macOS/Linux machine with Python 3.12+, Git
   and uv, obtain/verify the exact source SHA above. Use `git archive` at that
   SHA to extract **only** `examples/quickstart/` into a fresh staging directory;
   do not copy `.venv`, databases, caches or package source. Preserve
   `manage.py`, `quickstart/` and `shop/` in the participant workspace.
2. **Do not hand over the completed registration.** In this disposable copy
   only, replace `shop/asklens_registration.py` with the single line
   `# Register the synthetic Order model here.`. Keep `shop/apps.py` and its
   single startup import unchanged. Record this one-file study modification.
   The host model, migration, fixture command, dummy plans and CLI are supplied;
   the participant must author the registration. Copying a complete unchanged
   quickstart would measure tutorial replay, not registration effort.
3. Download/authenticate the public wheel and sdist using the pinned source's
   `scripts/download_pypi_artifacts.py` and the exact hashes above, as in
   [quickstart step 2](quickstart-app.md#2-authenticate-and-install-the-public-core-wheel).
   Stage them as `artifacts/` in the workspace. Stop on authentication failure;
   never bypass the digest or relabel a local build. Keep a separate pristine
   example outside the participant workspace for facilitator rehearsal only.
4. Supply the participant with the brief below, workspace/artifact paths and
   read-only docs at the same pinned source commit: quickstart-app,
   registration, troubleshooting and installation. Docs lookup/copying is
   allowed; record which guidance was used. Do not provide the completed
   registration file or proactively point to a solution. No AI assistance,
   live provider, optional adapter, Docker, web login or API key is needed.
5. Record actual Python, Django, Pydantic, uv, OS/architecture/shell versions,
   wheel hash, source SHA, protocol SHA and dependency resolution (privately,
   no machine paths/usernames). Fix the environment policy for the series:
   use a new core-only venv per session, no editable install or module-path
   injection, and do not change installed dependencies between attempts.
   A lock-selected dependency set may be staged, but must be named and reused;
   version differences limit comparisons. Do not collect the full environment.
6. Rehearse once as a **maintainer check**, not a participant. Confirm the stub
   gives an empty registry before authoring, then restore the reviewed scoped
   registration in a separate rehearsal copy and run migrations, checks,
   seed, Alice/Bob/denied commands and `manage.py test shop`. Check the installed
   import comes from that venv; DRF/FastMCP must be absent. Clean up only owned
   rehearsal files. Failed rehearsal blocks sessions until fixed/reviewed.

This is a prepared **registration task variant**, not a claim that the stock
quickstart is broken. Record facilitator staging/download durations separately;
they are excluded from participant time and must be disclosed in results.
Participants still create a venv and install the selected wheel themselves.
Do not claim a fresh-machine end-to-end ten-minute result from pre-staged assets.

## Participant brief — read verbatim after consent

> We are evaluating these instructions and tools, not you. Negative findings
> are useful. You may stop or decline any question. Please work independently
> using the supplied docs; tell us if you want help. You do not need to keep
> talking while you work. There is no preferred opinion or speed.
>
> In this disposable Django project, install the provided authenticated AskLens
> core wheel in a new environment. The synthetic `shop.Order` model, migrations,
> dummy questions and local CLI are already supplied, but its registration is
> intentionally blank. Register **one** resource named `orders`, exposing only
> `product` (string), `status` (string) and `total_cents` (integer), all non-null,
> with UTC timezone and product-ascending order. Require `shop.view_order` and
> scope rows to the currently authenticated user's ownership; do not expose
> owner identifiers. Keep the single existing startup import. Use only the
> synthetic database; do not add real data, provider keys or optional extras.
>
> Apply migrations, run the setup checks and seed the supplied synthetic data.
> Ask exactly `Show my paid orders` as `alice`, then as `bob`. Tell us what
> confirms each result is scoped. Then ask the **same exact question** as
> `no-report` and explain the safe failure and what you would check next.
> Do not grant permissions, use superuser or broaden scope to make that last
> command succeed. Tell us when you consider the task complete or want to stop.

### Fixed commands and observer success criteria

These are task instructions, not timed hints. Use the supplied quickstart for
venv/install/provenance commands; participant executes the following in the
copied project with its own installed environment:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check
.venv/bin/python manage.py check_asklens --fail-on-empty
.venv/bin/python manage.py seed_quickstart
.venv/bin/python manage.py ask_orders 'Show my paid orders' --as-user alice
.venv/bin/python manage.py ask_orders 'Show my paid orders' --as-user bob
.venv/bin/python manage.py ask_orders 'Show my paid orders' --as-user no-report
```

Observer criteria (do not coach toward these while the task is running):

- Alice: `response_type: "query"`, `result.data` exactly North class/2000 then
  North membership/1200; no draft or South order; no truncation.
- Bob: same exact question, only South membership/9900. The participant explains
  current user/owner scope rather than a client-chosen filter or global data.
- `no-report`: nonzero exit, `response_type: "error"`, safe
  `asklens.member.unavailable`; not an empty successful result. They identify
  resource access as the intended difference and describe checking trusted
  host permission/registration configuration without exposing diagnostics or
  changing policy. Not guessing an undisclosed internal implementation detail.
- Setup counts alone do not prove migrations, provider validity or row scope.
  A technically passing but unsafe/global registration is **not completion**.
  After task timing ends, inspect registration and run the supplied `shop`
  tests to check negative/metadata-audit behavior; record any discrepancy.
  Do not silently recategorize a later repaired attempt as first success.

## Timing and measurement definitions

Use a monotonic stopwatch and relative offsets, not screen/terminal capture by
default. Keep wall elapsed and any explicitly paused breaks separate. Record
unknowns as unknown; do not estimate a missing timing from memory.

| Measurement | Start / end and recording rule |
| --- | --- |
| Participant prerequisites | Before T0: from beginning acquisition of missing Python/uv/Git to a usable prerequisite set. Record download/install waits and pre-existing tools separately. If already present, say so, not a measured zero-cost fresh install. Facilitator source/artifact staging is a separate duration. |
| Time to first query | **T0**: after consent/prerequisite check, when the brief, workspace and staged artifacts/docs are handed over; includes reading, venv, install, registration, migrations and mistakes. **TQ**: first successful Alice command with all expected scoped rows/metadata, later confirmed safe by registration/tests. Record elapsed `TQ−T0`, not time to a green registry check or any JSON response. |
| Download/network wait during task | Note start/end of dependency/interpreter acquisition and network retry intervals after T0. Keep them in gross time-to-first-query and report separately; do not subtract overlapping waits twice or call adjusted time the headline. No provider requests are permitted. |
| Scoped verification / task end | Record Bob verification time separately. **TE**: participant has completed both scoped commands and diagnosed the fixed safe failure, or stop/cap/withdrawal occurs. Task duration `TE−T0`; censored/incomplete is not a 25-minute success. |
| Registration effort | First registration edit to first nonempty registry check, then to validated scoped success. Count edit/test attempts and resource/field declarations; note copied versus authored/edited guidance and safety mistakes, without collecting source. Reading before first edit remains in total time. |
| Assistance | Record every requested/provided hint, command, doc pointer or safety intervention with offset and phase. Docs supplied from the start are allowed unassisted resources; new targeted pointers, AI help or facilitator fixes are assistance. Report TQ and whole-task completion as unassisted/assisted/incomplete separately. |
| Confusion/errors | Short de-identified descriptions, safe error code, step and recovery/abandonment; include artifact/setup problems and misunderstood empty/denied results. No raw logs or provider/host payloads. |
| Continue/decline | After TE ask: “Would you choose to try this further in a suitable project? Why or why not?” Allow yes/no/unsure/skip; optional next needed improvement. Interest is not endorsement, adoption or production intent. |

After the task, ask neutrally: “What, if anything, was unclear?”, “What did you
expect at that step?”, and “What would you change first?” Do not ask for stars,
testimonials, positive answers or public quotes during the timed task. Report
actual sample size, observed times/ranges, missing/censored sessions and count
of eligible unassisted TQ ≤ ten minutes. No significance or generalization
claim is warranted by 3–5 sessions or a pre-staged environment.

## Consent, privacy and retention

Before T0, explain purpose, voluntary participation, stopping/withdrawal, planned
minimal notes/public aggregate, storage/access/retention and optional recording.
Obtain explicit consent; do not treat participation or silence as consent to
recording or quotation. Declining recording/quotes must not affect eligibility.
Do not seek contact or collect consent in this preparation task.

- Collect only random session ID, coarse Django/AskLens familiarity, selected
  artifact/version/platform, relative timings, outcomes, assistance and
  de-identified friction/continue reasons. No employer, project identity,
  demographic profile, IP address, home path, account handle or full terminal
  history is needed. Keep any consent/contact mapping separate from notes.
- **Prohibited:** customer/production data, proprietary host code, source
  secrets, credentials, provider prompts/payloads, account sessions, real tenant
  identifiers or raw external errors. Use only this synthetic local fixture.
  Stop capture if unexpected private data appears; do not paste it into issues.
  Ask the participant to close unrelated windows/notifications before work.
- Recording is **off by default**. Only with separate opt-in and maintainer-
  approved local storage may a bounded workspace-only recording be made; no
  cloud/AI transcription or full-desktop recording. Stop/pause on request.
  Notes-only is sufficient. This task authorizes no recordings.
- Before recruitment, name one maintainer custodian and an access-controlled,
  encrypted non-public location (not repository/issues/PR attachments). Only
  the custodian and named session analyst may access raw notes/consent; no
  sharing to providers. Delete recordings within **7 days** after extraction
  of consented notes; delete raw notes and consent/contact mapping within
  **30 days of the session**, including controlled backup copies. Publish only
  the reviewed de-identified summary. Do not recruit if storage/deletion
  controls or an appropriate consent process cannot be supplied.
- Offer withdrawal/deletion via the authorized consent channel and session ID
  until public aggregation, no later than day 30. Explain that already public
  aggregates may not be individually retractable; do not promise erasure from
  external copies. Retain only consented de-identified aggregate findings after
  raw-data expiry, not identifiable transcripts.
- Default public output is aggregate/paraphrase. For any verbatim quote, obtain
  **separate explicit permission for the exact de-identified text and public
  destination** after the session, before publication; allow refusal/edits.
  With no permission, omit the quote. No identifying attribution is needed.

## Session/result instrument

Use one short record per session. Keep the consent record separately; publish
only a reviewed de-identified subset, not this private working instrument.

```text
Session ID / protocol commit / date:
Eligibility: independent human? prior Django/AskLens bands? conflict/rehearsal?
Consent recorded separately? notes yes/no; recording separate yes/no (default no)
Custodian / restricted store / recording-delete and raw-delete due dates:
Package filename/version/SHA-256; source SHA; study stub applied:
Python / Django / Pydantic / uv / OS / architecture / shell; dependency policy:
Prerequisites pre-existing vs acquired; participant wait; facilitator staging:
T0; first registration edit; nonempty-check time; edit/test attempts:
TQ Alice; Bob verification; TE or stop reason; breaks; network waits:
TQ unassisted/assisted/incomplete; whole task unassisted/assisted/incomplete:
Registration/scope/test review passed? discrepancy/repaired attempt noted?
Confusing steps/errors/recoveries, relative times and assistance categories:
Continue yes/no/unsure/skip + reasons; first suggested improvement:
Limitations/missing timings; finding IDs; permitted public subset:
Exact public quote/destination permission, if separately obtained (otherwise none):
Deletion completed on / by (record without retaining participant identity):
```

### Finding triage and #193 handoff

For each finding record: **severity, category, synthetic reproduction, expected
versus actual safe outcome, artifact/version/digests/source+protocol SHAs,
platform, recurrence count, next action/owner and evidence limitations**. Link a
focused issue only after removing private detail; synthesize minimal repro data
rather than uploading a session recording, transcript or terminal log.

| Severity | Triage and next action |
| --- | --- |
| Critical | Suspected scope/permission bypass, secret/row leakage or mutation. Stop session, preserve only minimal safe metadata and use [private security reporting](../SECURITY.md); never publish an exploit/participant payload. Maintainer assesses before resuming. |
| High | Reproducible safe setup/query blocker on the selected supported artifact, no safe documented recovery. File minimal synthetic defect/repro, prioritize before the next batch; never loosen safeguards to finish. |
| Medium | Recoverable confusing documentation, registration mistake or misleading state; file exact step/expected outcome and focused docs/test action. Distinguish defect from prerequisite/environment problem. |
| Low | Wording or optional improvement that does not block safe completion; group duplicates, rank by observed recurrence and effort. |
| Out of scope / insufficient evidence | Product request, unsupported platform, unverified cause or missing timing. Record limitation and investigate/defer, not an invented defect or a participant failure. |

The exact protocol's maintainer-review gate is satisfied as recorded above.
Before #193 contacts anyone: separately authorize a specific recruitment
route/consent process, name the custodian/storage, and pass the fixed-artifact
rehearsal. Then run actual willing independent sessions (at least three, aiming
for five), report all outcomes including negative/incomplete results, triage
focused issues and publish only consented de-identified findings. Fewer sessions
leave #193's sample criterion incomplete unless the maintainer explicitly
revises scope. Protocol approval, preparation, worker review, rehearsal and CI
do not authorize or complete #193's study. See the [roadmap evidence/status](maintenance-roadmap.md#issues-191-and-192-contract-review-and-study-preparation).
