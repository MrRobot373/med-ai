#!/usr/bin/env python3
"""Vendor-side licence tool. Run on YOUR machine, never on a customer's server.

    python tools/licence.py keygen  --out ~/gms-vendor-keys          one time: creates the signing key pair
    python tools/licence.py issue   --key ~/gms-vendor-keys/licence_private.pem \\
        --customer "Life Care Medico" --install-id 9F2C41A07B3D5E68 \\
        --clinicians 5 --staff 4 --branches 2 --expires 2027-11-01 --out licence-lifecare.json
    python tools/licence.py inspect licence-lifecare.json            show what a licence file says

After `keygen`, copy licence_public.pem to backend/app/assets/licence_public.pem and rebuild the product.
KEEP licence_private.pem SAFE AND BACKED UP: it is the only thing that can issue licences, and if it
is lost every customer must be re-licensed from a new build. Never commit it.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def keygen(args) -> int:
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    priv_path, pub_path = out / "licence_private.pem", out / "licence_public.pem"
    if priv_path.exists() and not args.force:
        print(f"{priv_path} already exists. Refusing to overwrite a signing key (use --force if you are sure).", file=sys.stderr)
        return 1
    key = Ed25519PrivateKey.generate()
    priv_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    priv_path.chmod(0o600)
    pub_path.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    print(f"Private key: {priv_path}  (keep secret, keep backed up)\nPublic key:  {pub_path}  (goes into backend/app/assets/)")
    return 0


def issue(args) -> int:
    key = serialization.load_pem_private_key(Path(args.key).expanduser().read_bytes(), password=None)
    payload = {
        "v": 1,
        "licence_id": args.licence_id or f"LIC-{date.today():%Y%m%d}-{args.install_id[:4]}",
        "customer": args.customer,
        "install_id": args.install_id,
        "issued_at": date.today().isoformat(),
        "expires_at": args.expires or None,
        "grace_days": args.grace_days,
        "limits": {"clinicians": args.clinicians, "staff": args.staff, "branches": args.branches},
    }
    doc = {"payload": payload, "signature": base64.b64encode(key.sign(canonical(payload))).decode()}
    Path(args.out).write_text(json.dumps(doc, indent=2) + "\n")
    print(f"Wrote {args.out}")
    return 0


def inspect(args) -> int:
    print(json.dumps(json.loads(Path(args.file).read_text())["payload"], indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen")
    k.add_argument("--out", required=True)
    k.add_argument("--force", action="store_true")
    k.set_defaults(fn=keygen)
    i = sub.add_parser("issue")
    i.add_argument("--key", required=True)
    i.add_argument("--customer", required=True)
    i.add_argument("--install-id", required=True, help="shown in the product under Settings → Licence")
    i.add_argument("--clinicians", type=int, required=True)
    i.add_argument("--staff", type=int, required=True, help="front-desk and viewer accounts")
    i.add_argument("--branches", type=int, default=1)
    i.add_argument("--expires", help="YYYY-MM-DD; omit for a perpetual licence")
    i.add_argument("--grace-days", type=int, default=30)
    i.add_argument("--licence-id")
    i.add_argument("--out", required=True)
    i.set_defaults(fn=issue)
    n = sub.add_parser("inspect")
    n.add_argument("file")
    n.set_defaults(fn=inspect)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
