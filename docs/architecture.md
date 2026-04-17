# Architecture

## Today (dev)

```
┌──────────────────┐       ┌──────────────────────────┐
│  CMS NPPES zip   │──────▶│  snaps loader (Python)   │
│  ~1 GB monthly   │       │  stream-decompress + CSV │
└──────────────────┘       └────────────┬─────────────┘
                                        │ 3x COPY FROM STDIN
                                        ▼
                           ┌────────────────────────────┐
                           │  Postgres 14 on VPS        │
                           │  providers_doctors         │
                           │  providers_dentists        │
                           │  providers_pharmacists     │
                           └────────────────────────────┘
```

## Later (prod)

Public read API moves to Cloudflare so the VPS doesn't eat API traffic:

```
clients ──▶ Cloudflare Worker ──▶ D1 (SQLite snapshot) ──▶ R2 (monthly NPPES archive)
                    │
                    └─ fallback ──▶ Postgres on Hetzner CPX21 (only if we need joins D1 can't do)
```

D1 free tier (5 GB storage, 25 M reads/mo) holds the ~2 M filtered individual
rows comfortably. When a paid customer actually shows up and needs real
transactions, we spin up Hetzner and replicate from the VPS.

## Why not Postgres on Cloudflare

D1 is SQLite on the edge — reads are globally fast, writes are eventually
consistent, and we don't care about multi-row write transactions for a
read-heavy directory. Sync pipeline: Postgres on VPS is the source of truth,
D1 is the read replica, the monthly NPPES refresh is the write path.

## HIPAA boundary

Nothing in this repo ever sees PHI. NPI data is public CMS data, not PHI.
The messaging side of MedChat (pc-ios) keeps PHI in a separate BAA-eligible
store. Keep those two worlds in separate repos and separate networks.
