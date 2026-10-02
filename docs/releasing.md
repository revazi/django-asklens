# Release process

This process applies to releases after `0.2.0`. The existing `v0.2.0` tag,
GitHub Release, and PyPI files are immutable and must not be recreated or
replaced.

## 0.3.0 candidate status

Current source metadata prepares `0.3.0`, but it is an unpublished release
candidate. Candidate validation does not authorize a tag, GitHub Release, PyPI
upload, deployment, protected-environment approval, or remote Trusted Publisher
change. Record the exact candidate commit, wheel and source-distribution
SHA-256 values, and check results in the candidate pull request; do not present
those local files as immutable published artifacts.

The repository workflow and local checks can verify the intended publisher
identity and artifact handoff, but they cannot independently confirm the
current browser-side PyPI Trusted Publisher configuration. An authorized
operator must confirm that remote setting and the protected GitHub `pypi`
environment before any later publication decision.

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
5. passes those exact files to the environment-protected publish job;
6. publishes with `pypa/gh-action-pypi-publish`; and
7. downloads the files back from PyPI, authenticates them against the build
   digests, and runs isolated core, API, MCP, Django-system, and migration checks
   across the supported Python/Django matrix.

Pre-publication CI remains the release gate. Post-publication verification is a
separate check that the immutable public bytes resolve and behave as expected;
it cannot make a bad upload safe or replace candidate review.

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
   changelog on the exact candidate commit. Live-provider, production, external
   adoption, and independent-security evidence must be described as absent
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
  --version 0.2.0 \
  --wheel-sha256 af0881945d5f5f227332aac8bb13df10d4cf5bd3e54a038acd6545db5640d1d8 \
  --sdist-sha256 11af90303fd2d23123e4caa98c6e6cb660b7b8f32d6fba0c57a4554c8d39e022 \
  --django-package 'Django>=6.1,<6.2' \
  --django-version-prefix '6.1.'
```

The verifier accepts only the fixed `django-asklens` PyPI endpoint and
`files.pythonhosted.org` artifact host, exactly one non-yanked universal wheel
and one sdist, exact release filenames, and matching metadata/download digests.
It then installs each artifact's core, `api`, and `mcp` surfaces independently.
This is public-artifact evidence, not proof of production deployment or
independent security review.
