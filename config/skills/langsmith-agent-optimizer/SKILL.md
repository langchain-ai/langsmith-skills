---
name: langsmith-agent-optimizer
description: "INVOKE THIS SKILL when you want to iteratively improve an LLM agent using LangSmith as the system of record. Covers the full loop: finding problems in production traces, curating an eval dataset, writing evaluators, making targeted code changes, and running before/after experiments to measure improvement."
---

<oneliner>
Iterative agent improvement loop: **inspect production traces → identify a problem → curate an eval dataset → write evaluators → change the code → run before/after experiments**. LangSmith is the system of record for every step.
</oneliner>

<mental_model>
## Core Mental Model

**One tracing project = one agent.** The tracing project is your source of truth — real user traffic, real failures, real behavior. Everything else (datasets, experiments, evaluators) is organized around it.

The improvement loop:
1. **Diagnose** — sample recent traces to find what's broken or suboptimal
2. **Curate** — build an eval dataset from real traces that covers the problem
3. **Baseline** — run an experiment against the dataset before changing anything
4. **Change** — make the smallest targeted code change that addresses the problem
5. **Verify** — run the experiment again and compare to baseline
</mental_model>

<setup>
Environment Variables

```bash
LANGSMITH_API_KEY=lsv2_pt_your_api_key_here          # Required
LANGSMITH_PROJECT=your-project-name                   # The agent's tracing project
LANGSMITH_WORKSPACE_ID=your-workspace-id              # Optional: for org-scoped keys
OPENAI_API_KEY=your_openai_key                        # For LLM-as-Judge evaluators
```

**IMPORTANT:** `LANGSMITH_PROJECT` is the agent you are improving. Check the environment or `.env` file first. If it is not set, list projects and ask the user to identify the right one.

CLI Tool
```bash
curl -sSL https://raw.githubusercontent.com/langchain-ai/langsmith-cli/main/scripts/install.sh | sh
```

Python Dependencies
```bash
pip install langsmith langchain-openai python-dotenv
```
</setup>

<finding_the_project>
## Step 1: Find the Right Tracing Project

```bash
# List projects — note: default limit is 20, use --limit to get more
langsmith project list --limit 100
```

If the CLI doesn't find the project by name, use the SDK to search:

```python
from langsmith import Client

client = Client()
projects = list(client.list_projects(limit=100))
for p in projects:
    print(p.id, p.name)
```

Once you have the project name or ID, set it:
```bash
export LANGSMITH_PROJECT="your-project-name"
```
</finding_the_project>

<diagnosing_problems>
## Step 2: Diagnose — Sample Traces to Find Problems

Pull a sample of recent traces and look for patterns: errors, wrong behavior, off-topic responses, refusals that shouldn't happen, bad formatting, etc.

```bash
# Sample recent traces with full inputs/outputs
langsmith trace export ./traces --project "$LANGSMITH_PROJECT" --limit 50 --full

# Focus on failures
langsmith trace list --project "$LANGSMITH_PROJECT" --error --limit 20
langsmith trace export ./traces/errors --project "$LANGSMITH_PROJECT" --error --limit 20 --full

# Focus on slow traces
langsmith trace list --project "$LANGSMITH_PROJECT" --min-latency 10 --limit 20
```

Read through the exported traces and categorize problems. Pick **one problem** to fix at a time. Trying to fix multiple things in one iteration makes it impossible to know what helped.

**Document your hypothesis:** "The agent is doing X when it should do Y because Z."
</diagnosing_problems>

<dataset_naming>
## Dataset Naming Convention

Since LangSmith doesn't yet have a first-class link between a tracing project and its eval datasets, use this naming convention so datasets are always discoverable:

```
optimizer:<project-name>:evals
```

For example, if the project is `chat-langchain`:
```
optimizer:chat-langchain:evals
```

This single dataset grows over time. You add examples to it — never replace it. It is the permanent record of every scenario the agent must handle correctly.

```bash
# Check if the dataset already exists
langsmith dataset list | grep "optimizer:$LANGSMITH_PROJECT"

# Create it if it doesn't exist yet
langsmith dataset create --name "optimizer:$LANGSMITH_PROJECT:evals" \
  --description "Eval dataset for $LANGSMITH_PROJECT agent optimizer"
```
</dataset_naming>

<curating_dataset>
## Step 3: Curate the Eval Dataset

Pull examples from the traces you diagnosed — inputs where the agent failed, plus a sample of inputs where it behaved correctly. These become your before/after test set.

```python
import json
from pathlib import Path
from langsmith import Client

client = Client()
dataset_name = f"optimizer:{project_name}:evals"

# Check how many examples already exist
existing = list(client.list_examples(dataset_name=dataset_name))
print(f"Existing examples: {len(existing)}")

# Process exported traces into examples
new_examples = []
for jsonl_file in Path("./traces").glob("*.jsonl"):
    runs = [json.loads(line) for line in jsonl_file.read_text().strip().split("\n")]
    root = next((r for r in runs if r.get("parent_run_id") is None), None)
    if root and root.get("inputs") and root.get("outputs"):
        new_examples.append({
            "inputs": root["inputs"],
            "outputs": root["outputs"],   # expected / reference output
            "metadata": {
                "trace_id": root.get("trace_id"),
                "source_project": project_name,
                "added_for": "describe the problem this example covers",
            }
        })

# Add to the existing dataset (do NOT recreate it)
client.create_examples(
    inputs=[e["inputs"] for e in new_examples],
    outputs=[e["outputs"] for e in new_examples],
    metadata=[e["metadata"] for e in new_examples],
    dataset_name=dataset_name,
)
print(f"Added {len(new_examples)} examples. Total: {len(existing) + len(new_examples)}")
```
</curating_dataset>

