"""LangSmith side-effect management for the eval harness.

Every trial gets its own project named ``lsskills-<run_id>``.

The prefix is deliberately NOT ``bench-``: skills-benchmarks' sweep.py creates
``bench-<run_id>`` projects in the same workspace, and an orphan sweep keyed on
that prefix would delete another tool's in-flight runs. Per-run cleanup is
scoped to the exact run_id suffix, and the orphan sweep additionally requires
this prefix, so neither can touch anything this harness did not create.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from langsmith import Client

PROJECT_PREFIX = "lsskills-"
RUN_ID_RE = re.compile(r"^[0-9a-f]{8}$")


def project_name(run_id: str) -> str:
    if not RUN_ID_RE.match(run_id):
        raise ValueError(f"run_id must be 8 lowercase hex chars, got {run_id!r}")
    return f"{PROJECT_PREFIX}{run_id}"


def _delete_dataset_tree(client: Client, suffix: str) -> list[str]:
    """Delete suffix-matched datasets and the experiments pointing at them.

    An experiment is a project named by whatever ``experiment_prefix`` the agent
    chose, so it cannot be found by suffix. It is reachable only through its
    ``reference_dataset_id``, so resolve the dataset first and delete its
    experiments before the dataset itself. Evaluator rules bound to the dataset
    go with it.
    """
    deleted: list[str] = []
    for dataset in client.list_datasets():
        name = dataset.name or ""
        if not name.endswith(suffix):
            continue
        try:
            experiments = list(client.list_projects(reference_dataset_id=dataset.id))
        except Exception as exc:  # noqa: BLE001 - cleanup is best effort
            print(f"[cleanup] could not list experiments for {name}: {exc}")
            experiments = []
        for experiment in experiments:
            try:
                client.delete_project(project_id=experiment.id)
                deleted.append(f"experiment:{experiment.name}")
            except Exception as exc:  # noqa: BLE001
                print(f"[cleanup] could not delete experiment {experiment.name}: {exc}")
        try:
            client.delete_dataset(dataset_id=dataset.id)
            deleted.append(f"dataset:{name}")
        except Exception as exc:  # noqa: BLE001
            print(f"[cleanup] could not delete dataset {name}: {exc}")
    return deleted


def cleanup(run_id: str, *, client: Client | None = None) -> list[str]:
    """Delete every project, dataset, and experiment belonging to one run."""
    if not RUN_ID_RE.match(run_id):
        raise ValueError(f"refusing to clean up with run_id={run_id!r}")
    client = client or Client()
    suffix = f"-{run_id}"
    deleted: list[str] = _delete_dataset_tree(client, suffix)
    for project in client.list_projects():
        name = project.name or ""
        if name.endswith(suffix):
            try:
                client.delete_project(project_name=name)
                deleted.append(name)
            except Exception as exc:  # noqa: BLE001 - cleanup is best effort
                print(f"[cleanup] could not delete {name}: {exc}")
    return deleted


def sweep_orphans(hours: float, *, client: Client | None = None) -> list[str]:
    """Delete this harness's own stale projects, for cancelled runs."""
    client = client or Client()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    deleted: list[str] = []
    for project in client.list_projects():
        name = project.name or ""
        started = getattr(project, "start_time", None)
        if not name.startswith(PROJECT_PREFIX) or started is None:
            continue
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if started < cutoff:
            try:
                client.delete_project(project_name=name)
                deleted.append(name)
            except Exception as exc:  # noqa: BLE001 - cleanup is best effort
                print(f"[sweep] could not delete {name}: {exc}")
    for dataset in client.list_datasets():
        name = dataset.name or ""
        created = getattr(dataset, "created_at", None)
        if not name.startswith(PROJECT_PREFIX) or created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created < cutoff:
            deleted += _delete_dataset_tree(client, name[len(PROJECT_PREFIX) - 1 :])
    return deleted
