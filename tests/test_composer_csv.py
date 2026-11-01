"""HTTP integration tests for the neutral "Your CSV" mode.

One ThreadingHTTPServer on an ephemeral loopback port, driven with urllib: multipart upload,
bounded capture, interpretation confirmation, dataset passport, neutral recipe validation and
job launch with a stubbed render (labelled; the real render is covered by the R smoke and the
pinned-image render).
"""
import hashlib
import json
import os
import shutil
import threading
import time as _time
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.client import HTTPConnection
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "health_pipeline"))

import composer_site  # noqa: E402
import neutral_describe  # noqa: E402
import neutral_publish  # noqa: E402
import neutral_library as neutral_lib  # noqa: E402

SESSIONS = {}


def stub_render(bundle, output, fmt, quarto, provenance, provenance_out, composition):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    Path(provenance_out).write_text(json.dumps(provenance), encoding="utf-8")
    output.write_text("<!DOCTYPE html><title>stub neutral report</title><p>stub</p>",
                      encoding="utf-8")
    (output.parent / "methods.html").write_text("<p>methods</p>", encoding="utf-8")
    (output.parent / "data").mkdir(exist_ok=True)
    return output


def neutral_stub_render(bundle, output, fmt, quarto, provenance, provenance_out, composition):
    """TEST DOUBLE: the neutral package layout without invoking Quarto.

    It writes the same recorded identities the reuse validator reads (provenance built by the
    real neutral_publish builder, frozen composition, package data), so reuse/history tests run
    fast. Real Quarto renders are covered by the render scripts and the Data & sources tests.
    """
    output = Path(output)
    package = output.parent
    package.mkdir(parents=True, exist_ok=True)
    recipe_path = Path(composition)
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    frozen = package / "composition.json"
    if recipe_path.resolve() != frozen.resolve():
        shutil.copyfile(recipe_path, frozen)
    (package / "reproduction").mkdir(exist_ok=True)
    shutil.copyfile(frozen, package / "reproduction" / "composition.json")
    bundle = Path(bundle)
    record = neutral_publish.build_neutral_provenance(bundle, recipe, composition, ROOT)
    # The real renderer records the disclosure evaluation separately; reuse validation reads it.
    analysis = json.loads((bundle / "neutral-analysis.json").read_text(encoding="utf-8"))
    prepared = json.loads((bundle / "prepared.json").read_text(encoding="utf-8"))
    record["disclosure"] = neutral_publish.disclosure_record(
        recipe["disclosure"], analysis, prepared, recipe)
    record["preview"] = {"status": "preview", "accepted_output": False,
                         "notice": "Stub preview render."}
    Path(provenance_out).write_text(json.dumps(record), encoding="utf-8")
    output.write_text("<!DOCTYPE html><title>stub neutral report</title>", encoding="utf-8")
    (package / "methods.html").write_text("<p>methods</p>", encoding="utf-8")
    data = package / "data"
    data.mkdir(exist_ok=True)
    for name in ("dataset.json", "interpretation.json"):
        shutil.copyfile(bundle / name, data / name)
    if (recipe.get("disclosure") or {}).get("policy") == "restricted-share":
        shutil.copyfile(bundle / "neutral-analysis.json", data / "neutral-summary.json")
    else:
        shutil.copyfile(bundle / "neutral-analysis.json", data / "neutral-analysis.json")
    return output


class RenderCounter:
    """Counts renderer invocations so a test can prove a reuse did not render."""

    def __init__(self):
        self.calls = 0

    def __call__(self, bundle, output, fmt, quarto, provenance, provenance_out, composition):
        self.calls += 1
        return neutral_stub_render(bundle, output, fmt, quarto, provenance, provenance_out,
                                   composition)


def make_site(tmp_path, render=stub_render):
    site = composer_site.Site(tmp_path / "work", tmp_path / "inputs", tmp_path / "inputs",
                              tmp_path / "recipes", workflow_config=None, quarto="quarto",
                              render=render)
    server = composer_site.build_server(site, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host = f"127.0.0.1:{server.server_address[1]}"
    return site, server, host


def token_exchange(host, token):
    conn = HTTPConnection("127.0.0.1", int(host.rsplit(":", 1)[1]))
    conn.request("GET", f"/?token={token}", headers={"Host": host})
    response = conn.getresponse()
    conn.close()
    return response.status, dict(response.getheaders())


def cookie_from(headers):
    return headers.get("Set-Cookie", "").split(";", 1)[0]


def multipart_body(filename, payload):
    boundary = "----csvtestboundary"
    parts = [f"--{boundary}\r\n",
             f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n',
             "Content-Type: text/csv\r\n\r\n",
             payload.decode("utf-8"),
             f"\r\n--{boundary}--\r\n"]
    return "".join(parts).encode("utf-8"), boundary


@pytest.fixture()
def real_csv_site(tmp_path):
    """Same site, but with the real Quarto renderer: the report package is the real one."""
    site, server, host = make_site(tmp_path, render=None)
    status, headers = token_exchange(host, site.access_token)
    assert status == 302
    cookie = cookie_from(headers)
    assert cookie
    SESSIONS[host] = cookie
    yield site, host
    site.wait_idle(30)
    server.shutdown()


@pytest.fixture()
def csv_site(tmp_path):
    site, server, host = make_site(tmp_path)
    status, headers = token_exchange(host, site.access_token)
    assert status == 302
    cookie = cookie_from(headers)
    assert cookie
    SESSIONS[host] = cookie
    yield site, host
    site.wait_idle(5)
    server.shutdown()


def api(site, host, method, path, payload=None, headers=None):
    h = {"Host": host, "Cookie": SESSIONS[host]}
    if headers:
        h.update(headers)
    body = None
    if isinstance(payload, bytes):
        body = payload
        h["Content-Type"] = headers.get("Content-Type", "application/octet-stream")
    elif isinstance(payload, str):
        body = payload.encode("utf-8")
        h["Content-Type"] = "text/plain"
    elif payload is not None:
        body = json.dumps(payload).encode("utf-8")
        h["Content-Type"] = "application/json"
        if "/api/csv/confirm" in path:
            h["X-Composer-Action"] = "csv-confirm"
        elif "/api/csv/generate" in path:
            h["X-Composer-Action"] = "csv-generate"
        elif "/api/csv/edit" in path:
            h["X-Composer-Action"] = "csv-edit"
    request = urllib.request.Request(f"http://{host}{path}", data=body, method=method,
                                     headers=h)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = json.loads(error.read().decode("utf-8")) if error.headers.get(
            "Content-Type", "").startswith("application/json") else {}
        return error.code, detail


SAMPLE = ("city,value,year\n"
          "Zurich,120,2021\nZurich,150,2022\n"
          "Bern,90,2021\nBern,110,2022\n")


def upload(site, host, payload=SAMPLE, filename="sample.csv"):
    body, boundary = multipart_body(filename, payload.encode("utf-8"))
    status, doc = api(site, host, "POST", "/api/csv/upload", body,
                      headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return status, doc


def test_csv_mode_document_lists_empty_datasets(csv_site):
    site, host = csv_site
    status, doc = api(site, host, "GET", "/api/csv")
    assert status == 200
    assert doc["mode"] == "csv"
    assert doc["datasets"] == []
    assert doc["selected_digest"] is None


def test_upload_capture_and_confirmation_flow(csv_site):
    site, host = csv_site
    status, doc = upload(site, host)
    assert status == 200
    capture = doc["capture"]
    assert capture["logical_records"] == 4
    assert capture["columns"] == ["city", "value", "year"]
    digest = capture["input_sha256"]
    assert digest == hashlib.sha256(SAMPLE.encode("utf-8")).hexdigest()

    status, doc = api(site, host, "GET", f"/api/csv?digest={digest}")
    assert status == 200
    assert doc["selected_digest"] == digest
    suggestion = doc["confirmation"]["suggestion"]
    assert suggestion == {"category": "city", "measure": "value", "time": "year"}
    assert doc["confirmation"]["preview"]["logical_records"] == 4

    interpretation = {
        "category": "city", "measure": "value", "time": "year",
        "measure_label": "Observed value", "unit": "not specified",
        "meaning": "a reading per city per year",
    }
    status, doc = api(site, host, "POST", "/api/csv/confirm",
                      {"digest": digest, "interpretation": interpretation})
    assert status == 200
    assert doc["confirmed"]["category"] == "city"
    assert doc["analysis"]["row_count"] == 4
    assert doc["analysis"]["group_count"] == 2
    assert doc["analysis"]["summary"]["median"] == 115.0
    assert doc["analysis"]["time"]["has_time"] is True

    status, doc = api(site, host, "GET", f"/api/csv?digest={digest}")
    assert status == 200
    assert doc["recipe"]["audience"] == "neutral-overview"
    blocks = [entry["block"] for entry in doc["recipe"]["blocks"]]
    assert blocks[1] == "data-overview"
    assert "values-over-time" in blocks and "values-by-group" not in blocks
    assert "limitations" in blocks and "reproduction" in blocks


def test_upload_rejects_bad_structure_and_keeps_no_dataset(csv_site):
    site, host = csv_site
    status, doc = upload(site, host, payload="a,b\n1,2,3\n", filename="broken.csv")
    assert status == 400
    assert doc["error"]["code"] == "csv_rejected"
    status, doc = api(site, host, "GET", "/api/csv")
    assert doc["datasets"] == []


def test_upload_rejects_wrong_extension(csv_site):
    site, host = csv_site
    status, doc = upload(site, host, payload=SAMPLE, filename="evil.txt")
    assert status == 400
    assert ".csv and .tsv" in doc["error"]["message"]


def test_confirmation_requires_existing_columns(csv_site):
    site, host = csv_site
    status, doc = upload(site, host)
    digest = doc["capture"]["input_sha256"]
    status, doc = api(site, host, "POST", "/api/csv/confirm",
                      {"digest": digest, "interpretation": {"category": "nope",
                                                            "measure": "value"}})
    assert status == 400
    assert doc["error"]["code"] == "csv_conflict"


def test_generate_requires_confirmation(csv_site):
    site, host = csv_site
    status, doc = upload(site, host)
    digest = doc["capture"]["input_sha256"]
    status, doc = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest, "recipe": neutral_lib.default_recipe(False)})
    assert status == 409
    assert doc["error"]["code"] == "csv_not_confirmed"


