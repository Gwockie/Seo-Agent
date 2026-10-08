# Approved local storage policy

The user approved optional disk encryption for this single-user app on their
protected Windows computer. This supersedes encryption requirements in the
initial MVP plan and historical handoffs. It does not waive folder access checks,
credential safeguards or website approval requirements.

Live setup, collection, legacy imports and local backup/restore require verified
Windows access restricted to the current user, SYSTEM and Administrators on every
existing entry. Reparse points, unreadable entries and incomplete checks still
fail closed. A missing workspace is not itself verified. The app never changes
permissions, enables encryption or changes machine-wide settings automatically.

`storage-check` reports encryption separately. Unverified EFS/BitLocker does not
block local operation when access passes. To check encryption as well:

```powershell
.\.venv-mvp\Scripts\python.exe -m seo_agent storage-check --path secrets --require-encryption
```

Ordinary SQLite, CSV, Markdown and ZIP files may be unencrypted. Local backups
must pass the same access check and exclude credentials. Before copying evidence
or backups off this computer, select appropriate protected storage; a ZIP file is
not encryption. Original legacy credentials remain unchanged during migration.

New Google credentials still require the validated Windows Vault backend, its
payload limits and exactly `webmasters.readonly`; there is no plaintext fallback.
The browser stays on loopback with CORS/XSRF protection and disabled telemetry.
There is no separate app sign-in. Other software running as the same Windows user,
administrators, malicious local software and app defects remain risks. This policy
reduces exposure; it does not promise zero risk.

Changing folder permissions is a separate, reviewable local action. Keep a local
rollback record and verify original file hashes when restricting historical
evidence. Account and exact property access must still pass read-only validation
before a live audit can be reported as verified.
