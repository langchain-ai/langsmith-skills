"""Exercise local preview and artifact verification without LangSmith credentials."""

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "config/skills/langsmith-online-eval-engineering/scripts/preview_code_evaluator.py"
)
SPEC = importlib.util.spec_from_file_location("preview_code_evaluator", SCRIPT)
preview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preview)


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "evaluator.py"
        self.source.write_text(
            'def perform_eval(run):\n    return {"has_answer": bool((run.get("outputs") or {}).get("answer"))}\n'
        )
        self.runs = self.root / "runs.json"
        self.runs.write_text(
            json.dumps(
                [
                    {"id": "good", "outputs": {"answer": "private answer"}},
                    {"id": "missing", "outputs": {}},
                    {"id": "errored", "error": "private error", "outputs": None},
                ]
            )
        )
        self.report = self.root / "preview.json"

    def save_preview(self):
        report = preview.preview(self.source, self.runs)
        self.report.write_text(json.dumps(report))
        return report

    def cli(self, action, report=None):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                action,
                "--source",
                str(self.source),
                "--runs",
                str(self.runs),
                "--report",
                str(report or self.report),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def test_scores_and_hashes_without_payloads(self):
        report = self.save_preview()
        self.assertEqual(report["failed"], 0)
        self.assertEqual(
            [row["scores"]["has_answer"] for row in report["results"]],
            [True, False, False],
        )
        self.assertEqual(
            report["source_sha256"],
            hashlib.sha256(self.source.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["samples_sha256"], hashlib.sha256(self.runs.read_bytes()).hexdigest()
        )
        self.assertNotIn("private", self.report.read_text())
        preview.verify(self.source, self.runs, self.report)

    def test_runtime_errors_are_redacted_and_block_verification(self):
        self.source.write_text(
            'def perform_eval(run):\n    raise RuntimeError("private token")\n'
        )
        report = self.save_preview()
        self.assertEqual(report["failed"], 3)
        self.assertEqual(report["results"][0]["error_type"], "RuntimeError")
        self.assertNotIn("private token", self.report.read_text())
        with self.assertRaisesRegex(ValueError, "failures"):
            preview.verify(self.source, self.runs, self.report)

    def test_source_drift_blocks_verification(self):
        self.save_preview()
        self.source.write_text(self.source.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "Source changed"):
            preview.verify(self.source, self.runs, self.report)

    def test_sample_drift_blocks_verification(self):
        self.save_preview()
        self.runs.write_text(self.runs.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "Samples changed"):
            preview.verify(self.source, self.runs, self.report)

    def test_invalid_scores(self):
        for scores in (
            {},
            [],
            {"": 1},
            {"score": "yes"},
            {"score": None},
            {"score": float("nan")},
            {"score": float("inf")},
            {"score": {"value": 1}},
        ):
            with self.subTest(scores=scores), self.assertRaises(ValueError):
                preview.validate_scores(scores)
        self.assertEqual(
            preview.validate_scores({"a": 0.5, "b": 1, "c": False}),
            {"a": 0.5, "b": 1, "c": False},
        )

    def test_invalid_samples_are_rejected(self):
        for runs in (
            [],
            {},
            [None],
            [{"outputs": {}}],
            [{"id": 1}],
            [{"id": "same"}, {"id": "same"}],
        ):
            with self.subTest(runs=runs):
                self.runs.write_text(json.dumps(runs))
                with self.assertRaises(ValueError):
                    preview.preview(self.source, self.runs)

    def test_missing_function_is_rejected(self):
        self.source.write_text("value = 1\n")
        with self.assertRaisesRegex(ValueError, "perform_eval"):
            preview.preview(self.source, self.runs)

    def test_incomplete_or_mismatched_results_block_verification(self):
        report = self.save_preview()
        for results in (
            [],
            report["results"][:-1],
            [{"run_id": "wrong", "scores": {"score": 1}} for _ in range(3)],
        ):
            with self.subTest(results=results):
                self.report.write_text(json.dumps({**report, "results": results}))
                with self.assertRaises(ValueError):
                    preview.verify(self.source, self.runs, self.report)

    def test_cli_preview_and_verify(self):
        self.assertEqual(self.cli("preview").returncode, 0)
        self.assertEqual(self.cli("verify").returncode, 0)
        self.assertIn("publication still requires review", self.cli("verify").stdout)

    def test_cli_failure_returns_nonzero_without_exception_message(self):
        self.source.write_text(
            'def perform_eval(run):\n    raise ValueError("private token")\n'
        )
        result = self.cli("preview")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(
            "private token", result.stdout + result.stderr + self.report.read_text()
        )
        self.assertEqual(self.cli("verify").returncode, 1)

    def test_cli_rejects_overwriting_source_or_samples(self):
        for path in (self.source, self.runs):
            original = path.read_bytes()
            self.assertNotEqual(self.cli("preview", report=path).returncode, 0)
            self.assertEqual(path.read_bytes(), original)

    def test_source_load_failure_removes_stale_report(self):
        self.save_preview()
        self.source.write_text('raise ValueError("private token")\n')
        result = self.cli("preview")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("private token", result.stdout + result.stderr)
        self.assertFalse(self.report.exists())


if __name__ == "__main__":
    unittest.main()
