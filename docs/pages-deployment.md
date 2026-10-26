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

## Prepared manual Pages deployment

`.github/workflows/docs-pages.yml` is manual-only and separate from package
publication. For a selected default-branch ref, its build job repeats the
strict build and validation and uploads only the generated `site/` directory as
a Pages artifact. The dependent deploy job uses the dedicated `github-pages`
environment and only `pages: write` plus `id-token: write`; it cannot run when
the default-branch build is skipped or fails. Concurrency does not cancel an
in-progress deployment.

The workflow pins the official Pages actions to reviewed commit SHAs. It does
not run on a push, publish a Python package, modify Pages settings, or establish
that a site is live merely by existing in source. The package Documentation URL
and README badge continue to point to GitHub until the deployed site is
separately verified.

## Operator-only activation steps

A repository owner who separately decides to publish the site must:

1. Recheck the rendered site and review the default-branch commit containing
   the deployment workflow, including its pinned action versions and minimal
   job-level permissions.
2. Review and merge that activation change through the normal repository
   process. Then, as an explicit remote settings action, select **GitHub
   Actions** under **Repository settings → Pages → Build and deployment** and
   review any `github-pages` environment protection.
3. Manually dispatch **Deploy documentation to Pages** on the intended default
   branch. Approve the `github-pages` environment if its protection requires
   operator review.
4. Require the build, validation, artifact upload, and deploy jobs to pass, then
   verify the reported `https://revazi.github.io/django-asklens/` URL,
   navigation, assets, and provenance wording in a private browser session.
5. Only after that verification, make a separate reviewed source change to
   update the README documentation badge and package metadata URL from their
   currently published GitHub locations to the live site.

The merge, Pages settings selection, workflow dispatch, environment approval,
deployment, and later URL change all require owner authorization. Preparing the
workflow locally performs none of them.
