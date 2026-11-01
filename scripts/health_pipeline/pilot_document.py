"""Minimal, HTML-first document helpers for the R-free tabular pilot.

This is deliberately not a general document framework. It provides only the primitives the
supplied-table HTML route needs: escaped HTML, numeric display formatting, tables, sections,
figures and the embedded provenance record. Markdown/LaTeX emission for the canonical and
PDF routes is a hypothesis and is not implemented here.
"""
from __future__ import annotations

import base64
import html
import json
import math


class PilotDocumentError(ValueError):
    pass


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def display_number(value, digits=1, preserve_whole=False) -> str:
    """Port of tabular_display_number: display rounding only, never analysis."""
    if value is None or isinstance(value, (list, dict)):
        return "Not available"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Not available"
    if not math.isfinite(number):
        return "Not available"
    if number != 0 and abs(number) < 0.05:
        return f"{number:.3g}"
    if preserve_whole and number == int(number):
        digits = 0
    number = round(number, digits)
    if number == 0:
        number = 0.0
    return f"{number:,.{digits}f}"


def records(rows) -> list[dict]:
    """Column order follows first appearance, as in the R helper."""
    if not rows:
        return []
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    out = []
    for row in rows:
        item = {}
        for key in columns:
            value = row.get(key)
            if isinstance(value, (list, tuple)):
                item[key] = ", ".join(str(v) for v in value)
            else:
                item[key] = value
        out.append(item)
    return out


LABELS = {
    "category": "Series", "n": "Valid observations", "rows": "Rows",
    "missing_values": "Missing values", "missing_dates": "Missing dates",
    "periods": "Selected periods", "first_period": "First period",
    "last_period": "Last period", "mean": "Mean", "sd": "SD", "min": "Minimum",
    "q1": "25th percentile", "median": "Median", "q3": "75th percentile",
    "max": "Maximum", "baseline": "Reference value", "latest": "Latest value",
    "difference": "Absolute change", "percent": "Change (%)", "note": "Interpretation",
}