def test_generate_launches_job_with_stub_render(csv_site):
    site, host = csv_site
    status, doc = upload(site, host)
    digest = doc["capture"]["input_sha256"]
    api(site, host, "POST", "/api/csv/confirm",
        {"digest": digest,
         "interpretation": {"category": "city", "measure": "value", "time": "year"}})
    recipe = neutral_lib.default_recipe(has_time=True)
    recipe["disclosure"] = neutral_lib.disclosure_record("local-audit")
    status, doc = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest, "recipe": recipe})
    assert status == 202
    job = doc
    assert job["mode"] == "csv" and job["origin"] == "csv" and job["context"] == digest
    site.wait_idle(10)
    status, doc = api(site, host, "GET", f"/api/jobs/{job['job_id']}")
    assert doc["status"] == "succeeded"
    assert "publish.py html" in doc["replay_command"]
    assert "csv-datasets" in doc["replay_command"]
    found = sorted((site.jobs_root / job["job_id"]).rglob("provenance.json"))
    assert found
    record = json.loads(found[0].read_text())
    source = record["code"]["source_identity"]
    assert source["content"]["digest"]
    assert source["origin"] in {"runtime-git", "unavailable", "host-supplied"}


def test_csv_generation_fails_closed_on_invalid_supplied_identity(csv_site, tmp_path,
                                                                  monkeypatch):
    site, host = csv_site
    broken = tmp_path / "broken-identity.json"
    broken.write_text("{", encoding="utf-8")
    monkeypatch.setenv("HEALTH_REPORT_SOURCE_IDENTITY", str(broken))
    status, doc = upload(site, host)
    digest = doc["capture"]["input_sha256"]
    api(site, host, "POST", "/api/csv/confirm",
        {"digest": digest,
         "interpretation": {"category": "city", "measure": "value", "time": "year"}})
    recipe = neutral_lib.default_recipe(has_time=True)
    recipe["disclosure"] = neutral_lib.disclosure_record("local-audit")
    status, job = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest, "recipe": recipe})
    assert status == 202
    site.wait_idle(10)
    status, doc = api(site, host, "GET", f"/api/jobs/{job['job_id']}")
    assert doc["status"] == "failed"
    assert "source-identity" in doc["error"].lower() or "source identity" in doc["error"].lower()
    assert not list((site.jobs_root / job["job_id"]).rglob("report.html"))


def test_recipe_validation_rejects_health_blocks(csv_site):
    site, host = csv_site
    status, doc = upload(site, host)
    digest = doc["capture"]["input_sha256"]
    api(site, host, "POST", "/api/csv/confirm",
        {"digest": digest,
         "interpretation": {"category": "city", "measure": "value", "time": "year"}})
    status, doc = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest,
                       "recipe": {"contract": "health-report/composition-recipe/2",
                                  "audience": "neutral-overview",
                                  "blocks": [
                                      {"block": "series-collection",
                                       "instance_id": "c-series-0001",
                                       "topics": "eligible", "measure": "cases"}]}})
    assert status == 400
    assert doc["error"]["code"] == "csv_recipe"


# ------------------------------------------------------------------ full journey

INTERP = {"category": "city", "measure": "value",
          "measure_label": "Observed value", "unit": "not specified",
          "meaning": "a reading per city", "missing_tokens": []}

SNAPSHOT_CSV = "city,value\nA,10\nA,20\nB,5\nB,15\n"
TIMESERIES_CSV = ("city,value,year\nZurich,120,2021\nZurich,150,2022\n"
                  "Bern,90,2021\nBern,110,2022\n")


def journey(site, host, payload, interpretation=None, time=None):
    status, doc = upload(site, host, payload=payload, filename="data.csv")
    assert status == 200, doc
    digest = doc["capture"]["input_sha256"]
    interp = dict(interpretation or INTERP)
    if time:
        interp["time"] = time
    status, doc = api(site, host, "POST", "/api/csv/confirm",
                      {"digest": digest, "interpretation": interp})
    assert status == 200, doc
    return digest, doc


def choose(site, host, digest, policy="local-audit", permit_records=False):
    """Record the explicit disclosure choice on the saved draft."""
    status, doc = api(site, host, "POST", "/api/csv/edit",
                      {"digest": digest, "action": "set-disclosure", "instance": None,
                       "value": {"policy": policy, "permit_records": permit_records}})
    assert status == 200, doc
    return doc["document"]


def test_generate_requires_an_explicit_disclosure_choice(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    status, doc = api(site, host, "GET", f"/api/csv?digest={digest}")
    assert doc["disclosure"] is None
    assert [item["code"] for item in doc["disclosure_conflicts"]] == ["disclosure_required"]
    status, doc = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest, "recipe": doc["recipe"]})
    assert status == 400
    assert doc["error"]["code"] == "csv_disclosure"
    assert "Choose how observed values are handled" in doc["error"]["message"]


def test_restricted_policy_rejects_value_sections_and_accepts_the_named_coverage_block(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, TIMESERIES_CSV, time="year")
    doc = choose(site, host, digest, "restricted-share")
    blocks = [entry["block"] for entry in doc["recipe"]["blocks"]]
    assert "values-over-time" in blocks
    conflicts = doc["disclosure_conflicts"]
    assert [item["code"] for item in conflicts] == ["incompatible_block"]
    assert "Values over time" in conflicts[0]["message"]
    assert "Observation coverage over time" in conflicts[0]["message"]
    # The server refuses the unresolved combination before any job exists.
    status, error = api(site, host, "POST", "/api/csv/generate",
                        {"digest": digest, "recipe": doc["recipe"]})
    assert status == 400 and error["error"]["code"] == "csv_disclosure"
    assert "restricted shareable export excludes" in error["error"]["message"]

    # Replace it with the explicitly named availability block: now it publishes.
    instance = next(entry["instance_id"] for entry in doc["recipe"]["blocks"]
                    if entry["block"] == "values-over-time")
    api(site, host, "POST", "/api/csv/edit",
        {"digest": digest, "action": "exclude", "instance": instance, "value": None})
    doc = api(site, host, "POST", "/api/csv/edit",
              {"digest": digest, "action": "include", "instance": "coverage-over-time",
               "value": None})[1]["document"]
    assert [entry["block"] for entry in doc["recipe"]["blocks"]].count(
        "coverage-over-time") == 1
    assert doc["disclosure_conflicts"] == []
    status, job = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest, "recipe": doc["recipe"]})
    assert status == 202
    site.wait_idle(10)
    record = api(site, host, "GET", f"/api/jobs/{job['job_id']}")[1]
    assert record["status"] == "succeeded"
    assert record["replay_command"]


