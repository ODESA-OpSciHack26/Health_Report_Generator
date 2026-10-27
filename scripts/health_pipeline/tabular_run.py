"""One-command opt-in preparation, bundle publication and shared HTML rendering."""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path

import tabular_bundle as bundles
from tabular_prepare import _parameters, prepare_payload
from tabular_render import render_tabular_reports, verify_tabular_reports

REQUEST_SCHEMA = "health-report/tabular-request/1"


def load_request(path):
    request = bundles._json_load(Path(path).read_bytes())
    expected = {"schema", "source_sha256", "mapping", "mode", "period"}
    if not isinstance(request, dict) or set(request) != expected:
        raise ValueError("Request has missing or unexpected fields.")
    if request["schema"] != REQUEST_SCHEMA:
        raise ValueError("Unsupported request schema.")
    digest = request["source_sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Request requires a lowercase SHA-256 source identity.")
    _parameters(request["mapping"], request["mode"], request["period"])
    return request


def run_tabular(source, request, destination, *, quarto="quarto"):
    """Publish one complete three-audience result, without replacing outputs.

    A missing output parent is created only after request/input validation.
    Failure may leave that parent but never a partially successful destination.
    """
    request = load_request(request)
    destination = bundles._safe_path(destination)
    if not destination.name:
        raise ValueError("A named output destination is required.")
    if os.path.lexists(destination):
        raise FileExistsError(str(destination))
    source = Path(source)
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != request["source_sha256"]:
        raise ValueError("Source bytes differ from the checksum-pinned request.")
    prepared = prepare_payload(payload, source_filename=source.name,
        mapping=request["mapping"], mode=request["mode"], period=request["period"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=f".{destination.name}.run-", dir=destination.parent))
    try:
        bundle = bundles.publish_prepared_bundle(prepared, scratch / "input-bundle")
        reports = render_tabular_reports(bundle, scratch / "reports", quarto=quarto)
        verify_tabular_reports(reports)
        bundles._rename_no_replace(reports, destination)
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    build = commands.add_parser("build", help="Prepare and render three audiences")
    build.add_argument("--input", required=True)
    build.add_argument("--request", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--quarto", default="quarto")
    verify = commands.add_parser("verify", help="Verify an existing report set")
    verify.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "build":
            run_tabular(args.input, args.request, args.output, quarto=args.quarto)
            print("Prepared and verified HTML reports published for all three audiences.")
        else:
            verify_tabular_reports(args.output)
            print("Report artifacts, preparation and embedded provenance verified.")
    except (ValueError, OSError, NotImplementedError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
