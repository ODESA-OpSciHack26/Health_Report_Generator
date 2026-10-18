#!/usr/bin/env python3
"""Prepare a reader's own cleaned table (CSV or Parquet) for render_quarto.py.

The reports read a results folder: harmonised.csv plus checks.csv, datasets.csv and
harmonised_snapshot.json. An uploaded table has only the first, so this writes the other
three describing the upload itself: the checks run here, one dataset row for the file and
a snapshot named after its checksum. The project's own results are never touched.

A table that fails a check is refused. Output: <out_root>/<sha256[:12]>/, reused when the
same file is uploaded again.

Usage:  python upload_table.py my_table.csv --out results/uploads
"""
import argparse
import ast
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[2]
# What the reports read (reports/shared/helpers.py COLUMNS); a test keeps the two equal.
REQUIRED = ["topic", "source_system", "measure", "period", "period_type", "place", "place_type", "age_group",
            "sex", "breakdown", "value", "pop", "incValue", "is_stat_row", "year"]
COUNTS = {"cases", "consultations"}
KEY = ["topic", "source_system", "measure", "period", "period_type", "place", "place_type", "age_group", "sex",
       "breakdown"]
UPLOAD_INFO = "upload.json"


def known_diseases():
    """Disease ids the reports know, read from reports/shared/helpers.py without importing it."""
    tree = ast.parse((PROJECT / "reports" / "shared" / "helpers.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "ALL_DISEASES" for t in node.targets):
            return list(ast.literal_eval(node.value))
    raise RuntimeError("ALL_DISEASES not found in reports/shared/helpers.py")


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, low_memory=False)


def check(frame: pd.DataFrame, diseases) -> list[dict]:
    """The upload's quality checks, in the same form as checks.py writes them."""
    def row(name, ok, detail, failure="FAIL"):
        return {"dataset_id": "uploaded", "check": name, "status": "PASS" if ok else failure, "detail": detail}

    missing = [c for c in REQUIRED if c not in frame.columns]
    rows = [row("required_columns", not missing,
                f"missing: {', '.join(missing)}" if missing else f"all {len(REQUIRED)} report columns present")]
    if missing:
        return rows
    rows.append(row("not_empty", len(frame) > 0, f"{len(frame):,} rows"))
    values = pd.to_numeric(frame.value, errors="coerce")
    unreadable = int((values.isna() & frame.value.notna()).sum())
    rows.append(row("numeric_values", unreadable == 0, f"{unreadable:,} values are not numbers"))
    years = pd.to_numeric(frame.year, errors="coerce")
    rows.append(row("integer_years", bool(years.notna().all() and (years % 1 == 0).all()),
                    f"{int(years.isna().sum()):,} missing or unreadable years"))
    negative = int(((values < 0) & frame.measure.isin(COUNTS)).sum())
    rows.append(row("nonnegative_counts", negative == 0, f"{negative:,} negative case or consultation counts"))
    found = sorted(set(frame.topic.dropna()) & set(diseases))
    rows.append(row("known_diseases", bool(found), f"{len(found)} of {len(diseases)} report diseases: {', '.join(found)}"))
    other = sorted(set(frame.topic.dropna()) - set(diseases))
    rows.append(row("other_topics", True, f"{len(other)} topics are not report diseases and are only used where "
                                          f"a section needs them: {', '.join(other[:10])}" if other else "none"))
    duplicates = int(frame.duplicated(KEY).sum())
    rows.append(row("unique_keys", duplicates == 0, f"{duplicates:,} rows repeat a topic, measure, period, place "
                                                    f"and subgroup", failure="WARN"))
    return rows


def prepare(source, name: str, out_root) -> dict:
    """Check the table at `source`, write a results folder for it, return its summary.

    Raises ValueError (with the failed checks) when the table cannot be used.
    """
    source, out_root = Path(source), Path(out_root)
    digest = hashlib.sha256()
    with open(source, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    sha = digest.hexdigest()
    folder = out_root / sha[:12]
    if (folder / UPLOAD_INFO).is_file():
        return json.loads((folder / UPLOAD_INFO).read_text(encoding="utf-8"))

    frame = read_table(source)
    diseases = known_diseases()
    checks = pd.DataFrame(check(frame, diseases))
    failed = checks[checks.status == "FAIL"]
    if len(failed):
        raise ValueError("; ".join(f"{r.check}: {r.detail}" for r in failed.itertuples()))

    frame = frame.assign(year=frame.year.astype(int))
    present = set(frame.topic)
    years = frame[frame.topic.isin(diseases)].year
    uploaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    info = {"name": name, "sha256": sha, "bytes": source.stat().st_size, "rows": len(frame),
            "diseases": [t for t in diseases if t in present],
            "years": [int(years.min()), int(years.max())], "uploaded_at": uploaded_at}

    # Written into a temporary folder and moved in place, so a half-written upload is never used.
    out_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out_root) as tmp:
        work = Path(tmp)
        frame.to_csv(work / "harmonised.csv", index=False)
        checks.to_csv(work / "checks.csv", index=False)
        pd.DataFrame([{
            "source_file": name, "metadata_file": "", "sha256": sha, "metadata_sha256": "", "snapshot_id": f"upload-{sha[:12]}",
            "dataset_id": "uploaded", "topic": "uploaded table", "source_system": "uploaded by the reader",
            "publishing_date": uploaded_at[:10], "rows": len(frame), "status": "ok", "detail": "uploaded table",
        }]).to_csv(work / "datasets.csv", index=False)
        (work / "harmonised_snapshot.json").write_text(json.dumps({
            "snapshot_id": f"upload-{sha[:12]}", "files": [{"path": name, "sha256": sha, "bytes": info["bytes"]}],
        }, indent=2) + "\n", encoding="utf-8")
        (work / UPLOAD_INFO).write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        if folder.exists():
            shutil.rmtree(folder)
        shutil.move(str(work), folder)
        work.mkdir()  # TemporaryDirectory removes its own folder on exit
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("table", help="cleaned table, .csv or .parquet")
    ap.add_argument("--out", default="results/uploads")
    a = ap.parse_args()
    try:
        print(json.dumps(prepare(a.table, Path(a.table).name, a.out), indent=2))
    except ValueError as exc:
        raise SystemExit(f"table refused: {exc}")
