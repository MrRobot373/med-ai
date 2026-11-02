# Security operations

What protects patient data in this product, what the clinic must do, and what to do when something goes wrong.

## What the product does

| Protection | Detail |
|---|---|
| Sign-in | Argon2 password hashes; 12+ character policy with a common-password block; lockout after repeated failures; absolute session length; one-click sign-out of other devices |
| Two-step verification | TOTP (authenticator app) + one-time recovery codes; **required for doctors and administrators in production** |
| Roles | Administrator · Clinician · Viewer · Front desk (front desk cannot read clinical content) |
| Transport | HTTPS through the bundled proxy; secure cookies; HSTS; strict content-security headers; no-store caching of API responses; CSRF checks |
| Uploaded files | AES-256-GCM encryption (set `DATA_ENCRYPTION_KEY`); type and size checks; optional ClamAV scan, **fail-closed** |
| Backups | AES-256-GCM encrypted; integrity-checked; production refuses to take an unencrypted backup |
| Audit trail | Every view, change, print, export, sign-in and administrative act, in a **tamper-evident hash chain** (`python -m app.cli audit-verify`) |
| Secrets | API keys stored encrypted under `APP_SECRET_KEY`; partner keys stored only as hashes |
| Partner access | Scoped, expiring, revocable keys; signed webhooks; no clinical content in messages by default |

## What the product cannot do (the clinic must)

- **Encrypt the disk.** The database file and search index sit on the volume; only disk encryption protects them if the machine is stolen. The installer checks and asks.
- **Keep the three keys safe, away from the server.** Lose them and encrypted data is unrecoverable; leak them and encryption is void.
- **Restrict physical and network access.** The server in a locked room; the LAN not shared with guests; no direct exposure to the internet. If remote access is needed use a VPN, never a port-forward.
- **Patch the server's operating system and Docker.** Apply updates monthly.
- **Remove access when people leave**, the same day.

## Keys: rotation and loss

- `APP_SECRET_KEY` rotation: `python -m app.cli rotate-secret <old> <new>` re-encrypts stored secrets, then change `.env` and restart.
- `DATA_ENCRYPTION_KEY`: files are encrypted individually; `python -m app.cli encrypt-existing` encrypts older plain files after a key is first set.
- `BACKUP_ENCRYPTION_KEY`: a backup needs the key it was made with. Keep every key that ever encrypted a backup you still hold.
- Suspected leak: rotate, re-run a backup, and treat the leaked key's backups as exposed.

## If you suspect a breach

1. **Contain**: unplug the server from the network (do not power it off — keep memory and logs); change the administrators' passwords from another machine; revoke API keys (Settings → Integrations).
2. **Preserve**: `docker compose logs app > incident-logs.txt`; copy the latest backup; note the time and what was seen. Run `python -m app.cli audit-verify` and keep its output (a broken chain is evidence).
3. **Assess** with the audit log (Settings → Audit): which accounts, which patients, which exports.
4. **Notify**: your lawyer and insurer first; then — if personal data was affected — the Data Protection Board and affected people as the law requires (DPDP Act), and **CERT-In within six hours** for a cyber incident of the types it lists. See `compliance/INCIDENT_RESPONSE.md`.
5. **Recover** from a backup made before the incident, change every key, and write down what happened.

## Reporting a vulnerability

Security reports go to the vendor's security contact (set in the support agreement). Include the version and steps; do not include patient data. Expect acknowledgement within two working days.
