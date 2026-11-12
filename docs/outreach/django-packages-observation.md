# Django Packages read-only observation and operator steps

**Observed:** 2026-11-12 UTC (read-only checks completed at approximately
15:24 UTC), without logging in or changing external state.

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

Every listed URL returned HTTP 200 in the signed-out check.

## Package-listing observation

The package listing exists and identified `django-asklens`. It linked the
project's GitHub repository, documentation, and PyPI project. The public
release-data endpoint included both `0.3.2` and `0.3.1`, so the earlier
point-in-time stale-version observation no longer applies. This establishes only
that the public Django Packages response exposed those release labels; it is not
an endorsement, usage signal, security review, or guarantee that every metadata
field is current.

No fetch/refresh control was used. The listing was already sufficient for this
read-only observation, and using that control would change external state and
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
2. Recheck the package listing metadata. Use the site's package-data refresh
   control only if visible metadata has become stale, then verify the signed-out
   page afterward.
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
