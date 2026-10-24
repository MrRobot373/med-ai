# Deploying GMS Clinical AI on a local server (demo and manual testing)

This guide takes a fresh Linux server on your office network to a working GMS Clinical AI with the
Life Care Medico demo data, so doctors and testers can open it from their own computers. Follow
the parts in order. Each step says what to run and what you should see.

There are two ways to run it. Pick one in **Part 2**:

| | Option A — Docker (recommended) | Option B — directly on the server |
|---|---|---|
| Best for | Demos, testing, keeping the server clean | Developers who want to edit and debug code |
| Installs | Docker only | Python 3.12, Node 22, build tools |
| Updates | Rebuild the image | `git pull` and restart |

And two ways to provide the AI. Pick one in **Part 4**:

| | Test AI (mock) | Real models (Ollama) |
|---|---|---|
| Needs | Nothing extra | A GPU server (16–24 GB VRAM for MedGemma 27B; 8 GB for smaller models) |
| AI answers | Assembled from the patient's own data, no reasoning — **interface testing only** | Real clinical reasoning |
| Use for | Click-through demos, UI testing, training front-desk staff | Doctor evaluation of the AI itself |

Everything except the AI answers is real in both cases: report reading, lab value extraction,
the India formulary safety checks, scores, orders and matching all run on the server.

---

## Part 1 — Prepare the server

### 1.1 Hardware and OS

| | Minimum (test AI) | With real models on the same machine |
|---|---|---|
| OS | Ubuntu 22.04 / 24.04 LTS (64-bit) | same |
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 32 GB |
| Disk | 20 GB free | 80 GB free (models are large) |
| GPU | not needed | NVIDIA, 24 GB VRAM for `medgemma:27b`, 8 GB for `medgemma:4b` / `qwen3.5:9b` |

Give the server a **fixed IP address** on your network (for example `192.168.1.50`) in your router
or with your IT team, so everyone can reach it at the same address every day.

### 1.2 Update the server and install basics

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install git curl ca-certificates ufw
```

### 1.3 Get the code

```bash
sudo mkdir -p /opt/gms && sudo chown $USER:$USER /opt/gms
cd /opt/gms
git clone https://github.com/MrRobot373/med-ai.git
cd med-ai
git checkout claude/admiring-ride-a15jgs     # the branch with the Life Care Medico demo
```

Check: `ls` shows `backend  frontend  patient-files  knowledge-packs  docker-compose.yml …`

---

## Part 2 — Install and start the app

### Option A — Docker (recommended)

**A.1 Install Docker**

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker                 # or log out and back in
docker --version && docker compose version
```

**A.2 Create the settings file**

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Open `.env` (`nano .env`) and change:

```ini
APP_ENV=demo
APP_SECRET_KEY=<paste the long random value printed above>
BOOTSTRAP_ADMIN_EMAIL=admin@lifecaremedico.in
BOOTSTRAP_ADMIN_PASSWORD=<choose a strong password>
BOOTSTRAP_ADMIN_NAME=Vikram Shah
```

Leave `DATA_DIR` as it is; Docker overrides it to `/data` inside the container.

**A.3 Build and start**

For a demo with the test AI (no GPU):

```bash
docker compose build                      # 5–10 minutes the first time
docker compose --profile mock up -d       # starts the app and the test AI
docker compose ps                         # both should show "running"; app becomes "healthy" in ~30 s
```

For real models running on this same server, see Part 4 first, then:

```bash
docker compose build
docker compose up -d                      # the app talks to Ollama on the host
```

Check: `curl http://localhost:8000/api/health` prints `{"status":"ok", …}`.

### Option B — Directly on the server

**B.1 Install Python 3.12 and Node 22**

```bash
sudo apt -y install python3 python3-venv python3-dev build-essential
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt -y install nodejs
python3 --version     # 3.11 or newer
node --version        # v22.x
```

**B.2 Install dependencies and create `.env`**

```bash
scripts/setup.sh
```

This creates `backend/.venv`, installs the Python and JavaScript packages and writes `.env` with
a fresh secret key. Then edit `.env` as in step A.2 (set `APP_ENV=demo` and the admin password).

**B.3 Start it**

With the test AI:

```bash
scripts/demo.sh --mock
```

With real models (after Part 4):

```bash
scripts/demo.sh
```

`demo.sh` builds the web app, loads the demo data (Part 3) and serves on port 8000. It stays in the
foreground; to keep it running after you log out, use the service in **Part 7**.

---

## Part 3 — Load the Life Care Medico demo data

The demo data is 4 staff accounts and the 15 patient folders in `patient-files/` (83 documents:
lab reports, X-rays, ultrasound, CT and MRI, ECGs, discharge summaries, outside prescriptions),
plus five patients booked on today's list.

**Docker:**

