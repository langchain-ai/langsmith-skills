---
name: langsmith-dataset
description: "Create evaluation datasets, upload datasets to LangSmith, or manage existing datasets. Covers dataset types (final_response, single_step, trajectory, RAG), CLI management commands, SDK-based creation, and example management. Uses the langsmith CLI tool."
---

## Setup

```bash
LANGSMITH_API_KEY=lsv2_pt_your_api_key_here
LANGSMITH_PROJECT=your-project-name
```

IMPORTANT: Always check `.env` for `LANGSMITH_PROJECT` before querying.

Dependencies:
```bash
pip install langsmith          # Python
npm install langsmith          # JavaScript
```

CLI Tool:
```bash
curl -sSL https://raw.githubusercontent.com/langchain-ai/langsmith-cli/main/scripts/install.sh | sh
```

## Dataset Types

- **final_response** — Full conversation with expected output. Tests complete agent behavior.
- **single_step** — Single node inputs/outputs. Tests specific node behavior.
- **trajectory** — Tool call sequence. Tests execution path.
- **rag** — Question/chunks/answer/citations. Tests retrieval quality.

## CLI Commands

```bash
# Datasets
langsmith dataset list
langsmith dataset get <name-or-id>
langsmith dataset create --name <name>
langsmith dataset delete <name-or-id>
langsmith dataset export <name-or-id> <output-file>
langsmith dataset upload <file> --name <name>

# Examples
langsmith example list --dataset <name>
langsmith example create --dataset <name> --inputs <json>
langsmith example delete <example-id>

# Experiments
langsmith experiment list --dataset <name>
langsmith experiment get <name>
```

SAFETY: CLI prompts for confirmation before destructive operations. NEVER use `--yes` unless user explicitly requests it.

## Creating Datasets from Traces

### Step 1: Export traces
```bash
langsmith trace export ./traces --project my-project --limit 20 --full
```

### Step 2: Process into dataset (Python)
```python
import json
from pathlib import Path
from langsmith import Client

client = Client()
examples = []
for jsonl_file in Path("./traces").glob("*.jsonl"):
    runs = [json.loads(line) for line in jsonl_file.read_text().strip().split("\n")]
    root = next((r for r in runs if r.get("parent_run_id") is None), None)
    if root and root.get("inputs") and root.get("outputs"):
        examples.append({
            "trace_id": root.get("trace_id"),
            "inputs": root["inputs"],
            "outputs": root["outputs"]
        })

with open("/tmp/dataset.json", "w") as f:
    json.dump(examples, f, indent=2)
```

### Step 2 (TypeScript alternative)
```typescript
import { readFileSync, writeFileSync, readdirSync } from "fs";
import { join } from "path";

const examples = [];
const files = readdirSync("./traces").filter(f => f.endsWith(".jsonl"));
for (const file of files) {
  const lines = readFileSync(join("./traces", file), "utf-8").trim().split("\n");
  const runs = lines.map(line => JSON.parse(line));
  const root = runs.find(r => r.parent_run_id == null);
  if (root?.inputs && root?.outputs) {
    examples.push({ trace_id: root.trace_id, inputs: root.inputs, outputs: root.outputs });
  }
}
writeFileSync("/tmp/dataset.json", JSON.stringify(examples, null, 2));
```

### Step 3: Upload
```bash
langsmith dataset upload /tmp/dataset.json --name "My Evaluation Dataset"
```

### Using SDK Directly (Python)
```python
from langsmith import Client

client = Client()
dataset = client.create_dataset("My Dataset", description="Evaluation dataset")
client.create_examples(
    inputs=[{"query": "What is AI?"}, {"query": "Explain RAG"}],
    outputs=[{"answer": "AI is..."}, {"answer": "RAG is..."}],
    dataset_name="My Dataset",
)
```

### Using SDK Directly (TypeScript)
```typescript
import { Client } from "langsmith";

const client = new Client();
const dataset = await client.createDataset("My Dataset", { description: "Evaluation dataset" });
await client.createExamples({
  inputs: [{ query: "What is AI?" }, { query: "Explain RAG" }],
  outputs: [{ answer: "AI is..." }, { answer: "RAG is..." }],
  datasetName: "My Dataset",
});
```

## Dataset Structures

### Final Response
```json
{"trace_id": "...", "inputs": {"query": "What are the top genres?"}, "outputs": {"response": "The top genres are..."}}
```

### Trajectory
```json
{"trace_id": "...", "inputs": {"query": "..."}, "outputs": {"expected_trajectory": ["tool_a", "tool_b", "tool_c"]}}
```

### RAG
```json
{"trace_id": "...", "inputs": {"question": "How do I..."}, "outputs": {"answer": "...", "retrieved_chunks": ["..."], "cited_chunks": ["..."]}}
```

## Complete Workflow

```bash
# 1. Export traces
langsmith trace export ./traces --project my-project --limit 20 --full

# 2. Process traces into dataset format (Python/JS code above)

# 3. Upload
langsmith dataset upload /tmp/final_response.json --name "Skills: Final Response"

# 4. Verify
langsmith dataset list
langsmith dataset get "Skills: Final Response"
langsmith example list --dataset "Skills: Final Response" --limit 3
```

## Troubleshooting

- **Upload fails**: Verify API key, check JSON validity (needs `inputs` key), dataset name must be unique
- **Empty dataset**: Verify JSON has array of objects with `inputs` key
- **Export has no data**: Ensure traces exported with `--full` flag