def test_restricted_policy_cannot_permit_values_or_records(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    status, doc = api(site, host, "POST", "/api/csv/edit",
                      {"digest": digest, "action": "set-disclosure", "instance": None,
                       "value": {"policy": "restricted-share", "permit_records": True}})
    assert status == 400
    assert doc["error"]["code"] == "csv_recipe"
    assert "cannot include contributing records" in doc["error"]["message"]


def test_local_audit_cannot_withhold_values(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    status, doc = api(site, host, "POST", "/api/csv/edit",
                      {"digest": digest, "action": "set-disclosure", "instance": None,
                       "value": {"policy": "local-audit", "permit_records": False}})
    assert status == 200
    assert doc["recipe"]["disclosure"]["permit_values"] is True
    status, doc = api(site, host, "POST", "/api/csv/edit",
                      {"digest": digest, "action": "set-disclosure", "instance": None,
                       "value": {"policy": "local-audit", "permit_values": False,
                                 "permit_records": False}})
    assert status == 400 and doc["error"]["code"] == "csv_recipe"


def test_disclosure_choice_persists_and_reaches_the_saved_recipe(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest, "local-audit", permit_records=True)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert doc["disclosure"]["policy"] == "local-audit"
    assert doc["disclosure"]["permit_values"] is True
    assert doc["disclosure"]["permit_records"] is True
    # The published document advertises the consequences, not just the policy names.
    options = {entry["policy"]: entry for entry in doc["disclosure_options"]}
    assert "not private once you share" in options["local-audit"]["detail"]
    assert "anonymous or universally safe" in options["restricted-share"]["detail"]


def test_unsupported_capability_is_rejected_before_generation(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)      # no time column
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    recipe = dict(doc["recipe"])
    recipe["blocks"] = list(recipe["blocks"]) + [
        {"block": "coverage-over-time", "instance_id": "c-coverage-0001",
         "time_period": "year"}]
    status, error = api(site, host, "POST", "/api/csv/generate",
                        {"digest": digest, "recipe": recipe})
    assert status == 400 and error["error"]["code"] == "csv_capability"
    assert "No time column is confirmed" in error["error"]["message"]


def test_failed_generation_leaves_the_previous_report_intact(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    status, job = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest, "recipe": doc["recipe"]})
    assert status == 202
    site.wait_idle(10)
    first = api(site, host, "GET", f"/api/jobs/{job['job_id']}")[1]
    assert first["status"] == "succeeded"
    # A refused request never replaces accepted output.
    bad = dict(doc["recipe"])
    bad["blocks"] = [entry for entry in bad["blocks"] if entry["block"] != "limitations"]
    status, error = api(site, host, "POST", "/api/csv/generate",
                        {"digest": digest, "recipe": bad})
    assert status == 400
    still = api(site, host, "GET", f"/api/jobs/{job['job_id']}")[1]
    assert still["status"] == "succeeded"
    assert still["recipe_sha256"] == first["recipe_sha256"]


def test_journey_snapshot(csv_site):
    site, host = csv_site
    digest, conf = journey(site, host, SNAPSHOT_CSV)
    assert conf["analysis"]["time"]["has_time"] is False
    assert conf["analysis"]["group_count"] == 2
    assert conf["analysis"]["summary"]["median"] == 12.5
    status, doc = api(site, host, "GET", f"/api/csv?digest={digest}")
    assert status == 200
    blocks = [entry["block"] for entry in doc["recipe"]["blocks"]]
    assert "values-by-group" in blocks and "values-over-time" not in blocks
    assert doc["composer"][0]["block"] == "intro"
    doc = choose(site, host, digest)
    status, job = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest, "recipe": doc["recipe"]})
    assert status == 202
    site.wait_idle(10)
    status, record = api(site, host, "GET", f"/api/jobs/{job['job_id']}")
    assert record["status"] == "succeeded"
    assert "csv-datasets" in record["replay_command"]


def test_journey_timeseries(csv_site):
    site, host = csv_site
    digest, conf = journey(site, host, TIMESERIES_CSV, time="year")
    assert conf["analysis"]["time"]["column"] == "year"
    status, doc = api(site, host, "GET", f"/api/csv?digest={digest}")
    blocks = [entry["block"] for entry in doc["recipe"]["blocks"]]
    assert "values-over-time" in blocks
    doc = choose(site, host, digest)
    status, job = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest, "recipe": doc["recipe"]})
    assert status == 202
    site.wait_idle(10)
    status, record = api(site, host, "GET", f"/api/jobs/{job['job_id']}")
    assert record["status"] == "succeeded"


def test_csv_edit_persists_draft(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    status, doc = api(site, host, "GET", f"/api/csv?digest={digest}")
    first = doc["recipe"]["blocks"][1]["instance_id"]
    status, result = api(site, host, "POST", "/api/csv/edit",
                         {"digest": digest, "action": "set-title", "instance": first,
                          "value": "City values"})
    assert status == 200
    assert result["recipe"]["titles"][first] == "City values"
    assert result["document"]["composer"][1]["title"] == "City values"
    status, doc = api(site, host, "GET", f"/api/csv?digest={digest}")
    assert doc["recipe"]["titles"][first] == "City values"


def test_csv_capability_separation(csv_site):
    """Neutral data is reachable by the neutral composer, and never by the health one."""
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    status, doc = api(site, host, "GET", f"/api/csv?digest={digest}")
    assert doc["analysis"]["row_count"] == 4
    import composer_library as library
    offered = [entry["block"] for entry in library.inventory()]
    assert not {"data-overview", "values-by-group", "values-over-time", "data-quality"} \
        & set(offered)
    status, doc = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest,
                       "recipe": {"contract": "health-report/composition-recipe/2",
                                  "audience": "neutral-overview",
                                  "blocks": [{"block": "series-collection",
                                              "instance_id": "c-series-0001",
                                              "topics": "eligible",
                                              "measure": "cases"}]}})
    assert status == 400 and doc["error"]["code"] == "csv_recipe"


# ------------------------------------------------------------------ review regressions
# Findings A–D from the human browser review, exercised through the same site methods the HTTP
# routes call. Styles and the DOM contract are covered by the Node harness separately.

FIXTURE_SNAPSHOT = ('record_id,group,value\n'
                    '"001","North, region A",12.5\n'
                    '"002","North, region A",13.5\n'
                    '"003","North, region A",\n'
                    '"004","South",20\n'
                    '"005","South",21\n'
                    '"006",,22\n'
                    '"007","South",23\n'
                    '"008","South",24\n')


def test_record_counts_are_served_before_after_and_on_reopen(csv_site):
    """Finding C: the list said 'null records' and the passport '?'."""
    site, host = csv_site
    status, doc = upload(site, host, payload=FIXTURE_SNAPSHOT, filename="snapshot.csv")
    assert status == 200, doc
    assert doc["capture"]["logical_records"] == 8
    digest = doc["capture"]["input_sha256"]

    doc = api(site, host, "GET", "/api/csv")[1]
    listed = next(item for item in doc["datasets"] if item["digest"] == digest)
    assert listed["record_count"] == 8

    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert doc["confirmation"]["dataset"]["record_count"] == 8
    assert doc["confirmation"]["preview"]["logical_records"] == 8

    api(site, host, "POST", "/api/csv/confirm",
        {"digest": digest, "interpretation": {"category": "group", "measure": "value",
                                              "time": None}})
    doc = api(site, host, "GET", "/api/csv?digest={}".format(digest))[1]
    assert doc["confirmation"]["dataset"]["record_count"] == 8
    assert doc["analysis"]["row_count"] == 8
    assert api(site, host, "GET", "/api/csv")[1]["datasets"][0]["record_count"] == 8


def test_api_offers_and_accepts_the_coverage_block(csv_site):
    """Finding A: the editor offered it while the API called it unknown."""
    site, host = csv_site
    digest, _ = journey(site, host, TIMESERIES_CSV, time="year")
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert "coverage-over-time" in [entry["block"] for entry in doc["blocks"]]
    status, doc = api(site, host, "POST", "/api/csv/edit",
                      {"digest": digest, "action": "include",
                       "instance": "coverage-over-time", "value": None})
    assert status == 200, doc
    row = next(entry for entry in doc["document"]["composer"]
               if entry["block"] == "coverage-over-time")
    assert row["label"] == "Observation coverage over time"
    assert row["summary"] is None
    assert "coverage-over-time" in [entry["block"] for entry in doc["document"]["recipe"]["blocks"]]


def test_health_library_never_offers_neutral_blocks(csv_site):
    import composer_library as library
    offered = {entry["block"] for entry in library.inventory()}
    assert not {"data-overview", "values-by-group", "values-over-time", "coverage-over-time",
                "data-quality"} & offered


def test_snapshot_with_no_time_records_no_observation_date(csv_site):
    """Finding D: record_id was suggested as time and '001' failed."""
    site, host = csv_site
    status, doc = upload(site, host, payload=FIXTURE_SNAPSHOT, filename="snapshot.csv")
    digest = doc["capture"]["input_sha256"]
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert doc["confirmation"]["suggestion"]["time"] is None
    status, doc = api(site, host, "POST", "/api/csv/confirm",
                      {"digest": digest, "interpretation": {"category": "group",
                                                            "measure": "value",
                                                            "time": None}})
    assert status == 200, doc
    assert doc["analysis"]["time"]["has_time"] is False
    assert doc["analysis"]["time"]["column"] is None
    assert doc["analysis"]["missing"]["periods"] == 0
    # Quoted labels survive verbatim, including the comma inside the name.
    assert doc["analysis"]["groups"][0]["group"] == "North, region A"
    reopened = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert reopened["confirmation"]["confirmation"]["time"] is None


def test_legacy_no_policy_draft_is_recoverable_but_requires_a_choice(csv_site, tmp_path):
    """Finding B: an old draft without a disclosure choice must not generate silently."""
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    draft_dir = site.work_root / "drafts" / "csv" / digest
    draft_dir.mkdir(parents=True, exist_ok=True)
    legacy = {"schema": "health-report/csv-draft/1", "digest": digest,
              "recipe": neutral_lib.default_recipe(False), "updated_utc": "2026-10-30T00:00:00Z"}
    (draft_dir / "editor.json").write_text(json.dumps(legacy), encoding="utf-8")

    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert doc["recipe"]["blocks"], "the legacy draft must still be readable"
    assert "disclosure" not in doc["recipe"]
    assert [item["code"] for item in doc["disclosure_conflicts"]] == ["disclosure_required"]
    jobs_before = len(list(site.jobs_root.glob("*")))
    status, error = api(site, host, "POST", "/api/csv/generate",
                        {"digest": digest, "recipe": doc["recipe"]})
    assert status == 400 and error["error"]["code"] == "csv_disclosure"
    assert len(list(site.jobs_root.glob("*"))) == jobs_before, "a refused request made a job"

    doc = choose(site, host, digest)
    assert doc["disclosure_conflicts"] == []
    status, job = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest, "recipe": doc["recipe"]})
    assert status == 202


