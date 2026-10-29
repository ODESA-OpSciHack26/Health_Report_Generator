"""HTTP integration tests for the Round A composer website.

One ThreadingHTTPServer on an ephemeral loopback port, driven with urllib: routing, session
protection, preset invalidation of the old Custom redirect, per-audience drafts, pending disease
selections, reset, bounded jobs, job classification and artifact containment. Rendering is
stubbed (clearly labelled); the real end-to-end generation is recorded in the evidence directory.
"""
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import quote

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import composer_site  # noqa: E402
import composer_workspace as workbench  # noqa: E402
from test_composer_series import build_series_bundle  # noqa: E402

RECIPES = ROOT / "scripts/health_pipeline/config/composer/compositions"
WEB = ROOT / "src" / "composer_web"
SESSIONS = {}
RESEARCHER_COLLECTION = "researcher-series-collection"
EMPTY_SELECTION = ("Select at least one disease, or turn off "
                   "‘Annual trends by disease’.")


# --------------------------------------------------------------------------- fixtures

def stub_render(bundle, output, fmt, quarto, provenance, provenance_out, composition):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    Path(provenance_out).write_text(json.dumps(provenance), encoding="utf-8")
    output.write_text("<!DOCTYPE html><title>stub report</title><p>stub</p>", encoding="utf-8")
    (output.parent / "methods.html").write_text("<p>methods</p>", encoding="utf-8")
    (output.parent / "data").mkdir(exist_ok=True)
    (output.parent / "data" / "series.csv").write_text(
        "topic,year,value\ncampylobacteriosis,2025,16\n", encoding="utf-8")
    (output.parent / "reproduction").mkdir(exist_ok=True)
    (output.parent / "reproduction" / "composition.json").write_bytes(
        Path(composition).read_bytes())


class BlockingRender:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def __call__(self, *args, **kwargs):
        self.started.set()
        if not self.release.wait(10):
            raise RuntimeError("test did not release the render")
        return stub_render(*args, **kwargs)


def token_exchange(host, token):
    connection = HTTPConnection("127.0.0.1", int(host.split(":")[1]), timeout=10)
    connection.request("GET", "/?token=" + quote(token))
    response = connection.getresponse()
    status, headers, body = response.status, response.getheaders(), response.read()
    connection.close()
    return status, headers, body


def cookie_from(headers):
    for name, value in headers:
        if name.lower() == "set-cookie":
            return value.split(";", 1)[0]
    return None


