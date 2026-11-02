# Partner API (v1)

For the technician connecting a pharmacy, billing system or other software. The clinic's administrator creates a key
in **Settings → Integrations**. All requests use HTTPS and the header `Authorization: Bearer gms_…`.

| Method and path | Scope needed | Returns |
|---|---|---|
| `GET /api/integration/v1/prescriptions?since=<ISO time>&limit=100&after=<id>` | `prescriptions:read` | Issued prescriptions, oldest first; `next` is the id to pass as `after` for the next page |
| `GET /api/integration/v1/prescriptions/{id}` | `prescriptions:read` | One issued prescription (drafts are never visible) |
| `POST /api/integration/v1/prescriptions/{id}/dispensed` `{"dispensed_by": "City Pharmacy", "note": "…"}` | `prescriptions:dispense` | The prescription with its dispensed record. A second call returns **409** |
| `GET /api/integration/v1/visits?since=<ISO time>&limit=100` | `visits:read` | Completed visits with the services given |
| `GET /api/integration/v1/patients/{mrn}` | `patients:read` | Name, age, sex, date of birth, phone |

Errors: `401` key missing/invalid/expired/revoked · `403` the key lacks the scope · `404` not found · `409` already dispensed · `422` invalid input.

## Prescription object

```json
{ "id": "…", "status": "final", "issued_at": "2026-11-02T10:14:00+00:00",
  "patient": {"mrn": "LCM-10231", "name": "Rohit Verma", "age": 69, "sex": "male", "date_of_birth": "1957-05-10", "phone": "+91…"},
  "doctor": {"name": "Dr. Ananya Rao", "registration_no": "KMC-48213"}, "branch": {"code": "MAIN", "name": "Main clinic"},
  "diagnosis": "Acute gastritis", "advice": "…", "follow_up_date": "2026-11-16",
  "items": [{"drug": "Pan 40", "generic": "pantoprazole", "dose": "1 tab", "frequency": "OD", "duration_days": 14, "instructions": "Before breakfast"}],
  "dispensed": null }
```

## Webhooks

Configured in **Settings → Integrations → Webhooks**. Events: `prescription.finalized`, `prescription.dispensed`,
`visit.completed`, `letter.issued`, `patient.created`. Body (IDs only by default):

```json
{"event": "prescription.finalized", "id": "<prescription id>", "occurred_at": "…", "patient_mrn": "LCM-10231"}
```

Headers: `X-GMS-Event`, `X-GMS-Delivery` (unique id — use it to ignore a repeat), `X-GMS-Timestamp`,
`X-GMS-Signature: t=<timestamp>,v1=<hex>`.

**Verify every message.** Compute `HMAC_SHA256(secret, "<timestamp>.<raw body>")` as hex and compare with `v1` using a
constant-time comparison; reject if the timestamp is more than five minutes old. Reply `2xx` quickly. Any other answer
(or no answer) is retried after 1 min, 5 min, 15 min, 1 h, 3 h, 6 h, 12 h and 24 h, then marked failed (the
administrator can retry from the log). Messages may arrive more than once and out of order.

```python
import hmac, hashlib, time
def verify(secret: str, header: str, body: bytes) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(","))
    if abs(time.time() - int(parts["t"])) > 300:
        return False
    expected = hmac.new(secret.encode(), f"{parts['t']}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])
```

## Verifying a printed prescription or letter (no key needed)

The QR code opens `https://<clinic server>/verify/rx/<id>?s=<signature>`; the page calls
`GET /api/verify/rx/{id}?s=…` which returns validity, issue date, organisation and doctor — never patient details.
Letters use `/api/verify/letter/{id}?s=…`.