def test_conflicting_combination_creates_no_job(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, TIMESERIES_CSV, time="year")
    doc = choose(site, host, digest, "restricted-share")
    jobs_before = len(list(site.jobs_root.glob("*")))
    status, error = api(site, host, "POST", "/api/csv/generate",
                        {"digest": digest, "recipe": doc["recipe"]})
    assert status == 400 and error["error"]["code"] == "csv_disclosure"
    assert len(list(site.jobs_root.glob("*"))) == jobs_before


# ------------------------------------------------------------------ display settings
# Presentation-only controls (P1-P4). The saved analysis must never change underneath them.

def display_edit(site, host, digest, instance, display):
    return api(site, host, "POST", "/api/csv/edit",
               {"digest": digest, "action": "set-display", "instance": instance,
                "value": display})


def block_row(document, instance):
    return next(entry for entry in document["composer"] if entry["instance_id"] == instance)


def test_display_settings_persist_and_leave_the_analysis_untouched(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, TIMESERIES_CSV, time="year")
    choose(site, host, digest)
    analysis_path = site._csv_dataset_dir(digest) / "neutral-analysis.json"
    before = analysis_path.read_bytes()
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    instance = block_row(doc, "csv-values-over-time")["instance_id"]
    status, result = display_edit(site, host, digest, instance, {
        "groups": ["Zurich"], "periods": {"mode": "list",
                                          "values": ["2021-01-01T00:00:00"]},
        "axis_labels": {"mode": "every_n", "n": 2}, "layout": "panels",
        "precision": {"mode": "decimal", "places": 2}, "height": 4.0, "columns": 1,
        "panel_scale": "shared"})
    assert status == 200, result
    assert analysis_path.read_bytes() == before, "display settings changed the analysis"
    row = block_row(result["document"], instance)
    assert row["display"]["layout"] == "panels"
    assert row["display"]["groups"] == ["Zurich"]
    assert "Showing 1 of 2 analysed groups" in row["display_summary"]
    reopened = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert block_row(reopened, instance)["display"]["axis_labels"] == {"mode": "every_n", "n": 2}
    assert analysis_path.read_bytes() == before


def test_display_rejects_unknown_groups_and_wrong_layout(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, TIMESERIES_CSV, time="year")
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    instance = block_row(doc, "csv-values-over-time")["instance_id"]
    status, error = display_edit(site, host, digest, instance, {"groups": ["Atlantis"]})
    assert status == 400 and error["error"]["code"] == "csv_recipe"
    assert "not in the saved analysis" in error["error"]["message"]
    status, error = display_edit(site, host, digest, instance, {"layout": "table", "bogus": 1})
    assert status == 400
    by_group = block_row(doc, "csv-values-over-time")
    status, error = display_edit(site, host, digest, by_group["instance_id"],
                                 {"periods": {"mode": "list", "values": ["1999-01-01T00:00:00"]}})
    assert status == 400 and "not in the saved analysis" in error["error"]["message"]


def test_statistics_columns_and_precision_are_saved_per_instance(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    instance = block_row(doc, "csv-values-by-group")["instance_id"]
    status, result = display_edit(site, host, digest, instance, {
        "statistics": ["n", "median", "middle50", "range", "sd"],
        "precision": {"mode": "decimal", "places": 2}})
    assert status == 200, result
    row = block_row(result["document"], instance)
    assert row["display"]["statistics"] == ["n", "median", "middle50", "range", "sd"]
    assert row["display"]["precision"]["places"] == 2


def test_duplicate_instances_keep_independent_display_settings(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, TIMESERIES_CSV, time="year")
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    original = block_row(doc, "csv-values-over-time")["instance_id"]
    status, result = api(site, host, "POST", "/api/csv/edit",
                         {"digest": digest, "action": "duplicate", "instance": original,
                          "value": None})
    assert status == 200, result
    copy = [entry for entry in result["document"]["composer"]
            if entry["block"] == "values-over-time"
            and entry["instance_id"] != original][0]["instance_id"]
    display_edit(site, host, digest, original, {"groups": ["Zurich"]})
    display_edit(site, host, digest, copy, {"groups": ["Bern"]})
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert block_row(doc, original)["display"]["groups"] == ["Zurich"]
    assert block_row(doc, copy)["display"]["groups"] == ["Bern"]


def test_excluded_section_keeps_its_settings_when_restored(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, TIMESERIES_CSV, time="year")
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    instance = block_row(doc, "csv-values-over-time")["instance_id"]
    display_edit(site, host, digest, instance, {"layout": "table",
                                                "precision": {"mode": "decimal", "places": 3}})
    api(site, host, "POST", "/api/csv/edit",
        {"digest": digest, "action": "set-title", "instance": instance,
         "value": "North detail"})
    status, result = api(site, host, "POST", "/api/csv/edit",
                         {"digest": digest, "action": "exclude", "instance": instance,
                          "value": None})
    assert status == 200
    assert instance not in [entry["instance_id"] for entry in result["document"]["recipe"]["blocks"]]
    status, result = api(site, host, "POST", "/api/csv/edit",
                         {"digest": digest, "action": "include", "instance": instance,
                          "value": None})
    assert status == 200, result
    row = block_row(result["document"], instance)
    assert row["display"]["layout"] == "table"
    assert row["display"]["precision"]["places"] == 3
    assert row["title"] == "North detail"


def test_compatibility_cache_is_content_keyed_not_mtime(csv_site):
    """Restoring the mtime must not resurrect a cached "compatible" verdict."""
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert doc["analysis_stale"] is None           # a compatible verdict is now cached

    path = site._csv_dataset_dir(digest) / "neutral-analysis.json"
    original = path.read_bytes()
    stat = path.stat()
    tampered = original.replace(b"12.5", b"99.5", 1)   # same byte length
    assert tampered != original and len(tampered) == len(original)
    path.write_bytes(tampered)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert path.stat().st_mtime_ns == stat.st_mtime_ns

    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert doc["analysis_stale"], "a cached verdict survived a content change with restored mtime"
    status, error = api(site, host, "POST", "/api/csv/generate",
                        {"digest": digest, "recipe": doc["recipe"]})
    assert status == 409 and error["error"]["code"] == "csv_analysis_stale"

    # The same gate the CLI uses must also refuse the tampered bytes.
    prepared = json.loads((site._csv_dataset_dir(digest) / "prepared.json").read_bytes())
    stored = json.loads(tampered)
    confirmed = json.loads((site._csv_dataset_dir(digest) / "interpretation.json").read_bytes())
    ok, reason = neutral_describe.analysis_compatible(prepared, stored, confirmed)
    assert not ok and "no longer matches" in reason


def test_stale_analysis_is_refused_and_updated_explicitly(csv_site):
    """A stored analysis that no longer matches the current definitions must not be reused."""
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    analysis_path = site._csv_dataset_dir(digest) / "neutral-analysis.json"
    stored = json.loads(analysis_path.read_text())
    stored.setdefault("method", {})["calc_version"] = 1   # an older calculation version
    stored["groups"][0]["summary"]["median"] = 999.0      # with a result that no longer matches
    # The current version marker must be equally insufficient on its own; that case is covered
    # by test_compatibility_is_identity_and_integrity_not_version in the data-layer tests.
    analysis_path.write_text(json.dumps(stored), encoding="utf-8")

    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert doc["analysis_stale"], "a doctored analysis must be reported as stale"
    status, error = api(site, host, "POST", "/api/csv/generate",
                        {"digest": digest, "recipe": doc["recipe"]})
    assert status == 409 and error["error"]["code"] == "csv_analysis_stale"
    assert "Update the analysis" in error["error"]["message"]

    # The owner's explicit action: confirm the same interpretation again.
    status, refreshed = api(site, host, "POST", "/api/csv/confirm",
                            {"digest": digest,
                             "interpretation": doc["confirmation"]["confirmation"]})
    assert status == 200, refreshed
    assert refreshed["analysis"]["groups"][0]["summary"]["median"] != 999.0
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert not doc["analysis_stale"]
    status, job = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest, "recipe": doc["recipe"]})
    assert status == 202


def test_new_requests_freeze_the_resolved_display_defaults(csv_site):
    """An omitted display field must not be reinterpreted by future code defaults."""
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert "display" not in [entry for entry in doc["recipe"]["blocks"]
                             if entry["block"] == "values-by-group"][0]
    status, job = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest, "recipe": doc["recipe"]})
    assert status == 202
    snapshot = json.loads((site.jobs_root / job["job_id"] / "composition.json").read_text())
    row = next(entry for entry in snapshot["blocks"] if entry["block"] == "values-by-group")
    assert row["display"]["statistics"] == ["n", "median", "middle50", "range"]
    assert row["display"]["precision"] == {"mode": "decimal", "places": 1}
    assert row["display"]["groups"] is None


def test_display_never_changes_the_numbers_in_the_saved_result(csv_site):
    """A display subset must not alter dataset-wide or per-group statistics."""
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    before = doc["analysis"]["summary"]["median"]
    instance = block_row(doc, "csv-values-by-group")["instance_id"]
    display_edit(site, host, digest, instance, {"groups": ["A"]})
    after = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    assert after["analysis"]["summary"]["median"] == before
    assert after["available"]["groups"] == ["A", "B"]


# ------------------------------------------------------------------ Data & sources panel

