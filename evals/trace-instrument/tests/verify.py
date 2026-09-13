#!/usr/bin/env python3
"""Score the trace-instrument task from observed LangSmith state.

Every check reads live API state. Nothing here greps application source: an
import that survives a commented-out call would satisfy a regex while producing
no trace at all.

Checks score trace SHAPE, never run names. Names are an authoring choice the
instruction does not constrain -- tracing `main()` or passing
`@traceable(name=...)` is good instrumentation that a name match would fail.
Names are reported as stats so drift stays visible without gating reward.

Ingestion is asynchronous, and child runs land after their root, so each check
polls until the structure it needs appears or a shared deadline expires.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

from langsmith import Client

UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
WORKSPACE = Path("/workspace")
RESULTS = Path(os.environ.get("VERIFIER_RESULTS", "/logs/verifier/_test_results.json"))
CLI_VERSION_FILE = Path("/opt/langsmith-cli-version.txt")
BUDGET_SEC = float(os.environ.get("VERIFIER_BUDGET_SEC", "110"))
POLL_SEC = 5.0
# Conventional names from the reference solution. Stats only -- never scored.
PLAIN_ROOT = "rag_pipeline"
PLAIN_CHILDREN = ("retrieve_docs", "generate_answer")
CHAIN_TOOL = "get_track_count"
# plain_app has two internal steps around its one LLM call; both must surface.
PLAIN_MIN_STEPS = 2


class Scorer:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.stats: dict[str, object] = {}
        self.deadline = time.monotonic() + BUDGET_SEC

    def record(self, check: str, ok: bool, detail: str) -> bool:
        (self.passed if ok else self.failed).append(f"{check}: {detail}")
        return ok

    def time_left(self) -> float:
        return self.deadline - time.monotonic()

    def write(self) -> int:
        payload = {"passed": self.passed, "failed": self.failed, "stats": self.stats}
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        RESULTS.write_text(json.dumps(payload, indent=2))
        print(json.dumps(payload, indent=2))
        return 1 if self.failed else 0


def read_trace_id(name: str) -> str | None:
    path = WORKSPACE / name
    if not path.is_file():
        return None
    match = UUID_RE.search(path.read_text())
    return match.group(0) if match else None


def poll(scorer: Scorer, fetch, ready) -> object:
    """Re-fetch until ready(value) or the shared budget runs out."""
    value = None
    while True:
        try:
            value = fetch()
        except Exception as exc:  # noqa: BLE001 - transient API errors are expected
            scorer.stats.setdefault("api_errors", []).append(str(exc))  # type: ignore[union-attr]
            value = value if value is not None else []
        if ready(value) or scorer.time_left() <= 0:
            return value
        time.sleep(min(POLL_SEC, max(scorer.time_left(), 0.1)))


def split(runs: list) -> tuple[object | None, list]:
    root = next((r for r in runs if r.parent_run_id is None), None)
    return root, [r for r in runs if r.parent_run_id is not None]


def steps_below_root(runs: list) -> list:
    """Descendant runs that represent application steps rather than LLM calls.

    `@traceable` defaults to run_type "chain"; an agent that types a step as
    "tool" or "retriever" instead is instrumenting better, not worse, so
    anything non-llm counts.
    """
    _, descendants = split(runs)
    return [r for r in descendants if r.run_type != "llm"]


def has_nested_llm(runs: list) -> bool:
    _, descendants = split(runs)
    return any(r.run_type == "llm" for r in descendants)


def rooted(runs: list) -> bool:
    """A trace tree whose root is the application, not the raw LLM call."""
    root, _ = split(runs)
    return root is not None and root.run_type != "llm"


def chain_ready(runs: list) -> bool:
    """Tracing is on and the LLM call sits inside the trace.

    chain_app is fixed with env vars alone, so this is the whole of the
    chain-side task. Whether the ReAct loop reaches for its tool is the model's
    call, not the agent's, and is deliberately not scored.
    """
    return rooted(runs) and has_nested_llm(runs)


def plain_ready(runs: list) -> bool:
    """The pipeline's steps are visible as their own spans, LLM call nested."""
    return (
        rooted(runs)
        and has_nested_llm(runs)
        and len(steps_below_root(runs)) >= PLAIN_MIN_STEPS
    )


