---
name: langsmith-graph-evaluator
description: "Experimental. Build a LangSmith evaluator as a graph of steps with openevals.graph: code checks, LLM judges and decision models wired together, each traced as its own span and drawn as a graph in LangSmith. Use when an evaluator needs several chained checks, or the user asks for a graph, multi-step or composed evaluator. For a single judge or code check, use langsmith-evaluator."
---

# Build a graph evaluator

`openevals.graph` is experimental; its API may change between releases. Python only.

```bash
pip install "openevals==0.2.5" langchain-anthropic   # or the provider your judges use; openevals[typesafe] for Jev
```

Set the provider keys the graph calls (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `TYPESAFE_API_KEY` for Jev). Never write a key into the evaluator file.

## Decide what to measure first

Read the agent's code and a sample of its traces before writing nodes (see `langsmith-trace`). Confirm the exact fields in `run.inputs`, `run.outputs` and the dataset's `example.outputs`. Make a node only for a meaningful step; keep small helpers as plain functions. One node is fine.

## Nodes

Every node is a top-level name in the file, so LangSmith can read the graph from the source.

- **Code:** a function decorated with `@node` that returns a dict. A parameter named `run`, `thread`, `trajectory` or `example` (or annotated `Run`, `Thread`, `Trajectory`, `Example`) gets that context. A parameter named after another node gets that node's outputs.
- **LLM judge:** `LLM(model="<provider>:<model>", prompt=..., inputs={...}, output_schema=...)`. `prompt` is a string or a list of `(role, content)` messages with `{{name}}` placeholders. `output_schema` is a TypedDict or Pydantic class defined in the file, or a JSON schema; without one the node returns `{"score": number}`, and `feedback_key` renames that key.
- **Decision model:** `DecisionModel(model=..., inputs={...}, questions={...})` for yes/no, scale and choice judgements. `model` is required: `"typesafe:jev-latest"`, or any `langchain_core.decisions.BaseDecisionModel` instance. It takes no prompt; its inputs are the state it judges, so each question names the inputs it compares. Each question key is an output of the node.

Questions are `langchain_core.decisions` types, re-exported by `openevals.graph`, and take keyword arguments only:

```python
Noul(instructions="Does the answer address the question?")          # probability of yes
Score(instructions="How helpful is it?", criteria=["poor", "ok", "great"])  # index into criteria
Choice(instructions="Tone", criteria={"calm": None, "rude": None})   # chosen label
```

`inputs` maps each name to a typed reference, never a string: `Run.inputs.question`, `Run.outputs.answer`, `Example.outputs.reference`, or another node's output like `tool_usage.calls`.

## Example

```python
from openevals.graph import Choice, DecisionModel, Graph, LLM, Noul, Run, node

judge = LLM(
    model="anthropic:claude-sonnet-5",
    prompt="Rate this answer from 0 to 1: {{answer}}",
    inputs={"answer": Run.outputs.answer},
)
checks = DecisionModel(
    model="typesafe:jev-latest",
    inputs={"question": Run.inputs.question, "answer": Run.outputs.answer},
    questions={
        "on_topic": Noul(instructions="Does the answer address the question?"),
        "tone": Choice(instructions="Tone", criteria={"calm": None, "rude": None}),
    },
)


@node
def answer(judge, checks):
    ok = checks["on_topic"] > 0.5 and checks["tone"] == "calm"
    return {"score": judge["score"] if ok else 0}


graph = Graph([judge, checks, answer])
```

`Graph([...])` checks the wiring when it is built: a parameter that names no listed node, an output a node does not produce, or a cycle raises `ValueError` before any model is called. Nodes run after the nodes they read, whatever order they are listed in.

## Run it as an evaluator

```python
graph_evaluator = graph.as_evaluator(answer)
```

`as_evaluator(node)` returns a `(run, example)` evaluator that runs the graph and reports that node's `score` (and `comment`, if it returns one) under the node's name; `key="..."` renames it. A node with exactly one output reports that output instead. `run` and `example` can be LangSmith objects or dicts, and `example` is optional for online evaluators.

Test it on a few real runs before attaching it anywhere: fetch them with `langsmith run get '<run-id>' --full --format json`, call `graph_evaluator(run)` locally, and check each node's output with `graph.run(run=run)`. With tracing on, each node appears as its own span under the evaluator's run, so a wrong final score can be traced to the node that produced it.

Use `graph_evaluator` offline by passing it to `evaluate(..., evaluators=[graph_evaluator])` (see `langsmith-evaluator` for run functions and datasets).

## Run it inside LangSmith

Create it through the API rather than `langsmith evaluator upload`, which can't declare the packages a graph needs. `POST <LangSmith API URL>/v1/platform/evaluators` with the headers `x-api-key` and `X-Tenant-Id: <workspace id>`:

```json
{"name": "Answer quality", "type": "code", "code_evaluator": {
  "code": "<the whole Python file>", "language": "python", "advanced_features_enabled": true,
  "workspace_secrets_keys": ["ANTHROPIC_API_KEY", "TYPESAFE_API_KEY"],
  "dependencies": "openevals[typesafe]==0.2.5\nlangchain-anthropic"}}
```

- `dependencies` is one package per line: pin `openevals==0.2.5` (`openevals[typesafe]==0.2.5` when the file has a `typesafe:` decision model, as in this example), and add `langchain-<provider>` for each judge provider other than OpenAI.
- `workspace_secrets_keys` names the provider keys the file calls. LangSmith sends each workspace secret with the model calls, so the file never holds a key; the clients still need some key to start, so set a placeholder at the top of the file:

```python
import os

for key in ("ANTHROPIC_API_KEY", "TYPESAFE_API_KEY"):
    os.environ.setdefault(key, "set-by-langsmith")
```

- Define `evaluate(ctx)` and return exactly a `score` and optional `comment`, so the feedback is named after the evaluator:

```python
def evaluate(ctx):
    results = graph.run(ctx)
    return {"score": results[answer]["score"]}
```

- Give each `LLM` and `DecisionModel` a `description="..."`, and a code node a docstring, so LangSmith can label the nodes; add `display_name="..."` when a name doesn't read well as a label. Write their arguments inline as literals (only `prompt` may name a top-level constant, and `output_schema` a class in the file), not computed values like f-strings, and list every node in one `Graph([...])`.

Then attach the evaluator to a project or dataset in LangSmith. To change it later, `PATCH <LangSmith API URL>/v1/platform/evaluators/<id>` with `{"code_evaluator": {"code": "<the whole Python file>"}}`.
