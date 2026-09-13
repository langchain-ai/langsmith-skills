#!/usr/bin/env python3
"""Score the offline-eval-setup task from observed LangSmith state.

Pass iff the shipped test cases exist as a LangSmith dataset, an experiment
scored the app against every one of them, the scores discriminate the case the
app actually gets wrong, and results.json agrees with live state.

Nothing here asserts a scoring metric, an evaluator name, or a mechanism. The
agent chooses those, so requiring any of them would score a hidden preference.
Instead the fixture is shaped so that any sensible metric must rank the cases
the same way, and C5 checks only that ordering.

results.json is written by the evaluated agent: it is untrusted input, parsed
defensively and only ever compared numerically against live state.

Ingestion is asynchronous and feedback lands after its run, so every check
polls for the structure it needs until a shared deadline expires.
"""

import json
import os
import sys
import time
from pathlib import Path

from langsmith import Client

WORKSPACE = Path("/workspace")
FIXTURES = Path("/tests/fixtures")
RESULTS = Path(os.environ.get("VERIFIER_RESULTS", "/logs/verifier/_test_results.json"))
INVALID = Path(os.environ.get("VERIFIER_INVALID", "/logs/verifier/invalid.txt"))
CLI_VERSION_FILE = Path("/opt/langsmith-cli-version.txt")
BUDGET_SEC = float(os.environ.get("VERIFIER_BUDGET_SEC", "300"))
POLL_SEC = 5.0
CHECKS = (
    "C1_dataset_loaded",
    "C2_experiment_linked",
    "C3_all_cases_scored",
    "C4_app_driven_correctly",
    "C5_scores_discriminate",
    "C6_results_readback",
)
INFRA_MARKERS = ("connection", "auth", "unauthorized", "forbidden", "timeout", "503", "502", "500")


class Invalid(Exception):
    """Evidence is unobtainable: an infrastructure fault, not agent failure."""


class Scorer:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.stats: dict[str, object] = {}
        self.deadline = time.monotonic() + BUDGET_SEC

    def record(self, check: str, ok: bool, detail: str) -> bool:
        (self.passed if ok else self.failed).append(f"{check}: {detail}")
        return ok

    def skip_rest(self, after: str, why: str) -> None:
        for check in CHECKS[CHECKS.index(after) + 1 :]:
            self.record(check, False, f"skipped, {why}")

    def time_left(self) -> float:
        return self.deadline - time.monotonic()

    def note_error(self, exc: Exception) -> None:
        msg = f"{type(exc).__name__}: {exc}"
        self.stats.setdefault("api_errors", []).append(msg[:300])  # type: ignore[union-attr]
        if any(m in msg.lower() for m in INFRA_MARKERS):
            raise Invalid(msg[:300])

    def write(self) -> int:
        payload = {"passed": self.passed, "failed": self.failed, "stats": self.stats}
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        RESULTS.write_text(json.dumps(payload, indent=2))
        print(json.dumps(payload, indent=2))
        return 1 if self.failed else 0


def poll(scorer: Scorer, fetch, ready):
    value = None
    while True:
        try:
            value = fetch()
        except Invalid:
            raise
        except Exception as exc:  # noqa: BLE001 - transient API errors are expected
            scorer.note_error(exc)
            value = value if value is not None else []
        if ready(value) or scorer.time_left() <= 0:
            return value
        time.sleep(min(POLL_SEC, max(scorer.time_left(), 0.1)))


def load_cases() -> list[dict]:
    cases = json.loads((FIXTURES / "test_cases.json").read_text())
    return [
        {
            "topic": c["inputs"]["policy_topic"],
            "expected": c["outputs"]["expected_answer"],
        }
        for c in cases
    ]


def contains_value(blob: object, needle: str) -> bool:
    """Is `needle` present anywhere in this structure's values?"""
    return needle.lower() in json.dumps(blob, default=str).lower()


def numbers_in(blob: object) -> list[float]:
    found: list[float] = []

    def walk(node: object) -> None:
        if isinstance(node, bool):
            found.append(1.0 if node else 0.0)
        elif isinstance(node, (int, float)):
            found.append(float(node))
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(blob)
    return found