def describe(runs: list) -> str:
    """Shape summary. The CI artifact excludes agent/**, so this line is the
    only forensic evidence a CI failure leaves behind."""
    root, _ = split(runs)
    return (
        f"root_type={getattr(root, 'run_type', None)} "
        f"nested_llm={has_nested_llm(runs)} "
        f"step_count={len(steps_below_root(runs))} "
        f"({len(runs)} runs in trace)"
    )


def main() -> int:
    scorer = Scorer()
    project = os.environ.get("LANGSMITH_PROJECT", "")
    if not project:
        scorer.record("setup", False, "LANGSMITH_PROJECT is unset in the verifier environment")
        return scorer.write()

    scorer.stats["project"] = project
    if CLI_VERSION_FILE.is_file():
        scorer.stats["langsmith_cli_version"] = CLI_VERSION_FILE.read_text().strip()

    client = Client()
    chain_id = read_trace_id("chain_trace.txt")
    plain_id = read_trace_id("plain_trace.txt")

    if not scorer.record(
        "C1_ids_written",
        bool(chain_id and plain_id),
        f"chain={chain_id or 'missing'} plain={plain_id or 'missing'}",
    ):
        for check in ("C2_runs_live", "C3_chain_traced", "C4_plain_hierarchy", "C5_apps_worked"):
            scorer.record(check, False, "skipped, trace IDs were not written")
        return scorer.write()

    wanted = {chain_id, plain_id}
    roots = poll(
        scorer,
        lambda: {str(r.id) for r in client.list_runs(project_name=project, is_root=True)},
        lambda seen: wanted <= seen,
    )
    scorer.stats["root_runs_in_project"] = len(roots)
    live_ok = scorer.record(
        "C2_runs_live",
        wanted <= roots,
        f"{len(wanted & roots)}/2 reported IDs are root runs in {project}",
    )

    def runs_for(trace_id: str, ready) -> list:
        return poll(
            scorer,
            lambda: list(client.list_runs(project_name=project, trace_id=trace_id)),
            ready,
        )

    chain_runs = runs_for(chain_id, chain_ready) if live_ok else []
    plain_runs = runs_for(plain_id, plain_ready) if live_ok else []

    chain_names = {r.name for r in chain_runs}
    scorer.stats["chain_run_names"] = sorted(chain_names)
    scorer.stats["chain_tool_run"] = "tool" in {r.run_type for r in chain_runs}
    scorer.stats["chain_tool_named"] = CHAIN_TOOL in chain_names
    scorer.record("C3_chain_traced", chain_ready(chain_runs), describe(chain_runs))

    plain_root, _ = split(plain_runs)
    plain_names = {r.name for r in plain_runs}
    plain_root_name = getattr(plain_root, "name", None)
    scorer.stats["plain_run_names"] = sorted(plain_names)
    scorer.stats["plain_root_name"] = plain_root_name
    scorer.stats["plain_step_count"] = len(steps_below_root(plain_runs))
    scorer.stats["plain_names_conventional"] = plain_root_name == PLAIN_ROOT and all(
        c in plain_names for c in PLAIN_CHILDREN
    )
    scorer.record("C4_plain_hierarchy", plain_ready(plain_runs), describe(plain_runs))

    chain_root, _ = split(chain_runs)
    empty = [
        label
        for label, run in (("chain", chain_root), ("plain", plain_root))
        if run is None or not run.outputs
    ]
    scorer.record("C5_apps_worked", not empty, f"roots with empty outputs: {empty or 'none'}")

    return scorer.write()


if __name__ == "__main__":
    sys.exit(main())
