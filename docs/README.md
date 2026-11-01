# User documentation

This software generates audience-specific health reports and provides an
experimental local CSV report composer. Use the instructions for the route you
intend to run; the canonical health pipeline, supplied-table CLI and optional
GitHub-backed interface are separate entry points.

## Install and generate a first report

- [Installation and setup](../GETTING_STARTED.md)
- [Reproduce and verify reports](reproduction.md)
- [Audience-specific reports](audiences.md)

## Work with data

- [Data sources, attribution and terms](../data/README.md)
- [Supplied-table CLI](m4-tabular-reproduction.md)
- [Descriptive tables and charts](m4-tabular-descriptive-visuals.md)
- [Retired local reporting form](local-interface.md)
- [Local CSV and health-report composer](composer.md)

The local reporting form and optional GitHub-backed interface are not the
experimental composer. See the composer guide for its separate entry point,
access credential, runtime requirements and input-path limitations.

## Understand results and limitations

- [Methods and scientific policy](scientific-policy.md)
- [Known limitations](limitations.md)
- [Canonical health-pipeline architecture](architecture.md)
- [Software environments and dependency locks](dependency-ownership.md)

Canonical health reports and generic CSV reports have different capabilities.
Do not assume generic PDF/app support or universal spreadsheet compatibility.
The CSV structural preview is limited to the first 100 rows and 20 columns;
scrolling does not reveal additional records or columns.

## Retired GitHub-backed interface

- [Connector setup](../CONNECTOR_SETUP.md)

The connector UI is retired from this product tree. Its documentation link
is retained as a retirement notice. GitHub credentials are not required for
the standard local canonical reporting workflow.

## Contribute and cite

- [Contributor guidance](../CONTRIBUTING.md)
- [Software licence](../LICENSE)
- [Citation information](../CITATION.cff)

Development plans and historical acceptance records are not user instructions.
Their presence does not establish that a proposed feature is implemented.