def write_bundle(tmp_path, audience):
    built = build_series_bundle(
        tmp_path, root=tmp_path / f"build-{audience}", topic="campylobacteriosis",
        label="Campylobacteriosis",
        extra_topics=(("influenza", ((2021, "10.0"), (2025, "12.0"))),))
    stakeholder = built["bundle"] / "stakeholder.json"
    data = json.loads(stakeholder.read_text(encoding="utf-8"))
    if audience != "researcher":
        data["id"] = audience
    data.update({"years": [2021, 2025], "reference_year": 2019, "geography": "CHFL"})
    stakeholder.write_text(json.dumps(data), encoding="utf-8")
    (built["bundle"] / "sources.csv").write_text(
        "dataset_id,topic,source_system,source_file,publishing_date,used,sha256,"
        "metadata_sha256\nds1,campylobacteriosis,mandatory_reporting_system,"
        "data/virus/data.csv,2026-10-01,True," + "b" * 64 + "," + "c" * 64 + "\n",
        encoding="utf-8")
    (built["bundle"] / "checks.csv").write_text(
        "dataset_id,check,status,detail\nds1,value_present,PASS,\n", encoding="utf-8")
    manifest = json.loads((built["bundle"] / "bundle.json").read_text(encoding="utf-8"))
    for name in ("sources.csv", "checks.csv", "stakeholder.json"):
        manifest["files"][name] = hashlib.sha256(
            (built["bundle"] / name).read_bytes()).hexdigest()
    manifest["snapshot_id"] = json.loads(
        (built["bundle"] / "snapshot.json").read_text(encoding="utf-8"))["snapshot_id"]
    (built["bundle"] / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
    return built["bundle"]


def make_site(tmp_path, render=stub_render, audiences=("researcher",)):
    inputs = tmp_path / "inputs"
    for audience in audiences:
        built = write_bundle(tmp_path, audience)
        destination = inputs / audience / "data"
        destination.parent.mkdir(parents=True, exist_ok=True)
        built.rename(destination)
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "researcher.json").write_bytes((RECIPES / "researcher.json").read_bytes())
    (recipes / "public.json").write_bytes((RECIPES / "public.json").read_bytes())
    site = composer_site.Site(tmp_path / "work", inputs, tmp_path / "inputs", recipes,
                              workflow_config=None, quarto="quarto", render=render)
    server = composer_site.build_server(site, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host = f"127.0.0.1:{server.server_address[1]}"
    status, headers, _ = token_exchange(host, site.access_token)
    assert status == composer_site.HTTPStatus.FOUND, status
    cookie = cookie_from(headers)
    assert cookie and cookie.startswith("composer_session="), headers
    SESSIONS[host] = cookie
    return site, server, host


@pytest.fixture()
def web(tmp_path):
    site, server, host = make_site(tmp_path)
    yield site, host
    server.shutdown()
    server.server_close()


# --------------------------------------------------------------------------- helpers

def call(host, method, path, body=None, action=None, origin=None, timeout=10, auth=True,
         cookie=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(f"http://{host}{path}", data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if action:
        request.add_header("X-Composer-Action", action)
    if origin:
        request.add_header("Origin", origin)
    if cookie:
        request.add_header("Cookie", cookie)
    elif auth and SESSIONS.get(host):
        request.add_header("Cookie", SESSIONS[host])
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read()
    except urllib.error.HTTPError as failure:
        return failure.code, failure.headers.get("Content-Type", ""), failure.read()


def payload(response):
    return json.loads(response[2].decode("utf-8"))


def editor(host, preset="researcher"):
    status, _, body = call(host, "GET", f"/api/editor?preset={preset}")
    return status, json.loads(body)


def edit(host, action, instance, value=None, preset="researcher"):
    status, _, body = call(host, "POST", "/api/edit",
                           {"preset": preset, "action": action, "instance": instance,
                            "value": value}, action="edit")
    return status, json.loads(body)


def generate(host, preset="researcher"):
    status, _, body = call(host, "POST", "/api/generate", {"preset": preset},
                           action="generate")
    return status, (json.loads(body) if body else None)


def generate_ok(host, preset="researcher"):
    status, job = generate(host, preset)
    assert status == 202, job
    assert job is not None
    return job


def wait_for_job(host, job_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, _, body = call(host, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        job = json.loads(body)
        if job["status"] in ("succeeded", "failed", "interrupted"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish in time")


def block(document, instance_id):
    return next(item for item in document["blocks"] if item["instance_id"] == instance_id)


def collection(document):
    return block(document, RESEARCHER_COLLECTION)


def draft_path(site, audience="researcher"):
    return site.drafts_root / audience / workbench.DRAFT_RECIPE


# --------------------------------------------------------------------------- frontend

def test_frontend_keeps_the_four_cards_and_the_advanced_height_control(web):
    _, host = web
    status, content_type, body = call(host, "GET", "/")
    assert status == 200 and content_type.startswith("text/html")
    assert b'id="presets"' in body and b'role="radiogroup"' in body
    assert b"Generate preview" in body and b"Reset to default" in body
    assert b"Advanced display options" not in body          # built by app.js
    assert b'aria-live="polite"' in body
    assert call(host, "GET", "/app.css")[0] == 200
    assert call(host, "GET", "/app.js")[0] == 200
    assert call(host, "GET", "/missing")[0] == 404


def test_frontend_has_no_custom_redirect_and_restores_focus():
    source = (WEB / "app.js").read_text(encoding="utf-8")
    assert 'mutate("draft"' not in source and "/api/draft" not in source
    assert "Customized" in source
    assert "Advanced display options" in source
    assert "Chart height" in source
    assert "no-op must not change the recipe" in source
    assert "state.seq" in source and "seq !== state.seq" in source
    assert "document.activeElement" in source and "focus()" in source
    assert "default-open-moved" in source and "announce(" in source
    assert "Disease expanded when the report opens" in source
    assert "Other checked diseases remain available in the report." in source


def test_custom_card_is_disabled_with_the_approved_text(web):
    _, host = web
    presets = payload(call(host, "GET", "/api/presets"))["presets"]
    custom = next(item for item in presets if item["id"] == "custom")
    assert custom["available"] is False
    assert custom["reason"] == "Build from the block library — coming in the next revision."


# --------------------------------------------------------------------------- session

def test_every_page_api_and_asset_needs_the_session(web):
    _, host = web
    for method, path, body, action in (
        ("GET", "/", None, None),
        ("GET", "/app.js", None, None),
        ("GET", "/api/presets", None, None),
        ("GET", "/api/editor?preset=researcher", None, None),
        ("GET", "/api/saved", None, None),
        ("GET", "/api/jobs", None, None),
        ("POST", "/api/edit", {"preset": "researcher", "action": "move-up",
                               "instance": "intro-0001"}, "edit"),
        ("POST", "/api/reset", {"preset": "researcher"}, "reset"),
        ("POST", "/api/generate", {"preset": "researcher"}, "generate"),
    ):
        status, _, _ = call(host, method, path, body, action=action, auth=False)
        assert status == 401, (path, status)


def test_token_exchange_sets_a_strict_httponly_cookie(web):
    site, host = web
    status, headers, _ = token_exchange(host, site.access_token)
    assert status == 302
    set_cookie = next(value for name, value in headers if name.lower() == "set-cookie")
    assert "HttpOnly" in set_cookie and "SameSite=Strict" in set_cookie and "Path=/" in set_cookie
    expected = hashlib.sha256(site.access_token.encode("utf-8")).hexdigest()[:32]
    assert cookie_from(headers) == "composer_session=" + expected


def test_wrong_token_and_forged_cookie_are_refused(web):
    site, host = web
    status, headers, body = token_exchange(host, "not-the-run-token")
    assert status == 401 and cookie_from(headers) is None and b"access token" in body
    assert call(host, "GET", "/api/presets", auth=False,
                cookie="composer_session=" + "0" * 32)[0] == 401


def test_access_token_is_redacted_from_the_service_log(web):
    import contextlib
    import io
    site, host = web
    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        status, _, _ = token_exchange(host, site.access_token)
        time.sleep(0.2)
    log = buffer.getvalue()
    assert status == 302 and site.access_token not in log and "token=[redacted]" in log


def test_service_refuses_a_non_loopback_bind(tmp_path):
    with pytest.raises(SystemExit):
        composer_site.main(["--host", "0.0.0.0", "--port", "0",
                            "--work-root", str(tmp_path / "work")])
    assert not (tmp_path / "work").exists()


# --------------------------------------------------------------------------- protection

def test_state_changing_request_requires_the_action_header(web):
    _, host = web
    assert call(host, "POST", "/api/generate", {"preset": "researcher"})[0] == 403
    status, _, body = call(host, "POST", "/api/generate", {"preset": "researcher"},
                           action="edit")
    assert status == 403 and b"action header" in body


def test_cross_origin_request_is_refused(web):
    _, host = web
    status, _, _ = call(host, "POST", "/api/edit",
                        {"preset": "researcher", "action": "move-up",
                         "instance": "intro-0001"}, action="edit",
                        origin="http://evil.example")
    assert status == 403
    # Same-origin edit is accepted (it creates the copy as the first accepted change).
    processed, _, _ = call(host, "POST", "/api/edit",
                           {"preset": "researcher", "action": "move-up",
                            "instance": "intro-0001"}, action="edit",
                           origin=f"http://{host}")
    assert processed == 400         # intro is already first; the point is that it was processed


def test_unknown_fields_and_wrong_content_type_are_rejected(web):
    _, host = web
    status, _, body = call(host, "POST", "/api/generate",
                           {"preset": "researcher", "extra": 1}, action="generate")
    assert status == 400 and b"Unknown field" in body
    request = urllib.request.Request(f"http://{host}/api/generate", data=b"preset=x",
                                     method="POST")
    request.add_header("Content-Type", "text/plain")
    request.add_header("X-Composer-Action", "generate")
    request.add_header("Cookie", SESSIONS[host])
    with pytest.raises(urllib.error.HTTPError) as failure:
        urllib.request.urlopen(request, timeout=10)
    assert failure.value.code == 415


def test_unrecognised_host_header_is_rejected(web):
    _, host = web
    connection = HTTPConnection("127.0.0.1", int(host.split(":")[1]), timeout=10)
    connection.request("GET", "/api/presets", headers={"Host": "evil.example"})
    response = connection.getresponse()
    assert response.status == 400
    connection.close()


def test_page_and_get_requests_write_nothing(web):
    site, host = web
    for path in ("/", "/api/presets", "/api/editor?preset=researcher",
                 "/api/saved", "/api/jobs"):
        assert call(host, "GET", path)[0] == 200, path
    assert list(site.drafts_root.iterdir()) == []
    assert list(site.jobs_root.iterdir()) == []
    assert workbench.file_digest(site.recipes_root / "researcher.json") == \
        workbench.file_digest(RECIPES / "researcher.json")


# --------------------------------------------------------------------------- editor basics

def test_opening_the_editor_is_not_customization(web):
    site, host = web
    status, doc = editor(host)
    assert status == 200
    assert doc["draft"] is False and doc["customized"] is False
    assert doc["ready"] is True and doc["blocking_reason"] is None
    assert doc["revision"] == 0 and doc["excluded"] == []
    assert doc["pending_sha256"] == doc["renderable_sha256"] == doc["default_recipe_sha256"]
    assert [item["instance_id"] for item in doc["blocks"]] == [
        "intro-0001", RESEARCHER_COLLECTION, "block-coverage-selection",
        "block-sensitivity-comparison", "block-reference-comparison", "limitations-0001",
        "reproduction-0001"]
    chosen = collection(doc)
    assert chosen["selected_topics"] == doc["eligible_topics"]
    assert chosen["topic_choices"] == doc["eligible_topics"]
    assert chosen["default_topic"] in chosen["selected_topics"]
    assert set(chosen["editable"]) == {"style", "topics", "default_topic"}
    assert block(doc, "limitations-0001")["required"] is True
    assert "Always" not in doc["required_blocks"]["limitations"]
    assert list(site.drafts_root.iterdir()) == []


def test_edit_and_exact_return_to_default(web):
    site, host = web
    _, before = editor(host)
    status, doc = edit(host, "move-down", "block-coverage-selection")
    assert status == 200 and doc["customized"] is True
    assert doc["differences"]["reordered"] is True
    assert doc["ready"] is True
    status, doc = edit(host, "move-up", "block-coverage-selection")
    assert status == 200
    assert doc["customized"] is False
    assert doc["differences"] == {"excluded": [], "reordered": False, "style": [],
                                 "selection": []}
    assert doc["pending_sha256"] == before["pending_sha256"]


def test_style_edit_and_return_to_default(web):
    _, host = web
    status, doc = edit(host, "set-style", RESEARCHER_COLLECTION, "compact")
    assert status == 200 and doc["customized"] is True
    assert doc["differences"]["style"] == [RESEARCHER_COLLECTION]
    status, doc = edit(host, "set-style", RESEARCHER_COLLECTION, "standard")
    assert status == 200 and doc["customized"] is False


def test_empty_selection_is_customized_and_not_ready(web):
    site, host = web
    status, doc = edit(host, "set-topics", RESEARCHER_COLLECTION, [])
    assert status == 200
    assert doc["customized"] is True and doc["ready"] is False
    assert doc["blocking_reason"] == EMPTY_SELECTION
    assert collection(doc)["selected_topics"] == []
    assert collection(doc)["default_topic"] is None
    # The pending state is in the editor file; the saved recipe stays renderable.
    draft = workbench.open_draft(site.drafts_root / "researcher")
    assert draft.selection[RESEARCHER_COLLECTION]["topics"] == []
    assert draft.effective()             # last accepted recipe still validates
    assert draft.pending_problem()["kind"] == "empty-selection"


def test_invalid_pending_state_never_renders_the_previous_selection(web):
    site, host = web
    status, job = generate(host)
    assert status == 202 and job is not None, job
    first = wait_for_job(host, job["job_id"])
    assert first["status"] == "succeeded"
    edit(host, "set-topics", RESEARCHER_COLLECTION, [])
    status, body = generate(host)
    assert status == 400 and body is not None, body
    assert body["error"]["message"] == EMPTY_SELECTION
    assert body["error"]["code"] == "collection_empty"
    # No new job was created by the refusal; the earlier report is still served.
    jobs = payload(call(host, "GET", "/api/jobs"))["jobs"]
    assert len(jobs) == 1
    assert call(host, "GET", first["report_url"])[0] == 200


def test_subset_selection_shows_in_the_editor_and_survives_reload(web):
    _, host = web
    _, doc = editor(host)
    subset = [doc["eligible_topics"][0]]
    status, doc = edit(host, "set-topics", RESEARCHER_COLLECTION, subset)
    assert status == 200, doc
    chosen = collection(doc)
    assert chosen["selected_topics"] == subset
    assert chosen["topic_choices"] == doc["eligible_topics"]   # full list stays available
    assert chosen["default_topic"] == subset[0]
    _, reopened = editor(host)
    assert collection(reopened)["selected_topics"] == subset


def test_select_all_does_not_claim_to_restore_defaults(web):
    site, host = web
    _, doc = editor(host)
    edit(host, "set-style", RESEARCHER_COLLECTION, "compact")
    edit(host, "set-topics", RESEARCHER_COLLECTION, [doc["eligible_topics"][0]])
    status, doc = edit(host, "set-topics", RESEARCHER_COLLECTION,
                       doc["eligible_topics"])
    assert status == 200
    # Every disease is checked again, but the style still differs, so this is not a default.
    assert collection(doc)["selected_topics"] == doc["eligible_topics"]
    assert doc["customized"] is True
    assert doc["differences"]["style"] == [RESEARCHER_COLLECTION]
    # The saved recipe keeps the compact style until it is changed back.
    draft = workbench.open_draft(site.drafts_root / "researcher")
    saved = next(item for item in draft.recipe["blocks"]
                 if item["instance_id"] == RESEARCHER_COLLECTION)
    assert saved["presentation"]["style"] == "compact"


def test_deselecting_the_open_disease_moves_it_and_reports_the_replacement(web):
    _, host = web
    _, doc = editor(host)
    choices = doc["eligible_topics"]
    status, doc = edit(host, "set-topics", RESEARCHER_COLLECTION, [choices[0], choices[1]])
    assert status == 200
    assert collection(doc)["default_topic"] == choices[0]
    status, doc = edit(host, "set-topics", RESEARCHER_COLLECTION, [choices[1]])
    assert status == 200
    assert doc["notes"] == [{"kind": "default-open-moved",
                             "from": choices[0], "to": choices[1]}]
    assert collection(doc)["default_topic"] == choices[1]
    status, doc = edit(host, "set-default-open", RESEARCHER_COLLECTION, choices[1])
    assert status == 200 and collection(doc)["default_topic"] == choices[1]
    status, body = edit(host, "set-default-open", RESEARCHER_COLLECTION, choices[0])
    assert status == 400      # not one of the checked diseases


def test_excluding_and_re_enabling_preserves_the_disease_selection(web):
    site, host = web
    _, doc = editor(host)
    subset = doc["eligible_topics"][:1]
    edit(host, "set-topics", RESEARCHER_COLLECTION, subset)
    status, doc = edit(host, "exclude", RESEARCHER_COLLECTION)
    assert status == 200 and block(doc, RESEARCHER_COLLECTION)["included"] is False
    draft = workbench.open_draft(site.drafts_root / "researcher")
    assert draft.selection[RESEARCHER_COLLECTION]["topics"] == subset
    status, doc = edit(host, "include", RESEARCHER_COLLECTION)
    assert status == 200
    assert collection(doc)["selected_topics"] == subset
    assert collection(doc)["included"] is True


def test_required_sections_and_validator_rules_are_unchanged(web):
    site, host = web
    for instance in ("limitations-0001", "reproduction-0001"):
        status, body = edit(host, "exclude", instance)
        assert status == 400 and "Required" in body["error"]["message"]
    status, body = edit(host, "set-style", RESEARCHER_COLLECTION, "fancy")
    assert status == 400 and "style" in body["error"]["message"].lower()
    status, body = edit(host, "set-topics", RESEARCHER_COLLECTION, ["not-a-topic"])
    assert status == 400 and "Not included" in body["error"]["message"]
    status, body = edit(host, "set-topic", "block-reference-comparison", "x")
    assert status == 400 and "Unknown edit action" in body["error"]["message"]
    assert list(site.drafts_root.iterdir()) == []


# --------------------------------------------------------------------------- drafts, reset

def test_reset_confirmed_restores_defaults_and_keeps_reports(web):
    site, host = web
    job = generate_ok(host)
    finished = wait_for_job(host, job["job_id"])
    assert finished["status"] == "succeeded"
    report_url = finished["report_url"]
    report = call(host, "GET", report_url)[2]
    _, doc = editor(host)
    edit(host, "set-topics", RESEARCHER_COLLECTION, [doc["eligible_topics"][0]])
    edit(host, "set-style", RESEARCHER_COLLECTION, "compact")
    status, _, raw = call(host, "POST", "/api/reset", {"preset": "researcher"}, action="reset")
    assert status == 200
    reset = json.loads(raw)
    assert reset["customized"] is False and reset["excluded"] == []
    assert collection(reset)["selected_topics"] == reset["eligible_topics"]
    assert collection(reset)["style"] == "standard"
    # The copy is byte-identical to the maintained recipe again.
    assert draft_path(site).read_bytes() == (RECIPES / "researcher.json").read_bytes()
    # History is untouched: same job record, same report bytes, still served.
    assert (site.jobs_root / job["job_id"] / "job.json").is_file()
    assert call(host, "GET", report_url)[2] == report
    jobs = payload(call(host, "GET", "/api/saved"))["jobs"]
    assert jobs[0]["job_id"] == job["job_id"]


def test_reset_without_a_copy_is_refused(web):
    site, host = web
    status, _, raw = call(host, "POST", "/api/reset", {"preset": "researcher"}, action="reset")
    body = json.loads(raw)
    assert status == 409 and body["error"]["code"] == "no_draft"
    assert list(site.drafts_root.iterdir()) == []


def test_drafts_are_independent_per_audience(tmp_path):
    site, server, host = make_site(tmp_path, audiences=("researcher", "public"))
    try:
        edit(host, "set-style", RESEARCHER_COLLECTION, "compact", preset="researcher")
        status, public_doc = editor(host, "public")
        assert status == 200
        assert public_doc["customized"] is False and public_doc["draft"] is False
        presets = {item["id"]: item for item in payload(call(host, "GET", "/api/presets"))["presets"]}
        assert presets["researcher"]["customized"] is True
        assert presets["public"]["customized"] is False
        # A copy exists only for the edited audience.
        assert sorted(path.name for path in site.drafts_root.iterdir()) == ["researcher"]
        # Editing public does not touch researcher's copy.
        researcher_before = draft_path(site, "researcher").read_bytes()
        edit(host, "set-style", "pub-series-collection", "compact", preset="public")
        assert draft_path(site, "researcher").read_bytes() == researcher_before
    finally:
        server.shutdown()
        server.server_close()


# --------------------------------------------------------------------------- generation

def test_default_generation_is_classified_default(web):
    site, host = web
    job = generate_ok(host)
    assert job["mode"] == "standard"
    finished = wait_for_job(host, job["job_id"])
    assert finished["status"] == "succeeded"
    assert finished["classification"] == "default"
    record = site._job_record(job["job_id"])
    assert record["classification"] == "default"
    assert record["classification_basis"] == hashlib.sha256(
        workbench.recipe_bytes(workbench.open_recipe(RECIPES / "researcher.json"))).hexdigest()
    assert list(site.drafts_root.iterdir()) == []


def test_customized_generation_commits_the_pending_selection(web):
    site, host = web
    _, doc = editor(host)
    subset = doc["eligible_topics"][:1]
    edit(host, "set-topics", RESEARCHER_COLLECTION, subset)
    edit(host, "set-style", RESEARCHER_COLLECTION, "compact")
    job = generate_ok(host)
    assert job["mode"] == "customized"
    finished = wait_for_job(host, job["job_id"])
    assert finished["status"] == "succeeded"
    assert finished["classification"] == "customized"
    record = site._job_record(job["job_id"])
    snapshot = workbench.open_recipe(site.work_root / record["snapshot"])
    rendered = next(item for item in snapshot["blocks"]
                    if item["instance_id"] == RESEARCHER_COLLECTION)
    assert rendered["topics"] == subset          # explicit author-ordered subset
    assert rendered["presentation"]["style"] == "compact"
    # The commit wrote the pending selection into the saved copy.
    draft = workbench.open_draft(site.drafts_root / "researcher")
    assert draft.selection == {}
    assert next(item for item in draft.recipe["blocks"]
                if item["instance_id"] == RESEARCHER_COLLECTION)["topics"] == subset
    # And the editor now reports the committed state.
    _, after = editor(host)
    assert collection(after)["selected_topics"] == subset


def test_all_checked_generation_keeps_eligible(web):
    site, host = web
    _, doc = editor(host)
    edit(host, "set-topics", RESEARCHER_COLLECTION, list(doc["eligible_topics"]))
    _, doc = editor(host)
    # Selecting every disease in bundle order reproduces the default resolved selection.
    assert doc["customized"] is False
    status, gen = generate(host)
    assert status == 202 and gen is not None
    finished = wait_for_job(host, gen["job_id"])
    assert finished["classification"] == "default"
    record = site._job_record(gen["job_id"])
    snapshot = workbench.open_recipe(site.work_root / record["snapshot"])
    rendered = next(item for item in snapshot["blocks"]
                    if item["instance_id"] == RESEARCHER_COLLECTION)
    assert rendered["topics"] == "eligible"


def test_rendered_recipe_is_exactly_the_snapshot_bytes(tmp_path):
    seen = {}

    def recording(bundle, output, fmt, quarto, provenance, provenance_out, composition):
        seen["path"] = Path(composition)
        seen["bytes"] = Path(composition).read_bytes()
        stub_render(bundle, output, fmt, quarto, provenance, provenance_out, composition)

    site, server, host = make_site(tmp_path, render=recording)
    try:
        edit(host, "exclude", "block-coverage-selection")
        job = generate_ok(host)
        finished = wait_for_job(host, job["job_id"])
        assert finished["status"] == "succeeded"
        record = site._job_record(job["job_id"])
        snapshot = site.work_root / record["snapshot"]
        package = site.work_root / record["preview_dir"]
        assert seen["path"] == package / "composition.json"
        assert seen["bytes"] == snapshot.read_bytes()
        assert hashlib.sha256(seen["bytes"]).hexdigest() == finished["recipe_sha256"]
        edit(host, "include", "block-coverage-selection")
        assert seen["path"].read_bytes() == seen["bytes"] == snapshot.read_bytes()
    finally:
        server.shutdown()
        server.server_close()


def test_duplicate_generate_is_refused_while_one_is_running(tmp_path):
    blocking = BlockingRender()
    site, server, host = make_site(tmp_path, render=blocking)
    try:
        job = generate_ok(host)
        assert blocking.started.wait(10)
        status, _ = generate(host)
        assert status == 409
        blocking.release.set()
    finally:
        blocking.release.set()
        server.shutdown()
        server.server_close()


def test_failed_render_keeps_the_previous_report_and_the_job_record(web):
    site, host = web
    first = generate_ok(host)
    good = wait_for_job(host, first["job_id"])
    url = good["report_url"]
    before = call(host, "GET", url)[2]
    site.render = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    second = generate_ok(host)
    failed = wait_for_job(host, second["job_id"])
    assert failed["status"] == "failed" and failed["report_url"] is None
    assert "boom" in failed["error"]
    assert call(host, "GET", f"/reports/{second['job_id']}/report.html")[0] == 404
    assert call(host, "GET", url)[2] == before
    jobs = payload(call(host, "GET", "/api/saved"))["jobs"]
    assert {job["job_id"] for job in jobs} == {first["job_id"], second["job_id"]}


def test_submission_failure_releases_the_render_reservation(web, monkeypatch):
    site, host = web

    def boom(**kwargs):
        raise RuntimeError("replay command failed")

    monkeypatch.setattr(composer_site.workbench, "replay_command", boom)
    status, _, _ = call(host, "POST", "/api/generate", {"preset": "researcher"},
                        action="generate")
    assert status == 500
    assert site._active is None and not site._threads
    monkeypatch.undo()
    job = generate_ok(host)
    assert wait_for_job(host, job["job_id"])["status"] == "succeeded"
    assert site._active is None and not site._threads


def test_finished_job_leaves_no_render_worker(web):
    site, host = web
    job = generate_ok(host)
    wait_for_job(host, job["job_id"])
    for _ in range(200):
        if not site._threads and site._active is None:
            break
        time.sleep(0.02)
    assert site._active is None and not site._threads
    assert not any(thread.name == f"render-{job['job_id']}" for thread in threading.enumerate())


def test_generate_rejects_unknown_or_unavailable_choices(web):
    _, host = web
    assert generate(host, preset="nope")[0] == 400
    assert generate(host, preset="health_institution")[0] == 404
    assert generate(host, preset="custom")[0] == 400


# --------------------------------------------------------------------------- history

def test_saved_history_is_honest_about_what_was_recorded(web):
    site, host = web
    job = generate_ok(host)
    wait_for_job(host, job["job_id"])
    rows = payload(call(host, "GET", "/api/saved"))["jobs"]
    assert rows[0]["classification"] == "default"
    assert rows[0]["snapshot_summary"]["available"] is True
    assert rows[0]["snapshot_summary"]["block_count"] == 7

    # A pre-Round-A record: mode recorded, no classification, snapshot still present.
    legacy = site.jobs_root / "20260101T000000Z-aaaaaaaaaa"
    legacy.mkdir()
    snapshot = legacy / "composition.json"
    snapshot.write_bytes((RECIPES / "researcher.json").read_bytes())
    (legacy / "job.json").write_text(json.dumps({
        "job_id": legacy.name, "preset": "researcher", "mode": "custom",
        "recipe_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "status": "succeeded", "created_utc": "2026-01-01T00:00:00+00:00",
        "started_utc": None, "finished_utc": "2026-01-01T00:00:30+00:00",
        "error": None, "snapshot": f"jobs/{legacy.name}/composition.json",
        "preview_dir": None}), encoding="utf-8")
    rows = payload(call(host, "GET", "/api/saved"))["jobs"]
    old = next(row for row in rows if row["job_id"] == legacy.name)
    assert old["classification"] is None          # never invented
    assert old["mode"] == "custom"                # the recorded render path is preserved
    assert old["snapshot_summary"]["available"] is True


def test_legacy_job_without_preset_keeps_its_audience(web):
    site, host = web
    job_dir = site.jobs_root / "20260101T000000Z-bbbbbbbbbb"
    job_dir.mkdir()
    (job_dir / "job.json").write_text(json.dumps({
        "job_id": job_dir.name, "bundle_id": "researcher", "status": "succeeded",
        "recipe_sha256": "a" * 64, "created_utc": "2026-01-01T00:00:00+00:00",
        "finished_utc": "2026-01-01T00:00:30+00:00", "error": None,
        "preview_dir": None, "snapshot": None}), encoding="utf-8")
    rows = payload(call(host, "GET", "/api/saved"))["jobs"]
    old = next(row for row in rows if row["job_id"] == job_dir.name)
    assert old["preset"] == "researcher"
    assert old["classification"] is None
    assert old["snapshot_summary"]["available"] is False


def test_interrupted_jobs_are_marked_after_restart(tmp_path):
    site, server, host = make_site(tmp_path)
    server.shutdown()
    server.server_close()
    job_dir = site.jobs_root / "20260101T000000Z-0123456789"
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(json.dumps({
        "job_id": job_dir.name, "preset": "researcher", "mode": "standard",
        "recipe_sha256": "a" * 64, "status": "running",
        "created_utc": "2026-01-01T00:00:00+00:00",
        "started_utc": "2026-01-01T00:00:01+00:00",
        "finished_utc": None, "error": None}), encoding="utf-8")
    website = composer_site.Site(tmp_path / "work", tmp_path / "inputs", tmp_path / "inputs",
                                 tmp_path / "recipes", workflow_config=None, render=stub_render)
    record = json.loads((website.jobs_root / job_dir.name / "job.json").read_text())
    assert record["status"] == "interrupted"
    assert "no report was produced" in record["error"]


# --------------------------------------------------------------------------- reuse

def reuse_of(host, preset="researcher"):
    status, doc = editor(host, preset)
    assert status == 200
    return doc["reuse"]


def test_no_reuse_before_any_generation(web):
    _, host = web
    assert reuse_of(host) is None
    source = (WEB / "app.js").read_text(encoding="utf-8")
    assert "matched ?" in source and "A matching report already exists" in source


def test_reset_matches_the_previously_generated_default(web):
    _, host = web
    job = generate_ok(host)
    finished = wait_for_job(host, job["job_id"])
    assert finished["status"] == "succeeded"
    edit(host, "set-style", RESEARCHER_COLLECTION, "compact")
    assert reuse_of(host) is None          # different settings, no match
    status, _, raw = call(host, "POST", "/api/reset", {"preset": "researcher"}, action="reset")
    assert status == 200
    reuse = json.loads(raw)["reuse"]
    assert reuse["available"] is True
    assert reuse["job_id"] == job["job_id"]
    assert reuse["recipe_sha256"] == finished["recipe_sha256"]
    assert reuse["classification"] == "default"
    assert reuse["report_url"].endswith(f"/reports/{job['job_id']}/report.html")
    assert reuse["replay_command"] == finished["replay_command"]


def test_returning_settings_match_the_previous_custom_generation(web):
    _, host = web
    _, doc = editor(host)
    subset = doc["eligible_topics"][:1]
    edit(host, "set-topics", RESEARCHER_COLLECTION, subset)
    edit(host, "set-style", RESEARCHER_COLLECTION, "compact")
    job = generate_ok(host)
    finished = wait_for_job(host, job["job_id"])
    assert finished["classification"] == "customized"
    # Change away, then restore exactly the generated settings.
    edit(host, "set-topics", RESEARCHER_COLLECTION, doc["eligible_topics"])
    assert reuse_of(host) is None
    edit(host, "set-topics", RESEARCHER_COLLECTION, subset)
    edit(host, "set-style", RESEARCHER_COLLECTION, "compact")
    reuse = reuse_of(host)
    assert reuse["job_id"] == job["job_id"] and reuse["classification"] == "customized"


def test_equivalent_normalised_settings_match_the_default(web):
    site, host = web
    job = generate_ok(host)
    wait_for_job(host, job["job_id"])
    _, doc = editor(host)
    # An explicit list of every disease in bundle order is the same composition as "eligible".
    edit(host, "set-topics", RESEARCHER_COLLECTION, list(doc["eligible_topics"]))
    _, doc = editor(host)
    assert doc["customized"] is False
    assert doc["reuse"] and doc["reuse"]["job_id"] == job["job_id"]


def test_invalid_pending_selection_cannot_reuse_a_stale_report(web):
    _, host = web
    job = generate_ok(host)
    wait_for_job(host, job["job_id"])
    edit(host, "set-topics", RESEARCHER_COLLECTION, [])
    status, doc = editor(host)
    assert doc["ready"] is False and doc["reuse"] is None
    status, _, raw = call(host, "POST", "/api/reuse",
                          {"preset": "researcher", "job_id": job["job_id"]}, action="reuse")
    body = json.loads(raw)
    assert status == 400 and body["error"]["message"] == EMPTY_SELECTION


def test_different_bundle_identity_prevents_reuse(web, tmp_path):
    site, host = web
    job = generate_ok(host)
    wait_for_job(host, job["job_id"])
    assert reuse_of(host)["job_id"] == job["job_id"]
    bundle_json = site.inputs_root / "researcher" / "data" / "bundle.json"
    manifest = json.loads(bundle_json.read_text(encoding="utf-8"))
    manifest["snapshot_id"] = "b" * 64
    bundle_json.write_text(json.dumps(manifest), encoding="utf-8")
    assert reuse_of(host) is None


def test_different_code_identity_prevents_reuse(web, monkeypatch):
    site, host = web
    job = generate_ok(host)
    wait_for_job(host, job["job_id"])
    assert reuse_of(host)["job_id"] == job["job_id"]
    original = site.environment_identity()
    changed = json.loads(json.dumps(original))
    changed["files"]["scripts/health_pipeline/publish.py"] = "0" * 64
    monkeypatch.setattr(site, "environment_identity", lambda: changed)
    assert reuse_of(host) is None
    monkeypatch.undo()
    assert reuse_of(host)["job_id"] == job["job_id"]


def test_failed_or_tampered_reports_are_not_reused(web):
    site, host = web
    job = generate_ok(host)
    finished = wait_for_job(host, job["job_id"])
    record = site._job_record(job["job_id"])
    package = site.work_root / record["preview_dir"]
    assert reuse_of(host)["job_id"] == job["job_id"]

    (package / "methods.html").write_text("<p>changed</p>", encoding="utf-8")
    assert reuse_of(host) is None

    (package / "methods.html").write_text("<p>methods</p>", encoding="utf-8")
    (package / "report.html").unlink()
    assert reuse_of(host) is None

    # A failed generation never becomes a candidate, even with the same settings.
    site.render = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    failed_job = generate_ok(host)
    failed = wait_for_job(host, failed_job["job_id"])
    assert failed["status"] == "failed"
    assert reuse_of(host) is None


def test_multiple_matches_choose_the_newest_deterministically(web):
    site, host = web
    first = generate_ok(host)
    wait_for_job(host, first["job_id"])
    assert reuse_of(host)["job_id"] == first["job_id"]

    # A second, identical generation produces a newer record with the same reuse key.
    second = generate_ok(host)
    wait_for_job(host, second["job_id"])
    record = site._job_record(second["job_id"])
    assert record["reuse_key"] == site._job_record(first["job_id"])["reuse_key"]
    assert reuse_of(host)["job_id"] == second["job_id"]

    # Forcing the newer record's timestamp back makes the choice flip, not wander.
    import composer_site as module
    record_path = site.jobs_root / second["job_id"] / "job.json"
    payload = json.loads(record_path.read_text())
    payload["finished_utc"] = "2020-01-01T00:00:00+00:00"
    record_path.write_text(json.dumps(payload), encoding="utf-8")
    assert reuse_of(host)["job_id"] == first["job_id"]


def test_reuse_becomes_unavailable_between_lookup_and_show(web):
    site, host = web
    job = generate_ok(host)
    wait_for_job(host, job["job_id"])
    reuse = reuse_of(host)
    assert reuse["job_id"] == job["job_id"]
    package = site.work_root / site._job_record(job["job_id"])["preview_dir"]
    (package / "report.html").unlink()
    status, _, raw = call(host, "POST", "/api/reuse",
                          {"preset": "researcher", "job_id": job["job_id"]}, action="reuse")
    body = json.loads(raw)
    assert status == 409 and body["error"]["code"] == "reuse_unavailable"
    assert "missing" in body["error"]["message"]
    source = (WEB / "app.js").read_text(encoding="utf-8")
    assert "Generate is available again" in source
    assert "the report on screen is unchanged" in source


def test_show_here_renders_nothing_and_preserves_history(web):
    site, host = web
    job = generate_ok(host)
    finished = wait_for_job(host, job["job_id"])
    record_before = (site.jobs_root / job["job_id"] / "job.json").read_bytes()
    report_before = call(host, "GET", finished["report_url"])[2]
    jobs_before = sorted(path.name for path in site.jobs_root.iterdir())

    status, _, raw = call(host, "POST", "/api/reuse",
                          {"preset": "researcher", "job_id": job["job_id"]}, action="reuse")
    shown = json.loads(raw)
    assert status == 200
    assert shown["job_id"] == job["job_id"]
    assert shown["replay_command"] == finished["replay_command"]
    assert shown["recipe_sha256"] == finished["recipe_sha256"]
    assert set(shown) == {"available", "job_id", "created_utc", "finished_utc",
                          "recipe_sha256", "classification", "package_files",
                          "report_url", "replay_command"}
    # No render happened: same jobs, same bytes, same job record, no active worker.
    assert sorted(path.name for path in site.jobs_root.iterdir()) == jobs_before
    assert (site.jobs_root / job["job_id"] / "job.json").read_bytes() == record_before
    assert call(host, "GET", finished["report_url"])[2] == report_before
    assert site._active is None and not site._threads


def test_reuse_rejects_unknown_or_legacy_jobs(web):
    site, host = web
    job = generate_ok(host)
    wait_for_job(host, job["job_id"])
    status, _, _ = call(host, "POST", "/api/reuse",
                        {"preset": "researcher", "job_id": "20260101T000000Z-aaaaaaaaaa"},
                        action="reuse")
    assert status == 404
    # A retained job without reuse metadata stays in history but is never auto-reused.
    legacy = site.jobs_root / "20260101T000000Z-bbbbbbbbbb"
    legacy.mkdir()
    (legacy / "job.json").write_text(json.dumps({
        "job_id": legacy.name, "preset": "researcher", "mode": "standard",
        "status": "succeeded", "recipe_sha256": "a" * 64,
        "created_utc": "2026-01-01T00:00:00+00:00", "finished_utc": None,
        "error": None, "preview_dir": None, "snapshot": None}), encoding="utf-8")
    assert reuse_of(host)["job_id"] == job["job_id"]     # legacy record ignored
    rows = payload(call(host, "GET", "/api/saved"))["jobs"]
    assert any(row["job_id"] == legacy.name for row in rows)


def test_reuse_ui_contract_in_source():
    source = (WEB / "app.js").read_text(encoding="utf-8")
    assert "A report matching these settings is already available." in source
    assert "already on screen" in source
    assert "prefers-reduced-motion" in source
    assert source.count("scrollIntoView") == 1        # only on Show here, never on discovery
    assert "showHere" in source and "focusReport" in source
    assert "seq !== state.seq" in source
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert 'id="report"' in html and 'tabindex="-1"' in html
    assert 'id="reuse-show"' in html and "Show here" in html


# ------------------------------------------------------- history labels vs reuse

def make_legacy_job(site, job_id="20260101T000000Z-dddddddddd", recipe_path=None,
                    mode="standard", classification=None):
    """A retained report with a valid snapshot but no reuse metadata."""
    recipe_path = recipe_path or (RECIPES / "researcher.json")
    directory = site.jobs_root / job_id
    directory.mkdir(parents=True)
    snapshot = directory / "composition.json"
    snapshot.write_bytes(Path(recipe_path).read_bytes())
    (directory / "job.json").write_text(json.dumps({
        "job_id": job_id, "preset": "researcher", "mode": mode,
        "classification": classification,
        "recipe_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "status": "succeeded", "created_utc": "2026-01-01T00:00:00+00:00",
        "finished_utc": "2026-01-01T00:00:30+00:00", "error": None,
        "snapshot": f"jobs/{job_id}/composition.json", "preview_dir": None}),
        encoding="utf-8")
    return directory


def test_default_classification_is_not_reuse_eligibility(web):
    """The reported Researcher case: a default report with no reuse metadata."""
    site, host = web
    make_legacy_job(site)
    # Its composition is exactly the current default, but it cannot be reused.
    assert reuse_of(host) is None
    rows = payload(call(host, "GET", "/api/saved"))["jobs"]
    row = next(item for item in rows if item["job_id"] == "20260101T000000Z-dddddddddd")
    assert row["classification"] is None          # never invented
    assert row["mode"] == "standard"              # the recorded render path
    assert row["status"] == "succeeded"           # still a valid, openable report
    assert row["reuse"]["eligible"] is False
    assert row["reuse"]["code"] == "no_metadata"
    assert row["reuse"]["reason"] == "Older report: reuse metadata was not recorded."
    assert row["composition_match"] == "same"     # settings match; eligibility does not
    source = (WEB / "app.js").read_text(encoding="utf-8")
    assert "Reusable now" in source and "Not reusable now" in source
    assert "A report stays openable" in (WEB / "index.html").read_text(encoding="utf-8")


def test_history_reuse_reasons_are_specific(web):
    site, host = web
    default_job = generate_ok(host)
    wait_for_job(host, default_job["job_id"])
    _, doc = editor(host)
    edit(host, "set-topics", RESEARCHER_COLLECTION, [doc["eligible_topics"][0]])
    custom_job = generate_ok(host)
    wait_for_job(host, custom_job["job_id"])
    call(host, "POST", "/api/reset", {"preset": "researcher"}, action="reset")
    rows = {row["job_id"]: row for row in payload(call(host, "GET", "/api/saved"))["jobs"]}
    assert rows[default_job["job_id"]]["reuse"]["eligible"] is True
    assert rows[default_job["job_id"]]["composition_match"] == "same"
    custom = rows[custom_job["job_id"]]
    assert custom["reuse"]["eligible"] is False
    assert custom["reuse"]["code"] == "different_identity"
    assert custom["reuse"]["reason"] == "Different settings, saved input, or renderer version."
    assert custom["composition_match"] == "different"
    assert custom["status"] == "succeeded"        # not demoted to failed
    # A tampered package is reported as an artifact problem, not as a bad report.
    record = site._job_record(default_job["job_id"])
    (site.work_root / record["preview_dir"] / "methods.html").write_text("x", encoding="utf-8")
    rows = {row["job_id"]: row for row in payload(call(host, "GET", "/api/saved"))["jobs"]}
    assert rows[default_job["job_id"]]["reuse"]["code"] == "artifact"
    assert rows[default_job["job_id"]]["reuse"]["reason"].startswith("Not reusable:")
    assert rows[default_job["job_id"]]["status"] == "succeeded"


def test_failed_reports_say_they_did_not_complete(web):
    site, host = web
    site.render = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    job = generate_ok(host)
    wait_for_job(host, job["job_id"])
    rows = {row["job_id"]: row for row in payload(call(host, "GET", "/api/saved"))["jobs"]}
    assert rows[job["job_id"]]["reuse"]["eligible"] is False
    assert rows[job["job_id"]]["reuse"]["reason"] == "This report did not complete."
    assert rows[job["job_id"]]["status"] == "failed"


def test_history_navigation_uses_the_shared_display_function():
    source = (WEB / "app.js").read_text(encoding="utf-8")
    assert source.count("function displayReport(") == 1
    assert source.count("displayReport(") >= 3          # definition + both callers
    assert "displaySaved(" in source and "showHere(" in source
    assert source.count("focusReport()") >= 2           # both explicit paths
    # Refreshing history or matches never moves focus by itself.
    load_saved = source.split("async function loadSaved", 1)[1].split("function displaySaved", 1)[0]
    assert "focusReport" not in load_saved and "scrollIntoView" not in load_saved
    render_reuse = source.split("function renderReuse", 1)[1].split("function focusReport", 1)[0]
    assert "focusReport" not in render_reuse
    assert "scrollIntoView" not in render_reuse


def test_saved_report_sections_are_named_honestly():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "Data and saved reports" not in html
    assert "Saved reports" in html
    assert "Data and source locations" in html
    assert 'id="saved-list"' in html and 'id="data-paths"' in html
    # The history list is visible; only the paths sit behind a disclosure.
    assert html.index('id="saved-list"') < html.index('id="data"')


def test_repeated_history_access_writes_nothing(web):
    site, host = web
    job = generate_ok(host)
    wait_for_job(host, job["job_id"])
    draft_before = (draft_path(site).read_bytes()
                    if draft_path(site).is_file() else None)
    revision_before = editor(host)[1]["revision"]
    jobs_before = sorted(path.name for path in site.jobs_root.iterdir())
    for _ in range(3):
        payload(call(host, "GET", "/api/saved"))
    assert sorted(path.name for path in site.jobs_root.iterdir()) == jobs_before
    assert editor(host)[1]["revision"] == revision_before
    assert (draft_path(site).read_bytes() if draft_path(site).is_file() else None) \
        == draft_before
    # The same retained report can be confirmed repeatedly, unchanged.
    first = payload(call(host, "POST", "/api/reuse",
                         {"preset": "researcher", "job_id": job["job_id"]}, action="reuse"))
    second = payload(call(host, "POST", "/api/reuse",
                          {"preset": "researcher", "job_id": job["job_id"]}, action="reuse"))
    assert first == second
    assert site._active is None and not site._threads


# --------------------------------------------------------------------------- containment

def test_artifact_paths_are_contained_and_symlinks_are_refused(web, tmp_path):
    site, host = web
    job = generate_ok(host)
    wait_for_job(host, job["job_id"])
    for path in (f"/reports/{job['job_id']}/../../composition.json",
                 f"/reports/{job['job_id']}/%2e%2e/%2e%2e/job.json",
                 f"/reports/{job['job_id']}/job.json",
                 "/reports/20260101T000000Z-0123456789/report.html",
                 f"/reports/{job['job_id']}/nope.html"):
        assert call(host, "GET", path)[0] == 404, path
    record = site._job_record(job["job_id"])
    package = site.work_root / record["preview_dir"]
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    (package / "escape.txt").symlink_to(outside)
    assert call(host, "GET", f"/reports/{job['job_id']}/escape.txt")[0] == 404
    assert call(host, "GET", f"/reports/{job['job_id']}/report.txt")[0] == 404


def test_draft_paths_stay_inside_the_work_root(web):
    site, host = web
    outside = site.work_root.parent / "elsewhere"
    outside.mkdir()
    os.symlink(outside, site.drafts_root / "researcher")
    status, body = edit(host, "move-down", "block-coverage-selection")
    assert status == 400 and "escapes the work root" in body["error"]["message"]
    assert not any(outside.iterdir())


def test_no_marimo_dependency_or_process():
    for path in (ROOT / "src" / "composer_site.py",
                 ROOT / "scripts" / "health_pipeline" / "composer_workspace.py",
                 *sorted(WEB.glob("*"))):
        assert "marimo" not in path.read_text(encoding="utf-8").lower(), path
    assert "marimo" not in sys.modules
    assert not (ROOT / "src" / "composer_ui.py").exists()
    assert "marimo" not in Path("/proc/self/cmdline").read_bytes().decode(
        "utf-8", "replace").lower()
    assert not any("marimo" in thread.name.lower() for thread in threading.enumerate())
