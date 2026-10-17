from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


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


def import_table(input_path: str, output_root: str) -> Path:
    source = Path(input_path)
    if source.suffix.lower() not in {".csv", ".tsv"}:
        raise ValueError("Input must be a .csv or .tsv file.")

    delimiter, columns, rows = inspect_table(source)
    dataset_dir = Path(output_root) / source.stem
    dataset_dir.mkdir(parents=True, exist_ok=True)

    data_path = dataset_dir / "data.csv"
    with source.open("r", encoding="utf-8-sig", newline="") as source_file:
        content = source_file.read()

    with data_path.open("w", encoding="utf-8", newline="") as output_file:
        output_file.write(content)

    metadata = {
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

    (dataset_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return dataset_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output-root", default="data/imported")
    args = parser.parse_args()

    output = import_table(args.input, args.output_root)
    print(f"Imported dataset into {output}")


if __name__ == "__main__":
    main()