```bash
# With the test AI, point the app at it first (once):
docker compose exec app python -m app.seed use-mock-ai http://mock-ai:9100/v1
# Then load the data (2–5 minutes; it reads every report):
docker compose exec app python -m app.seed demo
```

**Directly on the server:** `scripts/demo.sh` already did this.

Check: the last lines say `[83/83] … → ready`. If some say `failed`, the AI endpoint was not
reachable; fix Part 4 and run the seed command again, or use `python -m app.seed reprocess`.

**Today's list:** appointments are booked for the day you seed. To put the five patients back on
the list on another day:

```bash
docker compose exec app python -m app.seed today        # Docker
cd backend && .venv/bin/python -m app.seed today        # directly
```

**Start again from scratch** (deletes all data, including anything testers entered):

```bash
docker compose down && docker volume rm med-ai_gms-data && docker compose --profile mock up -d   # then Part 3 again
# directly: stop the app, then:  rm -rf data/  and run scripts/demo.sh --mock
```

---

## Part 4 — The AI

### 4.1 Test AI (no GPU)

Nothing more to do: `--profile mock` (Docker) or `demo.sh --mock` started it and the seed command
pointed the app at it. Remember it is **not** a model; tell demo audiences the AI text is placeholder.

### 4.2 Real models with Ollama (GPU)

On the GPU server (the same machine, or another one on your network):

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull medgemma:27b            # clinical reasoning (~17 GB); medgemma:4b on smaller GPUs
ollama pull qwen3.5:9b              # chat, summaries and reading scanned pages
ollama pull qwen3-embedding:0.6b    # search index
```

If Ollama runs on a **different** machine, let it listen on the network:
`sudo systemctl edit ollama` → add
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```
then `sudo systemctl restart ollama`.

Then in the app, signed in as admin: **Settings → AI models**

1. Language model: provider **Ollama**, base URL `http://host.docker.internal:11434` (Docker, Ollama
   on the same machine), `http://localhost:11434` (directly on the server) or
   `http://<gpu-server-ip>:11434`. Model `qwen3.5:9b`. **Test**, then **Save**.
2. Clinical reasoning model: `medgemma:27b`, timeout 600 s. **Test**, **Save**.
3. **Settings → Embeddings & reranking**: Ollama, same base URL, `qwen3-embedding:0.6b`. **Test**, **Save**.
4. If you switched from the test AI after seeding, click **Reindex** on the embeddings page so
   the search index is rebuilt with the real embedding model.

---

## Part 5 — Open it from other computers

### 5.1 Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8000/tcp
sudo ufw enable
sudo ufw status
```

Now open `http://192.168.1.50:8000` (your server's IP) from any computer on the same network.

### 5.2 Accounts

| Person | Role | Email | Password |
|---|---|---|---|
| Dr. Ananya Rao | Doctor | `ananya.rao@lifecaremedico.in` | `Clinic@2026` |
| Meera Pillai | Front desk | `meera.pillai@lifecaremedico.in` | `Desk@2026` |
| Vikram Shah | Administrator | `admin@lifecaremedico.in` | the password you set in `.env` |
| Rahul Menon | Read-only | `rahul.menon@lifecaremedico.in` | `Audit@2026` |

Change these passwords in **Settings → Users & roles** before giving testers access. Create a personal
account for each tester there too, so the audit log shows who did what.

### 5.3 Optional: a friendly name and HTTPS

For a name like `https://gms.lifecare.local`, put Caddy in front:

```bash
sudo apt -y install caddy
sudo tee /etc/caddy/Caddyfile >/dev/null <<'EOF'
gms.lifecare.local {
    tls internal
    reverse_proxy 127.0.0.1:8000
}
EOF
sudo systemctl reload caddy
sudo ufw allow 443/tcp
```

