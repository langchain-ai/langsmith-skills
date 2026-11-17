---
name: langsmith-graph-evaluator
description: "Experimental. Build a LangSmith evaluator as a graph of steps with openevals.graph: code checks, LLM judges and decision models wired together, each traced as its own span and drawn as a graph in LangSmith. Use when an evaluator needs several chained checks, or the user asks for a graph, multi-step or composed evaluator. For a single judge or code check, use langsmith-evaluator."
---

# Build a graph evaluator

`openevals.graph` is experimental; its API may change between releases. Python only.

The workflow, in order:

1. [Gather context](#gather-context): the agent's code and recent traces.
2. [Decide what to measure](#decide-what-to-measure): use the user's goal, or suggest one from the agent's type, and confirm it.
3. [Choose models](#choose-models): code, a decision model or an LLM judge for each node.
4. [Write the graph](#write-the-graph): one Python file.
5. [Test it locally](#test-it-locally) on real runs.
6. [Run it inside LangSmith](#run-it-inside-langsmith).

## Gather context

The target decides the kind of evaluator:

- **Agent and environment** (or a tracing project): an online evaluator on that project's runs. The environment's `project_id` is its tracing project.
- **Dataset:** an offline evaluator on experiments over that dataset.

Read the agent code in the user's repo and a sample of its recent traces in LangSmith (see `langsmith-trace`), or, for a dataset, its examples and recent experiment runs. Reuse any agent, environment, tracing project, dataset, trace link or code location already supplied in the conversation, selected target, or local project configuration. Do not assume the project is named `Dev` or require a separate Dev project when a tracing target is already supplied. Note what is still missing:

- **Code:** its repository path or entry point.
- **Traces:** a development (Dev) tracing project or a representative trace link.

From the traces, note the fields the evaluator could read and roughly how large they are (about 4 characters per token); input size decides the model (see Choose models).

## Decide what to measure

Agree on two things before writing the evaluator: **what to measure**, and whether to score **each run or whole threads** (conversations).

If the user has said what to measure, use it. If not, suggest a starting evaluator instead of only asking. Classify the agent from its code (system prompt, tools, entry point) and traces or dataset examples (what users ask, what it returns), then suggest the default for that type:

| Agent type | Examples | Default evaluator |
| --- | --- | --- |
| Customer service | Support chatbots, help desks | User satisfaction / frustration |
| Research & data analysis | Report writers, SQL or data Q&A, RAG over documents | Hallucination |
| Internal productivity | Ops assistants, ticket triage, workflow automation | Task completion |
| Code generation | Coding agents, code review, text-to-code | Code correctness |
| Content generation | Copywriting, summaries, drafts | User satisfaction / frustration |
| Sales / marketing automation | Lead research, outreach, CRM updates | Task completion |
| Other | Anything else | Hallucination |

- **User satisfaction / frustration:** a decision model reads the conversation and scores how frustrated the user is (`Score`) and whether they ended satisfied (`Noul`). Add code around it when needed, such as building a transcript from the thread's turns. Usually scores threads.
- **Hallucination:** whether every factual claim in the output is supported by the sources the agent had: retrieved documents, tool outputs, query results. A code node gathers those sources from the run; a decision model checks the output against them.
- **Task completion:** whether the agent did what was asked. A decision model by default; an LLM judge with a reasoning model when completion means checking several steps or tool results.
- **Code correctness:** code checks first (the generated code parses; test, lint or build tool calls in the trace succeeded), then an LLM judge with a reasoning model on whether the change does what was asked. A failed code check scores 0.

Add a second evaluator only for a failure the traces clearly show, such as repeated tool errors.

Ask one question that includes the suggestion and why it fits (the agent type and the evidence), runs or threads, and any missing code or tracing context from Gather context. Wait for the answer before writing the evaluator.

Then pin down the data:

- **Runs:** confirm the exact fields in `run.inputs` and `run.outputs`.
- **Threads:** choose the input representation: raw `thread`, `all_messages`, `human_ai_pairs`, or `first_human_last_ai`, and inspect representative data in that format. For raw `thread`, confirm the fields needed in each root run's `inputs` and `outputs` in `thread.runs`.
- **Dataset:** also confirm its `example.outputs`.

## Choose models

Pick the cheapest node type that can make each judgement:

1. **Code** for anything deterministic: parsing, matching, counting, tool-call checks.
2. **Decision model** for yes/no, scale and choice judgements. Cheaper and faster than an LLM judge, with calibrated probabilities. Choose by the size of the state each question reads:
   - **Under 32K tokens** (and the whole request under 64K): Jev, `model="typesafe:jev-latest"`.
   - **Over 32K tokens:** Jev with the long-context header (up to 262K tokens; slower and somewhat less accurate), or OpenAI Decisions. First consider trimming the state in a code node, for example to the final answer and the sources it cites.
3. **LLM judge** when the judgement needs reasoning: multi-step checks, math, comparing code against a request, or a written rationale. Use a reasoning model from whichever provider the user has keys for, such as `openai:gpt-5.5` or `anthropic:claude-opus-5` (Opus over Sonnet), but not a top-tier model like `claude-fable-5-1`: an evaluator runs on every run it scores, so pick the cheapest model that reasons well enough.

Optimize for cost throughout. If the user cares most about cost, build on decision models and code, and keep LLM judges to the nodes that need reasoning.

Jev with the long-context header:

```python
import httpx2
from langchain_typesafe import TypeSafeClassifier

grounded = DecisionModel(
    model=TypeSafeClassifier(
        model="jev-latest",
        client=httpx2.Client(timeout=120, headers={"TypeSafe-Danger-Zone-Long-Context": "true"}),
    ),
    inputs={"answer": Run.outputs.answer, "sources": sources.text},
    questions={"grounded": Noul(instructions="Is every factual claim in the answer supported by the sources?")},
    description="Checks the answer's claims against the sources",
)
```

For OpenAI Decisions, pass `model=OpenAIClassifier(model="gpt-6-luna")` instead (`from langchain_openai.decisions import OpenAIClassifier`), with `OPENAI_API_KEY` set.

## Write the graph

```bash
pip install "openevals==0.2.5"   # openevals[typesafe] for Jev; add langchain-<provider> for judges other than OpenAI
```

Set the provider keys the graph calls (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `TYPESAFE_API_KEY` for Jev). Never write a key into the evaluator file.

### Nodes

Make a node only for a meaningful step; keep small helpers as plain functions. One node is fine. Every node is a top-level name in the file, so LangSmith can read the graph from the source.

- **Code:** a function decorated with `@node` that returns a dict. A parameter named `run`, `thread`, `trajectory` or `example` (or annotated `Run`, `Thread`, `Trajectory`, `Example`) gets that context. A parameter named after another node gets that node's outputs.
- **LLM judge:** `LLM(model="<provider>:<model>", prompt=..., inputs={...}, output_schema=...)`. `prompt` is a string or a list of `(role, content)` messages with `{{name}}` placeholders. `output_schema` is a TypedDict or Pydantic class defined in the file, or a JSON schema; without one the node returns `{"score": number}`, and `feedback_key` renames that key.
- **Decision model:** `DecisionModel(model=..., inputs={...}, questions={...})`. `model` is required: `"typesafe:jev-latest"`, or any `langchain_core.decisions.BaseDecisionModel` instance (see Choose models). It takes no prompt; its inputs are the state it judges, so each question names the inputs it compares. Each question key is an output of the node.

Questions are `langchain_core.decisions` types, re-exported by `openevals.graph`, and take keyword arguments only:

```python
Noul(instructions="Does the answer address the question?")          # probability of yes
Score(instructions="How helpful is it?", criteria=["poor", "ok", "great"])  # index into criteria
Choice(instructions="Tone", criteria={"calm": None, "rude": None})   # chosen label
```

`inputs` maps each name to a typed reference, never a string: `Run.inputs.question`, `Run.outputs.answer`, `Example.outputs.reference`, or another node's output like `tool_usage.calls`.

### Rules for LangSmith

- Give each `LLM` and `DecisionModel` a `description="..."`, and a code node a docstring, so LangSmith can label the nodes; add `display_name="..."` when a name doesn't read well as a label.
- Write their arguments inline as literals (only `prompt` may name a top-level constant, and `output_schema` a class in the file), not computed values like f-strings.
- List every node in one `Graph([...])`.
- Define `evaluate(ctx)` and return exactly a `score` and optional `comment`, so the feedback is named after the evaluator.
- LangSmith sends each workspace secret with the model calls, so the file never holds a key; the clients still need some key to start, so set a placeholder at the top of the file.

### Example

A complete file that runs both locally and inside LangSmith:

```python
import os

for key in ("ANTHROPIC_API_KEY", "TYPESAFE_API_KEY"):
    os.environ.setdefault(key, "set-by-langsmith")

from openevals.graph import Choice, DecisionModel, Graph, LLM, Noul, Run, node

judge = LLM(
    model="anthropic:claude-opus-5",
    prompt="Check each step of this answer's reasoning. Score 0 to 1 for how sound it is: {{answer}}",
    inputs={"answer": Run.outputs.answer},
    description="Judges whether the answer's reasoning holds up",
)
checks = DecisionModel(
    model="typesafe:jev-latest",
    inputs={"question": Run.inputs.question, "answer": Run.outputs.answer},
    questions={
        "on_topic": Noul(instructions="Does the answer address the question?"),
        "tone": Choice(instructions="Tone", criteria={"calm": None, "rude": None}),
    },
    description="Checks the answer is on topic and calm",
)


@node
def answer(judge, checks):
    """Scores 0 unless the answer is on topic and calm."""
    ok = checks["on_topic"] > 0.5 and checks["tone"] == "calm"
    return {"score": judge["score"] if ok else 0}


graph = Graph([judge, checks, answer])


def evaluate(ctx):
    results = graph.run(ctx)
    return {"score": results[answer]["score"]}
```

`Graph([...])` checks the wiring when it is built: a parameter that names no listed node, an output a node does not produce, or a cycle raises `ValueError` before any model is called. Nodes run after the nodes they read, whatever order they are listed in.

### Threads

To score whole threads, read the thread instead of `Run`. For the folded formats (`all_messages`, `human_ai_pairs`, `first_human_last_ai`), read the selected string through a code node's `ctx` parameter (for example, `ctx.all_messages`). For raw `thread`, a code node's `thread` parameter gets `thread_id`, `session_id` and `runs`, the thread's root runs in order, each with its `inputs` and `outputs`. Build what a judge needs in a code node:

```python
@node
def transcript(thread):
    """Joins the thread's turns in order."""
    turns = [f"User: {r.inputs.question}\nAssistant: {r.outputs.answer}" for r in thread.runs]
    return {"text": "\n\n".join(turns)}


frustration = DecisionModel(
    model="typesafe:jev-latest",
    inputs={"conversation": transcript.text},
    questions={
        "frustration": Score(
            instructions="How frustrated is the user by the end of the conversation?",
            criteria=["Not frustrated", "Mildly frustrated", "Very frustrated"],
        ),
        "satisfied": Noul(instructions="Did the user end the conversation satisfied?"),
    },
    description="Reads the user's frustration and satisfaction",
)
```

## Test it locally

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

- `dependencies` is one package per line: pin `openevals==0.2.5` (`openevals[typesafe]==0.2.5` when the file has a Jev decision model, as in this example), add `langchain-<provider>` for each judge provider other than OpenAI, and `langchain-openai>=1.8.1` for OpenAI Decisions.
- `workspace_secrets_keys` names the provider keys the file calls, matching the placeholders at the top of the file.
- **Runs** (the default): leave out `code_evaluator_input`.
- **Threads:** set `code_evaluator_input` in `code_evaluator` to `thread`, `all_messages`, `human_ai_pairs`, or `first_human_last_ai`. Only the selected representation is populated. A thread evaluator can only be attached to threads, and a run evaluator only to runs.

Then attach the evaluator to the tracing project (online) or dataset (offline). To change it later, `PATCH <LangSmith API URL>/v1/platform/evaluators/<id>` with `{"code_evaluator": {"code": "<the whole Python file>"}}`.
