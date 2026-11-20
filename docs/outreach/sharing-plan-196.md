# #196 sharing plan — unexecuted, not permission to post

**Observed/reviewed:** 2026-11-20 UTC. **Status:** repository drafts only. No
post, submission, contact, recruitment, account automation, listing/grid edit,
release or site deployment has been made for #196. The creator/maintainer is
Revaz Zakalashvili; substantial AI assistance was used. This plan reuses the
[#168 Forum draft](django-forum-show-and-tell-draft.md),
[#168 News draft](django-news-draft.md),
[existing Packages observation](django-packages-observation.md),
[#169 packet](awesome-django-submission-packet.md) and
[#166 showcase](../showcase.md), not a new generic submission packet.

## What would be shared

The [practical integration article](../integration-article.md), not a launch
announcement: explicit host registration, private bindings, permission-filtered
metadata, current-request facade revalidation, and four installed-candidate
outcomes (success, empty, opaque denial, invalid provider plan). Its
[evidence record](../article-evidence-196.md) separates public `0.3.2` from newer
source/candidate material and records offline replay limits. Use the existing
captioned showcase only as a **different synthetic demo**, never as a screenshot
of these CLI outputs. There are no human-study, representative-application,
adoption or live-model findings to share.

Before even selecting an external action: resolve private maintainer triage,
independent exact-head review, CI/docs checks and factual/link review. The owner
must edit the AI-assisted text into their own voice, keep creator affiliation,
alpha, synthetic-data and exact-question disclosures, then separately authorize
the exact channel, text and action. A repository PR is not that authorization.

## Current authoritative public rules and channel disposition

Method: bounded, signed-out, read-only public HTTPS GETs, without cookies,
accounts, submission controls or provider requests. The dates below describe
observations, not permanent permissions. No private/editor-only rules were
available. The Forum terms restrict automated access: after reading that rule,
no further programmatic Forum requests were made; future rechecks must use the
maintainer's ordinary browser and respect those terms. Do not automate posting
or claim that a technically reachable endpoint is an approved submission route.

| Channel | Authoritative URLs read on 2026-11-20 UTC | Observed rules / actionable disposition |
| --- | --- | --- |
| Django Forum, Show & Tell | [category](https://forum.djangoproject.com/c/projects/11), [category description](https://forum.djangoproject.com/t/about-the-show-tell-category/229), [guidelines](https://forum.djangoproject.com/guidelines), [terms](https://forum.djangoproject.com/tos), linked [Django Code of Conduct](https://www.djangoproject.com/conduct/) — all HTTP 200 | Category invites showing Django projects and feedback. Guidelines require the right category, a single topic rather than duplicate cross-posts, and rights to contributed content. Terms prohibit advertisements/solicitations, false DSF affiliation/endorsement, automated access and circumvention. CoC requires honest, kind participation, consent/privacy and source credit, and restricts promotion outside community norms. **Conditional candidate, not cleared:** owner must determine that the practical, non-advertising article-led variant fits those rules. If not clear, keep blocked; this plan does not authorize moderator contact to seek an exception. No recruitment, mailing-list collection, star request or repeated promotional bump. |
| Django News | [homepage](https://django-news.com/) — HTTP 200, Buttondown-hosted newsletter; [previously guessed submit URL](https://django-news.com/submit/) — HTTP 404 | Homepage exposed subscription, archives, sponsorship, jobs and podcast links, not a discoverable public editorial submission route/rules. Sponsorship is not a content-submission route. **Blocked pending an authoritative editorial route/rules recheck.** Do not invent length/eligibility rules, guess editors' addresses or send the draft unsolicited. Keep the short article summary ready only for later human review. |
| Django Packages | [help](https://djangopackages.org/help/), [terms](https://djangopackages.org/terms/), [acceptable use](https://djangopackages.org/acceptable-use/) — all HTTP 200 | Help describes package/grid creation; terms require human accounts and accurate community-relevant content. AUP prohibits spam, unrelated promotion, affiliation misrepresentation, fake accounts, excessive automated requests and scraped-data spam. **Not an article distribution channel; no mutation planned.** Reuse the existing listing if later authorized maintenance is needed, never create a duplicate or use a grid as an advertisement. The 2026-11-12 listing/grid observation remains historical; no current membership, freshness or absence claim is made here. |
| Awesome Django | Current [contribution rules](https://github.com/wsvincent/awesome-django/blob/main/contributing.md) and [required template](https://github.com/wsvincent/awesome-django/blob/main/.github/pull_request_template.md), read via their corresponding signed-out `raw.githubusercontent.com` URLs — HTTP 200 | Still asks for six months' active maintenance, traction (template says under 100 stars does not qualify), stable release history, clear documentation and demonstrated community value; requires complete template, factual description, correct ordering and AI disclosure. **Blocked under #169**, not selected for #196. That packet's dated age/star observations are not refreshed counts. Repository creation on 2026-07-03 is still less than six months before this observation; alpha history and uncollected adoption evidence cannot be relabelled to satisfy qualitative criteria. No fork/PR/contact/exception request. |

Response-byte SHA-256 identifiers for the rule observations (HTML bytes include
site chrome and can change independently of the rules):

| Source | SHA-256 |
| --- | --- |
| Forum category description | `8185f7e502d8e2c673e35efaf79e8b10af0a3cc0b3f125be33e0f7a13fb7df86` |
| Forum guidelines | `db0ee11437641865e57ace16b4bef299403feb67c5ab174aa0b2f1129e6c15fc` |
| Forum terms | `df0487eeac3f4b820cef9582b46a40d190277894d5ee9d171313be640aab1c70` |
| Django Code of Conduct | `99be9d4b6a71c9a04bc7d1bd7a22f932f048f210979241ab08bf8ee74ddbdfa6` |
| News homepage | `3020f1994646b63f38b1b18184da7e49760e90f664186ff8671f93b87762c25d` |
| Packages help | `e6ded64e348d117bee1c1a383d1fc0666d7d3dc7f81ec649a558ef3d8cc329d7` |
| Packages terms | `7935d3539c23e2b1b0644882b0150a643cb21b96ed89611a3cf0deddeab6b827` |
| Packages AUP | `f2ed490cc887c26218d3de85eff4439adea35e0777378cd2c509759e6428255c` |
| Awesome contribution rules | `723ab6870d5d62e4376756cf0138abc59935e90c5c68bb8a559d82afd8e8a24b` |
| Awesome PR template | `c5366414f6d8c1fcfdb48bbe728358c9662a61501baedeac33f371f2ff7a12f2` |

These are observation identifiers, not archived rule guarantees or evidence of
editor/moderator acceptance. No raw external errors or private content are
retained in this packet. If a future lookup fails or a rule is unclear, that
channel is blocked pending recheck—not presumed compliant.

## Concrete sequence, only after separate authorization

1. **Owner review:** use the article-led sections in the existing Forum/News
   drafts. Resolve review/triage gates; recheck the then-current rules signed out
   in a normal browser. Confirm every claim against the exact merged source and
   candidate evidence, not mutable `main` alone. Retain the public artifact hash
   link and do not describe an unreleased fix as public `0.3.2` behavior.
2. **Choose one educational conversation:** if permitted and explicitly
   authorized, manually preview one Show & Tell topic using the existing Forum
   title and article-led variant. Link the GitHub article at the exact reviewed
   commit unless a separately authorized deployment makes a checked public
   article URL available. Keep code readable; link the accessible showcase
   rather than uploading unverified new media. If a rule would treat it as
   advertising, stop. No automatic cross-post campaign.
3. **Keep News blocked:** do not send its article summary until an authoritative
   editorial route and current rules are found and the owner authorizes that
   exact submission. If the editor later supplies field limits, shorten the
   existing summary without losing disclosures; do not manufacture compliance.
4. **Do not act on Packages/Awesome:** no listing refresh, grid addition or
   Awesome submission is required to complete #196. Their existing packets
   remain historical/deferred and do not become approved by this plan.
5. **Record only real actions:** after an actually authorized human post, record
   date, exact submitted text/revision and public URL separately. Until then the
   action ledger is **none performed**. No promised stars, adoption, responses
   or endorsement; no automated replies, scraping, recruitment or unsolicited
   follow-up. Any future feedback must be consented/sanitized and is not a #193
   session merely because it is public.

Completion of #196 means a reviewed article and an honest, concrete **unexecuted**
plan. It does not require distribution. This maintainer packet stays out of the
rendered docs/search and Python artifacts under the existing exclusions.
