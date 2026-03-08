# Autoresearch for Agents

> Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — but instead of optimizing ML training code, we optimize **agents** using [LangSmith](https://smith.langchain.com/) observability and evals.

## The Idea

Give an AI coding agent a working agent implementation and an evaluation dataset. Let it experiment autonomously: modify the agent code, run evals, check if scores improved, keep or discard, and repeat. You wake up in the morning to a log of experiments and (hopefully) a better agent.

```
┌─────────────────────────────────────────────────────┐
│                  EXPERIMENT LOOP                     │
│                                                      │
│  1. Read agent.py + results so far                   │
│  2. Propose a change (prompt, tools, architecture)   │
│  3. Edit agent.py                                    │
│  4. git commit                                       │
│  5. Run evaluation: python run_eval.py               │
│  6. Parse scores from eval output                    │
│  7. If improved → keep commit                        │
│     If worse   → git reset  (discard)                │
│  8. Log result to results.tsv                        │
│  9. Repeat forever                                   │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Comparison with Karpathy's autoresearch

| | karpathy/autoresearch | autoresearch for agents |
|---|---|---|
| **What's optimized** | ML training code (`train.py`) | Agent code (`agent.py`) |
| **Metric** | `val_bpb` (lower is better) | Eval score (higher is better) |
| **Evaluation** | Fixed 5-min training run | LangSmith evaluation pipeline |
| **Observability** | Training logs | LangSmith traces |
| **What the agent edits** | Model architecture, optimizer, hyperparams | Prompts, tools, agent architecture |
| **What's fixed** | `prepare.py` (data, eval) | `run_eval.py` (eval harness), `dataset.json` |

## Project Structure

```
agent.py        — the agent implementation (THIS IS WHAT GETS OPTIMIZED)
run_eval.py     — evaluation harness using LangSmith (do not modify)
dataset.json    — evaluation dataset (do not modify)
program.md      — instructions for the AI coding agent
results.tsv     — experiment log (auto-generated)
```

## Quick Start

### Prerequisites

- Python 3.10+
- A [LangSmith API key](https://smith.langchain.com/)
- An [OpenAI API key](https://platform.openai.com/) (or Anthropic, etc.)

### Setup

```bash
# 1. Install dependencies
pip install langsmith langchain langchain-openai langgraph

# 2. Set environment variables
export LANGSMITH_API_KEY=<your-key>
export LANGSMITH_TRACING=true
export OPENAI_API_KEY=<your-key>

# 3. Verify the baseline agent works
python agent.py "What is the capital of France?"

# 4. Run a single evaluation
python run_eval.py
```

### Running the Autonomous Agent

Point your coding agent (Claude Code, Cursor, Codex, etc.) at this directory and prompt:

```
Read program.md and let's kick off a new experiment! Do the setup first.
```

The coding agent will then autonomously iterate on `agent.py`, running evals and tracking results.

## How It Works

### The Agent (`agent.py`)

A simple ReAct agent built with LangGraph. It has:
- A system prompt (tune this!)
- A set of tools (add/remove/modify these!)
- An agent architecture (change this!)

Everything in `agent.py` is fair game for the coding agent to modify.

### The Evaluation (`run_eval.py`)

Uses LangSmith's `evaluate()` to run the agent against a fixed dataset and score it with multiple evaluators:
- **Correctness**: Does the answer match the expected output?
- **Helpfulness**: Is the response helpful and well-structured?
- **Tool Usage**: Did the agent use tools appropriately?

All traces are sent to LangSmith for full observability.

### The Dataset (`dataset.json`)

A fixed set of test cases with inputs and expected outputs. The coding agent cannot modify this — it's the ground truth.

## Customization

This example uses a simple Q&A agent with a web search tool. To adapt it for your own agent:

1. **Replace `agent.py`** with your agent implementation
2. **Replace `dataset.json`** with your evaluation cases
3. **Update evaluators in `run_eval.py`** to match your quality criteria
4. **Update `program.md`** to guide the coding agent on what to optimize

## License

MIT
