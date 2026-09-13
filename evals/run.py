#!/usr/bin/env python3
"""Run the langsmith-skills Harbor evals and report a regression verdict.

Harbor is the only eval mechanism here: this script seeds nothing, judges
nothing, and runs no tests of its own. It allocates a per-trial LangSmith
project, invokes `harbor run`, reads the reward Harbor recorded, checks whether
the skill under test was actually invoked, and cleans up.

    uv run --project evals python evals/run.py
    uv run --project evals python evals/run.py --reps 3 --fresh-env
    uv run --project evals python evals/run.py --no-skills   # control

Exit codes: 0 clean | 1 reward regression | 2 skill never invoked
            3 infrastructure error | 4 usage error
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
import uuid
from pathlib import Path

from dotenv import load_dotenv

EVALS_DIR = Path(__file__).resolve().parent
REPO_DIR = EVALS_DIR.parent
ENV_FILE = EVALS_DIR / ".env"
DEFAULT_JOBS_DIR = EVALS_DIR / "jobs"
DEFAULT_SKILLS = REPO_DIR / "config" / "skills"
SKILL_PATH_MARKER = "/skills/"

EXIT_OK, EXIT_REWARD, EXIT_GATE, EXIT_INFRA, EXIT_USAGE = 0, 1, 2, 3, 4

sys.path.insert(0, str(EVALS_DIR))
from langsmith_env import cleanup, project_name, sweep_orphans  # noqa: E402


def load_env_file(path: Path) -> None:
    """Load .env into os.environ; the harbor subprocess inherits it.

    Uses python-dotenv so ${VAR} references expand exactly as they do under
    harbor's own --env-file handling. A hand-rolled parser would forward the
    literal "${LANGSMITH_API_KEY}" into the container and the gateway 403s.
    """
    if not path.exists():
        return
    load_dotenv(path, override=True)


def resolve_task(name: str) -> Path:
    """Resolve a task name against the evals directory, rejecting traversal."""
    if "/" in name or "\\" in name or name in (".", ".."):
        raise SystemExit(f"unsafe task name: {name!r}")
    task_dir = (EVALS_DIR / name).resolve()
    if task_dir.parent != EVALS_DIR or not (task_dir / "task.toml").is_file():
        raise SystemExit(f"no task.toml under {EVALS_DIR / name}")
    return task_dir


def expected_skills(task_dir: Path) -> list[str]:
    """Skills a task expects the agent to invoke.

    `metadata.skills` is a list for tasks that span more than one skill;
    `metadata.skill` remains supported for single-skill tasks.
    """
    meta = tomllib.loads((task_dir / "task.toml").read_text()).get("metadata", {})
    listed = meta.get("skills")
    if isinstance(listed, list):
        return [s for s in listed if isinstance(s, str)]
    single = meta.get("skill")
    return [single] if isinstance(single, str) else []


def snapshot_jobs(jobs_dir: Path) -> set[Path]:
    return set(jobs_dir.glob("*/")) if jobs_dir.exists() else set()


def git_sha() -> str:
    """Short commit of the skills being evaluated, for per-commit experiment history."""
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_DIR), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        sha = out.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "nogit"
    dirty = subprocess.run(
        ["git", "-C", str(REPO_DIR), "diff", "--quiet", "HEAD", "--"],
    ).returncode
    return f"{sha}-dirty" if dirty else sha


def experiment_names(task: str, run_id: str, *, no_skills: bool) -> tuple[str, str]:
    """(dataset, experiment). One dataset per task so runs stack up in its
    Experiments view; the experiment names the commit, so history reads per-commit."""
    suffix = "-control" if no_skills else ""
    return f"langsmith-skills-{task}", f"{task}-{git_sha()}{suffix}-{run_id}"


def invoke_harbor(
    task_dir: Path,
    project: str,
    *,
    agent: str,
    model: str,
    skills: Path | None,
    jobs_dir: Path,
    fresh_env: bool,
    experiment: str | None = None,
    dataset: str | None = None,
) -> tuple[int, Path | None]:
    before = snapshot_jobs(jobs_dir)
    argv = [
        "harbor", "run",
        "--path", str(task_dir),
        "--agent", agent,
        "-m", model,
        "--env", "docker",
        "--ae", f"LANGSMITH_PROJECT={project}",
        "--ve", f"LANGSMITH_PROJECT={project}",
        # Tasks that create a dataset need a per-trial name so concurrent runs
        # cannot collide and cleanup stays scoped to this run_id.
        "--ae", f"LANGSMITH_DATASET={project}",
        "--ve", f"LANGSMITH_DATASET={project}",
        "--agent-setup-timeout-multiplier", "3",
        "--environment-build-timeout-multiplier", "5",
        "--yes", "-k", "1", "-n", "1",
        "-o", str(jobs_dir),
    ]
    if ENV_FILE.exists():
        argv += ["--env-file", str(ENV_FILE)]
    if skills is not None:
        argv += ["--skills", str(skills)]
    if fresh_env:
        argv += ["--force-build"]
    for artifact in ("chain_trace.txt", "plain_trace.txt"):
        argv += ["--artifact", f"/workspace/{artifact}"]
    if experiment is not None:
        # Harbor's own LangSmith plugin logs the trial as an experiment run linked
        # to a dataset example, carrying reward and check feedback. It reads
        # LANGSMITH_API_KEY / LANGSMITH_ENDPOINT from this process's env.
        argv += [
            "--plugin", "harbor_langsmith:LangSmithPlugin",
            "--pk", f"dataset_name={dataset}",
            "--pk", f"experiment_name={experiment}",
        ]

    print(f"\n=== {task_dir.name} | {agent} | {model} | project={project} ===", flush=True)
    proc = subprocess.run(argv)  # list argv, never shell=True
    new_jobs = snapshot_jobs(jobs_dir) - before
    job_dir = max(new_jobs, key=lambda p: p.stat().st_mtime) if new_jobs else None
    return proc.returncode, job_dir


def read_job(job_dir: Path) -> dict:
    """Classify trials from Harbor's own job-level result.json."""
    out = {"rewards": {}, "errored": set(), "exceptions": {}}
    result_file = job_dir / "result.json"
    if not result_file.is_file():
        return out
    stats = json.loads(result_file.read_text()).get("stats", {})
    # Eval keys are composite (agent__model__suite), so never hardcode one.
    for ev in (stats.get("evals") or {}).values():
        for exc_type, trial_ids in (ev.get("exception_stats") or {}).items():
            for tid in trial_ids:
                out["errored"].add(tid)
                out["exceptions"][tid] = exc_type
        # Reward keys arrive as strings ("0.0" / "1.0").
        for value, trial_ids in ((ev.get("reward_stats") or {}).get("reward") or {}).items():
            for tid in trial_ids:
                out["rewards"][tid] = float(value)
    return out


