---
name: langsmith-evaluator
description: "Build evaluation pipelines for LangSmith. Covers creating evaluators (LLM-as-Judge, custom code), defining run functions to capture outputs and trajectories, and running evaluations locally with evaluate() or via uploaded evaluators. Uses the langsmith CLI tool."
---

## Setup

```bash
LANGSMITH_API_KEY=lsv2_pt_your_api_key_here
LANGSMITH_PROJECT=your-project-name
OPENAI_API_KEY=your_openai_key  # For LLM as Judge
```

Python: `pip install langsmith langchain-openai python-dotenv`
TypeScript: `npm install langsmith openai`

CLI Tool:
```bash
curl -sSL https://raw.githubusercontent.com/langchain-ai/langsmith-cli/main/scripts/install.sh | sh
```

## Golden Rule: Inspect Before You Implement

CRITICAL: Before writing ANY evaluator:
1. Run your agent on sample inputs and capture actual output
2. Inspect the output — print it, query LangSmith traces, understand exact structure
3. Only then write code that processes that output

## Offline vs Online Evaluators

**Offline** (attached to datasets): `(run, example)` — compares to expected values. Upload with `--dataset`.
**Online** (attached to projects): `(run)` only — real-time quality checks. Upload with `--project`.

Each evaluator returns ONE metric only. For multiple metrics, create multiple functions.

### Local vs Uploaded Differences

| | Local `evaluate()` | Uploaded to LangSmith |
|---|---|---|
| Python `run` type | `RunTree` → `run.outputs` | `dict` → `run["outputs"]` |
| TypeScript `run` type | Always `run.outputs?.field` | Always `run.outputs?.field` |
| Python return | `{"score": value, "comment": "..."}` | `{"score": value, "comment": "..."}` |
| TS return (local) | `{ key: "name", score, comment }` | `{ score, comment }` |

## LLM as Judge (Python)

```python
from typing import TypedDict, Annotated
from langchain_openai import ChatOpenAI

class Grade(TypedDict):
    reasoning: Annotated[str, ..., "Explain your reasoning"]
    is_accurate: Annotated[bool, ..., "True if response is accurate"]

judge = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(Grade, method="json_schema", strict=True)

async def accuracy_evaluator(run, example):
    run_outputs = run.outputs if hasattr(run, "outputs") else run.get("outputs", {}) or {}
    example_outputs = example.outputs if hasattr(example, "outputs") else example.get("outputs", {}) or {}
    grade = await judge.ainvoke([{"role": "user", "content": f"Expected: {example_outputs}\nActual: {run_outputs}\nIs this accurate?"}])
    return {"score": 1 if grade["is_accurate"] else 0, "comment": grade["reasoning"]}
```

## LLM as Judge (TypeScript)

```javascript
import OpenAI from "openai";
const openai = new OpenAI();

async function accuracyEvaluator(run, example) {
    const runOutputs = run.outputs ?? {};
    const exampleOutputs = example.outputs ?? {};
    const response = await openai.chat.completions.create({
        model: "gpt-4o-mini",
        temperature: 0,
        response_format: { type: "json_object" },
        messages: [
            { role: "system", content: 'Respond with JSON: {"is_accurate": boolean, "reasoning": string}' },
            { role: "user", content: `Expected: ${JSON.stringify(exampleOutputs)}\nActual: ${JSON.stringify(runOutputs)}\nIs this accurate?` }
        ]
    });
    const grade = JSON.parse(response.choices[0].message.content);
    return { score: grade.is_accurate ? 1 : 0, comment: grade.reasoning };
}
```

## Custom Code Evaluators

### Python
```python
def trajectory_evaluator(run, example):
    run_outputs = run.outputs if hasattr(run, "outputs") else run.get("outputs", {}) or {}
    example_outputs = example.outputs if hasattr(example, "outputs") else example.get("outputs", {}) or {}
    actual = run_outputs.get("YOUR_TRAJECTORY_FIELD", [])
    expected = example_outputs.get("YOUR_EXPECTED_FIELD", [])
    return {"score": 1 if actual == expected else 0, "comment": f"Expected {expected}, got {actual}"}
```

### TypeScript
```javascript
function trajectoryEvaluator(run, example) {
    const actual = run.outputs?.YOUR_TRAJECTORY_FIELD ?? [];
    const expected = example.outputs?.YOUR_EXPECTED_FIELD ?? [];
    const match = JSON.stringify(actual) === JSON.stringify(expected);
    return { score: match ? 1 : 0, comment: `Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}` };
}
```

## Run Functions

Test your run function FIRST before writing evaluators. Output shapes vary by framework.

### Python
```python
def run_agent(inputs: dict) -> dict:
    result = your_agent.run(inputs)
    print(f"DEBUG - type: {type(result)}, keys: {result.keys() if hasattr(result, 'keys') else 'N/A'}")
    return {"output": result}  # Adjust to match dataset schema
```

### TypeScript
```javascript
async function runAgent(inputs) {
    const result = await yourAgent.invoke(inputs);
    console.log("DEBUG - type:", typeof result, "keys:", Object.keys(result));
    return { output: result };
}
```

### Capturing Trajectories (LangGraph)
```python
import uuid

def run_agent_with_trajectory(agent, inputs: dict) -> dict:
    config = {"configurable": {"thread_id": f"eval-{uuid.uuid4()}"}}
    trajectory = []
    final_result = None
    for chunk in agent.stream(inputs, config=config, stream_mode="debug", subgraphs=True):
        print(f"DEBUG chunk: {chunk}")
        # Extract based on YOUR observed structure
    return {"output": final_result, "trajectory": trajectory}
```

## Uploading Evaluators

Uploaded evaluators auto-run when you run experiments on that dataset.

Uploaded evaluators run in sandboxed environment — only standard library imports, place all imports inside function body.

```bash
langsmith evaluator list

# Offline (dataset)
langsmith evaluator upload my_evaluators.py \
  --name "Trajectory Match" --function trajectory_evaluator \
  --dataset "My Dataset" --replace

# Online (project)
langsmith evaluator upload my_evaluators.py \
  --name "Quality Check" --function quality_check \
  --project "Production Agent" --replace

langsmith evaluator delete "Trajectory Match"
```

## Running Evaluations

### Python
```python
from langsmith import evaluate

# Uploaded evaluators auto-run
results = evaluate(run_agent, data="My Dataset", experiment_prefix="eval-v1")

# Or pass local evaluators
results = evaluate(run_agent, data="My Dataset", evaluators=[my_evaluator], experiment_prefix="eval-v1")
```

### TypeScript
```javascript
import { evaluate } from "langsmith/evaluation";

const results = await evaluate(runAgent, {
  data: "My Dataset",
  evaluators: [myEvaluator],
  experimentPrefix: "eval-v1",
});
```

## Troubleshooting

- **Output mismatch**: Query LangSmith trace to see exact inputs/outputs at each step
- **One metric per evaluator**: Return `{"score": value, "comment": "..."}` only
- **Field name mismatch**: Run function output must match dataset schema — inspect dataset first
- **RunTree vs dict (Python)**: Handle both: `run.outputs if hasattr(run, "outputs") else run.get("outputs", {}) or {}`

## Resources
- [LangSmith Evaluation Concepts](https://docs.langchain.com/langsmith/evaluation-concepts)
- [Custom Code Evaluators](https://changelog.langchain.com/announcements/custom-code-evaluators-in-langsmith)
- [OpenEvals - Readymade Evaluators](https://github.com/langchain-ai/openevals)