Point `gms.lifecare.local` at the server's IP in your router's DNS (or each computer's hosts file),
set `COOKIE_SECURE=true` in `.env`, and restart the app. Browsers will warn about the internal
certificate once; accept it or install Caddy's root certificate on the test machines.

---

## Part 6 — Manual test plan (about 30 minutes)

Run this after every deployment. Tick each line.

**Front desk** (sign in as Meera)
- [ ] Home shows *Today's list* with 5 patients; mark Harish Chandra Gupta as arrived.
- [ ] Open Rohit Verma → upload `patient-files/01 - Rohit Verma (LCM-10231)/To upload/…USG Abdomen and Pelvis report….pdf`. It is filed as an imaging report with *Identity verified*.
- [ ] The *Assistant* menu is not visible; opening `/assistant` sends you back home.

**Doctor** (sign in as Dr. Ananya Rao)
- [ ] Dashboard greets you and lists today's patients with *result back* and *abnormal* counts.
- [ ] Rohit Verma → **Overview**: chest X-ray in the viewer, *Glycaemic control 8.1 %*, creatinine 1.36 *Above range*.
- [ ] **Consultation** → *Prepare brief* produces a brief; *Start consultation*; type notes, vitals and the diagnosis *Acute gastritis*; *Check diagnosis* gives a second look.
- [ ] *Write prescription*: **Pan-D** fills *1 cap · OD*; **Meftal-Spas** shows cautions (BPH, aspirin); **Septran DS** shows a red **Stop & check — Allergy: Sulfa drugs**.
- [ ] Remove Septran DS → *Finalise prescription* → *Print* shows the Life Care Medico letterhead.
- [ ] *Order test* "USG abdomen and pelvis". If the front desk already uploaded the report, the order shows *Result back*; otherwise upload it now and refresh.
- [ ] *Read report against the question* lists the impression (cholelithiasis, fatty liver, prostatomegaly); *Mark reviewed*.
- [ ] Kavita Joshi → **Results**: creatinine 1.30 → 1.45 → 1.62, eGFR 46 → 41 → 36. **Overview** shows *CKD stage G3b A3*.
- [ ] Kavita Joshi → **Assistant**: ask "How has her kidney function changed?" — the answer has citation chips that open the source report.
- [ ] Harish Chandra Gupta → **Overview**: echo report in the viewer, CHA₂DS₂-VASc 3 *Anticoagulation recommended*.
- [ ] Suresh Babu Reddy → **Reports & imaging** → *CT brain – axial* opens in the viewer; zoom works.

**Administrator** (sign in as Vikram Shah)
- [ ] **Settings → AI models → Test connection** succeeds.
- [ ] **Settings → Users & roles** lists the four accounts; create and disable a test account.
- [ ] **Audit log** shows the actions above.

**Read-only** (sign in as Rahul Menon)
- [ ] Can open charts; there is no *Register patient*, *Upload* or *Write prescription*.

Note anything that looks wrong with the patient name, the page and a screenshot.

---

## Part 7 — Keep it running

**Docker** restarts the containers automatically after a reboot (`restart: unless-stopped`).

**Directly on the server**, run it as a service instead of `demo.sh`:

```bash
sudo tee /etc/systemd/system/gms.service >/dev/null <<EOF
[Unit]
Description=GMS Clinical AI
After=network.target

[Service]
User=$USER
WorkingDirectory=/opt/gms/med-ai/backend
EnvironmentFile=/opt/gms/med-ai/.env
ExecStart=/opt/gms/med-ai/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now gms
sudo systemctl status gms
```

For the test AI as a service, create `gms-mock.service` the same way with
`ExecStart=/opt/gms/med-ai/backend/.venv/bin/python -m app.devtools.mock_ai --port 9100`.

### Updating to a new version

```bash
cd /opt/gms/med-ai && git pull
docker compose build && docker compose --profile mock up -d          # Docker
# directly: (cd frontend && npm ci && npx vite build) && backend/.venv/bin/pip install -e backend && sudo systemctl restart gms
```

Database changes are applied automatically when the app starts.

### Backups

Everything (database, uploaded files, search index) is in one place:
Docker volume `med-ai_gms-data`, or the `data/` folder when running directly.

```bash
# Docker
docker run --rm -v med-ai_gms-data:/data -v $PWD:/backup alpine tar czf /backup/gms-$(date +%F).tgz -C /data .
# Directly
tar czf gms-$(date +%F).tgz data/
```

Restore by stopping the app and unpacking the archive back into the volume or folder.

---

## Part 8 — Troubleshooting

| Symptom | Fix |
|---|---|
| Browser can't reach `http://<ip>:8000` | `docker compose ps` / `systemctl status gms`; `curl localhost:8000/api/health` on the server; `sudo ufw status` shows 8000 allowed. |
| Sign-in fails for the admin | The admin is created only on the very first start. If you changed `.env` later, reset the data (Part 3) or change the password from another admin account. |
| Seed shows `failed … Cannot reach the embedding service` | The AI endpoint is down. Docker test AI: `docker compose --profile mock up -d`. Ollama: `curl http://<host>:11434/api/tags`. Then run the seed again. |
| No patients on today's list | Run `python -m app.seed today` (Part 3). |
| AI panels are slow with MedGemma | Normal on smaller GPUs. Use `medgemma:4b`, or turn on *Use the main language model* for the clinical reasoning model. |
| Logs | `docker compose logs -f app` or `journalctl -u gms -f` |

---

## Before any real patient data

This demo setup is for demonstrations and testing with the fictional patients only. Before real
use: personal accounts with strong passwords, HTTPS (`COOKIE_SECURE=true`), real models instead
of the test AI, daily off-server backups, and a review of where the AI endpoints run (patient
context is sent to whatever model endpoint you configure).
