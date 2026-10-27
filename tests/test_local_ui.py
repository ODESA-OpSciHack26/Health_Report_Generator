"""Exercise the submit cell without importing Marimo or running Docker."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def invoke(value, runner):
    tree = ast.parse((ROOT / "src/local_ui.py").read_text())
    cells = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and "run_request" in {arg.arg for arg in node.args.args}
    ]
    assert len(cells) == 1
    cell = cells[0]
    cell.decorator_list = []
    module = ast.Module(body=[cell], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {}
    exec(compile(module, "local_ui.py", "exec"), namespace)

    messages, kinds = [], []

    def markdown(text):
        messages.append(text)
        return text

    def callout(text, kind):
        kinds.append(kind)
        return text

    namespace[cell.name](
        ROOT=ROOT,
        local_form=SimpleNamespace(value=value),
        mo=SimpleNamespace(md=markdown, callout=callout),
        run_request=runner,
    )
    return messages, kinds


def test_no_submission_does_not_render():
    def forbidden(*args):
        pytest.fail("No submission must not render.")

    messages, kinds = invoke(None, forbidden)
    assert messages and not kinds


def test_submission_passes_selected_parameters():
    seen = []

    def render(*args):
        seen.append(args)
        return {
            "status": "hit",
            "cache_key": "a" * 64,
            "output": ROOT / "results/local-ui/runs/example/report",
        }

    messages, kinds = invoke(
        {"audience": "public_health_expert", "start": 2022, "end": 2025},
        render,
    )
    assert seen == [("public_health_expert", 2022, 2025)]
    assert kinds == ["success"]
    assert any("cache hit" in text for text in messages)


@pytest.mark.parametrize("error", [
    ValueError("Choose an ordered year range."),
    RuntimeError("Local rendering failed. Inspect the run log."),
])
def test_expected_failures_are_visible(error):
    def fail(*args):
        raise error

    messages, kinds = invoke(
        {"audience": "public", "start": 2025, "end": 2021}, fail
    )
    assert kinds == ["danger"]
    assert str(error) in messages


def test_unexpected_error_details_are_not_displayed():
    def fail(*args):
        raise OSError("PRIVATE-DETAIL-SENTINEL")

    messages, kinds = invoke(
        {"audience": "public", "start": 2021, "end": 2025}, fail
    )
    assert kinds == ["danger"]
    assert not any("PRIVATE-DETAIL-SENTINEL" in text for text in messages)
