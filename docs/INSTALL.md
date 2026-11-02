# Installing GMS Clinical AI on the clinic's server

For the technician. Allow **one hour** for the install and **one more** for the first-day checks.

## 1. What you need

| | Minimum | Recommended |
|---|---|---|
| Server | 4 CPU cores, 8 GB memory, 50 GB free disk | 8 cores, 16 GB, SSD, 200 GB |
| Operating system | Ubuntu 22.04/24.04 or Debian 12 (other Linux works), Windows 11 Pro / macOS with Docker Desktop for a small trial | Ubuntu LTS |
| Software | Docker Engine 24+ with Compose v2 | |
| Network | A fixed address on the clinic LAN (e.g. `192.168.1.10`). **No internet is needed after install** | UPS on the server |
| AI models | A machine running **Ollama** (or any OpenAI-compatible server) reachable from the server. The AI features need a GPU for good speed; everything else works without | NVIDIA GPU with 16–24 GB for the 27B clinical model |
| Disk encryption | **Encrypt the disk or volume that holds the data** (LUKS on Linux, BitLocker on Windows). The installer checks | Required for real patient data |

## 2. Install

1. Copy `gms-clinical-ai-<version>.tar.gz` to the server (USB drive is fine) and check it:
   `sha256sum -c gms-clinical-ai-<version>.tar.gz.sha256`
2. `tar -xzf gms-clinical-ai-<version>.tar.gz && cd gms-clinical-ai-<version>`
3. `./install.sh`

The installer: checks CPU, memory, disk, ports 80/443, the clock and disk encryption; asks for the clinic name, the
administrator's name and email, the address people will type, the time zone and where the AI server is; creates the
clinic's own secret keys; loads the product; starts it; waits until it is healthy; runs a final check; and prints the
web address and the administrator's one-time password. Re-running it is safe: it never replaces existing keys.

Non-interactive (for scripted installs):
`./install.sh --yes --org "Life Care Medico" --admin-email dr@lifecare.in --site clinic.local --disk-encrypted`

## 3. Do these on day one (the installer reminds you)

1. **Store the three keys** from `.env` (`APP_SECRET_KEY`, `DATA_ENCRYPTION_KEY`, `BACKUP_ENCRYPTION_KEY`) in a password manager
   or a printed sheet kept in a safe — **not only on the server**. A restored backup cannot be read without them.
2. **Trust the certificate.** Browsers warn until each computer trusts the clinic's own certificate authority:
   `docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt ./clinic-root-ca.crt`, then install that file as a
   *trusted root certificate* on every clinic computer (Windows: double-click → Install → Local Machine → Trusted Root
   Certification Authorities). Or put the clinic's own certificate in `./certs` and set `TLS_ARGS=/certs/clinic.crt /certs/clinic.key` in `.env`.
3. **Sign in** as the administrator: choose your own password, then set up **two-step verification** (an authenticator app on your phone).
4. **Settings → Licence & usage**: send the *Installation ID* to your supplier; install the licence file you receive.
5. **Settings → AI models**: point to the AI server and press *Test*.
6. **Settings → Letterhead & print**: clinic name, address, phone, footer; check the preview. **Settings → Branches** if more than one site.
7. **Settings → Users**: add the doctors (each must add their **registration number** in Profile) and front desk.
8. **Settings → Backups**: run **Back up now**, then **Check** it. Set up the off-site copy (below).
9. **Settings → Clinical content**: the clinic's senior doctor (and a pharmacist) review and sign. See `CLINICAL_GOVERNANCE.md`.
10. Settings → *System status*: the **Security checklist** should be green; each red line says what to do.

## 4. Optional parts

Set `COMPOSE_PROFILES` in `.env` (comma separated) then `docker compose up -d`:
`clamav` (virus-scan every upload; also set `CLAMAV_HOST=clamav`) · `qdrant` (dedicated vector database for large clinics) ·
`ollama` (run the AI models in a container on this server; needs an NVIDIA GPU and its container toolkit).

## 5. Off-site backup copy

`./backup-offsite.sh /mnt/usb-drive` copies new encrypted backups to a second place and keeps the newest 30. Schedule it:
`crontab -e` → `0 3 * * * /opt/gms/backup-offsite.sh /mnt/usb-drive`. A backup on the same disk does not survive that disk failing.

## 6. Moving patients in from the old system

*Patients → Import*: an Excel or CSV file with a heading row. The wizard maps columns, flags rows that are missing a
name, have a bad date or look like patients already registered, and saves nothing until you confirm. Patients without
an MRN are numbered automatically. Then *Patients → Duplicates* lists charts that look like the same person, and
merging moves everything into one.

## 7. Uninstall / move to another server

Back up, copy the folder and the data folder to the new server, run `./install.sh` (it keeps the existing `.env`), then
`docker compose run --rm app python -m app.cli restore <backup file> --yes`.
