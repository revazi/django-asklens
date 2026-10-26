# Awesome Django submission packet — not a pull request

**Recommendation as observed 2026-10-26 UTC: not ready to submit.** This packet
is complete for maintainer review, but the repository is not yet six months old
and has 5 GitHub stars. Current Awesome Django guidance expects at least six
months of active maintenance and says projects with fewer than 100 stars are
usually too early; its pull request template says a project only a few months
old or under 100 stars does not meet the criteria. A complete packet, several
releases, or a possible maintainer exception does not override those written
criteria or imply acceptance. Recheck every fact and upstream rule before any
future operator submission.

No fork, branch, issue, pull request, account login, or upstream write was made.

## Read-only upstream and project observations

Observed on 2026-10-26 UTC:

- Upstream contribution rules:
  <https://github.com/wsvincent/awesome-django/blob/main/contributing.md>
- Required pull request template:
  <https://github.com/wsvincent/awesome-django/blob/main/.github/pull_request_template.md>
- Current General section:
  <https://github.com/wsvincent/awesome-django/blob/main/README.md#general>
- Upstream `main` resolved through the public GitHub API to commit
  [`d3172df8c12f9be714fa490f7d6c402ce15e3afe`](https://github.com/wsvincent/awesome-django/commit/d3172df8c12f9be714fa490f7d6c402ce15e3afe).
  The raw rules, template, and README at `main` were read. No `AskLens` or
  `django-asklens` entry was present. The guidelines say that when a section is
  not alphabetical, a new item goes at the end; the proposed entry below would
  follow the current final General item, `iommi`.
- <https://api.github.com/repos/revazi/django-asklens> reported repository
  creation at `2026-07-03T02:07:07Z`, 5 stars, and `main` as the default branch.
- <https://api.github.com/repos/revazi/django-asklens/releases?per_page=100>
  reported five releases: `v0.1.0a0`, `v0.1.0a1`, `v0.2.0`, `v0.3.0`, and
  `v0.3.1`.
- <https://pypi.org/pypi/django-asklens/json> reported published version
  `0.3.1` and the same five version keys.

These unauthenticated public responses are point-in-time metadata, not adoption,
quality, production-readiness, or future eligibility evidence. GitHub counts
can change. The immutable public `0.3.1` artifact remains an alpha; current
source-demo and documentation polish may be newer.

## Proposed General entry

Place at the end of **General** only if the project later meets current upstream
criteria and an operator chooses to submit:

```markdown
- [django-asklens](https://github.com/revazi/django-asklens) - Validate read-only semantic query plans over explicitly registered Django models.
```

## Fully completed upstream template

### Project Information

1. **Project Name:** Django AskLens

2. **Project URL:** <https://github.com/revazi/django-asklens>

3. **Description:**

   Django AskLens is a BSD-licensed public-alpha Django package that validates
   structured, read-only query plans against an explicitly registered semantic
   catalog and current-request permissions, then compiles Django ORM queries
   without executing LLM-generated SQL.

----

### Criteria

1. **How long has the project been maintained?**

   Almost four months as of 2026-10-26. GitHub reports repository creation on
   2026-07-03. This does not currently meet the general expectation of at least
   six months of active maintenance with sustained development; the repository
   also has fewer than 100 stars.

2. **How many releases has it had if it's a library or package?**

   Five GitHub/PyPI versions as of 2026-10-26: `v0.1.0a0`, `v0.1.0a1`,
   `v0.2.0`, `v0.3.0`, and `v0.3.1`. Release history:
   <https://github.com/revazi/django-asklens/releases>. The current published
   package is the `0.3.1` alpha:
   <https://pypi.org/project/django-asklens/0.3.1/>.

3. **Are you the author, or are you submitting the project on behalf of a company?**

   - [x] I am the author
   - [ ] I am submitting on behalf of a company
   - [ ] Other (please specify)

   The submitter, Revaz Zakalashvili, is the project's author and maintainer.

4. **What makes it awesome?**

   It gives Django hosts an explicit alternative to LLM-generated SQL: hosts
   register only approved models, semantic fields, and metrics; provider output
   is structured and untrusted; current-request permissions and trusted row
   scope are revalidated before read-only ORM execution. An offline deterministic
   synthetic demo lets maintainers inspect that boundary without an API key.
   The project is still alpha and is not presented as production-certified or
   as evidence of broad adoption.

5. **Is this a paid product or service?**

   - [x] No, it is free and open source
   - [ ] Yes, it is paid, freemium, or has a paid tier
   - [ ] It is open source with a paid hosted or "pro" version

   **Pricing page:** Not applicable; Django AskLens is free,
   BSD-3-Clause-licensed open-source software and has no paid tier represented
   by this packet.

----

### AI Disclosure

- [x] Yes, this pull request was generated or assisted by AI.
- [ ] No, this pull request was authored entirely by a human.

This draft packet was prepared with AI assistance and must be reviewed and
edited by the author before any manual upstream submission.

----

### Additional Information

The repository documents exact public-package provenance, alpha/support limits,
security boundaries, and a deterministic source-checkout demo. Its test suite
covers trusted execution, opaque denials, tenant row scope, metadata-only audit
behavior, API/MCP adapters, and package artifacts. Those project-local checks
are not independent security review, production certification, or community
adoption evidence.

The author understands that the project currently falls below the written age
and star criteria and recommends waiting rather than asking for an exception.
If submitted in the future, this information, objective metadata, intended
entry location, and all upstream requirements will be rechecked against current
public sources.
