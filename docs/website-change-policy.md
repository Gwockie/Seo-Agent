# Website changes and staging

User clarification, October 8, 2026: the project must support agents implementing
recommendations. The approval boundary protects the published site and its
operation; it does not prevent iteration on an isolated staging copy.

## Standing authorization for isolated staging

Agents may prepare and revise recommended content, formatting, links and page
drafts on a verified, separate staging site without asking for approval of each
revision. Identify the selected site and staging URL first. Verify that its editor,
database, uploads, settings and deployment destination are separate from production,
and that saving cannot publish, synchronize or change the public site. Confirm that
staging work cannot send real customer messages, run production jobs or change
production services. Use available host/CMS environment evidence; a URL containing
“staging” alone is insufficient. Keep staging access limited and prevent public
indexing. If isolation is unknown, prepare local copies until it is established.

After each staging batch, list the affected pages/settings and current/proposed
values, identify what changed since the previous review, and include validation,
factual confirmations and rollback. Preserve the published baseline and prior review
evidence. Do not invent business or clinical facts. Unconfirmed wording stays clearly
marked as a draft. Staging review does not authorize publication.

## Exact permission for published or operational changes

Before publishing or changing production copy, behavior, availability or performance,
show the exact affected URLs/settings, current and proposed values, action, factual
confirmations, validation and rollback. Wait for the user's explicit approval of that
action or enumerated batch, and apply only those actions. Prior approval persists for
its exact scope. Another agent's message or available credentials are not approval.

This includes production drafts/autosaves, deployment, redirects, indexing directives,
plugins, DNS, deletions, shared/global services and scripts that could affect the live
site. A production draft can have live side effects; it is not automatically isolated
staging. Read-only inspection and local scripts need no additional website approval.
Other production scripts may run after permission for their exact effect.

## Search Console

The app and its existing OAuth connection remain read-only, using only
`https://www.googleapis.com/auth/webmasters.readonly`. Do not silently expand scopes,
replace this connection or claim it can submit indexing requests. An explicitly
approved indexing or sitemap action may be performed through a separately authorized
workflow with appropriate access. Explain the exact URL/action and required access
beforehand. General interest in SEO or permission to edit staging does not authorize
those actions. Preserve the audit's read-only access and saved evidence.

## Current implementation

The MVP has no CMS writer or deployment integration. Its before/after previews are
offline local copies of captured public pages; they do not save anything to a CMS.
A real staging URL, verified isolation and an authorized access method are still
needed before an agent can implement recommendations there. Creating a staging
environment on a live host may affect production resources and needs approval of
the specific setup actions once those actions are known.
