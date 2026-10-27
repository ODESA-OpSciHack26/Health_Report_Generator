import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    from local_report import ROOT, run_request

    return ROOT, mo, run_request


@app.cell
def _(mo):
    audience = mo.ui.dropdown(
        options={
            "Researcher": "researcher",
            "Health institution": "health_institution",
            "Public": "public",
            "Public health expert": "public_health_expert",
        },
        value="Public",
        label="Audience",
    )
    start = mo.ui.dropdown(
        options={str(year): year for year in range(2021, 2026)},
        value="2021",
        label="First year",
    )
    end = mo.ui.dropdown(
        options={str(year): year for year in range(2021, 2026)},
        value="2025",
        label="Last year",
    )
    local_form = mo.ui.form(
        mo.md(
            "## Local health report\n\n"
            "No GitHub account, token, or Actions dispatch is used.\n\n"
            "{audience}\n\n{start}\n\n{end}\n\n"
            "National data: Switzerland and Liechtenstein. "
            "Reference and index baseline remain 2019. "
            "Reports describe notifications, not all infections; "
            "comparisons are descriptive, not causal or significance tests."
        ).batch(audience=audience, start=start, end=end),
        submit_button_label="Generate local report",
    )
    local_form
    return (local_form,)


@app.cell
def _(ROOT, local_form, mo, run_request):
    if local_form.value is None:
        result = mo.md("Choose the audience and years, then generate a report.")
    else:
        try:
            values = local_form.value
            response = run_request(
                values["audience"], values["start"], values["end"]
            )
            folder = response["output"].relative_to(ROOT)
            result = mo.callout(
                mo.md(
                    f"Report ready — cache {response['status']}.\n\n"
                    f"Cache key: `{response['cache_key']}`\n\n"
                    f"Open `{folder}/report.html` from your local filesystem. "
                    "Keep the complete report folder together. "
                    "Review its methods, limitations, and provenance."
                ),
                kind="success",
            )
        except (ValueError, RuntimeError) as error:
            result = mo.callout(mo.md(str(error)), kind="danger")
        except Exception:
            result = mo.callout(
                mo.md(
                    "Unexpected local execution error. Inspect the latest "
                    "run under results/local-ui/runs/ and the terminal. "
                    "No successful result is claimed."
                ),
                kind="danger",
            )
    result
    return


if __name__ == "__main__":
    app.run()