def raw_get(host, path):
    """GET without JSON parsing (downloads) and without following redirects."""
    request = urllib.request.Request(f"http://{host}{path}", method="GET",
                                     headers={"Host": host, "Cookie": SESSIONS[host]})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read(), dict(response.getheaders())
    except urllib.error.HTTPError as error:
        return error.code, error.read(), dict(error.headers)


def sources(site, host, job_id):
    return api(site, host, "GET", f"/api/jobs/{job_id}/sources")[1]


def test_sources_are_bound_to_the_saved_report_not_the_draft(real_csv_site):
    site, host = real_csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    instance = block_row(doc, "csv-values-by-group")["instance_id"]
    display_edit(site, host, digest, instance, {"groups": ["A"]})
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    status, job = api(site, host, "POST", "/api/csv/generate",
                      {"digest": digest, "recipe": doc["recipe"]})
    assert status == 202
    site.wait_idle(10)

    before = sources(site, host, job["job_id"])
    assert before["report"]["job_id"] == job["job_id"]
    assert before["data"]["digest"] == digest
    assert before["sections"][0]["groups"] == {"shown": 1, "analysed": 2}

    # Move the editable draft far away from the saved report.
    display_edit(site, host, digest, instance, {"groups": ["B"]})
    api(site, host, "POST", "/api/csv/edit",
        {"digest": digest, "action": "set-title", "instance": instance,
         "value": "Changed after generation"})
    choose(site, host, digest, "restricted-share")

    after = sources(site, host, job["job_id"])
    assert after == before, "the panel followed the draft instead of the saved report"
    assert after["disclosure"]["policy"] == "local-audit"


def test_two_reports_same_dataset_stay_distinguishable(real_csv_site):
    site, host = real_csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    instance = block_row(doc, "csv-values-by-group")["instance_id"]
    display_edit(site, host, digest, instance, {"groups": ["A"], "layout": "table"})
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    first = api(site, host, "POST", "/api/csv/generate",
                {"digest": digest, "recipe": doc["recipe"]})[1]
    site.wait_idle(10)
    display_edit(site, host, digest, instance, {"groups": ["B"], "layout": "chart"})
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    second = api(site, host, "POST", "/api/csv/generate",
                 {"digest": digest, "recipe": doc["recipe"]})[1]
    site.wait_idle(10)
    assert first["job_id"] != second["job_id"]
    one, two = sources(site, host, first["job_id"]), sources(site, host, second["job_id"])
    assert one["sections"][0]["layout"] == "table"
    assert two["sections"][0]["layout"] == "chart"
    assert one["report"]["recipe_sha256"] != two["report"]["recipe_sha256"]


def test_opening_sources_is_read_only(real_csv_site):
    site, host = real_csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    job = api(site, host, "POST", "/api/csv/generate",
              {"digest": digest, "recipe": doc["recipe"]})[1]
    site.wait_idle(10)

    def fingerprint():
        rows = {}
        draft = site.work_root / "drafts" / "csv" / digest / "editor.json"
        rows["draft"] = hashlib.sha256(draft.read_bytes()).hexdigest() if draft.is_file() else None
        analysis = site._csv_dataset_dir(digest) / "neutral-analysis.json"
        rows["analysis"] = hashlib.sha256(analysis.read_bytes()).hexdigest()
        package = site.jobs_root / job["job_id"] / "package"
        rows["package"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in sorted(package.rglob("*")) if path.is_file()}
        rows["jobs"] = sorted(path.name for path in site.jobs_root.glob("*"))
        return rows

    before = fingerprint()
    for _ in range(2):
        assert sources(site, host, job["job_id"])["report"]["job_id"] == job["job_id"]
    assert fingerprint() == before, "opening Data & sources changed saved state"


def test_restricted_report_offers_no_withheld_material(real_csv_site):
    site, host = real_csv_site
    digest, _ = journey(site, host, TIMESERIES_CSV, time="year")
    doc = choose(site, host, digest, "restricted-share")
    for entry in list(doc["composer"]):
        if entry["block"] in ("values-over-time", "values-by-group"):
            api(site, host, "POST", "/api/csv/edit",
                {"digest": digest, "action": "exclude", "instance": entry["instance_id"],
                 "value": None})
    api(site, host, "POST", "/api/csv/edit",
        {"digest": digest, "action": "include", "instance": "coverage-over-time", "value": None})
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    job = api(site, host, "POST", "/api/csv/generate",
              {"digest": digest, "recipe": doc["recipe"]})[1]
    site.wait_idle(10)
    payload = sources(site, host, job["job_id"])
    assert payload["disclosure"]["policy"] == "restricted-share"
    identifiers = [item["id"] for item in payload["artifacts"]]
    assert "data/neutral-summary.json" in identifiers
    assert "data/neutral-analysis.json" not in identifiers
    assert "data/selected-records.csv" not in identifiers
    assert payload["retained"]["reason"] == "withheld"
    assert "items" not in payload["retained"]
    def numbers(node, found=None):
        found = [] if found is None else found
        if isinstance(node, dict):
            for value in node.values():
                numbers(value, found)
        elif isinstance(node, list):
            for value in node:
                numbers(value, found)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            found.append(float(node))
        return found

    # Digits occur inside digests, so only parsed numbers can prove a value leak.
    assert not ({120.0, 150.0, 110.0} & set(numbers(payload))), "restricted panel leaked a value"
    status, _body, _headers = raw_get(host, f"/api/jobs/{job['job_id']}/retained/original.bin")
    assert status in (403, 404), "a restricted report served retained bytes"
    status, _body, _headers = raw_get(host,
                                      f"/api/jobs/{job['job_id']}/retained/neutral-analysis.json")
    assert status == 403, "a restricted report served its analysis file"


def test_retained_material_is_bound_to_the_report_and_permissions(real_csv_site):
    site, host = real_csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest, "local-audit", permit_records=True)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    job = api(site, host, "POST", "/api/csv/generate",
              {"digest": digest, "recipe": doc["recipe"]})[1]
    site.wait_idle(20)
    payload = sources(site, host, job["job_id"])
    retained = payload["retained"]
    offered = {item["id"] for item in retained["items"]}
    assert offered == {"neutral-analysis.json", "prepared.json"}, offered
    withheld = {item["id"] for item in retained["withheld"]}
    assert "original.bin" in withheld, "the raw capture must not be offered under local audit"
    assert "raw captured file" in next(item["detail"] for item in retained["withheld"]
                                       if item["id"] == "original.bin")
    status, body, _ = raw_get(host, f"/api/jobs/{job['job_id']}/retained/original.bin")
    assert status == 404, "the raw capture must not be downloadable"
    status, body, _ = raw_get(host,
                              f"/api/jobs/{job['job_id']}/retained/neutral-analysis.json")
    assert status == 200 and json.loads(body)["row_count"] == 4
    status, body, _ = raw_get(host, f"/api/jobs/{job['job_id']}/retained/prepared.json")
    assert status == 200 and len(json.loads(body)["rows"]) == 4


def test_a_newer_analysis_revision_is_never_presented_as_historical(real_csv_site):
    site, host = real_csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest, "local-audit", permit_records=True)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    job = api(site, host, "POST", "/api/csv/generate",
              {"digest": digest, "recipe": doc["recipe"]})[1]
    site.wait_idle(20)
    before = sources(site, host, job["job_id"])
    assert {item["id"] for item in before["retained"]["items"]} == {
        "neutral-analysis.json", "prepared.json"}

    # A newer confirmed revision in the same retained directory.
    status, _ = api(site, host, "POST", "/api/csv/confirm",
                    {"digest": digest, "interpretation": {"category": "city",
                                                          "measure": "value", "time": None}})
    assert status == 200

    after = sources(site, host, job["job_id"])
    assert after["data"]["roles"]["measure"] == before["data"]["roles"]["measure"]
    assert after["report"]["recipe_sha256"] == before["report"]["recipe_sha256"]
    assert after["retained"]["items"] == [], "current revision shown as the report's input"
    current = {item["id"] for item in after["retained"]["current"]}
    assert current == {"neutral-analysis.json", "prepared.json"}, current
    assert all("href" not in item for item in after["retained"]["current"])
    for name in ("neutral-analysis.json", "prepared.json"):
        status, _body, _headers = raw_get(host,
                                          f"/api/jobs/{job['job_id']}/retained/{name}")
        assert status == 409, f"{name} served although it differs from this report"


def test_local_audit_without_record_permission_withholds_rows(real_csv_site):
    site, host = real_csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest, "local-audit", permit_records=False)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    job = api(site, host, "POST", "/api/csv/generate",
              {"digest": digest, "recipe": doc["recipe"]})[1]
    site.wait_idle(20)
    retained = sources(site, host, job["job_id"])["retained"]
    assert {item["id"] for item in retained["items"]} == {"neutral-analysis.json"}
    reason = next(item for item in retained["withheld"] if item["id"] == "prepared.json")
    assert "does not include contributing records" in reason["detail"]
    status, _body, _headers = raw_get(host, f"/api/jobs/{job['job_id']}/retained/prepared.json")
    assert status == 403, "contributing records were served without permission"


