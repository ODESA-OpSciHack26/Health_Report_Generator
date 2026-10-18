"""Main and selected-report workflows must agree on audience IDs."""
import ast
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"researcher", "health_institution", "public"}


def test_main_and_selected_workflow_audiences_match():
    main = yaml.safe_load((ROOT / "workflow/config.yaml").read_text())
    selected = yaml.safe_load(
        (ROOT / ".github/workflows/render-selected-report.yml").read_text()
    )
    triggers = selected.get("on", selected.get(True))
    options = triggers["workflow_dispatch"]["inputs"]["audience"]["options"]

    assert set(main["stakeholders"]) == EXPECTED
    assert len(main["stakeholders"]) == len(EXPECTED)
    assert set(options) == EXPECTED
    assert len(options) == len(EXPECTED)


def test_selected_renderer_and_presentation_profiles_match():
    profiles = json.loads(
        (ROOT / "scripts/health_pipeline/config/audience_presentations.json")
        .read_text()
    )["profiles"]

    tree = ast.parse(
        (ROOT / "scripts/health_pipeline/render_selected.py").read_text()
    )
    assignments = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "AUDIENCES"
            for target in node.targets
        )
    ]

    assert len(assignments) == 1
    audiences = ast.literal_eval(assignments[0].value)
    assert set(audiences) == EXPECTED
    assert set(profiles) == EXPECTED
