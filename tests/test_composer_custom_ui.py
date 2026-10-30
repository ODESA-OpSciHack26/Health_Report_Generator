"""Custom composer rendering: execute the real frontend against a real-server transcript.

The browser defect this covers was a frontend statement that threw before any library entry was
built. HTTP and source-string assertions cannot catch that, so this module runs
``src/composer_web/app.js`` unmodified under Node with a spec-faithful DOM subset
(``tests/js/minidom.mjs``: ``Element.append`` returns undefined, like a browser). The fixture is a
transcript produced by a real in-process Site: every request the page is expected to send, paired
with the document that server call actually returned. A wrong action name, instance id or payload
therefore fails the harness, not just a slow assertion.

When Node is not installed the rendering test is skipped with that reason; it is not replaced by a
weaker assertion, and the browser retest remains required.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import composer_site  # noqa: E402
from test_composer_custom import build_inputs  # noqa: E402

HARNESS = ROOT / "tests" / "js" / "custom_dom_check.mjs"
NODE = shutil.which("node")
CONTEXTS = ("researcher", "health_institution", "public")
COLLECTION = "researcher-series-collection"


def make_site(tmp_path):
    inputs, recipes = build_inputs(tmp_path, audiences=CONTEXTS)
    return composer_site.Site(tmp_path / "work", inputs, inputs, recipes,
                              workflow_config=None, quarto="quarto",
                              render=lambda *args, **kwargs: None)


class Transcript:
    """Run the same actions the page will send and record what the server answered."""

    def __init__(self, site):
        self.site = site
        self.preset_steps = []
        self.custom_steps = []

    def preset(self, action, instance, value):
        request = {"preset": "researcher", "action": action, "instance": instance,
                   "value": value}
        document = self.site.save_draft_edit("researcher", action, instance, value)
        self.preset_steps.append({"request": request, "doc": document})
        return document

    def custom(self, action, instance, value=None, context="researcher"):
        request = {"context": context, "action": action, "instance": instance, "value": value}
        try:
            document = self.site.custom_edit(context, action, instance, value)
        except composer_site.SiteError as error:
            self.custom_steps.append({"request": request,
                                      "error": {"code": error.code, "message": error.message},
                                      "status": int(error.status)})
            return None
        self.custom_steps.append({"request": request, "doc": document})
        return document


def build_fixture(site):
    transcript = Transcript(site)
    initial = {"researcher": site.custom_document("researcher", selected="researcher")}
    researcher = initial["researcher"]
    measure = researcher["measures"][0]

    # Preset mode: the same Clear / Select all controls through the same handlers.
    editor = site.editor_document("researcher")
    transcript.preset("set-topics", COLLECTION, [])
    transcript.preset("set-topics", COLLECTION, list(editor["eligible_topics"]))

    # Custom mode: add the collection from its ordered row, pick two diseases, configure display,
    # exclude/restore it, bind a reference result, then duplicate and delete one instance.
    added = transcript.custom("add-block", None,
                              {"block": "series-collection", "options": {"measure": measure}})
    collection = next(item["instance_id"] for item in added["blocks"]
                      if item["block"] == "series-collection")
    transcript.custom("set-option", collection,
                      {"option": "presentation.layout", "value": "panels"})
    transcript.custom("set-option", collection,
                      {"option": "presentation.layout", "value": "combined"})
    transcript.custom("set-title", collection, "Hepatitis focus")
    transcript.custom("set-topics", collection, [])
    transcript.custom("set-topics", collection, ["campylobacteriosis"])
    transcript.custom("set-topics", collection, ["campylobacteriosis", "influenza"])
    transcript.custom("set-default-open", collection, "influenza")
    transcript.custom("set-option", collection, {"option": "presentation.style", "value": "compact"})
    transcript.custom("set-option", collection, {"option": "years", "value": [2022, 2024]})
    transcript.custom("move-up", collection)
    transcript.custom("remove", collection)
    transcript.custom("restore", collection)

    reference_choices = list(researcher["reference_topics"])
    reference_added = transcript.custom(
        "add-block", None, {"block": "reference-comparison",
                            "options": {"topic": reference_choices[0]}})
    reference = next(item["instance_id"] for item in reference_added["blocks"]
                     if item["block"] == "reference-comparison")
    transcript.custom("set-option", reference, {"option": "topic", "value": "campylobacteriosis"})

    monitoring_added = transcript.custom("add-block", None, {"block": "monitoring-overview", "options": {}})
    monitoring = next(item["instance_id"] for item in monitoring_added["blocks"]
                      if item["block"] == "monitoring-overview")
    duplicated = transcript.custom("duplicate", monitoring)
    instances = [item["instance_id"] for item in duplicated["blocks"]
                 if item["block"] == "monitoring-overview"]
    duplicate = next(name for name in instances if name != monitoring)
    transcript.custom("delete-instance", duplicate)

    final = site.custom_document("researcher")
    return {
        "presets": {"presets": site.presets()},
        "saved": site.saved(),
        "editor": {"researcher": site.editor_document("researcher")},
        "custom_state": initial,
        "custom_steps": transcript.custom_steps,
        "preset_steps": transcript.preset_steps,
        "context": "researcher",
        "audience": "researcher",
        "collection_instance": collection,
        "reference_instance": reference,
        "monitoring_instance": monitoring,
        "duplicate_instance": duplicate,
        "reference_target": "campylobacteriosis",
        "eligible_count": len(researcher["eligible_topics"]),
        "final_block_count": len(final["blocks"]),
        "app_js": str(ROOT / "src" / "composer_web" / "app.js"),
        "index_html": str(ROOT / "src" / "composer_web" / "index.html"),
    }


def test_frontend_does_not_chain_dom_mutators():
    """`Element.append()` returns undefined; chaining it lost the whole library render."""
    source = (ROOT / "src" / "composer_web" / "app.js").read_text(encoding="utf-8")
    offenders = [line.strip() for line in source.splitlines()
                 if re.search(r"\.(append|appendChild|replaceChildren)\([^;]*\)\s*\.", line)]
    assert offenders == []


@pytest.mark.skipif(NODE is None, reason="node is not installed in this runtime; "
                                        "the DOM harness runs where Node is available")
def test_shared_editor_renders_and_drives_both_modes(tmp_path):
    node = NODE
    assert node is not None
    fixture = build_fixture(make_site(tmp_path))
    # 18 custom requests + 2 preset requests.
    assert len(fixture["custom_steps"]) == 18
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    done = subprocess.run([node, str(HARNESS), str(path)], capture_output=True, text=True,
                          timeout=180)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "SUMMARY" in done.stdout and '"failures":0' in done.stdout
    assert "no request was unexpected or mismatched" in done.stdout


@pytest.mark.skipif(NODE is None, reason="node is not installed in this runtime")
def test_rendering_harness_still_catches_the_chained_append_defect(tmp_path):
    """Negative control: the same harness fails against the pre-fix statement."""
    node = NODE
    assert node is not None
    fixture = build_fixture(make_site(tmp_path))
    source = (ROOT / "src" / "composer_web" / "app.js").read_text(encoding="utf-8")
    fixed = ('    const confirm = document.createElement("div");\n'
             '    confirm.className = "inline-confirm";\n'
             '    item.append(confirm);')
    assert fixed in source
    broken = tmp_path / "pre-fix-app.js"
    broken.write_text(source.replace(fixed,
                                     '    item.append(document.createElement("div"))'
                                     '.className = "inline-confirm";'), encoding="utf-8")
    fixture["app_js"] = str(broken)
    path = tmp_path / "fixture-prefix.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    done = subprocess.run([node, str(HARNESS), str(path)], capture_output=True, text=True,
                          timeout=180)
    assert done.returncode == 1
    assert "Cannot set properties of undefined (setting 'className')" in done.stdout
    assert "preset editor renders the shared include checkbox — 0" in done.stdout
