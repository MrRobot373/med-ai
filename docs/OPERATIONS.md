# Operating GMS Clinical AI

For the clinic's administrator and technician. Everything here is done from the folder where the product was installed.

## Daily / weekly / monthly

| When | What | Where |
|---|---|---|
| Daily (automatic, 02:00) | Encrypted backup | Settings → Backups. A banner appears for administrators if the last backup is over 36 hours old |
| Weekly | Copy backups off the server | `./backup-offsite.sh <destination>` (cron) |
| Monthly | **Check a backup** (opens it and verifies every file) | Settings → Backups → *Check*. The security checklist turns red after 35 days without one |
| Monthly | Read the security checklist | Settings → System status |
| Quarterly | Test a full restore on a spare machine | Section "Restoring" below |
| When staff change | Deactivate leavers the same day; reset two-step verification for lost phones | Settings → Users |

## Status in one command

`docker compose exec app python -m app.cli status` — licence, usage, last backup, audit-log integrity.
`docker compose exec app python -m app.cli doctor` — configuration and surroundings (disk space, keys, AI server, scanner, clock).

## Updating

1. You receive `gms-clinical-ai-<new version>.tar.gz` and its `.sha256` file.
2. **Outside clinic hours** (about five minutes of downtime): `./update.sh gms-clinical-ai-<new version>.tar.gz`
3. The script checks the file is untampered, stops the application, takes an encrypted backup and **proves it can be opened**,
   loads the new version, starts it and waits until it is healthy.
4. **If the new version does not start properly, the script puts the previous version back and restores the backup
   automatically.** Nothing is lost; the failed attempt's data is moved aside, not deleted.
5. Later, if a problem appears that the health check could not see: `./rollback.sh` (same safety, manual).
   Anything entered *after* the update is not in the restored data — decide quickly; do not wait days.
6. After an update that changes medical content, the clinic's reviewer must sign again (Settings → Clinical content).

## Restoring from a backup

Restore replaces everything with the chosen backup, so it is done on the server with the application stopped:

```
docker compose stop app
docker compose run --rm app python -m app.cli backup-list
docker compose run --rm app python -m app.cli restore gms-backup-20261102-020000.gmsbak --yes
docker compose start app
```
You need the same `APP_SECRET_KEY` and `BACKUP_ENCRYPTION_KEY` as when the backup was made. The data it replaced is moved to
`data/before-restore-<time>` — delete it once you are satisfied. If the search index was not in the backup, run a re-index (Settings → Retrieval).

**Disaster recovery (server lost):** install on a new machine (`./install.sh`), copy a backup file into `data/backups/`,
put the *old* keys into `.env` (replacing the new ones before first sign-in), restore as above. Expect an hour.

## Licence

Settings → Licence & usage shows the Installation ID, what the licence allows and what is used. **A lapsed licence never stops
patient care**: everyone keeps working; only adding *new* people or branches is blocked until renewal. Without a licence the
installation is in *evaluation* (2 doctors, 2 other users, 1 branch) in production. The usage report is counts only.

## Troubleshooting

| Symptom | Do |
|---|---|
| Browser says the connection is not private | Install the clinic root certificate on that computer (INSTALL.md §3.2) |
| Cannot sign in, "too many attempts" | Wait 10 minutes. A locked account: Settings → Users → ⋯ → Unlock, or `python -m app.cli unlock <email>` |
| Doctor lost their phone (two-step) | Settings → Users → ⋯ → Reset two-step verification |
| AI features say the model is unreachable | Settings → AI models → *Test*; check the Ollama machine and the address; the rest of the system keeps working |
| Uploaded reports stay "processing" | They resume automatically after a restart; or open the document → *Reprocess* |
| Disk nearly full | `doctor` shows free space; delete old `data/before-restore-*` folders and old backups; add disk |
| "No such table" from a command | The application has never started on this data folder: `docker compose up -d` first |
| Something else | `docker compose logs --tail 200 app` and send it to support |

## Support information to collect

Product version (`cat VERSION`), `status` and `doctor` output, the last 200 log lines, what the person was doing. **Never send `.env`,
backup files or patient information** — use the screen-share or the logs.