def test_package_links_follow_policy_and_package_digest(real_csv_site):
    site, host = real_csv_site
    digest, _ = journey(site, host, TIMESERIES_CSV, time="year")
    doc = choose(site, host, digest, "restricted-share")
    for entry in list(doc["composer"]):
        if entry["block"] in ("values-over-time", "values-by-group"):
            api(site, host, "POST", "/api/csv/edit",
                {"digest": digest, "action": "exclude", "instance": entry["instance_id"],
                 "value": None})
    api(site, host, "POST", "/api/csv/edit",
        {"digest": digest, "action": "include", "instance": "coverage-over-time",
         "value": None})
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    job = api(site, host, "POST", "/api/csv/generate",
              {"digest": digest, "recipe": doc["recipe"]})[1]
    site.wait_idle(20)
    package = site.jobs_root / job["job_id"] / "package"

    # Even if an analysis file were present in a restricted package, policy wins.
    (package / "data" / "neutral-analysis.json").write_text("{}", encoding="utf-8")
    payload = sources(site, host, job["job_id"])
    assert "data/neutral-analysis.json" not in [a["id"] for a in payload["artifacts"]]
    assert "data/selected-records.csv" not in [a["id"] for a in payload["artifacts"]]

    # A package that no longer matches its recorded digest offers no file links at all.
    (package / "report.html").write_text("<html>tampered</html>", encoding="utf-8")
    tampered = sources(site, host, job["job_id"])
    assert tampered["artifacts"] == []
    assert any("no longer matches the digest" in note for note in tampered["notices"])


def test_historical_report_without_package_is_described_honestly(csv_site):
    site, host = csv_site
    legacy = site.jobs_root / "20260101T000000Z-0123456789"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "job.json").write_text(json.dumps({
        "job_id": "20260101T000000Z-0123456789", "preset": "researcher",
        "status": "succeeded", "created_utc": "2026-01-01T00:00:00+00:00",
        "finished_utc": "2026-01-01T00:00:10+00:00",
        "preview_dir": "jobs/20260101T000000Z-0123456789/package"}), encoding="utf-8")
    payload = sources(site, host, "20260101T000000Z-0123456789")
    assert payload["report"]["provenance_status"] == "unavailable"
    assert payload["artifacts"] == []
    assert payload["notices"], "a missing package must be explained"
    assert "methods" not in payload["report"]["links"]


def test_health_shaped_report_maps_recorded_attribution(csv_site):
    site, host = csv_site
    job_id = "20260101T000000Z-abcdef1234"
    job = site.jobs_root / job_id
    package = job / "package"
    package.mkdir(parents=True, exist_ok=True)
    (job / "job.json").write_text(json.dumps({
        "job_id": job_id, "preset": "researcher", "mode": "composed", "status": "succeeded",
        "created_utc": "2026-01-01T00:00:00+00:00",
        "replay_command": "python publish.py html --bundle <bundle> --composition <recipe>",
        "preview_dir": f"jobs/{job_id}/package"}), encoding="utf-8")
    (package / "provenance.json").write_text(json.dumps({
        "schema": "health-report-provenance/1.0",
        "data": {"publisher": "Federal Office of Public Health",
                 "api": "https://example.org/api", "datasets_in_snapshot": 56,
                 "datasets_used": 12, "publishing_date_range": ["2026-09-01", "2026-10-01"],
                 "retrieved_at_utc_range": ["2026-10-08T09:00:00+00:00"],
                 "snapshot_id": "abc123"},
        "filters": {"geography": "CHFL", "years": [2021, 2025]},
        "code": {"git_commit": "deadbeef", "git_worktree_clean": False,
                 "source_state": {"label": "uncommitted changes present"},
                 "workflow_config": {"sha256": "f" * 64}},
        "composition": {"audience": "researcher",
                        "display_scope": {"displayed_topics": ["a", "b"],
                                          "group_summaries": [], "monitoring_topics": []}}}),
        encoding="utf-8")
    payload = sources(site, host, job_id)
    assert payload["data"]["kind"] == "health"
    assert payload["attribution"]["recorded"] is True
    assert payload["attribution"]["publisher"] == "Federal Office of Public Health"
    assert payload["data"]["roles"] is None, "invented roles must not appear for health reports"
    assert payload["sections"][0]["displayed_topics"] == 2
    assert payload["methods"]["code"]["git_commit"] == "deadbeef"
    assert payload["methods"]["replay"]["state"] == "requires_private_inputs"


def test_sources_rejects_unknown_jobs_and_path_tricks(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    job = api(site, host, "POST", "/api/csv/generate",
              {"digest": digest, "recipe": doc["recipe"]})[1]
    site.wait_idle(10)
    assert api(site, host, "GET", "/api/jobs/not-a-job/sources")[0] == 404
    for path in (f"/api/jobs/{job['job_id']}/retained/..%2f..%2fetc%2fpasswd",
                 f"/api/jobs/{job['job_id']}/retained/..",
                 f"/api/jobs/{job['job_id']}/retained/notes.txt"):
        assert raw_get(host, path)[0] == 404, path


# ------------------------------------------------------------------ history and verified reuse

@pytest.fixture()
def reuse_site(tmp_path):
    """Site with a packaging stub and a render counter: proves when no render happened."""
    counter = RenderCounter()
    site, server, host = make_site(tmp_path, render=counter)
    status, headers = token_exchange(host, site.access_token)
    assert status == 302
    SESSIONS[host] = cookie_from(headers)
    yield site, host, counter
    site.wait_idle(10)
    server.shutdown()


def generate(site, host, digest, recipe=None):
    if recipe is None:
        recipe = api(site, host, "GET", f"/api/csv?digest={digest}")[1]["recipe"]
    return api(site, host, "POST", "/api/csv/generate",
               {"digest": digest, "recipe": recipe})


def history(site, host, digest):
    return api(site, host, "GET", f"/api/csv?digest={digest}")[1]["history"]


def test_history_is_dataset_scoped_and_isolates_equal_filenames(csv_site):
    site, host = csv_site
    first = journey(site, host, SNAPSHOT_CSV)[0]
    second = journey(site, host, "city,value\nA,30\nA,40\nB,50\nB,60\n")[0]
    assert first != second
    choose(site, host, first)
    status, job = generate(site, host, first)
    assert status == 202, job
    site.wait_idle(10)
    one = history(site, host, first)
    two = history(site, host, second)
    assert one["total"] == 1 and two["total"] == 0
    entry = one["items"][0]
    assert entry["dataset"]["digest"] == first
    assert entry["dataset"]["filename"] == "data.csv"
    assert entry["job_id"]
    body = json.dumps(one)
    assert "/review/" not in body and "/home/" not in body and "/evidence/" not in body


def test_generate_reuses_verified_package_without_rendering(reuse_site):
    site, host, counter = reuse_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    status, first = generate(site, host, digest)
    assert status == 202
    site.wait_idle(10)
    assert counter.calls == 1
    jobs_before = sorted(path.name for path in site.jobs_root.glob("*"))
    status, again = generate(site, host, digest)
    assert status == 200 and again.get("reused") is True
    assert again["job_id"] == first["job_id"]
    assert again["created_utc"] == first["created_utc"]
    assert counter.calls == 1, "a verified reuse still invoked the renderer"
    assert sorted(path.name for path in site.jobs_root.glob("*")) == jobs_before
    assert "No new render was performed" in again["reuse_message"]
    entry = history(site, host, digest)["items"][0]
    assert entry["reuse"]["state"] == "match"


def test_opening_a_historical_report_never_renders(reuse_site):
    site, host, counter = reuse_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    status, job = generate(site, host, digest)
    site.wait_idle(10)
    assert counter.calls == 1
    package = site.jobs_root / job["job_id"] / "package"
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in package.rglob("*") if path.is_file()}
    draft = site.work_root / "drafts" / "csv" / digest / "editor.json"
    draft_before = draft.read_bytes() if draft.is_file() else None
    jobs_before = sorted(path.name for path in site.jobs_root.glob("*"))

    status, body, headers = raw_get(host, f"/reports/{job['job_id']}/report.html")
    assert status == 200 and body == (package / "report.html").read_bytes()
    assert counter.calls == 1, "opening a report invoked the renderer"
    assert sorted(path.name for path in site.jobs_root.glob("*")) == jobs_before
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
             for path in package.rglob("*") if path.is_file()}
    assert after == before
    assert (draft.read_bytes() if draft.is_file() else None) == draft_before


def test_changed_settings_miss_and_restoring_them_hits_again(reuse_site):
    site, host, counter = reuse_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    instance = block_row(doc, "csv-values-by-group")["instance_id"]

    status, first = generate(site, host, digest)
    site.wait_idle(10)
    assert counter.calls == 1

    for patch in ({"groups": ["A"]}, {"precision": {"mode": "decimal", "places": 2}},
                  {"layout": "chart"}, {"statistics": ["n", "median"]}):
        display_edit(site, host, digest, instance, patch)
        status, miss = generate(site, host, digest)
        assert status == 202 and not miss.get("reused"), patch
        site.wait_idle(10)
    assert counter.calls == 5

    api(site, host, "POST", "/api/csv/edit",
        {"digest": digest, "action": "set-title", "instance": instance, "value": "A title"})
    status, _ = generate(site, host, digest)
    assert status == 202
    site.wait_idle(10)
    assert counter.calls == 6

    # Back to the original title, then back to the original display settings.
    api(site, host, "POST", "/api/csv/edit",
        {"digest": digest, "action": "set-title", "instance": instance, "value": None})
    display_edit(site, host, digest, instance, {"groups": None,
                                                "precision": {"mode": "decimal", "places": 1},
                                                "layout": "chart-and-table",
                                                "statistics": ["n", "median", "middle50",
                                                               "range"]})
    status, hit = generate(site, host, digest)
    assert status == 200 and hit.get("reused") is True
    assert hit["job_id"] == first["job_id"]
    assert counter.calls == 6, "restoring the original settings should reuse the first report"


