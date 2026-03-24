---
name: langsmith-trace
description: "Query and export LangSmith traces for debugging and analysis. Use when working with LangSmith tracing, querying traces, or exporting trace data. Covers adding tracing to applications and querying/exporting via the langsmith CLI tool."
---

## Setup

```bash
LANGSMITH_API_KEY=lsv2_pt_your_api_key_here
LANGSMITH_PROJECT=your-project-name
LANGSMITH_WORKSPACE_ID=your-workspace-id  # Optional
```

IMPORTANT: Always check `.env` for `LANGSMITH_PROJECT` before querying. This tells you which project contains the relevant traces.

CLI Tool:
```bash
curl -sSL https://raw.githubusercontent.com/langchain-ai/langsmith-cli/main/scripts/install.sh | sh
```

## Adding Tracing

### LangChain/LangGraph (automatic)
```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=<your-api-key>
```

### Non-LangChain (Python)
```python
from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI

client = wrap_openai(OpenAI())

@traceable
def my_llm_pipeline(question: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": question}],
    )
    return resp.choices[0].message.content

@traceable
def rag_pipeline(question: str) -> str:
    docs = retrieve_docs(question)
    return generate_answer(question, docs)
```

### Non-LangChain (TypeScript)
```typescript
import { traceable } from "langsmith/traceable";
import { wrapOpenAI } from "langsmith/wrappers";
import OpenAI from "openai";

const client = wrapOpenAI(new OpenAI());

const myLlmPipeline = traceable(async (question: string): Promise<string> => {
  const resp = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [{ role: "user", content: question }],
  });
  return resp.choices[0].message.content || "";
}, { name: "my_llm_pipeline" });
```

Best Practices:
- Apply traceable to all nested functions you want visible in LangSmith
- Wrapped clients auto-trace all calls
- Name your traces for easier filtering
- Add metadata for searchability

## Traces vs Runs

- **Trace** = Complete execution tree (root run + all children). One full agent invocation.
- **Run** = Single node in the tree (one LLM call, one tool call, etc.)

Generally, query traces first — they provide complete context.

## CLI Command Structure

```
langsmith
├── trace list|get|export    (full hierarchy, filters on root run)
├── run list|get|export      (flat list, filters on any run, supports --run-type)
├── dataset list|get|create|delete|export|upload
├── example list|create|delete
├── evaluator list|upload|delete
├── experiment list|get
├── thread list|get
└── project list
```

## Querying Traces

```bash
# List recent traces
langsmith trace list --limit 10 --project my-project

# With metadata (timing, tokens, costs)
langsmith trace list --limit 10 --include-metadata

# Filter by time
langsmith trace list --last-n-minutes 60
langsmith trace list --since 2025-01-20T10:00:00Z

# Get specific trace with full hierarchy
langsmith trace get <trace-id>

# Show hierarchy inline
langsmith trace list --limit 5 --show-hierarchy

# Export traces to JSONL (one file per trace)
langsmith trace export ./traces --limit 20 --full

# Performance filters
langsmith trace list --min-latency 5.0 --limit 10    # Slow traces
langsmith trace list --error --last-n-minutes 60     # Failed traces

# List specific run types (flat)
langsmith run list --run-type llm --limit 20
```

## Filters

All commands support these filters (AND together):

Basic: `--trace-ids`, `--limit`, `--project`, `--last-n-minutes`, `--since`, `--error/--no-error`, `--name`

Performance: `--min-latency`, `--max-latency`, `--min-tokens`, `--tags`

Advanced: `--filter QUERY` for raw LangSmith filter queries:
```bash
langsmith trace list --filter 'and(eq(feedback_key, "correctness"), gte(feedback_score, 0.8))'
```

## Export Format

JSONL files with fields: `run_id`, `trace_id`, `name`, `run_type`, `parent_run_id`, `inputs`, `outputs`

Use `--include-io` or `--full` to include inputs/outputs.

## Tips
- Start with traces — they provide complete context for datasets
- Use `traces export --full` for bulk data
- Always specify `--project` to avoid mixing data
- Use `/tmp` for temporary exports
- Stitch files: `cat ./traces/*.jsonl > all.jsonl`
