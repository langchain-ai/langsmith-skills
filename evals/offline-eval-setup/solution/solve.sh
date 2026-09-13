#!/usr/bin/env bash
# Reference solution. Its job is to prove the verifier can be satisfied.
#
# It uses the SDK for the dataset, the experiment, and the readback (stable
# field names), and the CLI only for the uploaded evaluator, which has no SDK
# equivalent. Agent runs are what exercise the CLI paths the skills teach.
#
# It deliberately does BOTH mechanisms -- one evaluator uploaded to the dataset
# so it auto-runs, one passed locally to evaluate(). The reward does not require
# either; mechanism is a stat.
#
# Note: a passing oracle does NOT prove the uploaded evaluator scored. Its
# feedback lands server-side long after the local evaluator's, and the verifier
# stops polling once every run has a score, so the uploaded score is usually
# not yet visible. The verifier reports the rules bound to the dataset
# (dataset_bound_evaluators) to show the attachment happened.
set -euo pipefail

cd /workspace
: "${LANGSMITH_DATASET:?LANGSMITH_DATASET must be set}"

# The uploaded evaluator runs server-side in a sandbox: stdlib only, and
# imports must sit inside the function body.
cat > evaluator_uploaded.py <<'PYEOF'
def answer_match(run, example):
    outputs = run["outputs"] if isinstance(run, dict) else (run.outputs or {})
    reference = example["outputs"] if isinstance(example, dict) else (example.outputs or {})
    actual = str((outputs or {}).get("answer", "")).strip()
    expected = str((reference or {}).get("expected_answer", "")).strip()
    return {"score": 1 if actual == expected else 0}
PYEOF

python - <<'PYEOF'
import json
import os
from pathlib import Path

from langsmith import Client

name = os.environ["LANGSMITH_DATASET"]
cases = json.loads(Path("test_cases.json").read_text())
client = Client()

dataset = client.create_dataset(dataset_name=name, description="support policy regression cases")
# Modern form: `inputs=`/`outputs=` lists still work but only as legacy kwargs.
client.create_examples(
    dataset_id=dataset.id,
    examples=[{"inputs": c["inputs"], "outputs": c["outputs"]} for c in cases],
)
print(f"dataset {name} -> {dataset.id} ({len(cases)} examples)")
PYEOF

# Attach the first evaluator to the dataset so it auto-runs on every experiment.
langsmith evaluator upload evaluator_uploaded.py \
  --name "answer_match_uploaded" \
  --function answer_match \
  --dataset "$LANGSMITH_DATASET"

python - <<'PYEOF'
import json
import os
import sys
import time
from pathlib import Path

from langsmith import Client

sys.path.insert(0, "/workspace")
from support_app.main import chain

name = os.environ["LANGSMITH_DATASET"]
client = Client()


def target(inputs: dict) -> dict:
    # Dataset inputs use policy_topic; the app takes topic.
    return chain.invoke({"topic": inputs["policy_topic"]})


def answer_match_local(outputs: dict, reference_outputs: dict) -> dict:
    actual = str((outputs or {}).get("answer", "")).strip()
    expected = str((reference_outputs or {}).get("expected_answer", "")).strip()
    return {"score": 1 if actual == expected else 0}


results = client.evaluate(
    target,
    data=name,
    evaluators=[answer_match_local],
    experiment_prefix=f"{name}-baseline",
    max_concurrency=1,
)
print(f"experiment: {getattr(results, 'experiment_name', '<unknown>')}")

# Read the scores back out of LangSmith rather than trusting the local return
# value: the uploaded evaluator scores server-side and only appears via the API.
dataset = client.read_dataset(dataset_name=name)
examples = {str(e.id): e for e in client.list_examples(dataset_id=dataset.id)}
deadline = time.time() + 240
report: list[dict] = []
while time.time() < deadline:
    report = []
    for project in client.list_projects(reference_dataset_id=dataset.id):
        for run in client.list_runs(project_id=project.id, is_root=True):
            example = examples.get(str(run.reference_example_id))
            if example is None:
                continue
            scores = {
                fb.key: fb.score
                for fb in client.list_feedback(run_ids=[run.id])
                if fb.score is not None
            }
            if not scores:
                continue
            report.append(
                {
                    "policy_topic": example.inputs["policy_topic"],
                    "answer": (run.outputs or {}).get("answer"),
                    "expected_answer": example.outputs["expected_answer"],
                    "scores": scores,
                    "score": min(scores.values()),
                }
            )
    if len(report) >= len(examples):
        break
    time.sleep(5)

Path("/workspace/results.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
if len(report) < len(examples):
    raise SystemExit(f"only {len(report)}/{len(examples)} cases had feedback before the deadline")
PYEOF
