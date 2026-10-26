# Django Packages read-only observation and operator steps

**Observed:** 2026-10-26 UTC, without logging in or changing external state.

## Observation

- The package listing exists at
  <https://djangopackages.org/packages/p/django-asklens/>. The public response
  identified `django-asklens` and linked its repository and package metadata.
- The Reporting grid landing page at
  <https://djangopackages.org/grids/g/reporting/> displayed 9 of 23 packages
  and explicitly said lower-scoring entries were omitted from that comparison,
  so the landing page alone was not sufficient evidence of absence.
- The public all-packages view at
  <https://djangopackages.org/grids/g/reporting/packages/> was therefore
  checked without logging in. Its paginated result contained 20 package links
  on page 1 and 3 on page 2; pages 1 and 2 together accounted for the stated 23
  entries. Neither returned page contained `AskLens` or `django-asklens`.

On that bounded, complete public-grid check, the existing AskLens package
listing was not a Reporting-grid member as observed. This remains a
point-in-time observation, not evidence of endorsement, usage, permanent
absence, or suitability for that grid. The lookup did not inspect authenticated
moderation state or hidden proposals.

## Operator-only correction

If the omission is still present and the Django Packages maintainers consider
AskLens appropriate for Reporting:

1. Sign in to Django Packages using the maintainer's own account; do not share
   credentials or automate account access.
2. Recheck the package listing metadata and use the site's package data refresh
   control if the visible public metadata is stale.
3. Open the Reporting grid's site-provided edit/add-package flow, select the
   existing `django-asklens` package rather than creating a duplicate, and
   propose only factual comparison fields supported by current documentation.
4. Disclose maintainer affiliation where the site asks for it and follow the
   grid maintainers' moderation instructions.
5. Verify the public result while signed out. If no edit control is available,
   use Django Packages' documented feedback/contact route and request review;
   do not bypass site permissions.

These are external writes and remain the operator's decision. No correction was
attempted from this repository task.
