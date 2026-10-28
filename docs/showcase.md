# Browser showcase

These assets were captured from the existing `tests.test_project` source demo
with its small seeded synthetic dataset and offline deterministic
`DummyProvider`. They contain no customer data, provider credentials, or live
LLM calls. The current source demo is alpha evidence, not a production
certification. At the immutable `v0.3.2` tag, they are release-source demo
evidence; mutable `main` may become newer than the public artifacts.

## Scoped grouped result

![AskLens local demo showing the exact question “Show paid billing revenue by product”, the North Studio current-user scope, and a grouped revenue result containing North membership.](https://raw.githubusercontent.com/revazi/django-asklens/main/docs/assets/showcase/scoped-revenue.png)

*The exact configured question **Show paid billing revenue by product** returns
a grouped table/chart for the signed-in `facility-owner`. The host-selected row
scope is North Studio; the screenshot does not establish access to or reveal
another tenant's rows.*

## 36-second offline walkthrough

<video controls preload="metadata" poster="https://raw.githubusercontent.com/revazi/django-asklens/main/docs/assets/showcase/scoped-revenue.png" style="display:block; width:100%; height:auto;" aria-describedby="offline-walkthrough">
  <source src="https://raw.githubusercontent.com/revazi/django-asklens/main/docs/assets/showcase/offline-demo.webm" type="video/webm">
  <track kind="captions" src="https://raw.githubusercontent.com/revazi/django-asklens/main/docs/assets/showcase/offline-demo.vtt" srclang="en" label="English" default>
  Download the <a href="https://raw.githubusercontent.com/revazi/django-asklens/main/docs/assets/showcase/offline-demo.webm">36-second WebM walkthrough</a> and read the text walkthrough below.
</video>

<div id="offline-walkthrough">
  <p><strong>Text walkthrough</strong></p>
  <ol>
    <li>The synthetic <code>facility-owner</code> account signs in through Django's existing login form.</li>
    <li>The page identifies North Studio as the host-selected current-user row scope; the label does not grant access or reveal other scopes.</li>
    <li>The exact configured question <strong>Show paid billing revenue by product</strong> returns three North-scoped groups as a bar chart and table.</li>
    <li>The exact configured question <strong>Show paid billing revenue for the no-sales demo product</strong> succeeds with the <strong>No matching rows</strong> state.</li>
  </ol>
</div>

The recording has no narration; the caption track and numbered walkthrough
provide the visual sequence in text. Offline dummy mode does not interpret
arbitrary natural-language wording.

## Opaque denial

<img src="https://raw.githubusercontent.com/revazi/django-asklens/main/docs/assets/showcase/neutral-denial.png" style="display:block; width:min(100%, 720px); height:auto;" alt="AskLens local demo denial page saying Access unavailable and offering a sign-out action without naming permissions, resources, or tenants.">

*The seeded `no-report` account gets the neutral host denial. The page does not
explain which permission, resource, membership, or tenant policy caused it.*

## Reproduce the capture

Install the locked development environment and Chromium once, then run the
capture script from a full Git checkout whose synthetic demo database does not
already exist. The maintainer capture tooling and media are deliberately not
included in Python source distributions:

```bash
uv sync --locked --group dev
uv run playwright install chromium
bash scripts/capture-showcase.sh
```

The script binds an available loopback port, creates and seeds only the ignored
`.asklens-test-project.sqlite3`, launches the existing Django demo, verifies the
scope/result/empty/error/denial text in Chromium, refreshes the two screenshots and
recording under `docs/assets/showcase/` (the reviewed caption file is maintained
alongside them), and removes its temporary server and database. It refuses to
replace an existing demo database. Docker is not required.

The capture intentionally keeps the existing authentication, CSRF handling,
explicit catalog, current-request permission checks, trusted row scope, and
query limits. To run the journey manually or transition from synthetic models
to host registration, follow the [source demo guide](test-project-demo.md).
