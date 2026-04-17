#!/usr/bin/env python3
"""
Stream-load NPPES monthly CSV into 3 filtered Postgres tables:

  providers_doctors     - taxonomy prefix 20 (Allopathic & Osteopathic)
  providers_dentists    - taxonomy prefix 12 (Dental Providers)
  providers_pharmacists - taxonomy prefix 18 (Pharmacy Service Providers)

Two-phase to stay sane on a 2 GB RAM box:
  Phase 1: stream the ZIP and write 3 filtered temp CSVs to /tmp.
           No DB connection yet, so no postgres backend memory in play.
  Phase 2: close temp files, then run 3 sequential COPY FROM commands.
           Only one postgres backend is busy at a time.

Individuals only (Entity Type Code = 1). Primary taxonomy wins, falls back
to slot 1. Facilities get their own tables in a follow-up.
"""
import csv, io, os, zipfile, subprocess, time

ZIP_PATH = os.environ.get("NPPES_ZIP_PATH", "/tmp/nppes.zip")
TMP_DIR  = os.environ.get("NPPES_TMP_DIR", "/tmp")

def pg_dsn():
    return "postgresql://{u}:{p}@{h}:{port}/{db}".format(
        u=os.environ["PGUSER"],
        p=os.environ["PGPASSWORD"],
        h=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        db=os.environ["PGDATABASE"],
    )

TAXONOMY_MAP = {
    "12": "providers_dentists",
    "20": "providers_doctors",
    "18": "providers_pharmacists",
}
COLS = [
    "npi","first_name","last_name","middle_name","credential","sex",
    "taxonomy_code","specialty_desc","is_sole_proprietor",
    "addr_line1","addr_line2","city","state","zip",
    "phone","fax","enumeration_date","last_updated","deactivation_date",
]

def norm_date(s):
    if not s or len(s) != 10:
        return ""
    m, d, y = s.split("/")
    return f"{y}-{m}-{d}"

def phase1_filter():
    tmp_paths = {t: os.path.join(TMP_DIR, f"nppes_{t}.csv") for t in TAXONOMY_MAP.values()}
    files    = {t: open(p, "w", encoding="utf-8", newline="") for t, p in tmp_paths.items()}
    writers  = {t: csv.writer(f) for t, f in files.items()}
    counts   = {t: 0 for t in files}
    skipped_org = skipped_other = 0
    total = 0
    start = time.time()

    with zipfile.ZipFile(ZIP_PATH) as z:
        main_csv = next(n for n in z.namelist()
                        if n.startswith("npidata_pfile_") and n.endswith(".csv")
                        and "FileHeader" not in n and "fileheader" not in n)
        print(f"[phase1] main CSV: {main_csv}", flush=True)
        with z.open(main_csv) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace"))
            header = next(reader)
            idx = {name: i for i, name in enumerate(header)}

            tax_slots = [
                (idx[f"Healthcare Provider Taxonomy Code_{n}"],
                 idx[f"Healthcare Provider Primary Taxonomy Switch_{n}"])
                for n in range(1, 16)
                if f"Healthcare Provider Taxonomy Code_{n}" in idx
                and f"Healthcare Provider Primary Taxonomy Switch_{n}" in idx
            ]
            I = {
                "npi":   idx["NPI"],
                "ent":   idx["Entity Type Code"],
                "last":  idx["Provider Last Name (Legal Name)"],
                "first": idx["Provider First Name"],
                "mid":   idx["Provider Middle Name"],
                "cred":  idx["Provider Credential Text"],
                "sex":   idx.get("Provider Gender Code", -1),
                "sole":  idx.get("Is Sole Proprietor", -1),
                "a1":    idx["Provider First Line Business Practice Location Address"],
                "a2":    idx["Provider Second Line Business Practice Location Address"],
                "city":  idx["Provider Business Practice Location Address City Name"],
                "state": idx["Provider Business Practice Location Address State Name"],
                "zip":   idx["Provider Business Practice Location Address Postal Code"],
                "phone": idx["Provider Business Practice Location Address Telephone Number"],
                "fax":   idx["Provider Business Practice Location Address Fax Number"],
                "enum":  idx["Provider Enumeration Date"],
                "upd":   idx["Last Update Date"],
                "deact": idx.get("NPI Deactivation Date", -1),
            }

            for row in reader:
                total += 1
                if total % 500000 == 0:
                    rate = total / (time.time() - start)
                    print(f"[phase1] {total:,} rows  ({rate:.0f}/s)  matched={counts}", flush=True)

                if row[I["ent"]] != "1":
                    skipped_org += 1
                    continue

                primary_code = ""
                for c_i, p_i in tax_slots:
                    if p_i < len(row) and row[p_i] == "Y":
                        primary_code = row[c_i].strip() if c_i < len(row) else ""
                        break
                if not primary_code and tax_slots and tax_slots[0][0] < len(row):
                    primary_code = row[tax_slots[0][0]].strip()

                table = TAXONOMY_MAP.get(primary_code[:2])
                if not table:
                    skipped_other += 1
                    continue

                def g(k):
                    i = I.get(k, -1)
                    return row[i] if 0 <= i < len(row) else ""

                writers[table].writerow([
                    g("npi"), g("first"), g("last"), g("mid"), g("cred"), g("sex"),
                    primary_code, "", g("sole"),
                    g("a1"), g("a2"), g("city"), g("state"), g("zip"),
                    g("phone"), g("fax"),
                    norm_date(g("enum")), norm_date(g("upd")), norm_date(g("deact")),
                ])
                counts[table] += 1

    for f in files.values():
        f.close()

    elapsed = time.time() - start
    print(f"[phase1] DONE total={total:,} orgs_skipped={skipped_org:,} "
          f"other_skipped={skipped_other:,} elapsed={elapsed:.0f}s", flush=True)
    print(f"[phase1] wrote: {counts}", flush=True)
    return tmp_paths, counts

def phase2_copy(tmp_paths, dsn):
    for table, path in tmp_paths.items():
        start = time.time()
        print(f"[phase2] TRUNCATE + COPY {table} from {path}", flush=True)
        subprocess.check_call(["psql", dsn, "-c", f"TRUNCATE {table};"])
        with open(path, "rb") as f:
            rc = subprocess.run(
                ["psql", dsn, "-c",
                 f"COPY {table} ({','.join(COLS)}) FROM STDIN WITH (FORMAT csv, NULL '')"],
                stdin=f, check=True
            )
        elapsed = time.time() - start
        print(f"[phase2] {table} loaded in {elapsed:.0f}s", flush=True)

def cleanup(tmp_paths):
    for p in tmp_paths.values():
        try:
            os.remove(p)
        except OSError:
            pass

def main():
    tmp_paths, counts = phase1_filter()
    phase2_copy(tmp_paths, pg_dsn())
    cleanup(tmp_paths)
    print("[loader] ALL DONE", flush=True)

if __name__ == "__main__":
    main()
