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

Reviewed documents belong to the selected site and audit. They are displayed as
inert text, preserving the saved wording, and can be downloaded. Automated
findings and local drafting remain below the review documents. An audit with no
automated findings is not necessarily healthy; read its source limitations.

Reading a document, saving a draft or marking a recommendation reviewed does
not approve publication. Website implementation requires your separate explicit
approval of exact actions, including confirmed facts, current/proposed values,
validation and rollback. The app has no website publishing integration.

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
