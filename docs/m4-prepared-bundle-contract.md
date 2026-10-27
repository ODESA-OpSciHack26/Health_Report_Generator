# Verified prepared tabular bundles

This opt-in module does not change the default workflow, rendering or UI.

## Operations

- `publish_prepared_bundle(prepared, destination)` independently replays
  preparation, checks mutable rows/provenance, stages artifacts, verifies the
  stage, then publishes without replacing an existing destination.
- `verify_prepared_bundle(destination)` reads artifacts, validates the exact
  manifest/file set and hashes, and independently reproduces preparation.
  It returns a PreparedTable without writing any files.

## Layout and serialization

Exactly four regular, non-symlink files: source.csv OR source.tsv, table.json,
provenance.json and manifest.json. Artifact paths are fixed, not supplied by
manifest traversal strings. JSON uses sorted keys, compact separators, UTF-8,
a trailing newline and no NaN/Infinity. Duplicate JSON keys are rejected.
Rows retain source order. Explicit column types distinguish category text,
numeric measures, timezone-naive ISO dates and nulls. Numeric precision still
follows pandas; exact decimal arithmetic is not promised.

The manifest hashes all three artifacts but not itself. It is not signed.
Verification rejects rehashed rows or substantive provenance that disagree
with the source and parameters. Preparation timestamps are checked for UTC
syntax but excluded from replay equality. A historical timestamp's truth is
not established. Verification requires matching preparation code files and
Python/pandas versions; upgrading them may require an explicit migration.

## Publication boundary

The destination parent must already exist and be trusted. Symlink paths and
parent traversal are rejected. Publication uses Linux renameat2 with
RENAME_NOREPLACE; unsupported kernels/filesystems fail without a fallback
that could replace a concurrent destination. Handled exceptions, including
KeyboardInterrupt during staging, clean up the stage. Abrupt termination such
as SIGKILL may leave a hidden staging directory, but not a partially published
success destination. Namespace atomicity is not a power-loss durability
promise. Hostile concurrent filesystem mutation is outside this contract.

## Trust and acceptance limits

An internally consistent replacement source+bundle cannot be distinguished
from the originally intended dataset without an external trusted identity.
Mutable returned objects are not automatically reverified. No upload-size,
security, browser, offline, accessibility or full release acceptance is claimed.
The existing scientific report pipeline and its release gates remain unchanged.