def test_disclosure_change_is_never_reused_across_policies(reuse_site):
    site, host, counter = reuse_site
    digest, _ = journey(site, host, TIMESERIES_CSV, time="year")
    choose(site, host, digest, "local-audit")
    status, local = generate(site, host, digest)
    site.wait_idle(10)
    assert status == 202

    doc = choose(site, host, digest, "restricted-share")
    for entry in list(doc["composer"]):
        if entry["block"] in ("values-over-time", "values-by-group"):
            api(site, host, "POST", "/api/csv/edit",
                {"digest": digest, "action": "exclude", "instance": entry["instance_id"],
                 "value": None})
    api(site, host, "POST", "/api/csv/edit",
        {"digest": digest, "action": "include", "instance": "coverage-over-time",
         "value": None})
    status, restricted = generate(site, host, digest)
    assert status == 202 and not restricted.get("reused")
    assert restricted["job_id"] != local["job_id"]
    site.wait_idle(10)
    assert counter.calls == 2


def test_record_permission_change_is_never_reused(reuse_site):
    site, host, counter = reuse_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest, "local-audit", permit_records=False)
    status, _ = generate(site, host, digest)
    site.wait_idle(10)
    assert status == 202
    choose(site, host, digest, "local-audit", permit_records=True)
    status, second = generate(site, host, digest)
    assert status == 202 and not second.get("reused")
    site.wait_idle(10)
    assert counter.calls == 2


def test_analysis_and_renderer_changes_invalidate_reuse(reuse_site):
    site, host, counter = reuse_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    status, first = generate(site, host, digest)
    site.wait_idle(10)
    assert counter.calls == 1

    # A renderer/helper change must miss even with identical data and settings.
    original = dict(site._csv_environment_cache)
    changed = json.loads(json.dumps(original))
    changed["files"]["scripts/health_pipeline/templates/report_helpers.R"] = "0" * 64
    site._csv_environment_cache = changed
    status, miss = generate(site, host, digest)
    assert status == 202 and not miss.get("reused")
    site.wait_idle(10)
    site._csv_environment_cache = original
    status, hit = generate(site, host, digest)
    assert status == 200 and hit["job_id"] == first["job_id"]
    assert counter.calls == 2


def test_corrupt_package_is_skipped_and_never_deleted(reuse_site):
    site, host, counter = reuse_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    status, first = generate(site, host, digest)
    site.wait_idle(10)
    package = site.jobs_root / first["job_id"] / "package"
    (package / "report.html").write_text("<!DOCTYPE html><p>tampered</p>", encoding="utf-8")

    status, second = generate(site, host, digest)
    assert status == 202 and not second.get("reused")
    assert second["job_id"] != first["job_id"]
    assert (package / "report.html").is_file(), "the older package was deleted"
    entry = next(item for item in history(site, host, digest)["items"]
                 if item["job_id"] == first["job_id"])
    assert entry["reuse"]["state"] in ("unavailable", "different")
    assert "changed" in entry["reuse"]["reason"] or "Not reusable" in entry["reuse"]["reason"]


def test_edit_a_copy_restores_settings_and_protects_the_draft(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    instance = block_row(doc, "csv-values-by-group")["instance_id"]
    display_edit(site, host, digest, instance, {"groups": ["A"],
                                                "precision": {"mode": "decimal", "places": 3}})
    api(site, host, "POST", "/api/csv/edit",
        {"digest": digest, "action": "set-title", "instance": instance, "value": "Original"})
    status, job = generate(site, host, digest)
    site.wait_idle(10)
    package = site.jobs_root / job["job_id"] / "package"
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in package.rglob("*") if path.is_file()}

    # Move the draft away from the report.
    display_edit(site, host, digest, instance, {"groups": ["B"]})
    api(site, host, "POST", "/api/csv/edit",
        {"digest": digest, "action": "set-title", "instance": instance, "value": "Edited"})

    status, error = api(site, host, "POST", "/api/csv/edit",
                        {"digest": digest, "action": "restore-composition", "instance": None,
                         "value": {"job_id": job["job_id"]}})
    assert status == 409 and error["error"]["code"] == "draft_has_edits"
    status, result = api(site, host, "POST", "/api/csv/edit",
                         {"digest": digest, "action": "restore-composition", "instance": None,
                          "value": {"job_id": job["job_id"], "confirm": True}})
    assert status == 200, result
    row = block_row(result["document"], instance)
    assert row["display"]["groups"] == ["A"]
    assert row["display"]["precision"]["places"] == 3
    assert row["title"] == "Original"
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
             for path in package.rglob("*") if path.is_file()}
    assert after == before, "copying settings changed the historical report"


def test_edit_copy_after_reinterpretation_needs_confirmation(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, TIMESERIES_CSV, time="year")
    choose(site, host, digest)
    status, job = generate(site, host, digest)
    site.wait_idle(10)
    status, _ = api(site, host, "POST", "/api/csv/confirm",
                    {"digest": digest, "interpretation": {"category": "city",
                                                          "measure": "value", "time": None}})
    assert status == 200
    status, error = api(site, host, "POST", "/api/csv/edit",
                        {"digest": digest, "action": "restore-composition", "instance": None,
                         "value": {"job_id": job["job_id"]}})
    assert status == 409 and error["error"]["code"] == "context_changed"
    assert "different confirmed interpretation" in error["error"]["message"]


def test_history_survives_a_reopened_site_and_excludes_health_jobs(csv_site):
    site, host = csv_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    status, job = generate(site, host, digest)
    assert status == 202
    site.wait_idle(10)

    # A health-shaped job with the same context must not appear in the CSV history.
    legacy = site.jobs_root / "20260101T000000Z-feedface00"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "job.json").write_text(json.dumps({
        "job_id": "20260101T000000Z-feedface00", "preset": "researcher",
        "mode": "composed", "context": digest, "status": "succeeded",
        "created_utc": "2026-01-01T00:00:00+00:00"}), encoding="utf-8")

    reopened = composer_site.Site(site.work_root, site.inputs_root, site.data_root,
                                  site.recipes_root, workflow_config=None, quarto="quarto",
                                  render=stub_render)
    listed = reopened.csv_history(digest)
    assert listed["total"] == 1
    assert listed["items"][0]["job_id"] == job["job_id"]
    assert [item["job_id"] for item in listed["items"]] == [job["job_id"]]


def test_match_indicator_follows_the_current_settings(reuse_site):
    site, host, _counter = reuse_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    instance = block_row(doc, "csv-values-by-group")["instance_id"]
    status, job = generate(site, host, digest)
    site.wait_idle(10)
    assert history(site, host, digest)["items"][0]["reuse"]["state"] == "match"
    display_edit(site, host, digest, instance, {"groups": ["A"]})
    entry = history(site, host, digest)["items"][0]
    assert entry["reuse"]["state"] == "different", entry["reuse"]


