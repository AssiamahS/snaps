#!/usr/bin/env python3
"""
Stream-load NPPES monthly CSV into 3 filtered Postgres tables:

  providers_doctors     - taxonomy prefix 20 (Allopathic & Osteopathic)
  providers_dentists    - taxonomy prefix 12 (Dental Providers)
  providers_pharmacists - taxonomy prefix 18 (Pharmacy Service Providers)

Individuals only (Entity Type Code = 1). Primary taxonomy wins; falls back to
slot 1 if no primary flag is set. Facilities (entity type 2) are ignored here —
they'll get their own tables later.

Connection and file paths come from env. No creds are embedded.
"""
import sys, csv, io, os, zipfile, subprocess, time

ZIP_PATH = os.environ.get("NPPES_ZIP_PATH", "/tmp/nppes.zip")

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

def open_copy(table, dsn):
    cmd = ["psql", dsn, "-c",
           f"COPY {table} ({','.join(COLS)}) FROM STDIN WITH (FORMAT csv, NULL '')"]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=sys.stderr)

def norm_date(s):
    # NPPES dates are MM/DD/YYYY; Postgres accepts YYYY-MM-DD cleanly.
    if not s or len(s) != 10:
        return ""
    m, d, y = s.split("/")
    return f"{y}-{m}-{d}"

def main():
    dsn = pg_dsn()
    procs = {t: open_copy(t, dsn) for t in TAXONOMY_MAP.values()}
    writers = {t: csv.writer(io.TextIOWrapper(procs[t].stdin, encoding="utf-8", write_through=True))
               for t in procs}
    counts = {t: 0 for t in procs}
    skipped_org = skipped_other = 0
    total = 0
    start = time.time()

    with zipfile.ZipFile(ZIP_PATH) as z:
        main_csv = next(n for n in z.namelist()
                        if n.startswith("npidata_pfile_") and n.endswith(".csv")
                        and "FileHeader" not in n and "fileheader" not in n)
        print(f"[loader] main CSV: {main_csv}", flush=True)
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
                    print(f"[loader] {total:,} rows  ({rate:.0f}/s)  matched={counts}", flush=True)

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

    for t, p in procs.items():
        p.stdin.close()
        rc = p.wait()
        print(f"[loader] COPY {t} rc={rc} rows={counts[t]:,}", flush=True)

    elapsed = time.time() - start
    print(f"[loader] DONE total={total:,} orgs_skipped={skipped_org:,} "
          f"other_skipped={skipped_other:,} elapsed={elapsed:.0f}s", flush=True)
    print(f"[loader] loaded: {counts}", flush=True)

if __name__ == "__main__":
    main()
