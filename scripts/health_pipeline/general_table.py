#!/usr/bin/env python3
"""Prepare any table (CSV, TSV or Parquet) for the general report, reports/general.qmd.

Tables in this pipeline's own format go to upload_table.py and the disease reports; every
other table comes here. Nothing is assumed about its columns: each one is classified once
as time, number or group, and that classification is saved next to the table, so the page
and the report describe the same thing. The report only adds up or averages what is in the
file; it never invents diseases, populations or rates.

A table that fails a check is refused. Output: <out_root>/general-<sha256[:12]>/ with
table.csv, profile.json, checks.csv and upload.json, reused when the same file comes again.

Usage:  python general_table.py my_table.csv --out results/uploads
"""
import argparse
import hashlib
import json
import re
import shutil
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

UPLOAD_INFO = "upload.json"
# A column whose name says it is a year, and whose values are whole numbers in this range.
YEAR_NAME = re.compile(r"year|jahr|annee|année|anno|^yr$", re.I)
YEARS = (1800, 2200)
TIME_NAME = re.compile(r"date|time|day|week|month|year|period|datum|jahr|monat|woche|fecha|annee|année", re.I)
# Numbers named like these are levels, so they are averaged; all others are counts and are added up.
MEAN_WORDS = {"rate", "ratio", "percent", "percentage", "pct", "share", "proportion", "mean", "avg", "average",
              "median", "index", "incidence", "prevalence", "score", "temperature", "temp", "age", "price",
              "density", "per", "level", "growth", "change"}
# The same in German, French and Italian names, where words are often joined (Durchschnittsalter).
MEAN_STEMS = ("durchschnitt", "mittelwert", "quote", "anteil", "prozent", "inzidenz", "moyenne", "taux",
              "pourcentage", "media", "tasso", "percentuale")
# Numbers named like these are labels (codes), not quantities.
CODE_WORDS = {"id", "code", "zip", "postcode", "plz", "fips", "iso", "nr", "no"}
MAX_GROUP_VALUES = 200  # a text column with more distinct values is free text or an identifier
MAX_GROUP_LIST = 40     # values of the main group offered on the page
ROWS = "Number of rows"  # the value counted for a table without number columns


def words(name: str) -> set:
    return set(re.split(r"[^a-z%]+", str(name).lower())) | ({"percent"} if "%" in str(name) else set())


def separator(path: Path) -> str:
    if path.suffix.lower() in (".tsv", ".tab"):
        return "\t"
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        head = f.readline()
    return max([",", ";", "\t", "|"], key=head.count)


def read_table(path: Path, nrows=None) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
        return frame.head(nrows) if nrows is not None else frame
    sep = separator(path)
    try:
        return pd.read_csv(path, sep=sep, nrows=nrows, low_memory=False, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, sep=sep, nrows=nrows, low_memory=False, encoding="latin-1")


def columns_of(path) -> list:
    """Column names only, to decide which route a file takes without reading all of it."""
    return [str(c) for c in read_table(Path(path), nrows=0).columns]


def as_number(s: pd.Series):
    """The column as floats, or None when it is not a number column (95% of its values must read)."""
    if pd.api.types.is_bool_dtype(s):
        return None
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float)
    text = s.dropna().astype(str).str.strip()
    if text.empty:
        return None
    for cleaned in (text,
                    text.str.replace(r"(?<=\d)[,' ](?=\d{3}(?:\D|$))", "", regex=True),  # 12,400 or 12'400
                    text.str.replace(",", ".", regex=False)):                           # 3,5 (decimal comma)
        values = pd.to_numeric(cleaned, errors="coerce")
        if values.notna().mean() >= 0.95:
            return values.reindex(s.index).astype(float)
    return None


def as_dates(s: pd.Series):
    """The column as dates, or None when fewer than 90% of its values read as dates."""
    text = s.dropna().astype(str).str.strip()
    if text.empty or text.str.fullmatch(r"-?\d+(\.\d+)?").mean() > 0.5:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sample = pd.to_datetime(text.head(1000), errors="coerce", format="mixed")
        if sample.notna().mean() < 0.9:
            return None
        return pd.to_datetime(s.astype("string"), errors="coerce", format="mixed")


def granularity(dates: pd.Series) -> str:
    d = pd.Series(dates.dropna().unique()).sort_values()
    if d.empty:
        return "day"
    if (d.dt.month.eq(1) & d.dt.day.eq(1)).all():
        return "year"
    if d.dt.day.eq(1).all():
        return "month"
    step = d.diff().dt.days.median() if len(d) > 1 else 1
    return "week" if 6 <= step <= 8 else "day"