<baseline_experiment>
## Step 4: Run a Baseline Experiment (Before Changing Anything)

**Always establish a baseline before making changes.** This is non-negotiable. Without a before score, you cannot know whether your change helped.

```python
from langsmith import evaluate

dataset_name = f"optimizer:{project_name}:evals"

# Import your agent's run function
from your_agent import run_agent  # adjust to your actual import

# Run baseline experiment
baseline_results = evaluate(
    run_agent,
    data=dataset_name,
    evaluators=[your_evaluator],   # see evaluator section
    experiment_prefix=f"baseline",
)

print(f"Baseline score: {baseline_results.to_pandas()['feedback.your_metric'].mean():.3f}")
```

Record the baseline score. You will compare every future experiment to this number.
</baseline_experiment>

<writing_evaluators>
## Writing Evaluators

Write evaluators that measure whether the agent is doing the right thing — not just that it produces output.

**Inspect actual outputs before writing evaluators:**
```python
from langsmith import Client
client = Client()
examples = list(client.list_examples(dataset_name=dataset_name, limit=3))
for ex in examples:
    print("inputs:", ex.inputs)
    print("expected outputs:", ex.outputs)
```

**LLM-as-Judge (for subjective quality):**
```python
from typing import TypedDict, Annotated
from langchain_openai import ChatOpenAI

class Grade(TypedDict):
    reasoning: Annotated[str, ..., "Explain your reasoning"]
    passed: Annotated[bool, ..., "True if the response is acceptable"]

judge = ChatOpenAI(model="gpt-4o", temperature=0).with_structured_output(
    Grade, method="json_schema", strict=True
)

async def quality_evaluator(run, example):
    run_outputs = run.outputs if hasattr(run, "outputs") else run.get("outputs", {}) or {}
    example_outputs = example.outputs if hasattr(example, "outputs") else example.get("outputs", {}) or {}
    grade = await judge.ainvoke([{
        "role": "user",
        "content": (
            f"Expected behavior: {example_outputs}\n"
            f"Actual response: {run_outputs}\n"
            "Did the agent respond correctly? Be strict."
        )
    }])
    return {"score": 1 if grade["passed"] else 0, "comment": grade["reasoning"]}
```

**Custom Code (for deterministic checks):**
```python
def refusal_evaluator(run, example):
    """Check that the agent refuses off-topic questions."""
    run_outputs = run.outputs if hasattr(run, "outputs") else run.get("outputs", {}) or {}
    response = str(run_outputs.get("output", "")).lower()
    refused = any(phrase in response for phrase in ["i can only help", "outside my scope", "i'm not able to"])
    return {"score": 1 if refused else 0, "comment": f"Response: {response[:200]}"}
```

**One metric per evaluator function.** For multiple metrics, create separate functions and pass them all to `evaluate()`.
</writing_evaluators>

<making_changes>
## Step 5: Make the Change

Make the **smallest possible change** that addresses the diagnosed problem. Common change types:

- **Prompt / system message** — update instructions, add examples, tighten constraints
- **Guardrails / middleware** — add or adjust pre/post-processing logic
- **Tool definitions** — clarify tool descriptions or adjust routing logic
- **Model** — swap to a different model or version

**Do not refactor, restructure, or clean up other things while making the change.** One variable changes, everything else stays constant. This is how you know whether your change was responsible for the improvement.

After making the change, verify it works on 1–2 examples manually before running the full experiment.
</making_changes>

<post_change_experiment>
## Step 6: Run the Post-Change Experiment and Compare

```python
# After making your code change, run the same dataset
after_results = evaluate(
    run_agent,   # same function, now running updated code
    data=dataset_name,
    evaluators=[your_evaluator],
    experiment_prefix=f"after-fix-describe-what-you-changed",
)

after_score = after_results.to_pandas()['feedback.your_metric'].mean()
print(f"Baseline: {baseline_score:.3f}")
print(f"After:    {after_score:.3f}")
print(f"Delta:    {after_score - baseline_score:+.3f}")
```

**Interpreting results:**
- Score went up across the full dataset → the change is safe to ship
- Score went up on new cases but down on old ones → you introduced a regression, do not ship
- Score is flat → the change had no effect, rethink the hypothesis
- Score went down → the change made things worse, revert

View results in LangSmith UI to see per-example breakdowns and understand which cases improved or regressed.
</post_change_experiment>


<troubleshooting>
## Common Pitfalls

**"I fixed the bug but the experiment score didn't improve"**
- Your evaluator may not be measuring the right thing — inspect per-example scores
- The run function may not be running the actual changed code — verify imports
- The dataset may not include the failing cases — check example inputs

**"The project has thousands of traces, I don't know where to start"**
- Filter for errors first: `langsmith trace list --error --limit 50`
- Filter for low feedback: `langsmith trace list --filter 'and(eq(feedback_key, "user_score"), lte(feedback_score, 0))'`
- Look at the most frequent root run names to understand traffic patterns

**"The CLI only returns 20 projects/traces"**
- Use `--limit 100` or higher
- Use the Python SDK for programmatic pagination when the CLI limit is not enough

**"I don't know what the agent's output structure looks like"**
- Export a single trace with `--full` and inspect it
- Print `run.outputs` inside your evaluator on the first run to see the shape
</troubleshooting>