def read_trial(job_dir: Path) -> dict:
    """Per-check detail so a reward of 0 names the check that failed."""
    out: dict[str, object] = {"failed_checks": [], "stats": {}, "invalid": None}
    for results in job_dir.glob("*/verifier/_test_results.json"):
        data = json.loads(results.read_text())
        out["failed_checks"] = [c.split(":")[0] for c in data.get("failed", [])]
        out["stats"] = data.get("stats", {})
        break
    # A verifier that could not obtain evidence -- LangSmith unreachable, auth
    # failure, ingestion incomplete at the deadline -- leaves this marker. That
    # is an infrastructure fault, so it must not read as failed agent work.
    for marker in job_dir.glob("*/verifier/invalid.txt"):
        reason = marker.read_text().strip()
        if reason:
            out["invalid"] = reason
        break
    return out


def skill_from_path(path: str) -> str | None:
    if SKILL_PATH_MARKER not in path:
        return None
    tail = path.split(SKILL_PATH_MARKER, 1)[1].strip("/")
    return tail.split("/")[0] or None


def skills_invoked(job_dir: Path) -> list[str]:
    """Scan the claude-code stream-json transcript for skill usage."""
    invoked: list[str] = []

    def add(name: str | None) -> None:
        if name and name not in invoked:
            invoked.append(name)

    for transcript in job_dir.glob("*/agent/claude-code.txt"):
        for line in transcript.read_text(errors="replace").splitlines():
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict) or msg.get("type") != "assistant":
                continue
            for item in msg.get("message", {}).get("content", []):
                if not isinstance(item, dict) or item.get("type") != "tool_use":
                    continue
                tool = item.get("name", "")
                inp = item.get("input") or {}
                if tool == "Skill":
                    add(inp.get("skill"))
                elif tool == "Read":
                    add(skill_from_path(inp.get("file_path", "")))
    return invoked


def verdict(records: list[dict], *, no_skills: bool = False) -> int:
    """Map per-rep records to an exit code. Infra errors outrank skill signals."""
    if any(r["exception"] or r.get("invalid") for r in records):
        return EXIT_INFRA
    if no_skills:
        return EXIT_OK
    if any(r["gate"] is False for r in records):
        return EXIT_GATE
    if any(r["reward"] != 1.0 for r in records):
        return EXIT_REWARD
    return EXIT_OK


