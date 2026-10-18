from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_table(path: Path) -> tuple[str, list[str], int]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        columns = next(reader, None)

        if not columns or any(not column.strip() for column in columns):
            raise ValueError("Input must contain a non-empty header row.")

        rows = 0
        for line_number, row in enumerate(reader, start=2):
            if not row:
                continue
            if len(row) != len(columns):
                raise ValueError(
                    f"Line {line_number} has {len(row)} fields; "
                    f"expected {len(columns)}."
                )
            rows += 1

    if rows == 0:
        raise ValueError("Input contains no data rows.")

    return delimiter, columns, rows


def infer_mapping(frame: pd.DataFrame, source: Path) -> dict:
    """Create internal metadata for an ordinary user table without prompting."""
    columns = list(frame.columns)
    time_candidates = [
        c for c in columns
        if any(token in c.lower() for token in ("date", "time", "period", "year"))
    ]
    time_column = None
    for column in time_candidates:
        parsed = pd.to_datetime(frame[column], errors="coerce")
        if parsed.notna().mean() >= 0.8:
            time_column = column
            break

    numeric_columns = [
        c for c in columns
        if pd.to_numeric(frame[c], errors="coerce").notna().mean() >= 0.8
        and c != time_column
    ]
    text_columns = [c for c in columns if c != time_column and c not in numeric_columns]
    if not numeric_columns:
        raise ValueError("Could not find a numeric measure column in the uploaded table.")
    if not text_columns:
        raise ValueError("Could not find a descriptive category column in the uploaded table.")

    if time_column:
        frame["__period_type"] = "date"
        temporal_column = time_column
        temporal_type_column = "__period_type"
        mode = "timeseries"
    else:
        frame["__snapshot_period"] = datetime.now(timezone.utc).date().isoformat()
        frame["__snapshot_period_type"] = "snapshot"
        temporal_column = "__snapshot_period"
        temporal_type_column = "__snapshot_period_type"
        mode = "snapshot"

    frame["__measure"] = "value"
    metadata = {
        "metaVariables": {
            "topic": source.stem,
            "source": "user_upload",
            "valueCategory": {"column": "__measure"},
        },
        "temporalVariables": {"column": temporal_column, "typeColumn": temporal_type_column},
        "groupingVariables": {
            column: {"column": column, "allValue": "All"} for column in text_columns
        },
        "valueVariables": {column: {} for column in numeric_columns},
        "generic_input": {
            "mode": mode,
            "inference": "numeric columns as measures; text columns as groupings",
            "source_has_time_field": bool(time_column),
        },
    }
    return metadata


def import_table(input_path: str, output_root: str, mapping_path: str | None = None) -> Path:
    source = Path(input_path)
    if source.suffix.lower() not in {".csv", ".tsv"}:
        raise ValueError("Input must be a .csv or .tsv file.")

    delimiter, columns, rows = inspect_table(source)
    dataset_dir = Path(output_root) / source.stem
    dataset_dir.mkdir(parents=True, exist_ok=True)

    data_path = dataset_dir / "data.csv"
    mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8")) if mapping_path else None
    if mapping is not None:
        mode = mapping.get("mode", "auto")
        if mode not in {"auto", "snapshot", "timeseries"}:
            raise ValueError("mapping mode must be auto, snapshot, or timeseries")
        frame = pd.read_csv(source, sep="\t" if delimiter == "\t" else ",")
        value_column = mapping.get("value_column")
        category_column = mapping.get("category_column")
        time_column = mapping.get("time_column")
        for name, column in (("value_column", value_column), ("category_column", category_column), ("time_column", time_column)):
            if column and column not in frame.columns:
                raise ValueError(f"{name} {column!r} is not present in the input")
        if not value_column or not category_column:
            raise ValueError("mapping requires category_column and value_column")
        if mode == "auto":
            mode = "timeseries" if time_column else "snapshot"
        if mode == "timeseries" and not time_column:
            raise ValueError("timeseries mode requires time_column")
        if mode == "snapshot":
            frame["__snapshot_period"] = datetime.now(timezone.utc).date().isoformat()
            frame["__snapshot_period_type"] = "snapshot"
            time_column = "__snapshot_period"
            time_type_column = "__snapshot_period_type"
        else:
            time_type_column = mapping.get("time_type_column")
            if not time_type_column:
                frame["__period_type"] = "date"
                time_type_column = "__period_type"
        frame["__measure"] = "value"
        frame.to_csv(data_path, index=False)
        metadata = {
            "metaVariables": {
                "topic": mapping.get("topic", source.stem),
                "source": mapping.get("source", "user_upload"),
                "valueCategory": {"column": "__measure"},
            },
            "temporalVariables": {"column": time_column, "typeColumn": time_type_column},
            "groupingVariables": {category_column: {"column": category_column, "allValue": "All"}},
            "valueVariables": {value_column: {}},
            "generic_input": {"mode": mode, "source_has_time_field": bool(mapping.get("time_column"))},
        }
    else:
        frame = pd.read_csv(source, sep="\t" if delimiter == "\t" else ",")
        metadata = infer_mapping(frame, source)
        frame.to_csv(data_path, index=False)

    provenance = {
        "source_filename": source.name,
        "source_format": source.suffix.lower().lstrip("."),
        "delimiter": "tab" if delimiter == "\t" else "comma",
        "imported_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": rows,
        "column_count": len(columns),
        "columns": columns,
        "input_sha256": sha256_file(source),
        "structural_validation": "passed",
    }
    if metadata is None:
        metadata = dict(provenance)
        metadata["generic_input"] = dict(provenance)
    else:
        metadata.update(provenance)
        metadata["generic_input"].update(provenance)

    (dataset_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return dataset_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output-root", default="data/imported")
    parser.add_argument("--mapping")
    args = parser.parse_args()

    output = import_table(args.input, args.output_root, args.mapping)
    print(f"Imported dataset into {output}")


if __name__ == "__main__":
    main()
