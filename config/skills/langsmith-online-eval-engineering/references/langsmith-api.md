# LangSmith online evaluator API

Evaluator management requires a current LangSmith SDK. At the time of this
guide, the documented minimums are Python `langsmith>=0.9.8` and TypeScript
`langsmith>=0.7.16`. Inspect the installed SDK before using these APIs.

```python
from langsmith import Client

client = Client()
```

The client reads LangSmith credentials and endpoint configuration from the
environment. Never hard-code them.

## Inspect traces

```python
import json

runs = list(
    client.list_runs(
        project_name=project_name,
        is_root=True,
        limit=5,
    )
)

for run in runs:
    print(run.id, run.name, run.run_type, run.status)
    print(json.dumps(run.inputs, default=str)[:2000])
    print(json.dumps(run.outputs, default=str)[:2000])
```

Inspect child runs or threads when the evaluator needs trajectory or
conversation evidence. Avoid printing full sensitive payloads.

## Create a code evaluator

Online code evaluators receive one run and return a mapping of feedback keys to
scores:

```python
import asyncio
import textwrap


evaluator_code = textwrap.dedent(
    """
    def perform_eval(run):
        outputs = run.get("outputs") or {}
        value = outputs.get("answer")
        return {"has_answer": bool(value)}
    """
)


async def create_code_evaluator():
    created = await client.evaluators.create(
        name="has-answer",
        type="code",
        code_evaluator={
            "code": evaluator_code,
            "language": "python",
        },
    )
    return created.evaluator.id


evaluator_id = asyncio.run(create_code_evaluator())
```

Code evaluators have no network access. Prefer the standard library; use only
packages explicitly allowed by the current runtime.

The reusable evaluator SDK may show a two-argument
`perform_eval(run, example)` because the same evaluator can be attached to a
dataset. Use the one-argument contract for an evaluator designed only for
online traces, and verify the installed runtime if one definition must support
both online and offline use.

## Create an LLM judge

The evaluator references a structured prompt in the LangSmith prompt hub:

```python
import asyncio


async def create_llm_evaluator():
    created = await client.evaluators.create(
        name="response-relevance",
        type="llm",
        llm_evaluator={
            "prompt_repo_handle": prompt_repo_handle,
            "commit_hash_or_tag": prompt_commit,
            "variable_mapping": {
                "question": "inputs.question",
                "answer": "outputs.answer",
            },
        },
    )
    return created.evaluator.id


evaluator_id = asyncio.run(create_llm_evaluator())
```

`prompt_repo_handle` is the internal repository handle, not the display title
or URL. Pin a reviewed commit for reproducibility; use a movable tag only when
updates should intentionally affect future evaluations.

The structured prompt's variables must exactly match the mapping keys. Its
schema should return a descriptive feedback key and put reasoning before the
score field.

## Manage evaluators

Evaluator operations are asynchronous:

```python
async def inspect_and_update(evaluator_id):
    evaluator = await client.evaluators.retrieve(evaluator_id)
    print(evaluator.name, evaluator.type, evaluator.feedback_keys)

    updated = await client.evaluators.update(
        evaluator_id,
        name="response-relevance-v2",
    )
    return updated.evaluator


async def list_matching():
    result = await client.evaluators.list(name="response")
    return list(result)


async def remove(evaluator_id):
    await client.evaluators.delete(
        evaluator_id,
        delete_run_rules=True,
    )
```

An evaluator is workspace-scoped. Updating it changes every attached project
and dataset. Deletion may also remove its rules; inspect attachments first.

## Attach to a tracing project

Creating an evaluator does not attach it. Create a run-level or thread-level
online rule through the supported LangSmith UI or current API. Configure:

- project and evaluator IDs;
- run or thread scope;
- filter expression;
- sampling rate;
- enabled state;
- optional creation-time backfill;
- LLM evaluator spend limit;
- scored-trace retention behavior.

The low-level run-rules endpoint and payload evolve faster than evaluator
management. When automating attachment, inspect the installed SDK and current
LangSmith API reference rather than copying an old payload. After creation,
retrieve the evaluator and confirm its rule reports the intended project,
filter, sampling rate, and enabled state.

Backfill is asynchronous and can be selected only when the rule is created.
Monitor evaluator logs for progress and failures.

## Update LLM runtime settings

Current LLM evaluators can use human score corrections as few-shot examples:

```python
await client.evaluators.update(
    evaluator_id,
    llm_evaluator={
        "prompt_repo_handle": prompt_repo_handle,
        "commit_hash_or_tag": prompt_commit,
        "variable_mapping": {
            "question": "inputs.question",
            "answer": "outputs.answer",
        },
        "use_corrections_dataset": True,
        "num_few_shot_examples": 3,
    },
)
```

Use corrections only after checking that the feedback policy and labels are
consistent. More examples do not repair an ambiguous rubric.