def print_table(records: list[dict]) -> None:
    print("\n" + "=" * 78)
    print("EVAL SUMMARY")
    print("=" * 78)
    header = f"{'rep':>3}  {'run_id':<10} {'reward':>7}  {'gate':>6}  {'cli':<12} failed / skills"
    print(header)
    print("-" * 78)
    for r in records:
        reward = "—" if r["reward"] is None else f"{r['reward']:.1f}"
        gate = "n/a" if r["gate"] is None else ("pass" if r["gate"] else "MISS")
        cli = str(r["stats"].get("langsmith_cli_version", "?"))[:12]
        detail = ", ".join(r["failed_checks"]) or ", ".join(r["skills"]) or "—"
        print(f"{r['rep']:>3}  {r['run_id']:<10} {reward:>7}  {gate:>6}  {cli:<12} {detail}")
        if r["exception"]:
            print(f"     infra: {r['exception']}")
        if r.get("invalid"):
            print(f"     INVALID RUN (no agent score): {r['invalid']}")
        if r.get("missing_skills"):
            print(f"     skills never invoked: {', '.join(r['missing_skills'])}")
        if r.get("experiment"):
            print(f"     experiment: {r['dataset']} / {r['experiment']}")
            print(f"     traces kept in project: {r['project']}")
        if r["job_dir"]:
            print(f"     {r['job_dir']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="trace-instrument")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--agent", default="claude-code")
    parser.add_argument("-m", "--model", default="claude-sonnet-4-6",
                        help="Bare model id: under a gateway base URL the "
                             "claude-code adapter forwards it verbatim.")
    parser.add_argument("--no-skills", action="store_true",
                        help="Control run: omit --skills. Informational, never fails.")
    parser.add_argument("--skills-path", default=str(DEFAULT_SKILLS))
    parser.add_argument("--fresh-env", action="store_true",
                        help="Rebuild the image so the langsmith CLI re-resolves to latest.")
    parser.add_argument("--keep", action="store_true", help="Leave the LangSmith project in place.")
    parser.add_argument("--langsmith-experiment", action="store_true",
                        help="Log each trial as a LangSmith experiment. Implies --keep, "
                             "so the app traces survive alongside the experiment.")
    parser.add_argument("--experiment-dataset", default=None,
                        help="Override the dataset name experiments attach to.")
    parser.add_argument("--jobs-dir", default=str(DEFAULT_JOBS_DIR))
    parser.add_argument("--cleanup-only", metavar="RUN_ID")
    parser.add_argument("--sweep-orphans", type=float, metavar="HOURS")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    load_env_file(ENV_FILE)

    if args.cleanup_only:
        print(f"deleted: {cleanup(args.cleanup_only) or 'nothing'}")
        return EXIT_OK
    if args.sweep_orphans is not None:
        print(f"deleted: {sweep_orphans(args.sweep_orphans) or 'nothing'}")
        return EXIT_OK

    if not os.environ.get("LANGSMITH_API_KEY"):
        print(f"LANGSMITH_API_KEY is not set (looked in env and {ENV_FILE})", file=sys.stderr)
        return EXIT_USAGE

    task_dir = resolve_task(args.task)
    jobs_dir = Path(args.jobs_dir)
    skills = None if args.no_skills else Path(args.skills_path)
    required_skills = [] if args.no_skills else expected_skills(task_dir)
    # Deleting the project would take the traces the experiment points at with it.
    keep = args.keep or args.langsmith_experiment

    records: list[dict] = []
    for rep in range(args.reps):
        run_id = uuid.uuid4().hex[:8]
        project = project_name(run_id)
        record: dict = {"rep": rep, "run_id": run_id, "project": project, "reward": None,
                        "gate": None, "skills": [], "failed_checks": [], "stats": {},
                        "exception": None, "job_dir": None, "invalid": None,
                        "missing_skills": []}
        dataset = experiment = None
        if args.langsmith_experiment:
            dataset, experiment = experiment_names(
                args.task, run_id, no_skills=args.no_skills
            )
            if args.experiment_dataset:
                dataset = args.experiment_dataset
            record["experiment"] = experiment
            record["dataset"] = dataset
        try:
            exit_code, job_dir = invoke_harbor(
                task_dir, project, agent=args.agent, model=args.model, skills=skills,
                jobs_dir=jobs_dir, fresh_env=args.fresh_env,
                experiment=experiment, dataset=dataset,
            )
            if job_dir is None:
                record["exception"] = f"harbor produced no job dir (exit {exit_code})"
            else:
                record["job_dir"] = str(job_dir)
                job = read_job(job_dir)
                trial = read_trial(job_dir)
                record["failed_checks"] = trial["failed_checks"]
                record["stats"] = trial["stats"]
                record["invalid"] = trial["invalid"]
                record["skills"] = skills_invoked(job_dir)
                if job["errored"]:
                    record["exception"] = ", ".join(sorted(set(job["exceptions"].values())))
                rewards = list(job["rewards"].values())
                record["reward"] = rewards[0] if rewards else None
                # Only claude-code writes a stream-json transcript, so the
                # gate is n/a for the oracle agent used in verifier calibration.
                # Gate on every listed skill: a task that spans two skills has
                # not exercised its subject unless both were reached.
                if required_skills and args.agent == "claude-code":
                    missing = [s for s in required_skills if s not in record["skills"]]
                    record["gate"] = not missing
                    record["missing_skills"] = missing
        finally:
            if not keep:
                cleanup(run_id)
        records.append(record)

    print_table(records)
    if args.json:
        print(json.dumps(records, indent=2, default=str))

    if args.no_skills and not any(r["exception"] for r in records):
        print("\ncontrol run: informational only, reward above is not a pass/fail signal")
    return verdict(records, no_skills=args.no_skills)


if __name__ == "__main__":
    sys.exit(main())
