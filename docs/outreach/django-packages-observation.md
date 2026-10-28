# Django Packages read-only observation and operator steps

**Observed:** 2026-10-27 UTC (read-only checks completed at approximately
23:39 UTC), without logging in or changing external state.

## Sources checked

- Package listing:
  <https://djangopackages.org/packages/p/django-asklens/>
- Package release-data endpoint loaded by the public listing:
  <https://djangopackages.org/packages/django-asklens/versions/?page=1>
- Reporting grid landing page:
  <https://djangopackages.org/grids/g/reporting/>
- Reporting grid all-packages page 1:
  <https://djangopackages.org/grids/g/reporting/packages/>
- Reporting grid all-packages page 2:
  <https://djangopackages.org/grids/g/reporting/packages/?page=2>

Each of the listing and grid URLs returned HTTP 200 in the signed-out check.
The public versions page 1 also returned HTTP 200; requesting versions page 2
returned HTTP 404, and the page-1 response did not expose another release-data
page.

## Package-listing observation

The package listing exists and identified `django-asklens`. It linked the
project's GitHub repository, documentation, and PyPI project. At observation
time it reported that its package data had last been fetched roughly 13 hours
and 34 minutes earlier. Its public release-data response still displayed
`0.3.1`, not the already-public PyPI `0.3.2` release:
<https://pypi.org/project/django-asklens/0.3.2/>.

That is a point-in-time stale-metadata observation, not evidence that the
`0.3.2` release is missing from PyPI or that Django Packages will remain stale.
No fetch/refresh control was used because that would change external state and
may require an authenticated maintainer action.

## Reporting-grid observation

The Reporting grid landing page displayed **9 of 23 packages** and explicitly
said lower-scoring entries were omitted from that comparison. The landing page
alone was therefore not sufficient evidence that AskLens was absent.

The signed-out all-packages view was also checked. It was paginated and
contained 20 distinct package links on page 1 and 3 on page 2. Pages 1 and 2
together accounted for the stated 23 entries. Neither returned page contained
`AskLens` or `django-asklens`.

On that bounded, complete public-grid check, the existing AskLens package
listing was not a Reporting-grid member as observed. This is not evidence of
endorsement, usage, permanent absence, rejection, or suitability for that grid.
The check did not inspect authenticated moderation state, hidden proposals, or
site-internal records. If the public count, pagination, or responses change, a
future reviewer must repeat the complete lookup rather than carrying this
absence conclusion forward.

## Operator-only follow-up

If the omission is still present and the Django Packages maintainers consider
AskLens appropriate for Reporting:

1. Sign in to Django Packages using the maintainer's own account; do not share
   credentials or automate account access.
2. Recheck the package listing metadata. If it is still stale, use the site's
   package-data refresh control and verify the signed-out page afterward.
3. Open the Reporting grid's site-provided edit/add-package flow, select the
   existing `django-asklens` package rather than creating a duplicate, and
   propose only factual comparison fields supported by current documentation.
4. Disclose maintainer affiliation where the site asks for it and follow the
   grid maintainers' moderation instructions.
5. Verify any resulting public state while signed out. If no edit control is
   available, use Django Packages' documented feedback/contact route and
   request review; do not bypass site permissions.

These are external writes and remain the operator's decision. No login,
metadata refresh, grid proposal, site edit, or contact request was attempted
while preparing this observation.
