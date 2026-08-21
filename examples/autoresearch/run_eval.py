"""
Evaluation harness for autoresearch agents.

Runs the agent against a dataset and scores it using LangSmith.
Customize this file BEFORE starting the autonomous experiment loop.
Once the loop begins, this file is fixed — only agent.py changes.

Usage:
    python run_eval.py
    python run_eval.py --dataset dataset.json --prefix "experiment-1"

Output format (parsed by the experiment loop):
    ---
    avg_correctness: 0.850000
    avg_helpfulness: 0.900000
    avg_tool_usage: 0.750000
    overall_score: 0.833333
    num_examples: 20
    num_errors: 0
    experiment_url: https://smith.langchain.com/...

Customization points (search for "CUSTOMIZE"):
    1. run_agent_for_eval() — how to call your agent
    2. Evaluators — what metrics to score
    3. EVALUATORS list — which evaluators to run
    4. DATASET_NAME — name of the persistent LangSmith dataset
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Annotated, Any

from langchain_openai import ChatOpenAI
from langsmith import Client, evaluate
from pydantic import BaseModel, Field

SCRIPT_DIR = Path(__file__).parent


def load_dataset(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# CUSTOMIZE 1: Run function — how to call your agent
#
# This function is called once per dataset example. It receives the example's
# inputs dict and must return a dict that your evaluators can score.
#
# The return dict is what evaluators see as `run.outputs`. If you need
# evaluators to check tool usage, trajectories, etc., return that data here.
# ---------------------------------------------------------------------------


def run_agent_for_eval(inputs: dict) -> dict:
    """Call the agent and return outputs for evaluators to score."""
    sys.path.insert(0, str(SCRIPT_DIR))
    from agent import run_agent_with_tools

    try:
        return run_agent_with_tools(inputs["question"])
    except Exception as e:
        return {"response": f"ERROR: {e}", "error": True, "tools_used": []}


# ---------------------------------------------------------------------------
# CUSTOMIZE 2: Evaluators
#
# Each evaluator takes (run, example) and returns {"score": number, "comment": str}.
# - run.outputs  = the dict your run function returned above
# - example.outputs = the "outputs" from your dataset.json
#
# Add, remove, or replace these to match your quality criteria.
# ---------------------------------------------------------------------------


class CorrectnessGrade(BaseModel):
    reasoning: Annotated[str, Field(description="Explain your reasoning")]
    score: Annotated[int, Field(description="1 if correct, 0 if incorrect")]


class HelpfulnessGrade(BaseModel):
    reasoning: Annotated[str, Field(description="Explain your reasoning")]
    score: Annotated[int, Field(description="1 if helpful, 0 if unhelpful")]


def _get_judge(schema: type[BaseModel]) -> Any:
    return ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(
        schema, method="json_schema", strict=True
    )


def correctness_evaluator(run, example) -> dict:
    """LLM-as-judge: is the response factually correct?"""
    run_outputs = run.outputs or {}
    example_outputs = example.outputs or {}

    response = run_outputs.get("response", "")
    expected = example_outputs.get("answer", "")

    if run_outputs.get("error"):
        return {"score": 0, "comment": "Agent returned an error"}

    judge = _get_judge(CorrectnessGrade)
    grade = judge.invoke(
        [
            {
                "role": "system",
                "content": (
                    "You are grading an AI assistant's response. "
                    "Score 1 if the response contains the correct answer (it doesn't need to match exactly, "
                    "just be factually equivalent). Score 0 if incorrect or missing."
                ),
            },
            {
                "role": "user",
                "content": f"Expected answer: {expected}\n\nActual response: {response}",
            },
        ]
    )
    return {"score": grade.score, "comment": grade.reasoning}


def helpfulness_evaluator(run, example) -> dict:
    """LLM-as-judge: is the response clear, direct, and helpful?"""
    run_outputs = run.outputs or {}
    example_inputs = example.inputs or {}

    response = run_outputs.get("response", "")
    question = example_inputs.get("question", "")

    if run_outputs.get("error"):
        return {"score": 0, "comment": "Agent returned an error"}

    judge = _get_judge(HelpfulnessGrade)
    grade = judge.invoke(
        [
            {
                "role": "system",
                "content": (
                    "You are grading an AI assistant's response for helpfulness. "
                    "Score 1 if the response is clear, direct, and helpful. "
                    "Score 0 if it's confusing, overly verbose, or unhelpful."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nResponse: {response}",
            },
        ]
    )
    return {"score": grade.score, "comment": grade.reasoning}


def tool_usage_evaluator(run, example) -> dict:
    """Code-based: did the agent use tools when expected?"""
    run_outputs = run.outputs or {}
    example_outputs = example.outputs or {}

    if run_outputs.get("error"):
        return {"score": 0, "comment": "Agent returned an error"}

    expected_tool_use = example_outputs.get("expected_tool_use", None)
    if expected_tool_use is None:
        return {"score": 1, "comment": "No tool usage expectation defined"}

    tools_used = run_outputs.get("tools_used", [])
    actually_used = len(tools_used) > 0

    if expected_tool_use and not actually_used:
        return {"score": 0, "comment": "Expected tool use but agent didn't use tools"}
    if not expected_tool_use and actually_used:
        return {"score": 0, "comment": f"Agent used tools when not expected: {tools_used}"}
    return {"score": 1, "comment": f"Tool usage matched expectations (tools: {tools_used})"}


# ---------------------------------------------------------------------------
# CUSTOMIZE 3: Which evaluators to run
# ---------------------------------------------------------------------------

EVALUATORS = [correctness_evaluator, helpfulness_evaluator, tool_usage_evaluator]

# ---------------------------------------------------------------------------
# CUSTOMIZE 4: Dataset name in LangSmith (persistent across experiments)
# ---------------------------------------------------------------------------

DATASET_NAME = "autoresearch-agent-eval"

# ---------------------------------------------------------------------------
# Evaluation infrastructure (you probably don't need to change below here)
# ---------------------------------------------------------------------------


def get_or_create_dataset(client: Client, dataset_path: str) -> str:
    """Return the persistent dataset name, creating it from dataset.json if it doesn't exist yet."""
    if client.has_dataset(dataset_name=DATASET_NAME):
        return DATASET_NAME

    examples = load_dataset(dataset_path)
    client.create_dataset(DATASET_NAME, description="Autoresearch agent evaluation dataset")
    client.create_examples(
        inputs=[e["inputs"] for e in examples],
        outputs=[e["outputs"] for e in examples],
        dataset_name=DATASET_NAME,
    )
    print(f"Created persistent dataset: {DATASET_NAME}")
    return DATASET_NAME


