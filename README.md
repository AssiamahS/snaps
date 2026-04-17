# snaps

NPI provider directory for MedChat. Ingests the monthly CMS NPPES dump and
serves filtered Postgres tables for individual practitioners by type.

- `providers_doctors`     — taxonomy 20xx (Allopathic & Osteopathic)
- `providers_dentists`    — taxonomy 12xx (Dental)
- `providers_pharmacists` — taxonomy 18xx (Pharmacy)

Facilities (entity type 2) are intentionally skipped for now. Hospital,
pharmacy-chain, and dental-clinic tables get wired in a follow-up.

## Data source

CMS NPPES monthly file — public domain, no auth required.
https://download.cms.gov/nppes/NPI_Files.html

## One-shot VPS bring-up

Ubuntu 22.04, 2+ GB RAM, 40+ GB free disk:

```bash
bash scripts/setup_vps.sh           # swap, Postgres, db, user, schema
bash scripts/fetch_nppes.sh         # grabs the latest monthly zip to /tmp/nppes.zip
cp .env.example .env && $EDITOR .env
set -a; . .env; set +a
python3 loader/npi_loader.py        # stream-load, ~5 min on a 2 GB box
psql $DSN -f schema/002_indexes.sql # indexes after the bulk load
```

## Why stream-load

The NPPES file is ~1 GB compressed, ~8 GB uncompressed. On a 2 GB RAM / 45 GB
free disk box you can't afford to extract it. `zipfile.ZipFile().open()` lets
Python read the CSV row-by-row without ever touching disk, and three
`COPY FROM STDIN` processes write each target table in parallel.

Typical run on a t3.small:
- ~8 M input rows
- ~21 K rows/sec
- ~5-7 min end-to-end
- <1 GB added to the Postgres data dir after the load

Indexes are created *after* the bulk load, not during, so the COPY doesn't
thrash the buffer cache.

## Monthly refresh

Add to cron on the first of each month after 04:00 UTC (new NPPES drops on the
second Friday, but being lazy about timing is fine):

```cron
0 4 1 * * /path/to/snaps/scripts/refresh.sh
```

(`scripts/refresh.sh` = `fetch_nppes.sh` + `TRUNCATE`s + loader + `ANALYZE`.)

## License

Code: MIT. Data: public domain (CMS NPPES).
