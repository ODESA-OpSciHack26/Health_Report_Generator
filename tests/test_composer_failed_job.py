"""Contract tests for the failed-job summary and diagnostics disclosure.

The DOM behaviour (native details/summary, keyboard operation, complete text in the disclosure)
is verified in the recorded browser evidence for this candidate; these tests guard the source
contract that the browser evidence depends on, without importing or editing another lane's
dirty test module (tests/test_composer_site.py).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "src" / "composer_web" / "app.js").read_text(encoding="utf-8")
APP_CSS = (ROOT / "src" / "composer_web" / "app.css").read_text(encoding="utf-8")


def _saved_list_block():
    start = APP_JS.index("async function loadSaved(")
    end = APP_JS.index("\nfunction ", start + 10)
    return APP_JS[start:end]


def test_failed_job_line_uses_bounded_headline_not_raw_error():
    block = _saved_list_block()
    assert 'failureHeadline(job.error)' in block
    assert '+ (job.error ? " — " + job.error : "")' not in block


def test_failure_headline_is_defined_and_capped():
    assert "function failureHeadline(" in APP_JS
    start = APP_JS.index("function failureHeadline(")
    body = APP_JS[start:APP_JS.index("\n}\n", start)]
    assert "<= 160" in body
    assert "…" in body


def test_failed_job_exposes_native_diagnostics_disclosure():
    block = _saved_list_block()
    assert 'job.status === "failed" && job.error' in block
    assert 'createElement("details")' in block
    assert 'createElement("summary")' in block
    assert 'diagnosticsSummary.textContent = "Full diagnostics"' in block
    assert 'createElement("pre")' in block
    assert "diagnosticsText.textContent = job.error" in block


def test_diagnostics_do_not_use_innerHTML():
    block = _saved_list_block()
    diagnostics = block[block.index('job.status === "failed" && job.error'):]
    diagnostics = diagnostics[:diagnostics.index("body.append(diagnostics)") + len("body.append(diagnostics)")]
    assert "innerHTML" not in diagnostics


def test_diagnostics_pre_is_bounded_and_wraps():
    start = APP_CSS.index(".saved-diagnostics pre {")
    rule = APP_CSS[start:APP_CSS.index("}", start)]
    assert "max-height:" in rule
    assert "overflow: auto" in rule
    assert "white-space: pre-wrap" in rule
    assert "overflow-wrap: anywhere" in rule