def html_table(rows: list[dict], columns=None) -> str:
    if not rows:
        return "<p>No compatible results are available for this selection.</p>"
    columns = [c for c in (columns or list(rows[0])) if c in rows[0]]
    head = "".join(f"<th>{esc(LABELS.get(c, c))}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{esc(row.get(c))}</td>" for c in columns) + "</tr>"
        for row in rows
    )
    return ('<div class="table-scroll"><table class="report-table" data-searchable="true">'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>")


def display_table(rows, columns, period="year") -> str:
    data = records(rows)
    if not data:
        return "<p>No compatible results are available for this selection.</p>"
    for row in data:
        for key in ("n", "rows", "missing_values", "missing_dates", "periods"):
            if key in row:
                row[key] = display_number(row[key], 0)
        for key in ("mean", "sd", "q1", "median", "q3"):
            if key in row:
                row[key] = display_number(row[key], 1)
        for key in ("min", "max", "baseline", "latest", "difference"):
            if key in row:
                row[key] = display_number(row[key], 1, True)
        if "percent" in row:
            try:
                number = float(row["percent"])
            except (TypeError, ValueError):
                row["percent"] = "Not available"
            else:
                prefix = "+" if number > 0 else ""
                row["percent"] = f"{prefix}{display_number(number, 1)}%"
        for key in ("first_period", "last_period"):
            if key in row:
                value = row[key]
                row[key] = "Not available" if value is None else str(value)[:4 if period == "year" else 10]
    return html_table(data, columns) + (
        '<p class="chart-note">Display rounding only: summaries use one decimal place; '
        "observation counts use whole numbers. Small nonzero values retain significant digits. "
        "Full precision is retained in analysis.json.</p>")


def section(section_id, title, body) -> str:
    return (f'<section class="report-section" id="{esc(section_id)}"><h2>{esc(title)}</h2>'
            f"{body}</section>")


def cards(values, labels) -> str:
    items = "".join(
        f'<article class="report-card"><span class="card-number">{esc(value)}</span>'
        f'<span class="card-label">{esc(label)}</span></article>'
        for value, label in zip(values, labels)
    )
    return f'<div class="report-cards">{items}</div>'


def disclosure(label, body) -> str:
    return f'<details class="report-disclosure"><summary>{esc(label)}</summary>{body}</details>'


def link(href, label, current=False) -> str:
    aria = ' aria-current="page"' if current else ""
    return f'<a href="{href}"{aria}>{esc(label)}</a>'


def figure(png: bytes, title: str, note: str, width=9, height=4.2, registry=None,
           narrow_png: bytes | None = None) -> str:
    data = base64.b64encode(png).decode("ascii")
    if narrow_png:
        # Responsive art direction: below 800 px the browser loads a chart
        # rendered for a narrow canvas (one panel per row, larger type) instead
        # of shrinking the wide figure until its labels are illegible.
        narrow = base64.b64encode(narrow_png).decode("ascii")
        image = (f'<picture><source media="(max-width: 800px)" '
                 f'srcset="data:image/png;base64,{narrow}">'
                 f'<img alt="{esc(title)}" src="data:image/png;base64,{data}">'
                 '</picture>')
    else:
        image = f'<img alt="{esc(title)}" src="data:image/png;base64,{data}">'
    markup = (f'<figure class="report-figure">{image}<figcaption>{esc(note)} '
              f'<a href="methods.html#statistics">Detailed statistics and methods</a>.</figcaption></figure>')
    if registry is None:
        return markup
    token = str(len(registry))
    registry[token] = markup
    return f'<div data-pilot-figure="{token}"></div>'


def restore_figures(rendered: str, registry: dict) -> str:
    """Replace pilot placeholders after Quarto render (Quarto rewrites raw <figure>)."""
    import re
    for token, markup in registry.items():
        pattern = re.compile(r'<div data-pilot-figure="%s">\s*</div>' % re.escape(token))
        if len(pattern.findall(rendered)) != 1:
            raise PilotDocumentError(
                f"pilot figure placeholder {token} was not preserved by the renderer")
        rendered = pattern.sub(lambda match: markup, rendered, count=1)
    return rendered


def provenance_script(record: dict) -> str:
    payload = json.dumps(record, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" id="report-provenance">{payload}</script>'


INTERACTIVE_TABLES_SCRIPT = """<script>
(function(){
  function num(t){var x=t.replace(/[,%+\\s]/g,'').replace('\\u2212','-');return x!==''&&!isNaN(x)?parseFloat(x):null;}
  document.querySelectorAll('table.report-table[data-searchable]').forEach(function(tbl,ti){
    var wrap=tbl.parentNode, body=tbl.tBodies[0]; if(!body) return;
    var input=document.createElement('input'); input.type='search'; input.className='table-filter';
    input.placeholder='Filter rows'; input.setAttribute('aria-label','Filter table rows');
    wrap.parentNode.insertBefore(input,wrap);
    input.addEventListener('input',function(){var q=input.value.toLowerCase();
      Array.prototype.forEach.call(body.rows,function(r){r.style.display=r.textContent.toLowerCase().indexOf(q)>-1?'':'none';});});
    Array.prototype.forEach.call(tbl.tHead?tbl.tHead.rows[0].cells:[],function(th,ci){
      th.tabIndex=0; th.className+=' sortable'; th.title='Sort by this column'; var asc=true;
      function sort(){var rows=Array.prototype.slice.call(body.rows);
        rows.sort(function(a,b){var x=a.cells[ci].textContent.trim(),y=b.cells[ci].textContent.trim(),nx=num(x),ny=num(y);
          var c=(nx!==null&&ny!==null)?nx-ny:x.localeCompare(y);return asc?c:-c;});
        rows.forEach(function(r){body.appendChild(r);}); th.setAttribute('aria-sort',asc?'ascending':'descending'); asc=!asc;}
      th.addEventListener('click',sort); th.addEventListener('keydown',function(e){if(e.key==='Enter')sort();});
    });
  });
})();
</script>"""


STYLE = """<style>
header#title-block-header{display:none}
.tabular-enriched{max-width:1240px;margin:auto;padding:18px;color:#18343c}
.tabular-enriched.audience-editorial{max-width:960px}
.tabular-enriched .report-hero{background:#173f63;color:#fff;padding:28px;border-radius:16px;margin:8px 0 16px}
.tabular-enriched .report-hero h1,.tabular-enriched .report-hero p,.tabular-enriched .report-hero .audience-kicker{color:#fff!important;opacity:1!important}
.tabular-enriched .report-hero h1{font-size:clamp(1.8rem,4vw,2.6rem);line-height:1.15;margin:10px 0 16px}
.tabular-enriched .report-hero p{font-size:1rem;line-height:1.6;margin:8px 0}
.tabular-enriched .audience-kicker{font-size:1rem;font-weight:700;letter-spacing:.04em}
.tabular-enriched.audience-editorial .report-hero{background:#f7f3ec}
.tabular-enriched.audience-editorial .report-hero h1,.tabular-enriched.audience-editorial .report-hero p,.tabular-enriched.audience-editorial .audience-kicker{color:#173f63!important}
.tabular-enriched .report-tabs{position:sticky;top:0;z-index:20;display:flex;gap:10px;flex-wrap:wrap;background:#fff;padding:12px 0;border-bottom:2px solid #d9e5e8;margin:0 0 22px}
.tabular-enriched .report-tabs a,.tabular-enriched .report-cta{display:inline-block;padding:11px 16px;border:2px solid #173f63;border-radius:8px;color:#173f63!important;background:#fff;font-size:1rem;font-weight:700;text-decoration:none;line-height:1.35}
.tabular-enriched .report-tabs a[aria-current=page],.tabular-enriched .report-cta.primary{background:#173f63;color:#fff!important}
.tabular-enriched a:focus-visible,.tabular-enriched summary:focus-visible{outline:3px solid #b95d35;outline-offset:4px}
.tabular-enriched .report-section{background:white;border:1px solid #dce6e8;border-radius:12px;padding:24px;margin:22px 0;scroll-margin-top:110px}
.tabular-enriched .report-section h2{margin:0 0 16px;color:#173f63;font-size:1.5rem}
.tabular-enriched .report-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:20px 0}
.tabular-enriched .report-card{padding:18px;background:#edf4f5;border-radius:10px;border-top:4px solid #247c85}
.tabular-enriched .card-number{display:block;font-size:1.8rem;font-weight:750;color:#173f63;line-height:1.2}
.tabular-enriched .card-label{display:block;color:#28474f;font-size:1rem;margin-top:8px}
.tabular-enriched .report-figure{margin:12px 0}.tabular-enriched .report-figure picture{display:block}.tabular-enriched .report-figure img{width:100%;height:auto}
.tabular-enriched figcaption,.tabular-enriched .chart-note{color:#354f58;font-size:.98rem;line-height:1.6}
.tabular-enriched .monitor-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:22px}
.tabular-enriched .monitor-grid .report-section{margin:0;min-width:0}
.tabular-enriched .priority-list{padding-left:22px}.tabular-enriched .priority-list li{padding:10px 0;line-height:1.7}
.tabular-enriched .report-disclosure{padding:16px;border:1px solid #dce6e8;border-radius:9px;margin:16px 0;background:#fafcfc}
.tabular-enriched .report-disclosure summary{cursor:pointer;font-weight:700;color:#173f63;font-size:1.05rem;padding:4px}
.tabular-enriched .coverage-inline{color:#354f58;font-size:1rem;line-height:1.6}
.tabular-enriched .story-lead{font-size:1.2rem;line-height:1.8;max-width:70ch}
.tabular-enriched .report-footer{padding:24px 0;border-top:2px solid #d9e5e8;margin-top:28px}
@media(max-width:800px){.tabular-enriched .monitor-grid{grid-template-columns:1fr}.tabular-enriched .report-hero,.tabular-enriched .report-section{padding:18px}.tabular-enriched .report-tabs a{flex:1 1 180px;text-align:center}}
</style>"""
