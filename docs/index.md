# Django AskLens docs

Django AskLens is the Django implementation of the [AskLens specification](asklens-specification.md): a read-only semantic query contract over explicitly registered models, with optional Django REST Framework and MCP adapters.

Django AskLens was created by [Revaz Zakalashvili](https://github.com/revazi) ([revaz.zakalashvili@gmail.com](mailto:revaz.zakalashvili@gmail.com)).

## Package provenance

> [!IMPORTANT]
> `django-asklens==0.3.1` is the current published alpha, not a stable or
> production-certified release. Install its exact public surfaces with
> `python -m pip install 'django-asklens==0.3.1'`,
> `python -m pip install 'django-asklens[api]==0.3.1'`, or
> `python -m pip install 'django-asklens[mcp]==0.3.1'`.
>
> Use the immutable
> [`v0.3.1` source snapshot](https://github.com/revazi/django-asklens/blob/v0.3.1/README.md)
> and [GitHub Release](https://github.com/revazi/django-asklens/releases/tag/v0.3.1).
> Their pre-publication wording is preserved as historical release evidence;
> this main-branch notice records the post-publication status. The annotated tag
> object `34f123230c2ea09622f0f2906eeaf775619f78bb` resolves to commit
> `1b19ba8dea81117d9ff79d64bd28e3136cd93e6e` and tree
> `5a914eb84b697d0d7c030b311d68c305df9a9ed5`. The public wheel is
> `django_asklens-0.3.1-py3-none-any.whl` with SHA-256
> `4332c62aad6e7b27f553af3f8796ed6090e6207ddad6a30a1c4665e9a1085887`;
> the public source distribution is `django_asklens-0.3.1.tar.gz` with SHA-256
> `5e011f2272a7fe6f53df5bae757d045042d39e31cfba40eb51766d703eb38dde`.
> Same-version local rebuilds remain separate local evidence and are not the
> public files. Package metadata requires Python `>=3.12` and Django
> `>=5.2,<7.0`; release checks cover Python 3.12/3.13 and Django 5.2/6.0/6.1.
>
> Immutable public `0.3.0` is the immediate prior supported upgrade origin. The
> immutable `django-asklens==0.2.0` release remains the supported older `0.2.x`
> origin. The historical `0.1.0a1` package was an unsupported testing artifact
> and is not an upgrade origin. See [Installation](installation.md) for
> authentication, upgrade guidance, and evidence limits before using the guides
> below.

## Guides

- [AskLens specification](asklens-specification.md)
- [Installation](installation.md)
- [Support lifecycle](support-lifecycle.md)
- [0.3.x compatibility boundary](compatibility.md)
- [Release process and Trusted Publishing setup](releasing.md)
- [0.3.x maintenance roadmap](maintenance-roadmap.md)
- [Current Django AskLens surface](alpha-surface-inventory.md)
- [Core-only executable quickstart](quickstart-core.md)
- [Usage guide](usage.md)
- [Core Python API](core-python-api.md)
- [Draft internal contract schemas](internal-contracts.md)
- [Internal semantic decision index](internal-semantic-decision-index.md)
- [Internal metadata, result, and error leakage audit](internal-surface-leakage-audit.md)
- [Issue #84 failure-mode and host-control matrix](internal-failure-mode-matrix.md)
- [Draft internal conformance corpus](conformance.md)
- [Custom UI guide](custom-ui.md)
- [Registration API](registration.md)
- [Provider configuration](providers.md)
- [Bounded MCP quickstart and integration notes](mcp-integration.md) — public `0.3.1` `[mcp]` extra, trusted context mapping, compact discovery, and safe row defaults
- [Security checklist](security-checklist.md)
- [Production checklist](production-checklist.md)
- [Host throttling, audit, and observability controls](host-throttle-and-audit-controls.md)
- [Multi-tenant security](multitenancy-security.md)
- [Evaluation fixtures](evaluation.md)
- [Synthetic performance baseline](performance-baseline.md)
- [Test coverage baseline and critical-boundary map](test-coverage.md)
- [Example Django AskLens integration](test-project-demo.md)
- [Demo query ideas](demo-queries.md)

## Current scope

AskLens is a read-only semantic query specification. Django AskLens is the first implementation. Callers supply an untrusted `query-plan`; the implementation resolves current identity, catalog, and row scope, compiles a read-only query, and returns typed result JSON. Optional DRF, MCP, admin, frontend, and provider adapters must use the same execution path.

AskLens does not execute LLM-generated SQL, mutate data, auto-expose Django models, send sample rows to providers, or require a frontend framework. See the [AskLens specification](asklens-specification.md).
