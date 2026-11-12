# Awesome Django submission packet — draft only, not a pull request

**Operator-only submission gate: CLOSED as observed 2026-11-12 UTC.** Django
AskLens is not ready to submit. The repository is younger than six months and
has 5 GitHub stars. Awesome Django's current template says that a project only
a few months old or with fewer than 100 stars does not meet its criteria. The
package also remains alpha, so this packet does not claim that its release
history satisfies upstream's qualitative "stable release history" requirement.

This file is evidence for maintainer review. It is not approval to submit and
is not a promise of acceptance. No Awesome Django fork, branch, issue, pull
request, submission, account login, maintainer contact, or other upstream write
was made. Do not ask for an exception on the strength of this packet.

## Observation method and authoritative sources

All observations below were made on **2026-11-12 UTC** with signed-out,
read-only HTTP access.

### Awesome Django snapshot

- The public `main` branch resolved to exact commit
  [`d3172df8c12f9be714fa490f7d6c402ce15e3afe`](https://github.com/wsvincent/awesome-django/commit/d3172df8c12f9be714fa490f7d6c402ce15e3afe),
  committed at `2026-10-26T01:53:25Z`. The public commit lookup was
  <https://api.github.com/repos/wsvincent/awesome-django/commits/main>.
- Contribution rules were read from the immutable revision at
  <https://github.com/wsvincent/awesome-django/blob/d3172df8c12f9be714fa490f7d6c402ce15e3afe/contributing.md>.
  The mutable current location is
  <https://github.com/wsvincent/awesome-django/blob/main/contributing.md>.
- The required pull request template was read from the immutable revision at
  <https://github.com/wsvincent/awesome-django/blob/d3172df8c12f9be714fa490f7d6c402ce15e3afe/.github/pull_request_template.md>.
  The mutable current location is
  <https://github.com/wsvincent/awesome-django/blob/main/.github/pull_request_template.md>.
- The list and intended category were read from the immutable README at
  <https://github.com/wsvincent/awesome-django/blob/d3172df8c12f9be714fa490f7d6c402ce15e3afe/README.md#general>.
  The mutable current location is
  <https://github.com/wsvincent/awesome-django/blob/main/README.md#general>.
- The complete README at that revision contained no case-insensitive match for
  `AskLens` or `django-asklens`. Django AskLens was therefore **not listed** in
  the observed snapshot.

These URLs identify both the exact evidence reviewed and the mutable locations
that a future operator must recheck. The immutable revision was still the tip
of upstream `main` when observed; it may not remain so.

### Django AskLens snapshot

- <https://api.github.com/repos/revazi/django-asklens> reported creation at
  `2026-07-03T02:07:07Z`, 5 stars, `main` as the default branch, a latest push
  timestamp of `2026-11-12T15:45:54Z`, an active/non-archived repository, and a
  detected `BSD-3-Clause` license. By calendar date, the repository was about
  four months and nine days old—still under six months.
- <https://api.github.com/repos/revazi/django-asklens/releases?per_page=100>
  reported six public GitHub releases: `v0.1.0a0` (2026-07-11), `v0.1.0a1`
  (2026-07-19), `v0.2.0` (2026-10-01), `v0.3.0` (2026-10-04), `v0.3.1`
  (2026-10-04), and `v0.3.2` (2026-10-27).
- <https://pypi.org/pypi/django-asklens/json> reported `0.3.2` as current and
  the same six published version keys. The immutable version record is
  <https://pypi.org/project/django-asklens/0.3.2/>; the immutable GitHub Release
  is <https://github.com/revazi/django-asklens/releases/tag/v0.3.2>.
- The annotated `v0.3.2` tag object is
  `5ab7e9e76f6a39a59894ae2fce600e4c707077c3`; it targets release commit
  `b3cb5a5b84fdeb35f1b4ce972a0abd33b6934982`, whose tree is
  `9fba0b64b5f4efc5ae15cc9790374d3528acc1af`. PyPI reported SHA-256
  `739d5411cd0b0ab63ac8dae9e9a0a4f2cf396cb2e0f0ef5bbfac9a2c4607b050`
  for the `0.3.2` wheel and
  `e522055e3b34eac434cabff6db8bb4c278e210591bcd95027956f2449daee177`
  for the `0.3.2` source distribution; neither file was yanked.
- The current live documentation at
  <https://revazi.github.io/django-asklens/> and its
  <https://revazi.github.io/django-asklens/installation/> page both returned
  HTTP 200 and identified `django-asklens==0.3.2` as the current published
  alpha. Live documentation is mutable and may include post-release
  clarification from `main`; it does not change the immutable tag, source tree,
  wheel, or source distribution above.

Public metadata, counts, and mutable pages are point-in-time observations. They
are not evidence of adoption, endorsement, broad stability, production
readiness, or security review.

## Current rules, category, list, and ordering

At the exact upstream revision above, the applicable location is **Third-Party
Packages → General** (`### General`). Its ten direct entries, in order, were:

1. `django-data-browser`
2. `django-filter`
3. `django-sql-explorer`
4. `django-tables2`
5. `django-maintenance-mode`
6. `django-freeze`
7. `django-nh3`
8. `Weblate`
9. `Django-Classy-Doc`
10. `iommi`

The sequence is not alphabetical. Upstream says to preserve first-come,
first-served order and, unless a section is alphabetical, add an item at the
end. At the observed revision, the proposed entry would therefore go directly
after `iommi` and immediately before `### Internationalisation (i18n)`. General
is proposed because its current entries include database exploration and query
tools; only upstream maintainers can decide whether that category and the
project meet their bar.

The observed requirements and their current disposition are:

| Upstream rule or convention | Current evidence and disposition |
| --- | --- |
| Make one individual PR per suggestion and complete every part of the required template. Incomplete templates are closed. | The draft below answers every current field. No PR has been made. |
| At least six months of active maintenance with sustained development, not just an initial release. | **Unmet.** Creation was 2026-07-03; only about four months and nine days had elapsed. Releases and a recent push show activity but cannot satisfy the minimum age. |
| Some community traction; fewer than 100 GitHub stars is usually too early. The template says a project under 100 stars does not meet the criteria. | **Unmet.** The observed count was 5. No adoption is inferred from repository traffic or release count. |
| A stable release history for a library or package. | **Inconclusive, and not claimed.** Six versions exist, but `django-asklens==0.3.2` is explicitly alpha. Upstream does not define a release-count threshold, and this packet does not relabel alpha history as stable. |
| Clear documentation. | Live documentation was reachable and version-labelled. Whether it is sufficiently clear is a qualitative upstream judgment, so eligibility remains **inconclusive**. |
| Solve a real problem for the broader Django community and meet the quality/maturity bar evident in the current list. | The project addresses validated read-only semantic querying, but broad value, demonstrated traction, and list-level fit remain **inconclusive** and are for upstream to judge. |
| Starter kits, boilerplates, configuration templates, and similar scaffolding are not listed. | Django AskLens is a Django library, not a starter-kit or scaffolding repository. |
| Commercial submissions have additional Django-use, public-age, affiliation, pricing-link, and factual-description requirements. | Not applicable: the represented project is free, open-source software with no paid, freemium, hosted, or pro tier. |
| License requirement. | The reviewed rules and template state **no separate license criterion**. Django AskLens nevertheless declares BSD-3-Clause. A license must not be invented as an upstream acceptance guarantee. |
| Ordering and entry formatting. | Append to this non-alphabetical section. The current list uses `- [Name](URL) - Description.` entries. The proposed entry follows that form and is one short factual sentence without adoption or marketing claims. |
| AI disclosure. | Required template field completed truthfully: this packet was AI-assisted and requires human maintainer review. |

The two objective failures—age and stars—are enough to keep the gate closed.
Several qualitative requirements also remain inconclusive. A complete draft,
six releases, documentation, or a possible maintainer exception does not
supersede the written criteria.

## Exact proposed General entry

Only after every gate below is met and a maintainer deliberately authorizes a
future submission, append this exact line after the then-current final General
entry:

```markdown
- [django-asklens](https://github.com/revazi/django-asklens) - Validate read-only semantic query plans over explicitly registered Django models.
```

## Fully completed current upstream template

### Project Information

1. **Project Name:** Django AskLens

2. **Project URL:** <https://github.com/revazi/django-asklens>

3. **Description:**

   Django AskLens is a BSD-3-Clause-licensed public-alpha Django package that
   validates structured, read-only query plans against an explicitly registered
   semantic catalog and current-request permissions, then compiles Django ORM
   queries without executing LLM-generated SQL.

----

### Criteria

1. **How long has the project been maintained?**

   About four months and nine days as of 2026-11-12 UTC. GitHub reports
   repository creation at `2026-07-03T02:07:07Z`, with releases from July
   through October and a latest push on 2026-11-12. This does not meet the
   general expectation of at least six months of active maintenance with
   sustained development. The repository also has fewer than 100 stars.

2. **How many releases has it had if it's a library or package?**

   Six public GitHub/PyPI versions as of 2026-11-12: `v0.1.0a0`, `v0.1.0a1`,
   `v0.2.0`, `v0.3.0`, `v0.3.1`, and `v0.3.2`. Release history:
   <https://github.com/revazi/django-asklens/releases>. The current immutable
   published package is the `django-asklens==0.3.2` alpha:
   <https://pypi.org/project/django-asklens/0.3.2/>. The existence of six
   versions is not represented as proof of a stable release history.

3. **Are you the author, or are you submitting the project on behalf of a company?**

   - [x] I am the author
   - [ ] I am submitting on behalf of a company
   - [ ] Other (please specify)

   The prospective submitter, Revaz Zakalashvili, is the project's creator and
   maintainer, not a third-party endorser.

4. **What makes it awesome?**

   It gives Django hosts an explicit alternative to LLM-generated SQL: hosts
   register only approved models, semantic fields, and metrics; provider output
   is structured and untrusted; current-request permissions and trusted row
   scope are revalidated before read-only ORM execution. The offline demo uses
   synthetic data and a deterministic dummy mode that handles only the exact
   configured questions; it does not interpret arbitrary natural-language
   wording. The package remains alpha. These repository-local properties are
   not claims of adoption, endorsement, broad stability, production readiness,
   or independent security review.

5. **Is this a paid product or service?**

   - [x] No, it is free and open source
   - [ ] Yes, it is paid, freemium, or has a paid tier
   - [ ] It is open source with a paid hosted or "pro" version

   **Pricing page:** Not applicable. Django AskLens is BSD-3-Clause-licensed
   open-source software, and this packet represents no paid tier.

----

### AI Disclosure

- [x] Yes, this pull request was generated or assisted by AI.
- [ ] No, this pull request was authored entirely by a human.

This draft packet was prepared with AI assistance. The creator/maintainer must
fact-check and edit it before any separately authorized manual submission.

----

### Additional Information

The repository documents exact public-package provenance, alpha/support limits,
security boundaries, and a deterministic source-checkout demo. The dummy demo
matches exact configured questions rather than arbitrary natural language, and
all demo records are synthetic. Repository tests and documentation are
maintainer-operated technical evidence, not independent review, production
certification, community adoption, or an upstream endorsement.

The author understands that the project currently fails the written age and
star criteria. The author is not asking for an exception. If a submission is
considered later, all objective metadata, qualitative requirements, intended
entry location, upstream text, and disclosures must be rechecked first.

## Independent review and lookup limitations

- **Independent review finding:** none was available or performed for this
  eligibility decision. This packet records signed-out public observations and
  repository-local checks, not an independent Awesome Django, adoption,
  usability, stability, or security assessment. A future upstream review cannot
  be predicted or substituted with project-local tests.
- GitHub creation time is not proof of continuous active maintenance; release
  and push timestamps show events, not their quality or sustainability.
- Stars are a mutable counter and are not equivalent to users. The observed
  count must be fetched again rather than copied into a future submission.
- GitHub's release flags, PyPI version records, and artifact hashes prove public
  records and identity, not upstream's qualitative meaning of a stable release
  history. The package's own status remains alpha.
- HTTP 200 responses and version-labelled pages prove availability at the time
  observed, not that upstream will find the documentation clear or complete.
- Absence was checked against one exact upstream README revision. Renames,
  alternate spellings, later commits, and category changes require a fresh
  full-list review.
- The reviewed rules contain no explicit license threshold and no objective
  test for "real problem" or documentation quality. Those must not be invented.
- Signed-out public lookups cannot establish private usage, private maintainer
  deliberations, or future acceptance, and none is claimed.

## Exact maintainer-only next actions

**The gate remains closed. Automation, assistants, and contributors must stop
at this packet. Only an authorized human maintainer may decide whether to take
future upstream account actions.**

1. Do not consider submission before `2027-01-03T02:07:07Z`, the earliest
   six-month anniversary of the reported repository creation time. Continue
   substantive maintenance; do not manufacture releases, stars, or testimonials
   to satisfy a checklist.
2. At that later decision point, use signed-out read-only access first to fetch
   upstream `main`'s new exact SHA, contribution rules, required PR template,
   complete README, General category, final General entry, and current ordering.
   Search the full list again for `AskLens` and `django-asklens`.
3. Re-fetch the Django AskLens repository creation time, maintenance/release
   history, star count, license, paid-product status, PyPI current version, and
   live documentation. Do not proceed while the repository is under six months
   old or under 100 stars.
4. Resolve the remaining qualitative criteria honestly: sustained maintenance,
   stable release history, clear documentation, and demonstrated value to the
   broader Django community. Do not call an alpha history stable merely to pass
   the gate. If any requirement is unmet or inconclusive, update this draft and
   stop without contacting upstream.
5. The creator/maintainer must manually review the exact proposed entry and
   every template answer, preserving the creator affiliation, AI assistance,
   alpha status, exact-question dummy limitation, synthetic-demo scope, and the
   absence of adoption, endorsement, broad stability, or security claims.
6. Only if all then-current requirements are truthfully met and the maintainer
   separately authorizes submission may that human authenticate, create one
   upstream fork/branch and one individual pull request, append the entry at the
   then-current correct location, and complete the then-current template. Do
   not seek an exception and do not reuse stale counts or wording.

## Repository publication boundary

This packet intentionally remains under `docs/outreach/`. That directory is
excluded by `mkdocs.yml` from rendered documentation and its search index, and
is pruned by `MANIFEST.in` from package source distributions. It is not in the
site navigation. Updating this draft does not submit or publish it upstream.
