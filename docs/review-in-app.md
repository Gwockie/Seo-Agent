# Reviewing together in the app

Double-click **Start SEO App.cmd** in the project folder, keep its window open,
and open [the local app](http://127.0.0.1:8502) on this Windows computer. The
launcher uses the existing environment and guarded local server; it does not
install software or expose the app to other computers. If the app is already
running at that address, use that browser page rather than starting another
server. This starter uses port 8502 to avoid the older development app; the CLI's
default port remains 8501.

1. Select your practice in the sidebar.
2. Open **Recommendations & changes** and select the saved audit.
3. In **Review together**, start with **Summary**, then **Recommendations**.
4. When you are ready, choose **Proposed edits**. Check the existing and proposed
   wording together and confirm the clinical facts that the report flags.

Reviewed documents belong to the selected site and audit. Headings, emphasis,
lists and tables are formatted safely; imported HTML, images and links remain
inert text. Original wording is available in **Original report text** and downloads. Automated
findings and local drafting remain below the review documents. An audit with no
automated findings is not necessarily healthy; read its source limitations.

Reading a document, saving a draft or marking a recommendation reviewed does
not approve publication. Agents may iterate on a verified isolated staging copy
and report each batch. Published or production-impacting changes require your
separate explicit approval of exact actions, including confirmed facts,
current/proposed values, validation and rollback. See
[the current change policy](website-change-policy.md). The app has no website
publishing integration.

## Appearance and page comparisons

Saving a new site automatically makes a bounded read-only attempt to import its
public colors and typography. **Setup → Site appearance → Refresh site appearance**
repeats that attempt. Each site's appearance is stored independently and included
in protected backups. Fonts are local copies; external styles and scripts are not
loaded into the app. If public access is blocked, Setup displays the cause and the
app uses a readable fallback. A successful styling capture does not establish a
complete SEO crawl.

For an audit with prepared page copies, **Proposed edits** includes **Page to
compare**, **Page display** and **Highlight differences**. Side-by-side copies show
the captured page and proposed wording. Use **Before** or **Proposed** for a larger
view. Red/green marks indicate removed/added words; gold outlines identify changed
link destinations. Browser titles are shown above the pages. The exact-action
packet below includes factual confirmations, validation and rollback.

Copies are static captures at the displayed screen width, with locally stored fonts/images. Scripts,
forms, active links and unsupported decorative elements are omitted. They cannot
access app credentials or contact outside services. Current values must match
the capture before a proposal can render. Capture dates stay visible; they are
historical evidence, not a promise that the live page is still unchanged. No
external staging or publication occurs. Page copies are supplementary evidence;
they do not change an audit's source status or earlier reports.

The original practice has no separate hosted staging site, as confirmed by the
user on October 8. Its local copies provide the review surface without a hosting
upgrade. Seven exact proposed actions across three captured pages are shown;
the proposed therapy contact addition remains in the written draft because its
precise insertion point has not been verified. Other sites need their own page
captures and exact proposals; they do not receive the practice's recommendations.
The latest capture uses a narrow layout for readability in the app panel. Earlier
desktop captures remain available through **Saved page capture** and are retained
in backups. New captures/proposals use new revisions rather than overwriting the
earlier page evidence. **Proposed** is the initial display; choose **Before** or
**Side by side** to compare.

The appearance/preview update passed **82 tests**, including eleven Streamlit
AppTest scenarios, in 23.242 seconds. Checks cover site/audit separation, current
value matching, inert report markup, empty iframe sandbox permissions, external
resource removal, character preservation across iframe wrappers, preservation of inline wording and surrounding page structure, capture revisions,
and credential-free backup/restore of appearance and preview artifacts. Runtime
dependencies and lock files did not change.

## Setup checkpoint: October 8, 2026

Restricted folder access, the original practice's exact Google property and
Windows Vault connection are verified. Historical evidence and the first live
Google collection are saved locally. A separate protected restore of the backup
preserved all three audits and all 72 evidence files; restored Google selections
were detached and the working connection remained unchanged.

The remaining collection blocker is the website's response to automated access.
A bounded read-only check found HTTP 202 and CAPTCHA-related HTML at
`robots.txt`, rather than completed crawler instructions. Collection stopped
without solving a CAPTCHA or changing website/security settings. The crawler now
rejects incomplete non-200 responses rather than interpreting them as rules.
The saved audit remains partial; its existing evidence and reports were not
rewritten.

The review-screen regression checks cover literal untrusted text, switching
documents, switching audits and sites, and unchanged change/approval records.
The full suite passed **65 tests** in 17.856 seconds, including eight Streamlit
AppTest scenarios. Dependency consistency, compilation and whitespace checks
passed. Dependency versions and locks did not change. A final recursive check
verified restricted access to the restored files and all private roots; all 49
original files remain unchanged.
The one-click starter was exercised against the actual configured workspace.
Socket inspection verified `127.0.0.1:8502`, and the browser displayed the saved
partial audit, all three review choices and its reviewed summary. The current app
was left available for the user; the older development server was not changed.

The next technical step is for whoever manages the website's hosting/security to
inspect why requests to `robots.txt` receive that response. Ask for a read-only
diagnosis first. Any proposed security setting change needs its own exact-action
approval. After a completed response is available, run a fresh bounded audit
without overwriting the old one. This collection issue does not prevent reviewing
the available Google evidence together.

The user identified SiteGround as the host. A concrete support request is:
“Please investigate why read-only requests to our site's `/robots.txt` using
`LocalSEOAudit/2.0 (authorized read-only audit)` receive HTTP 202 and challenge
HTML instead of a completed robots response. Please diagnose the cause first and
describe any proposed setting changes before making them.” No support request was
sent and no hosting/security setting was changed by this work.
