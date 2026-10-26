# Documentation site build and operator activation

The repository renders the existing Markdown with MkDocs `1.6.1` from the
isolated `docs` dependency group. MkDocs is not a package runtime dependency.
GitHub-style callouts remain readable in repository Markdown and a small
build-only hook renders them as admonitions. Links from docs to files outside
`docs/` become explicit `github.com/.../blob/main/` source links in the static
site rather than broken Pages-relative paths.

## Build and validate locally

```bash
uv sync --locked --group docs
uv run --no-sync mkdocs build --strict --clean
uv run --no-sync python scripts/verify-docs-site.py site
```

The validator checks generated local links and fragments, primary navigation,
image alternatives, showcase media, and the absence of outreach drafts, Python
hooks, bytecode, and other excluded internal artifacts. `site/` is generated
and Git-ignored; remove it after inspection:

```bash
rm -rf site
```

## Build-only CI

`.github/workflows/docs.yml` builds and validates the site for relevant pull
requests and `main` updates. It has only `contents: read`; it neither uploads a
Pages artifact nor requests Pages or OIDC permissions. Passing that workflow is
build evidence, not deployment evidence.

## Prepared Pages readiness check (no deployment)

`.github/workflows/docs-pages.yml` is deliberately manual-only and separate
from package publication. It repeats the strict build and validation only for
the selected default-branch ref. It has `contents: read` permission and no
artifact upload, Pages write, OIDC, environment, or deploy step. Dispatching it
would establish only build readiness, not a published site.

No workflow in this documentation slice can deploy the site. That keeps source
preparation separate from the owner decisions that were not made here.

## Operator-only activation steps

After the reviewed source is public, a repository owner who separately decides
to publish the site must:

1. Recheck the rendered site and run the **Prepare documentation for Pages (no
   deployment)** readiness workflow on the intended default-branch commit. Its
   build job refuses other refs.
2. Review GitHub's current Pages custom-workflow documentation and the pinned
   action versions before changing source. In a separate, authorized pull
   request, add the official Pages artifact upload and deploy jobs with the
   minimum documented permissions, default-branch restriction, concurrency,
   and any required `github-pages` environment protection. Do not reuse Python
   package publication permissions.
3. Review and merge that activation change through the normal repository
   process. Then, as an explicit remote settings action, select **GitHub
   Actions** under **Repository settings → Pages → Build and deployment**.
4. Manually run or approve only the reviewed default-branch deployment and
   verify the resulting URL, navigation, assets, and provenance wording in a
   private browser session.
5. Only after that verification, make a separate reviewed source change to
   update the README documentation badge and package metadata URL from their
   currently published GitHub locations to the live site.

Those future source, permissions, environment, settings, dispatch, and deploy
actions require owner authorization. None was performed or requested while
preparing this build-only configuration.
