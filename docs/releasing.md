# Release process

This process applies to releases after `0.2.0`. The existing `v0.2.0`,
`v0.3.0`, and `v0.3.1` tags, GitHub Releases, and PyPI files are immutable and
must not be moved, recreated, overwritten, or replaced.

## Immutable 0.3.1 release status

`django-asklens==0.3.1` is the current published alpha. Its immutable
[`v0.3.1` source snapshot](https://github.com/revazi/django-asklens/blob/v0.3.1/README.md)
and [GitHub Release](https://github.com/revazi/django-asklens/releases/tag/v0.3.1)
retain their pre-publication wording as historical release evidence. This
main-branch status records that annotated tag object
`34f123230c2ea09622f0f2906eeaf775619f78bb` resolves to commit
`1b19ba8dea81117d9ff79d64bd28e3136cd93e6e` and tree
`5a914eb84b697d0d7c030b311d68c305df9a9ed5`. The public wheel
`django_asklens-0.3.1-py3-none-any.whl` has SHA-256
`4332c62aad6e7b27f553af3f8796ed6090e6207ddad6a30a1c4665e9a1085887`;
the public source distribution `django_asklens-0.3.1.tar.gz` has SHA-256
`5e011f2272a7fe6f53df5bae757d045042d39e31cfba40eb51766d703eb38dde`.
A same-version local rebuild is separate local evidence, not either immutable
public artifact.

Package metadata requires Python `>=3.12` and Django `>=5.2,<7.0`; the public
release verification matrix covers Python 3.12/3.13 and Django 5.2/6.0/6.1.
This remains alpha evidence, not production certification or an independent
security review. Public `0.3.0` is the immediate prior supported upgrade origin.
Published `0.2.0` remains the supported older `0.2.x` origin, while `0.1.0a1`
remains an unsupported testing artifact.

The repository workflow and local checks verify the intended publisher identity
and artifact handoff, but cannot independently confirm the current browser-side
PyPI Trusted Publisher configuration. An authorized operator must confirm that
remote setting and the protected GitHub `pypi` environment before any future
publication decision.

## Trust model

`.github/workflows/publish.yml` uses PyPI Trusted Publishing. The protected
`publish` job requests GitHub's short-lived OIDC identity only after a GitHub
Release is published and the `pypi` environment permits the job. No PyPI API
token, password, or long-lived publishing credential belongs in repository or
environment secrets.

The workflow:

1. checks out the GitHub Release's tag rather than the default branch;
2. requires the tag to be exactly `v<project.version>` and to point at the
   checked-out commit;
3. builds one wheel and one source distribution from that checkout;
4. runs package metadata checks and records both SHA-256 values;
5. passes those files to the environment-protected publish job, where a
   repository-owned guard requires the exact top-level wheel and sdist names,
   regular non-symlink file types, no additional entries, and both recorded
   SHA-256 values;
6. publishes with `pypa/gh-action-pypi-publish`; and
7. downloads the files back from PyPI, authenticates them against the build
   digests, and runs isolated core, API, MCP, Django-system, and migration checks
   across the supported Python/Django matrix.

Pre-publication CI remains the release gate. Post-publication verification is a
separate check that the immutable public bytes resolve and behave as expected;
it cannot make a bad upload safe or replace source review.

## One-time operator configuration

These remote settings cannot be configured by a repository commit. An operator
with administration rights to the GitHub repository and owner rights to the
PyPI project must perform these steps in the web interfaces:

1. In GitHub, create an environment named exactly **`pypi`** under
   **Settings → Environments** for `revazi/django-asklens`. Add required
   reviewers and deployment-branch/tag protection appropriate to the repository.
   Environment approval is strongly recommended. Do not add a PyPI token or
   password secret.
2. In the existing `django-asklens` project on PyPI, open
   **Manage → Publishing → Add a new publisher → GitHub** and enter exactly:

   | PyPI field | Value |
   | --- | --- |
   | GitHub owner | `revazi` |
   | Repository name | `django-asklens` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

Save that publisher. Do not create a pending publisher for a different project,
do not enter `.github/workflows/publish.yml` in the workflow-name field, and do
not retain a fallback API token in repository or environment secrets.

The PyPI publisher configuration and the GitHub environment are trust controls.
Changes to either require an explicit maintainer review; this workflow does not
and cannot mutate them.

## Trusted Publisher incident and recovery

The first protected `0.3.0` publish attempt and one controlled retry received
PyPI `invalid-publisher` after GitHub had issued a valid OIDC token, before any
release file was uploaded. The immutable build artifacts were preserved. After
an authorized operator corrected the **production PyPI** existing-project
publisher mapping, a **failed-jobs-only rerun of the same workflow run** reused
those artifacts, crossed the protected-environment approval boundary again, and
completed. Preserve the failed attempts as part of the incident record.

A valid OIDC token plus `invalid-publisher` is a publisher-configuration or
service incident. It is not authorization to bypass Trusted Publishing. In
particular, production PyPI (`pypi.org`) is distinct from TestPyPI, and an
existing-project publisher for `django-asklens` is distinct from a pending
publisher used before a project exists. A mapping or successful rehearsal on
one service does not establish the mapping on the other.

Use this bounded triage procedure without printing, copying, decoding, or
otherwise inspecting the token itself:

1. Stop retries and record the workflow run and failed job. From the safe OIDC
   diagnostic fields and workflow context, compare the actual claims with the
   intended owner `revazi`, repository `django-asklens`, workflow filename
   `publish.yml`, and environment `pypi`. The workflow-name field is the filename,
   not `.github/workflows/publish.yml`.
2. Confirm which service rejected the publisher. For this workflow it must be
   the existing `django-asklens` project on production PyPI, not TestPyPI and not
   a pending publisher. An authorized owner may correct that remote mapping only
   after explicit maintainer review; repository automation must not change it.
3. **Before any retry, independently confirm that no release file was uploaded.**
   Check the production project/version record and its file list. If any wheel
   or source distribution exists, if the result is ambiguous, or if a partial
   upload may have occurred, stop and treat it as an immutable release incident;
   do not retry publication.
4. Confirm that the original tag and GitHub Release are unchanged, the preserved
   `release-distributions` workflow artifact is still available, and it contains
   exactly the same one wheel and one source distribution. Match the filenames
   and both SHA-256 values to the successful build outputs. Do not rebuild or
   substitute files during recovery.
5. Only when all preceding gates pass, use GitHub's **re-run failed jobs** action
   on that same workflow run. Do not start a new workflow run. The protected
   `pypi` job must request a fresh short-lived OIDC identity and receive its
   normal operator-only environment approval; recovery does not pre-approve the
   deployment.
6. Require the complete post-publication matrix to authenticate the public files
   against the preserved build digests. Record both failed attempts and the
   recovery result. Failed history is evidence and must not be hidden.

Recovery must preserve the immutable tag, GitHub Release, artifact filenames,
and workflow-recorded digests. Never move or recreate the tag, edit/recreate the
GitHub Release to trigger a different build, upload manually, add a PyPI token or
password fallback, use `skip-existing`, overwrite or replace a file, or conceal
a failed attempt. If the preserved artifact expired, any identity/digest differs,
or the no-upload gate cannot be proved, failed-job-only recovery is unavailable;
stop and conduct a separately reviewed release decision rather than improvising
a bypass.

## Preparing a future release

1. Choose the version under the support and compatibility policy. Update
   `project.version`, `django_asklens.__version__`, the changelog, versioned
   documentation statements, and release-specific test expectations together.
2. Run the contributor checks and the release-relevant evidence:

   ```bash
   uv sync --locked --group dev
   uv run --no-sync pytest --strict-config --strict-markers
   uv run --no-sync ruff check .
   uv run --no-sync ruff format --check .
   uv run --no-sync python -m django check --settings=tests.test_project.settings
   uv run --no-sync python -m django makemigrations asklens --check --dry-run \
     --settings=tests.test_project.settings
   bash scripts/alpha-candidate-package-smoke.sh
   PATH="$HOME/.docker/bin:$PATH" bash scripts/reference-demo-smoke.sh
   ```

3. Review all required CI jobs, package contents, dependency advisories, and the
   changelog on the exact proposed release commit. Live-provider, production,
   external adoption, and independent-security evidence must be described as absent
   unless they were separately authorized and actually run.
4. Create an immutable `v<project.version>` tag on the reviewed commit and a
   GitHub Release for that exact tag. Publishing the GitHub Release starts the
   workflow; it does not bypass the `pypi` environment approval.
5. Before approving the environment deployment, inspect the workflow's tag,
   version, build, metadata, and artifact-handoff jobs. Approve only the intended
   release. PyPI versions and files cannot be overwritten.
6. Require every post-publication matrix job to pass. Record the public wheel and
   sdist SHA-256 values in release closeout evidence. A failed public verification
   is an incident to diagnose; never use `skip-existing`, replace the files, or
   move the tag to conceal it.

Do not publish from a pull request, mutable branch head, local dirty tree, or
manual package upload as part of this workflow. Do not push, tag, publish, or
change remote settings without the repository owner's explicit authorization.

## Rechecking a published release locally

Run from any checkout containing the verifier; all package imports occur in
owned temporary directories with `PYTHONPATH` removed. Supply hashes obtained
from an independent release record, not values copied from the same response
being authenticated:

```bash
bash scripts/published-package-smoke.sh \
  --version 0.3.1 \
  --wheel-sha256 4332c62aad6e7b27f553af3f8796ed6090e6207ddad6a30a1c4665e9a1085887 \
  --sdist-sha256 5e011f2272a7fe6f53df5bae757d045042d39e31cfba40eb51766d703eb38dde \
  --django-package 'Django>=6.1,<6.2' \
  --django-version-prefix '6.1.'
```

The verifier accepts only the fixed `django-asklens` PyPI endpoint and
`files.pythonhosted.org` artifact host, exactly one non-yanked universal wheel
and one sdist, exact release filenames, and matching metadata/download digests.
It then installs each artifact's core, `api`, and `mcp` surfaces independently.
This is public-artifact evidence, not proof of production deployment or
independent security review.