def classify(frame: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Decide the role of every column; returns the profile and the table with typed columns."""
    frame = frame.copy()
    frame.columns = [str(c).strip() for c in frame.columns]
    numbers = {c: as_number(frame[c]) for c in frame.columns}
    time, period = None, None
    for c in frame.columns:  # a year column first, then a date column (named like one first)
        n = numbers[c]
        if YEAR_NAME.search(c) and n is not None and n.notna().any():
            known = n.dropna()
            if (known % 1 == 0).all() and known.between(*YEARS).all():
                time, period = c, "year"
                frame[c] = n.astype("Int64")
                break
    if time is None:
        for c in sorted(frame.columns, key=lambda c: not TIME_NAME.search(c)):
            if numbers[c] is None and (dates := as_dates(frame[c])) is not None:
                time, period = c, granularity(dates)
                frame[c] = dates.dt.strftime("%Y-%m-%d")
                break
    measures, groups, ignored = [], [], []
    for c in frame.columns:
        if c == time:
            continue
        n, distinct = numbers[c], frame[c].nunique(dropna=True)
        if n is not None and not words(c) & CODE_WORDS:
            frame[c] = n
            level = words(c) & MEAN_WORDS or any(stem in c.lower() for stem in MEAN_STEMS)
            measures.append({"name": c, "how": "mean" if level else "sum"})
        elif 2 <= distinct <= MAX_GROUP_VALUES:
            frame[c] = frame[c].astype("string").str.strip()
            groups.append(c)
        else:
            ignored.append(c)
    if not measures:  # a table of text only: count its rows, so it still gets charts and tables
        frame[ROWS] = 1
        measures.append({"name": ROWS, "how": "sum", "counted": True})
    profile = {"time": time, "period": period, "measures": measures, "groups": groups, "ignored": ignored}
    return profile, frame


def check(raw: pd.DataFrame, frame: pd.DataFrame, profile: dict) -> list[dict]:
    """The table's checks, in the same form as checks.py writes them."""
    def row(name, ok, detail, failure="FAIL"):
        return {"dataset_id": "uploaded", "check": name, "status": "PASS" if ok else failure, "detail": detail}

    names = [m["name"] for m in profile["measures"] if not m.get("counted")]
    time = profile["time"]
    rows = [row("not_empty", len(frame) > 0, f"{len(frame):,} rows, {len(raw.columns)} columns"),
            row("number_columns", bool(names), f"numbers in: {', '.join(names)}" if names else
                "no column holds numbers, so the report counts rows instead", failure="WARN")]
    rows.append(row("time_column", time is not None,
                    f"'{time}' read as {profile['period']}s" if time else
                    "no date or year column: the report is a snapshot, without charts over time", failure="WARN"))
    if time:
        unread = int((frame[time].isna() & raw[time].notna()).sum())
        rows.append(row("readable_times", unread == 0, f"{unread:,} values in '{time}' are not dates or years "
                                                       "and are left out of the charts over time", failure="WARN"))
    if names:
        missing = int(frame[names].isna().sum().sum())
        rows.append(row("missing_numbers", missing == 0, f"{missing:,} empty or unreadable number cells",
                        failure="WARN"))
        negative = int((frame[names] < 0).sum().sum())
        rows.append(row("negative_numbers", negative == 0, f"{negative:,} negative values (fine for changes, "
                                                           "unusual for counts)", failure="WARN"))
    duplicates = int(raw.duplicated().sum())
    rows.append(row("duplicate_rows", duplicates == 0, f"{duplicates:,} rows repeat another row exactly",
                    failure="WARN"))
    if profile["ignored"]:
        rows.append(row("unused_columns", False, f"not used in the charts: {', '.join(profile['ignored'])} "
                                                 "(one value only, or too many distinct values)", failure="WARN"))
    return rows


def prepare(source, name: str, out_root) -> dict:
    """Check the table at `source`, write its folder for the general report, return its summary.

    Raises ValueError (with the failed checks) when the table cannot be used.
    """
    source, out_root = Path(source), Path(out_root)
    digest = hashlib.sha256()
    with open(source, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    sha = digest.hexdigest()
    folder = out_root / f"general-{sha[:12]}"
    if (folder / UPLOAD_INFO).is_file():
        return json.loads((folder / UPLOAD_INFO).read_text(encoding="utf-8"))

    raw = read_table(source)
    raw.columns = [str(c).strip() for c in raw.columns]
    profile, frame = classify(raw)
    checks = pd.DataFrame(check(raw, frame, profile))
    failed = checks[checks.status == "FAIL"]
    if len(failed):
        raise ValueError("; ".join(f"{r.check}: {r.detail}" for r in failed.itertuples()))

    time, years = profile["time"], None
    if time and frame[time].notna().any():
        stamps = frame[time].dropna()
        found = stamps.astype(int) if profile["period"] == "year" and pd.api.types.is_integer_dtype(stamps) \
            else pd.to_datetime(stamps).dt.year
        years = [int(found.min()), int(found.max())]
    main = profile["groups"][0] if profile["groups"] else None
    first = profile["measures"][0]["name"]
    values = []
    if main:  # largest first, so the page lists the ones that matter
        values = (frame.groupby(main)[first].sum().sort_values(ascending=False).index[:MAX_GROUP_LIST].tolist())
    uploaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    info = {"kind": "general", "name": name, "sha256": sha, "bytes": source.stat().st_size, "rows": len(frame),
            "columns": len(frame.columns), **profile, "years": years, "main_group": main,
            "main_group_values": [str(v) for v in values],
            "main_group_more": bool(main) and int(frame[main].nunique()) > MAX_GROUP_LIST,
            "uploaded_at": uploaded_at}

    # Written into a temporary folder and moved in place, so a half-written upload is never used.
    out_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out_root) as tmp:
        work = Path(tmp)
        frame.to_csv(work / "table.csv", index=False)
        checks.to_csv(work / "checks.csv", index=False)
        (work / "profile.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
        (work / UPLOAD_INFO).write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        if folder.exists():
            shutil.rmtree(folder)
        shutil.move(str(work), folder)
        work.mkdir()  # TemporaryDirectory removes its own folder on exit
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("table", help="any table, .csv, .tsv or .parquet")
    ap.add_argument("--out", default="results/uploads")
    a = ap.parse_args()
    try:
        print(json.dumps(prepare(a.table, Path(a.table).name, a.out), indent=2))
    except ValueError as exc:
        raise SystemExit(f"table refused: {exc}")