def run_evaluation(dataset_path: str, prefix: str) -> dict[str, Any]:
    client = Client()

    dataset_name = get_or_create_dataset(client, dataset_path)

    results = evaluate(
        run_agent_for_eval,
        data=dataset_name,
        evaluators=EVALUATORS,
        experiment_prefix=prefix,
        max_concurrency=4,
    )

    scores_by_evaluator: dict[str, list[float]] = {}
    num_errors = 0
    num_examples = 0

    for result in results:
        num_examples += 1
        for er in result["evaluation_results"]["results"]:
            if er.score is not None:
                scores_by_evaluator.setdefault(er.key, []).append(er.score)

        outputs = result["run"].outputs or {}
        if outputs.get("error"):
            num_errors += 1

    averages = {k: sum(v) / len(v) for k, v in scores_by_evaluator.items() if v}
    overall = sum(averages.values()) / len(averages) if averages else 0

    experiment_url = ""
    try:
        projects = list(client.list_projects(name=results.experiment_name))
        if projects:
            experiment_url = projects[0].url or ""
    except Exception:
        pass

    summary = {f"avg_{k}": v for k, v in averages.items()}
    summary["overall_score"] = overall
    summary["num_examples"] = num_examples
    summary["num_errors"] = num_errors
    summary["experiment_url"] = experiment_url
    return summary


def main():
    parser = argparse.ArgumentParser(description="Run autoresearch agent evaluation")
    parser.add_argument("--dataset", default=str(SCRIPT_DIR / "dataset.json"), help="Path to dataset JSON")
    parser.add_argument("--prefix", default="autoresearch", help="Experiment prefix")
    args = parser.parse_args()

    summary = run_evaluation(args.dataset, args.prefix)

    print("---")
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key}: {value:.6f}")
        else:
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
