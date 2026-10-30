"""Preview trusted standalone Python online evaluators locally, without publishing."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_scores(scores: object) -> dict:
    if not isinstance(scores, dict) or not scores:
        raise ValueError("Expected a nonempty feedback mapping")
    for key, value in scores.items():
        if not isinstance(key, str) or not key:
            raise ValueError("Expected nonempty feedback keys")
        if type(value) not in (bool, int, float):
            raise ValueError("Expected boolean or numeric scores")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Expected finite scores")
    return scores


def preview(source: Path, runs_file: Path) -> dict:
    if source.resolve() == runs_file.resolve():
        raise ValueError("Source and samples must be separate files")
    code = source.read_bytes()
    samples = runs_file.read_bytes()
    runs = json.loads(samples)
    if not isinstance(runs, list) or not runs:
        raise ValueError("Expected a nonempty JSON array of run dictionaries")
    ids = []
    for run in runs:
        if (
            not isinstance(run, dict)
            or not isinstance(run.get("id"), str)
            or not run["id"]
        ):
            raise ValueError("Each run needs a nonempty string id")
        ids.append(run["id"])
    if len(set(ids)) != len(ids):
        raise ValueError("Run ids must be unique")
    namespace = {"__name__": "evaluator_preview", "__file__": str(source)}
    exec(compile(code, str(source), "exec"), namespace)
    evaluator = namespace.get("perform_eval")
    if not callable(evaluator):
        raise ValueError("Source must define perform_eval(run)")
    results = []
    for run, run_id in zip(runs, ids):
        try:
            scores = validate_scores(evaluator(run))
            results.append({"run_id": run_id, "scores": dict(scores)})
        except Exception as error:
            results.append({"run_id": run_id, "error_type": type(error).__name__})
    return {
        "mode": "local-code-preview-v1",
        "source_sha256": digest(code),
        "samples_sha256": digest(samples),
        "results": results,
        "failed": sum("error_type" in row for row in results),
    }


def verify(source: Path, runs_file: Path, report_file: Path) -> None:
    report = json.loads(report_file.read_bytes())
    if report.get("mode") != "local-code-preview-v1":
        raise ValueError("Unknown preview report format")
    if report.get("source_sha256") != digest(source.read_bytes()):
        raise ValueError("Source changed; rerun preview")
    if report.get("samples_sha256") != digest(runs_file.read_bytes()):
        raise ValueError("Samples changed; rerun preview")
    runs = json.loads(runs_file.read_bytes())
    results = report.get("results")
    if not isinstance(results, list) or not results or len(results) != len(runs):
        raise ValueError("Missing preview results")
    if report.get("failed") != 0 or any("error_type" in row for row in results):
        raise ValueError("Preview has failures; fix and rerun")
    if [row.get("run_id") for row in results] != [run["id"] for run in runs]:
        raise ValueError("Preview run ids do not match samples")
    for row in results:
        validate_scores(row.get("scores"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preview", "verify"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.resolve() in (args.source.resolve(), args.runs.resolve()):
        parser.error("Report must not overwrite source or samples")
    try:
        if args.action == "verify":
            verify(args.source, args.runs, args.report)
            print(
                "Preview matches source and samples; publication still requires review."
            )
            return 0
        args.report.unlink(missing_ok=True)
        report = preview(args.source, args.runs)
        args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(f"Previewed {len(report['results'])} runs; failures: {report['failed']}")
        return 1 if report["failed"] else 0
    except Exception as error:
        print(
            f"Preview blocked ({type(error).__name__}); inspect locally without sharing sensitive data."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
