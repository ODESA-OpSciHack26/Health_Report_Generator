# Shared-source tabular HTML renderer

This is opt-in: no default workflow, UI or dependency change.

Run `python scripts/health_pipeline/tabular_render.py --bundle INPUT --output OUTPUT`.
The output parent must exist. An existing output is never replaced. All three
canonical audience IDs render from report_shared.qmd, using presentation
profiles selected from the existing stakeholder configurations. Disease-specific
analytic settings/titles are not applied to reader-supplied tables.

The shared QMD defaults to canonical input. Its tabular branch is HTML only;
canonical HTML/PDF/Shiny behavior remains available. Canonical packaging also
ships the tabular presentation helper and records it as a source dependency.
No additional QMD is introduced. Report and methods views use parameters.

## Verification and publication

The input bundle is verified before any rendering tools run. A private verified
copy, reconstructed from captured bytes, is consumed by all audiences. Its
manifest, table and preparation-provenance hashes identify the consumed copy.
The original input manifest's raw formatting is not preserved or attested.
After all six HTML documents complete, output hashes, exact artifact paths,
reproduced input preparation, effective audience parameters and embedded/sidecar
provenance agreement are checked before no-replace publication.

The report verifier is not independent rerendering, a browser test or external
source authentication. Rehashing a wholly replaced internally consistent report
is not prevented without an external trust anchor. It validates current code
files and preparation runtime; recorded Quarto/R version strings are not an
independent attestation of the historical render environment.

## Communication contract

Every audience receives all observations in original data-record order, with
missing values visible and filter/sort interactivity. Missingness counts come
from preparation provenance, not presentation recalculation. No cross-category sums, rates, disease classifications, alert thresholds or inferred
geographies are introduced. The descriptive extension records within-category row
statistics and explicitly requested reference comparisons in analysis.json. Public wording is plain language; institutional
wording cautions against operational inference; technical views include mapping
and reproduction detail. Row filtering/sorting changes the view, not saved data.

Input strings are escaped in tables. Units, scientific validity, representative
sampling, uncertainty intervals and clinical recommendations are not inferred.
The bundle includes original source bytes: this is not a privacy-reviewed upload
or public-disclosure endpoint. Publication assumes a trusted parent directory,
Linux no-replace rename support and no hostile concurrent filesystem mutation.

## Gates

Unit tests mock Quarto; they do not establish real rendering. Run real snapshot
and annual-ISO synthetic fixtures for all three audiences, verify those reports,
and rerun canonical output/release checks and smoke tests after the source change.
Preserve the earlier canonical baseline rather than overwriting it.

The descriptive extension and its explicit calculation policy are documented in [descriptive visuals](m4-tabular-descriptive-visuals.md).
