---
name: langsmith-graph-evaluator
description: "Experimental. Build a LangSmith evaluator as a graph of steps with openevals.graph: code checks, LLM judges and decision models wired together, each traced as its own span and drawn as a graph in LangSmith. Use when an evaluator needs several chained checks, or the user asks for a graph, multi-step or composed evaluator. For a single judge or code check, use langsmith-evaluator."
---

# Build a graph evaluator

`openevals.graph` is experimental; its API may change between releases. Python only.

```bash
pip install -U "openevals[typesafe]" langchain-anthropic   # or the provider your judges use
```

Set the provider keys the graph calls (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `TYPESAFE_API_KEY` for Jev). Never write a key into the evaluator file.

## Decide what to measure first

Read the agent's code and a sample of its traces before writing nodes (see `langsmith-trace`). Confirm the exact fields in `run.inputs`, `run.outputs` and the dataset's `example.outputs`. Make a node only for a meaningful step; keep small helpers as plain functions. One node is fine.

## Nodes

Every node is a top-level name in the file, so LangSmith can read the graph from the source.

- **Code:** a function decorated with `@node` that returns a dict. A parameter named `run`, `thread`, `trajectory` or `example` (or annotated `Run`, `Thread`, `Trajectory`, `Example`) gets that context. A parameter named after another node gets that node's outputs.
- **LLM judge:** `LLM(model="<provider>:<model>", prompt=..., inputs={...}, output_schema=...)`. `prompt` is a string or a list of `(role, content)` messages with `{{name}}` placeholders. Without `output_schema` the node returns `{"score": number}`; `feedback_key` renames that key.
- **Decision model:** `DecisionModel(model=..., inputs={...}, questions={...})` for yes/no, scale and choice judgements. `model` is required: `"typesafe:jev-latest"`, or any `langchain_core.decisions.BaseDecisionModel` instance. It takes no prompt; its inputs are the state it judges, so each question names the inputs it compares.

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

To attach it to a dataset or project, upload it with `langsmith evaluator upload` as described in `langsmith-evaluator`. An uploaded evaluator runs only with the packages LangSmith's evaluator runtime provides, so confirm `openevals` and each provider package are available there before uploading; if they are not, run the evaluator offline instead and tell the user.