def main() -> int:
    scorer = Scorer()
    cases = load_cases()
    scorer.stats["expected_case_count"] = len(cases)
    if CLI_VERSION_FILE.is_file():
        scorer.stats["langsmith_cli_version"] = CLI_VERSION_FILE.read_text().strip()

    ds_name = os.environ.get("LANGSMITH_DATASET", "")
    if not ds_name:
        raise Invalid("LANGSMITH_DATASET is unset in the verifier environment")
    scorer.stats["dataset_name"] = ds_name

    client = Client()

    # --- C1: the shipped cases are in a dataset -----------------------------
    # Match on topic VALUES, not key names: the agent may legitimately rename
    # keys while uploading, and a user only cares that the right cases landed.
    def fetch_examples():
        ds = client.read_dataset(dataset_name=ds_name)
        return (ds, list(client.list_examples(dataset_id=ds.id)))

    found = poll(
        scorer,
        fetch_examples,
        lambda v: bool(v) and len(v[1]) >= len(cases),
    )
    if not found:
        scorer.record("C1_dataset_loaded", False, f"no dataset named {ds_name}")
        scorer.skip_rest("C1_dataset_loaded", "the dataset was never created")
        return scorer.write()

    dataset, examples = found
    present = [c["topic"] for c in cases if any(contains_value(e.inputs, c["topic"]) for e in examples)]
    missing = [c["topic"] for c in cases if c["topic"] not in present]
    scorer.stats["dataset_example_count"] = len(examples)
    if not scorer.record(
        "C1_dataset_loaded",
        len(examples) == len(cases) and not missing,
        f"{len(examples)} examples, missing_topics={missing or 'none'}",
    ):
        scorer.skip_rest("C1_dataset_loaded", "the dataset is incomplete")
        return scorer.write()

    # --- C2: an experiment ran against that dataset -------------------------
    experiments = poll(
        scorer,
        lambda: list(client.list_projects(reference_dataset_id=dataset.id)),
        lambda v: bool(v),
    )
    scorer.stats["experiment_count"] = len(experiments)
    scorer.stats["experiment_names"] = sorted(p.name for p in experiments)
    if not scorer.record(
        "C2_experiment_linked",
        bool(experiments),
        f"{len(experiments)} experiment(s) reference {ds_name}",
    ):
        scorer.skip_rest("C2_experiment_linked", "no experiment referenced the dataset")
        return scorer.write()

    # --- C3: every case ran and was scored ----------------------------------
    def fetch_scored():
        runs, feedback = [], {}
        for exp in experiments:
            rs = [r for r in client.list_runs(project_id=exp.id, is_root=True)]
            runs.extend(rs)
            if rs:
                for fb in client.list_feedback(run_ids=[r.id for r in rs]):
                    feedback.setdefault(str(fb.run_id), []).append(fb)
        return (runs, feedback)

    scored = poll(
        scorer,
        fetch_scored,
        lambda v: bool(v)
        and len(v[0]) >= len(cases)
        and all(str(r.id) in v[1] for r in v[0]),
    )
    # poll() yields [] if every fetch raised, so never unpack it blindly.
    runs, feedback = scored if scored else ([], {})
    errored = [r.name for r in runs if getattr(r, "error", None)]
    unscored = [str(r.id)[:8] for r in runs if str(r.id) not in feedback]
    scorer.stats["experiment_run_count"] = len(runs)
    scorer.stats["scored_run_count"] = len(runs) - len(unscored)
    keys = sorted({fb.key for fbs in feedback.values() for fb in fbs})
    scorer.stats["feedback_keys"] = keys
    # Which mechanism did the agent use? Feedback alone cannot answer this:
    # a local evaluator scores during evaluate(), while one bound to the dataset
    # runs server-side and lands much later (61s observed), so a poll that stops
    # at "every run is scored" never sees it. Ask for the bound rules directly
    # instead of waiting. Stat only -- reward must never depend on the
    # mechanism, and a schema change here must not break the run.
    try:
        rules = client.request_with_retries(
            "GET", "/runs/rules", params={"limit": 100}
        ).json()
        bound = [
            r.get("display_name")
            for r in rules
            if str(r.get("dataset_id") or "") == str(dataset.id)
        ]
        scorer.stats["dataset_bound_evaluators"] = sorted(n for n in bound if n)
        scorer.stats["evaluator_mechanism"] = (
            "both" if bound and keys else "uploaded" if bound else "local" if keys else "none"
        )
    except Exception as exc:  # noqa: BLE001 - a stat must never fail the run
        scorer.stats["dataset_bound_evaluators"] = f"unavailable: {type(exc).__name__}"
    # Deliberately NOT treated as an infrastructure fault. Partial feedback at
    # the deadline is ambiguous between slow ingestion and an agent that only
    # scored some cases -- and calling it invalid would mean this task could
    # never fail on partial scoring, which is the worse error for a regression
    # harness. Infra faults are identified by their exception type in
    # Scorer.note_error, never inferred from timing. Budget exhaustion is
    # recorded so a human triaging a zero can see it.
    scorer.stats["budget_exhausted"] = scorer.time_left() <= 0
    if not scorer.record(
        "C3_all_cases_scored",
        len(runs) == len(cases) and not errored and not unscored,
        f"{len(runs)}/{len(cases)} runs, errored={errored or 'none'}, unscored={unscored or 'none'}",
    ):
        scorer.skip_rest("C3_all_cases_scored", "not every case produced a scored run")
        return scorer.write()

    # --- C4: the app was actually driven, and still gets warranty wrong -----
    by_topic: dict[str, dict] = {}
    for run in runs:
        topic = next(
            (c["topic"] for c in cases if contains_value(run.inputs, c["topic"])),
            None,
        )
        if topic is None:
            continue
        expected = next(c["expected"] for c in cases if c["topic"] == topic)
        by_topic[topic] = {
            "run": run,
            "matches": contains_value(run.outputs, expected),
            "scores": [fb.score for fb in feedback.get(str(run.id), []) if fb.score is not None],
            "by_key": {
                fb.key: fb.score
                for fb in feedback.get(str(run.id), [])
                if fb.score is not None
            },
        }

    unmapped = [c["topic"] for c in cases if c["topic"] not in by_topic]
    matching = [t for t, v in by_topic.items() if v["matches"]]
    mismatching = [t for t, v in by_topic.items() if not v["matches"]]
    scorer.stats["matching_topics"] = sorted(matching)
    scorer.stats["mismatching_topics"] = sorted(mismatching)
    if not scorer.record(
        "C4_app_driven_correctly",
        not unmapped and len(mismatching) == 1 and len(matching) == len(cases) - 1,
        f"matched={sorted(matching)} mismatched={sorted(mismatching)} "
        f"unmapped={unmapped or 'none'} (expected exactly 1 mismatch)",
    ):
        scorer.skip_rest("C4_app_driven_correctly", "the app was not driven as shipped")
        return scorer.write()

    # --- C5: some metric ranks the failing case lowest ----------------------
    bad = mismatching[0]
    bad_scores = by_topic[bad]["by_key"]
    discriminating = [
        key
        for key, bad_score in bad_scores.items()
        if all(
            key in by_topic[t]["by_key"] and by_topic[t]["by_key"][key] > bad_score
            for t in matching
        )
    ]
    scorer.stats["discriminating_keys"] = discriminating
    scorer.stats["scores_by_topic"] = {t: v["by_key"] for t, v in by_topic.items()}
    if not scorer.record(
        "C5_scores_discriminate",
        bool(discriminating),
        f"'{bad}' is the case the app gets wrong; "
        f"keys ranking it below {sorted(matching)}: {discriminating or 'none'}",
    ):
        scorer.skip_rest("C5_scores_discriminate", "no metric separated the failing case")
        return scorer.write()

    # --- C6: results.json is a true readback of live state ------------------
    path = WORKSPACE / "results.json"
    if not path.is_file():
        scorer.record("C6_results_readback", False, "results.json missing")
        return scorer.write()
    try:
        reported = json.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001 - agent-authored, may be malformed
        scorer.record("C6_results_readback", False, f"results.json unparseable: {type(exc).__name__}")
        return scorer.write()

    # Accept a bare list, or a dict wrapping one under any key.
    entries: list = reported if isinstance(reported, list) else []
    if isinstance(reported, dict):
        entries = next(
            (v for v in reported.values() if isinstance(v, list)), []
        )
    key = discriminating[0]
    wrong: list[str] = []
    for topic, info in by_topic.items():
        live = info["by_key"][key]
        hit = next((e for e in entries if contains_value(e, topic)), None)
        if hit is None:
            wrong.append(f"{topic}: absent")
            continue
        if not any(abs(n - live) < 1e-6 for n in numbers_in(hit)):
            wrong.append(f"{topic}: no value equal to live {live}")
    scorer.stats["reported_entry_count"] = len(entries)
    scorer.record(
        "C6_results_readback",
        not wrong and len(entries) >= len(cases),
        f"compared against live '{key}'; mismatches={wrong or 'none'}",
    )
    return scorer.write()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Invalid as exc:
        INVALID.parent.mkdir(parents=True, exist_ok=True)
        INVALID.write_text(str(exc))
        print(f"INVALID RUN: {exc}", file=sys.stderr)
        sys.exit(2)
