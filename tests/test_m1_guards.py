"""M1 regression probes. HTML fixtures are synthetic, not rendered outputs."""
import copy
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from analyse import select_series
from publish import build_provenance
from test_pipeline import project, run  # noqa: F401
from verify_release import check_provenance

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("year", [2019, 2025])
@pytest.mark.parametrize("damage", ["absent", "null"])
def test_m1_missing_count_excluded(project, year, damage):  # noqa: F811
    bundle = run(project)
    data = pd.read_parquet(project[1] / "harmonised.parquet")
    mask = (data.topic == "virus") & (data.year == year)
    if damage == "absent":
        data = data.loc[~mask].copy()
    else:
        data.loc[mask, "value"] = float("nan")
    cfg = json.loads((bundle / "stakeholder.json").read_text())
    classes = pd.read_csv(project[3]).set_index("topic").to_dict("index")
    used, decisions = select_series(data, cfg, classes)
    assert "virus" not in {item["topic"] for item in used}
    excluded = decisions.loc[decisions.topic == "virus"]
    assert len(excluded) == 1
    assert excluded.iloc[0].status == "excluded"
    assert str(year) in excluded.iloc[0].reason


@pytest.fixture(params=["researcher", "health_institution", "public"])
def m1_provenance_case(project, tmp_path, request):  # noqa: F811
    cfg_path = project[2]
    cfg = json.loads(cfg_path.read_text())
    audience = request.param
    profile = json.loads((ROOT / "scripts/health_pipeline/config/stakeholders" /
                          f"{audience}.json").read_text())
    cfg.update({key: profile[key] for key in
                ("id", "title", "question", "outputs", "presentation")})
    cfg_path.write_text(json.dumps(cfg))
    bundle = run(project)
    folder = tmp_path / "reports" / audience
    folder.mkdir(parents=True)
    shutil.copytree(bundle, folder / "data")
    records = {
        "provenance.json": build_provenance(bundle, "html", quarto="m1-no-quarto"),
        "provenance.pdf.json": build_provenance(bundle, "pdf", quarto="m1-no-quarto"),
    }
    return folder, records


def write_records(folder, records):
    for name, record in records.items():
        (folder / name).write_text(json.dumps(record))
    script = ('<script type="application/json" id="report-provenance">' +
              json.dumps(records["provenance.json"]) + '</script>')
    for name in ("report.html", "methods.html"):
        (folder / name).write_text(script)


def test_m1_valid_provenance(m1_provenance_case):
    folder, records = m1_provenance_case
    write_records(folder, records)
    assert check_provenance(folder) == []


@pytest.mark.parametrize("field", ["effective_parameters", "filters", "stakeholder"])
def test_m1_consistent_but_false_provenance_rejected(m1_provenance_case, field):
    folder, original = m1_provenance_case
    records = copy.deepcopy(original)
    for record in records.values():
        if field == "stakeholder":
            record[field]["id"] = "wrong_audience"
        else:
            record[field]["geography"] = "CH" if record[field]["geography"] == "CHFL" else "CHFL"
    write_records(folder, records)
    assert check_provenance(folder), (
        f"Verifier accepted false {field} even though stakeholder.json is unchanged"
    )


def test_m1_embedded_mismatch_rejected(m1_provenance_case):
    folder, records = m1_provenance_case
    write_records(folder, records)
    (folder / "report.html").write_text(
        '<script type="application/json" id="report-provenance">{}</script>'
    )
    assert any("embedded provenance differs" in error for error in check_provenance(folder))


def test_m1_zero_reference_is_unavailable(project):  # noqa: F811
    from test_pipeline import edit_csv

    cfg_path = project[2]
    cfg = json.loads(cfg_path.read_text())
    cfg["index_base_year"] = 2021
    cfg_path.write_text(json.dumps(cfg))

    def change(data):
        data.loc[data.temporal == 2019, "value"] = 0
        return data

    edit_csv(project, change)
    bundle = run(project)
    metrics = pd.read_csv(bundle / "metrics.csv").set_index("metric_id")
    assert metrics.loc["virus:2019:count", "value"] == 0
    assert pd.isna(metrics.loc["virus:reference_change", "value"])
    assert pd.isna(metrics.loc["viral:main:reference_change", "value"])
    assert metrics.loc["viral:main:2021:index", "value"] == 100


def test_m1_positive_reference_preserves_percentage(project):  # noqa: F811
    bundle = run(project)
    metrics = pd.read_csv(bundle / "metrics.csv").set_index("metric_id")
    assert metrics.loc["virus:reference_change", "value"] == pytest.approx(60)
    assert metrics.loc["viral:main:reference_change", "value"] == pytest.approx(60)


def test_m1_zero_latest_is_minus_100_percent(project):  # noqa: F811
    from test_pipeline import edit_csv

    def change(data):
        data.loc[data.temporal == 2025, "value"] = 0
        return data

    edit_csv(project, change)
    bundle = run(project)
    metrics = pd.read_csv(bundle / "metrics.csv").set_index("metric_id")
    assert metrics.loc["virus:2025:count", "value"] == 0
    assert metrics.loc["virus:reference_change", "value"] == pytest.approx(-100)
    assert metrics.loc["viral:main:reference_change", "value"] == pytest.approx(-100)