def test_simultaneous_identical_requests_do_not_duplicate_renders(reuse_site):
    site, host, counter = reuse_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    recipe = api(site, host, "GET", f"/api/csv?digest={digest}")[1]["recipe"]

    slow = {"inner": counter}

    def slow_render(*args, **kwargs):
        _time.sleep(0.6)
        return counter(*args, **kwargs)

    site.render = slow_render
    results = []
    threads = [threading.Thread(target=lambda: results.append(
        api(site, host, "POST", "/api/csv/generate", {"digest": digest, "recipe": recipe})))
        for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    site.wait_idle(15)
    statuses = sorted(status for status, _payload in results)
    assert statuses == [202, 409], statuses
    assert len(list(site.jobs_root.glob("*"))) == 1, "a duplicate render was launched"
    status, again = generate(site, host, digest)
    assert status == 200 and again.get("reused") is True


def test_stale_analysis_blocks_reuse(reuse_site):
    site, host, counter = reuse_site
    digest, _ = journey(site, host, SNAPSHOT_CSV)
    choose(site, host, digest)
    status, job = generate(site, host, digest)
    site.wait_idle(10)
    assert status == 202

    analysis_path = site._csv_dataset_dir(digest) / "neutral-analysis.json"
    stored = json.loads(analysis_path.read_text())
    stored["groups"][0]["summary"]["median"] = 999.0
    stored.setdefault("method", {})["calc_version"] = 1
    analysis_path.write_text(json.dumps(stored), encoding="utf-8")

    status, error = generate(site, host, digest)
    assert status == 409 and error["error"]["code"] == "csv_analysis_stale"
    assert counter.calls == 1


# ------------------------------------------------------------------ DOM harness

def _node():
    import shutil
    return shutil.which("node")


HARNESS = ROOT / "tests" / "js" / "csv_dom_check.mjs"


def run_harness(fixture, tmp_path, name):
    """Run the DOM harness on one fixture; echo its transcript when asked for evidence."""
    import os
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    done = subprocess.run([_node(), str(HARNESS), str(path)], capture_output=True, text=True,
                          timeout=180)
    if os.environ.get("CSV_HARNESS_ECHO"):
        sys.stdout.write(done.stdout + done.stderr)
    assert done.returncode == 0, done.stdout + done.stderr
    assert '"failures":0' in done.stdout, done.stdout
    assert "unexpected request" not in done.stdout
    return done


def build_csv_dom_fixture(site, host, time=None, policy="local-audit", permit_records=False):
    """Real documents from the in-process Site, transcribed for the DOM harness."""
    payload = TIMESERIES_CSV if time else SNAPSHOT_CSV
    digest, _conf = journey(site, host, payload, time=time)
    choose(site, host, digest, policy, permit_records)
    editor_doc = api(site, host, "GET", f"/api/csv?digest={digest}")[1]
    health_editor = {
        "preset": "researcher", "label": "Researcher", "audience": "researcher",
        "draft": False, "revision": 0, "customized": False, "ready": True,
        "blocking_reason": None, "differences": {}, "source": None,
        "eligible_topics": [], "topic_labels": {}, "excluded": [],
        "blocks": [{"instance_id": "intro-0001", "block": "intro", "label": "Report context",
                    "description": "", "included": True, "repeatable": False,
                    "repeat_reason": None, "editable": [], "options": {}, "summary": None},
                   {"instance_id": "limitations-0001", "block": "limitations",
                    "label": "Limitations and cautions", "description": "", "included": True,
                    "repeatable": False, "repeat_reason": None, "required": True,
                    "editable": [], "options": {}, "summary": None}],
        "required_blocks": {"limitations": "Required"}}
    focus_instance = editor_doc["recipe"]["blocks"][1]["instance_id"]
    focused_recipe = json.loads(json.dumps(editor_doc["recipe"]))
    focused_recipe.setdefault("titles", {})[focus_instance] = "Focused title"
    focused_composer = json.loads(json.dumps(editor_doc["composer"]))
    for row in focused_composer:
        if row["instance_id"] == focus_instance:
            row["title"] = "Focused title"
    editor_doc["history"] = {
        "items": [{
            "job_id": "20261030T120000Z-1111111111",
            "created_utc": "2026-10-30T12:00:00+00:00",
            "finished_utc": "2026-10-30T12:00:08+00:00",
            "status": "succeeded",
            "dataset": {"filename": "data.csv", "digest": digest},
            "titles": ["North detail"], "blocks": ["data-overview", "values-over-time"],
            "policy": {"policy": "local-audit", "label": "Local audit and review output",
                       "permit_values": True, "permit_records": False},
            "preview": True,
            "reuse": {"state": "match", "reason": "Matches the current settings."},
            "links": {"report": "/reports/20261030T120000Z-1111111111/report.html"},
        }],
        "total": 1, "truncated": False, "limit": 20,
    }
    return {
          "app_js": str(ROOT / "src" / "composer_web" / "app.js"),
          "index_html": str(ROOT / "src" / "composer_web" / "index.html"),
          "presets": {"presets": [{"id": "researcher", "label": "Researcher", "available": True,
                                   "reason": None, "draft": False, "customized": False}]},
          "editor_state": {"researcher": health_editor},
        "csv_digest": digest,
        "csv_document": editor_doc,
        "capture": {"input_sha256": digest, "columns": ["city", "value", "year"],
                    "logical_records": 4,
                    "preview_rows": [["Zurich", "120", "2021"], ["Bern", "90", "2021"]],
                    "preview_columns": ["city", "value", "year"],
                    "preview_truncated_rows": 0, "preview_truncated_columns": 0,
                    "byte_count": len(payload.encode())},
        "confirmation_after_confirm": editor_doc["confirmation"],
        "analysis_after_confirm": editor_doc["analysis"],
        "recipe_after_confirm": editor_doc["recipe"],
        "confirmed_interpretation": editor_doc["confirmation"]["confirmation"],
        "focus_instance": focus_instance,
        "csv_edit_steps": [{
            "request": {"digest": digest, "action": "set-title",
                        "instance": focus_instance, "value": "Focused title"},
            "response": {"recipe": focused_recipe, "composer": focused_composer},
        }],
        "sources_document": {
            "report": {"job_id": "20261031T000000Z-0000000000",
                       "created_utc": "2026-10-31T00:00:00+00:00",
                       "finished_utc": "2026-10-31T00:00:05+00:00",
                       "status": "succeeded", "mode": "csv", "profile": "neutral-overview",
                       "package_sha256": "b" * 64, "package_files": 9,
                       "recipe_sha256": "c" * 64, "preview": True,
                       "preview_notice": "Preview render.",
                       "note": ("This information describes this saved report. The current "
                                "editable draft may differ."),
                       "links": {"report": "/reports/20261031T000000Z-0000000000/report.html",
                                 "methods": "/reports/20261031T000000Z-0000000000/methods.html"},
                       "provenance_status": "recorded", "composition_status": "recorded"},
            "disclosure": {"recorded": True, "policy": "local-audit",
                           "label": "Local audit and review output"},
            "data": {"kind": "neutral", "filename": "data.csv",
                     "digest": digest, "captured_at_utc": "2026-10-31T00:00:00+00:00",
                     "measured_at": None, "user_version": None,
                     "roles": {"category": "city", "measure": "value", "time": "year",
                               "missing_tokens": []},
                     "measure": {"label": "Observed value", "unit": "not specified",
                                 "meaning": "a reading per city and year"},
                     "filters": "None recorded", "counts": {"analysed_records": 4,
                                                           "analysed_groups": 2,
                                                           "analysed_periods": 2},
                     "coverage": {"from": "2021-01-01T00:00:00",
                                  "to": "2022-01-01T00:00:00"},
                     "status": "recorded"},
            "sections": [{"instance_id": "csv-values-over-time", "block": "values-over-time",
                          "title": "North detail", "layout": "chart-and-table",
                          "groups": {"shown": 1, "analysed": 2},
                          "periods": {"shown": 2, "analysed": 2}}],
            "attribution": {"recorded": True, "kind": "neutral",
                            "publisher": "<script>alert(1)</script>",
                            "url": "javascript:alert(1)",
                            "licence": "Not recorded for this report.",
                            "version": {"snapshot_id": "abc"},
                            "detail": "Recorded at render time."},
            "methods": {"methods_href": "/reports/20261031T000000Z-0000000000/methods.html",
                        "provenance_href": "/reports/20261031T000000Z-0000000000/provenance.json",
                        "composition_href": "/reports/20261031T000000Z-0000000000/composition.json",
                        "method": {"calc_version": 2},
                        "code": {"kind": "retained implementation at render time",
                                 "files": {"scripts/health_pipeline/neutral_describe.py": "d" * 64}},
                        "environment": {"kind": "not recorded in this package"},
                        "replay": {"command": "python publish.py html --bundle <bundle>",
                                   "state": "complete_local",
                                   "detail": "Complete local replay is possible."}},
            "artifacts": [{"id": "report.html",
                           "href": "/reports/20261031T000000Z-0000000000/report.html",
                           "label": "Report (HTML)", "bytes": 1024, "kind": "report"},
                          {"id": "data/neutral-analysis.json",
                           "href": "/reports/20261031T000000Z-0000000000/data/neutral-analysis.json",
                           "label": "Saved analysis (full precision)", "bytes": 2048,
                           "kind": "data"}],
            "retained": {"available": True, "reason": "permitted",
                         "detail": "Retained locally; not included in this report package.",
                         "items": [{"id": "neutral-analysis.json",
                                    "label": "Saved analysis used by this report",
                                    "href": "/api/jobs/20261031T000000Z-0000000000/retained/neutral-analysis.json",
                                    "status": "verified_now",
                                    "detail": "Identical to the recorded analysis digest."}],
                         "current": [{"id": "prepared.json", "label": "Prepared records",
                                      "detail": "Current retained workspace material; differs from this report."}],
                         "withheld": [{"id": "original.bin", "label": "Original captured file",
                                       "status": "withheld",
                                       "detail": "Not offered: the saved disclosure contract does not record permission for the raw captured file."}]},
            "notices": [],
        },
        "job_response": {"job_id": "20261031T000000Z-0000000000", "status": "queued",
                         "recipe_sha256": "a" * 64,
                         "replay_command": "python scripts/health_pipeline/publish.py html "
                                           "--bundle <captured-dataset> --composition <recipe>"},
        "file_name": "data.csv",
        "expect_conflict": bool(editor_doc.get("disclosure_conflicts")),
    }


@pytest.mark.skipif(_node() is None, reason="node is not installed in this runtime; "
                                            "the DOM harness runs where Node is available")
def test_csv_dom_journey_renders(csv_site, tmp_path):
    site, host = csv_site
    fixture = build_csv_dom_fixture(site, host, time="year", permit_records=True)
    done = run_harness(fixture, tmp_path, "csv-dom-fixture")
    assert "SUMMARY" in done.stdout


@pytest.mark.skipif(_node() is None, reason="node is not installed in this runtime; "
                                            "the DOM harness runs where Node is available")
def test_csv_dom_conflict_gate_renders(csv_site, tmp_path):
    """The incompatible combination is explained and generation stays blocked in the UI."""
    site, host = csv_site
    fixture = build_csv_dom_fixture(site, host, time="year", policy="restricted-share")
    assert fixture["expect_conflict"] is True
    run_harness(fixture, tmp_path, "csv-dom-conflict")