"""Regression guard for the audit/provenance identifier wrapping rules.

Long unbroken identifiers (snapshot ids, 40-char digests, snapshot paths) inside flex/grid children
must wrap instead of widening the document. These assertions guard the rule set that removes the
390/320 px page overflow measured in reproduced/r-website-diag-20261101T151842Z, and guard that the
intentional scrollers (tables, reproduction code) keep scrolling rather than being clipped.
"""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1]
       / "scripts" / "health_pipeline" / "templates" / "dashboard.css").read_text(encoding="utf-8")


def _rule(selector):
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert match, f"missing rule for {selector}"
    return {key.strip(): value.strip() for key, value in
            (part.split(":", 1) for part in match.group(1).split(";") if ":" in part)}


def test_audit_values_wrap_inside_their_panel():
    rule = _rule(".audit-row strong,.audit-row code,.provenance-list dd code")
    assert rule["min-width"] == "0"
    assert rule["overflow-wrap"] == "anywhere"
    assert rule["white-space"] == "normal"


def test_provenance_list_cell_can_shrink():
    rule = _rule(".provenance-list dd")
    assert rule["min-width"] == "0"
    assert rule["overflow-wrap"] == "anywhere"


def test_table_scroller_stays_intentional():
    rule = _rule(".table-scroll")
    assert rule["overflow-x"] == "auto"


def test_reproduction_code_keeps_scrolling():
    rule = _rule(".reproduction-code pre")
    assert rule["overflow"] == "auto"


def test_long_identifier_rule_does_not_hide_text():
    rule = _rule(".audit-row strong,.audit-row code,.provenance-list dd code")
    assert "text-overflow" not in rule          # no ellipsis
    assert "overflow" not in rule               # no clipping of the value itself
    assert "display" not in rule


# D4b: long inline dataset identifiers inside the quality explanation disclosure.
# Earlier these kept Quarto's `code{white-space:pre}` and widened the page to 929 px at 390 px
# when the disclosure was opened. The rule is scoped to that component only.

def test_quality_explanation_container_breaks_long_tokens():
    # Plain-text underscored identifiers (e.g. swiss_center_for_antibiotic_resistance) do not break
    # at word boundaries, so the disclosure container itself must allow breaking anywhere.
    rule = _rule(".quality-explanation")
    assert rule["overflow-wrap"] == "anywhere"
    assert rule["min-width"] == "0"


def test_quality_explanation_identifiers_wrap():
    rule = _rule(".quality-explanation code")
    assert rule["min-width"] == "0"
    assert rule["overflow-wrap"] == "anywhere"
    assert rule["white-space"] == "normal"


def test_preformatted_code_keeps_its_formatting():
    # Genuine examples must keep preformatted rendering, and no global code wrapping rule exists.
    rule = _rule(".reproduction-code pre code")
    assert rule["white-space"] == "pre"
    assert "overflow-wrap" not in rule
    for selector, body in re.findall(r"([^{}]+)\{([^}]*)\}", CSS):
        compact = body.replace(" ", "")
        bare = re.search(r"(^|,)\s*(code|\.dashboard code)\s*(,|$)", selector.strip())
        assert not (bare and "white-space:normal" in compact), f"global code wrapping rule: {selector.strip()}"
