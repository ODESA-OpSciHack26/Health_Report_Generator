from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts" / "health_pipeline"))

from ingest_tabular import import_table


def test_imports_csv_and_writes_metadata(tmp_path):
    source = tmp_path / "sample.csv"
    source.write_text("name,value\nA,10\nB,20\n", encoding="utf-8")

    output = import_table(str(source), str(tmp_path / "output"))
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))

    assert (output / "data.csv").exists()
    assert metadata["source_format"] == "csv"
    assert metadata["delimiter"] == "comma"
    assert metadata["row_count"] == 2
    assert metadata["column_count"] == 2
    assert metadata["structural_validation"] == "passed"
    assert len(metadata["input_sha256"]) == 64


def test_imports_tsv(tmp_path):
    source = tmp_path / "sample.tsv"
    source.write_text("name\tvalue\nA\t10\n", encoding="utf-8")

    output = import_table(str(source), str(tmp_path / "output"))
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["source_format"] == "tsv"
    assert metadata["delimiter"] == "tab"


def test_rejects_inconsistent_rows(tmp_path):
    source = tmp_path / "bad.csv"
    source.write_text("name,value\nA,10,unexpected\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expected 2"):
        import_table(str(source), str(tmp_path / "output"))


def test_imports_snapshot_with_arbitrary_columns(tmp_path):
    source = tmp_path / "mutations.csv"
    source.write_text(
        "GeneName,Number of mutations\nBRCA1,12\nTP53,27\n",
        encoding="utf-8",
    )
    mapping = tmp_path / "mutations.mapping.json"
    mapping.write_text(
        json.dumps({
            "topic": "gene_mutations",
            "source": "user_upload",
            "mode": "snapshot",
            "category_column": "GeneName",
            "value_column": "Number of mutations",
        }),
        encoding="utf-8",
    )

    output = import_table(
        str(source), str(tmp_path / "output"), str(mapping)
    )
    frame = __import__("pandas").read_csv(output / "data.csv")
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))

    assert "__snapshot_period" in frame.columns
    assert set(frame["__measure"]) == {"value"}
    assert set(frame["__snapshot_period_type"]) == {"snapshot"}
    assert metadata["generic_input"]["mode"] == "snapshot"
    assert metadata["temporalVariables"]["column"] == "__snapshot_period"
    assert metadata["valueVariables"] == {"Number of mutations": {}}
