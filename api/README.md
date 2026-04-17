# snaps api

FastAPI read layer for the snaps NPI tables. Runs on 8000 by default.

```bash
pip install -r requirements.txt
set -a; . ../.env; set +a
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## Endpoints

```
GET /healthz
GET /{kind}?state=&city=&last_name=&taxonomy_prefix=&limit=
GET /{kind}/{npi}
```

`kind` ∈ `doctors`, `dentists`, `pharmacists`.

### Examples

```bash
# 50 doctors in Newark, NJ
curl "http://localhost:8000/doctors?state=NJ&city=Newark&limit=50"

# Dentists named "Smith" in Texas
curl "http://localhost:8000/dentists?state=TX&last_name=Smith"

# Single NPI
curl "http://localhost:8000/doctors/1234567890"
```

## Prod plan

- Don't run this as the public origin long-term.
- Cloudflare Workers → D1 SQLite replica (read-only, free-tier).
- This FastAPI stays for the VPS admin side + webhooks.
