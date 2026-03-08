"""
Evaluation harness for autoresearch agents.

Runs the agent against a fixed dataset and scores it using LangSmith.
DO NOT MODIFY — this is the fixed evaluation, equivalent to prepare.py
in karpathy/autoresearch.

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
"""

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI
from langsmith import Client, evaluate, traceable

SCRIPT_DIR = Path(__file__).parent


def load_dataset(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Run function — wraps the agent for evaluation
# ---------------------------------------------------------------------------


@traceable(name="agent_run")
def run_agent_for_eval(inputs: dict) -> dict:
    sys.path.insert(0, str(SCRIPT_DIR))
    from agent import run_agent

    try:
        response = run_agent(inputs["question"])
        return {"response": response}
    except Exception as e:
        return {"response": f"ERROR: {e}", "error": True}


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------


def _get_judge():
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


def correctness_evaluator(run, example) -> dict:
    """Score whether the agent's response is factually correct compared to the expected answer."""
    run_outputs = run.outputs if hasattr(run, "outputs") else run.get("outputs", {}) or {}
    example_outputs = example.outputs if hasattr(example, "outputs") else example.get("outputs", {}) or {}

    response = run_outputs.get("response", "")
    expected = example_outputs.get("answer", "")

    if run_outputs.get("error"):
        return {"score": 0, "comment": "Agent returned an error"}

    judge = _get_judge()
    grade = judge.invoke(
        [
            {
                "role": "system",
                "content": (
                    "You are grading an AI assistant's response. "
                    "Score 1 if the response contains the correct answer (it doesn't need to match exactly, "
                    "just be factually equivalent). Score 0 if incorrect or missing. "
                    "Respond with ONLY a JSON object: {\"score\": 0 or 1, \"reasoning\": \"...\"}"
                ),
            },
            {
                "role": "user",
                "content": f"Expected answer: {expected}\n\nActual response: {response}",
            },
        ]
    )
    try:
        result = json.loads(grade.content)
        return {"score": result.get("score", 0), "comment": result.get("reasoning", "")}
    except (json.JSONDecodeError, AttributeError):
        content = grade.content if hasattr(grade, "content") else str(grade)
        return {"score": 0, "comment": f"Judge parse error: {content}"}


def helpfulness_evaluator(run, example) -> dict:
    """Score whether the response is helpful, clear, and well-structured."""
    run_outputs = run.outputs if hasattr(run, "outputs") else run.get("outputs", {}) or {}

    response = run_outputs.get("response", "")

    if run_outputs.get("error"):
        return {"score": 0, "comment": "Agent returned an error"}

    judge = _get_judge()
    grade = judge.invoke(
        [
            {
                "role": "system",
                "content": (
                    "You are grading an AI assistant's response for helpfulness. "
                    "Score 1 if the response is clear, direct, and helpful. "
                    "Score 0 if it's confusing, overly verbose, or unhelpful. "
                    "Respond with ONLY a JSON object: {\"score\": 0 or 1, \"reasoning\": \"...\"}"
                ),
            },
            {
                "role": "user",
                "content": f"Question: {example.inputs.get('question', '') if hasattr(example, 'inputs') else example.get('inputs', {}).get('question', '')}\n\nResponse: {response}",
            },
        ]
    )
    try:
        result = json.loads(grade.content)
        return {"score": result.get("score", 0), "comment": result.get("reasoning", "")}
    except (json.JSONDecodeError, AttributeError):
        content = grade.content if hasattr(grade, "content") else str(grade)
        return {"score": 0, "comment": f"Judge parse error: {content}"}


def tool_usage_evaluator(run, example) -> dict:
    """Score whether the agent used tools appropriately (used them when expected, didn't when not)."""
    run_outputs = run.outputs if hasattr(run, "outputs") else run.get("outputs", {}) or {}
    example_outputs = example.outputs if hasattr(example, "outputs") else example.get("outputs", {}) or {}

    if run_outputs.get("error"):
        return {"score": 0, "comment": "Agent returned an error"}

    expected_tool_use = example_outputs.get("expected_tool_use", None)
    if expected_tool_use is None:
        return {"score": 1, "comment": "No tool usage expectation defined"}

    response = run_outputs.get("response", "")
    used_tool = "Error:" not in response and any(
        marker in str(run_outputs)
        for marker in ["calculator", "unit_converter", "tool_calls"]
    )

    if expected_tool_use and not used_tool:
        return {"score": 0, "comment": "Expected tool use but agent didn't use tools"}
    if not expected_tool_use and used_tool:
        return {"score": 0, "comment": "Agent used tools when not expected"}
    return {"score": 1, "comment": "Tool usage matched expectations"}


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------


def run_evaluation(dataset_path: str, prefix: str) -> dict[str, Any]:
    client = Client()

    examples = load_dataset(dataset_path)

    dataset_name = f"autoresearch-eval-{uuid.uuid4().hex[:8]}"
    dataset = client.create_dataset(dataset_name, description="Autoresearch evaluation dataset")
    client.create_examples(
        inputs=[e["inputs"] for e in examples],
        outputs=[e["outputs"] for e in examples],
        dataset_name=dataset_name,
    )

    results = evaluate(
        run_agent_for_eval,
        data=dataset_name,
        evaluators=[correctness_evaluator, helpfulness_evaluator, tool_usage_evaluator],
        experiment_prefix=prefix,
        max_concurrency=4,
    )

    correctness_scores = []
    helpfulness_scores = []
    tool_usage_scores = []
    num_errors = 0

    for result in results:
        eval_results = result.get("evaluation_results", {})
        eval_list = eval_results.get("results", [])

        for er in eval_list:
            key = er.key if hasattr(er, "key") else er.get("key", "")
            score = er.score if hasattr(er, "score") else er.get("score", 0)
            if score is None:
                score = 0
            if "correctness" in key:
                correctness_scores.append(score)
            elif "helpfulness" in key:
                helpfulness_scores.append(score)
            elif "tool_usage" in key:
                tool_usage_scores.append(score)

        run_output = result.get("run", {})
        if hasattr(run_output, "outputs"):
            outputs = run_output.outputs or {}
        else:
            outputs = run_output.get("outputs", {}) or {}
        if outputs.get("error"):
            num_errors += 1

    avg_correctness = sum(correctness_scores) / len(correctness_scores) if correctness_scores else 0
    avg_helpfulness = sum(helpfulness_scores) / len(helpfulness_scores) if helpfulness_scores else 0
    avg_tool_usage = sum(tool_usage_scores) / len(tool_usage_scores) if tool_usage_scores else 0
    overall = (avg_correctness + avg_helpfulness + avg_tool_usage) / 3

    experiment_url = ""
    try:
        ds = client.read_dataset(dataset_name=dataset_name)
        experiments = list(client.list_experiments(dataset_id=ds.id))
        if experiments:
            experiment_url = experiments[0].url or ""
    except Exception:
        pass

    summary = {
        "avg_correctness": avg_correctness,
        "avg_helpfulness": avg_helpfulness,
        "avg_tool_usage": avg_tool_usage,
        "overall_score": overall,
        "num_examples": len(examples),
        "num_errors": num_errors,
        "experiment_url": experiment_url,
    }

    try:
        client.delete_dataset(dataset_name=dataset_name)
    except Exception:
        pass

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
