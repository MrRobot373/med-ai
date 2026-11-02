# Releasing and selling GMS Clinical AI — the vendor's checklist

For the owner and whoever does releases. Customers never see this file.

## One-time setup

1. **Create the licence signing key** (on your own machine, not a server that customers can reach):
   `backend/.venv/bin/python tools/licence.py keygen --out ~/gms-vendor-keys`
   - Copy `licence_public.pem` to `backend/app/assets/licence_public.pem` and commit it. **Do this before the first customer build**:
     a build without it cannot verify any licence, so every install stays in evaluation.
   - **Back up `licence_private.pem` in two separate safe places and never commit it.** If it is lost, no new licences can be issued for
     existing builds, and every customer would need a new build. If it leaks, anyone can issue licences: rotate the key (new key, new build).
2. Appoint the **Clinical Lead and Pharmacist** and sign their retainers — `CLINICAL_GOVERNANCE.md`.
3. Buy insurance and get the regulatory opinion — `compliance/INSURANCE_AND_CERTIFICATION.md`.

## Each release

1. Engineering: all tests green (`cd backend && .venv/bin/python -m pytest`; `cd frontend && npm test && npm run e2e`), lint and type checks clean.
2. If anything under the three medical-content areas changed (`formulary`, `scores.py`, `knowledge-packs`, `testbank.json`): list it in the release notes and obtain **both reviewers' signatures** (they sign in a staging copy of the release; export the record).
3. Bump `APP_VERSION` in `backend/app/api/system.py` and `version` in `backend/pyproject.toml`.
4. Build: `scripts/make-bundle.sh` (add `REGISTRY=…` / `CA_BUNDLE=…` for restricted networks; `--with clamav,qdrant` for offline sites).
   Output: `dist/gms-clinical-ai-<version>.tar.gz` and its `.sha256`. The same file installs *and* updates.
5. **Test the upgrade path on a copy of a real installation**: install the previous bundle, enter data, `./update.sh` the new one, and also practise a failing update (see below).
6. Deliver the tarball and its `.sha256` through a channel the customer trusts (signed download link, or hand-delivered USB).

## Selling and licensing a customer

1. Customer installs; **Settings → Licence & usage** shows the *Installation ID*. They send it to you.
2. Issue the licence:
   ```
   backend/.venv/bin/python tools/licence.py issue --key ~/gms-vendor-keys/licence_private.pem \
     --customer "Life Care Medico" --install-id 9F2C41A07B3D5E68 \
     --clinicians 5 --staff 4 --branches 2 --expires 2027-11-01 --out licence-lifecare.json
   ```
   Seats: *clinicians* = doctors; *staff* = front-desk and viewer accounts; administrators use no seat. `--grace-days` (default 30) is how long after expiry people and branches can still be added.
3. Send `licence-lifecare.json`; they install it under Settings → Licence & usage. Renewal = a new file with a later date.
4. Keep a ledger: customer, Installation ID, licence id, limits, expiry, support contract, contact.
   A licence is tied to one Installation ID: a copied installation shows a different ID and the file is refused.

**The licence is a business control, not copy protection.** It stops casual over-use and makes terms visible; a determined customer
with root access to their own server can defeat any local check. The contract is what binds them.

## Rehearse a failed update (do this before the first customer)

Build a bundle whose container cannot start (e.g. set a bad `CMD` in a throwaway Dockerfile, tag it as a higher version), run `./update.sh` on a test install,
and confirm: it reports the failure, restores the previous version and the pre-update backup, and the application is healthy again with the data from before the update.
This was done once with the supplied scripts; repeat it whenever `update.sh` or the migrations change.

## Support access

Remote access only when the customer asks, supervised, logged, and never copying patient data (`compliance/TERMS_DRAFT.md` §3). Keep the customer's `status` and `doctor` output with each ticket.
