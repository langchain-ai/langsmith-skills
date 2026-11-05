"""
Autoresearch agent — the file the coding agent optimizes.

This is a starting template using LangGraph. You can replace this entirely
with any agent implementation (plain OpenAI SDK, Anthropic, custom code, etc.)
as long as you preserve the function contract expected by run_eval.py.

Usage:
    python agent.py "What is 25 * 37?"
"""

import math
import sys

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# ---------------------------------------------------------------------------
# Tools (add, remove, or modify these)
# ---------------------------------------------------------------------------


def calculator(expression: str) -> str:
    """Evaluate a mathematical expression. Supports basic arithmetic, powers, roots, and common math functions."""
    allowed_names = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "pow": pow,
        "sqrt": math.sqrt,
        "pi": math.pi,
        "e": math.e,
        "log": math.log,
        "log10": math.log10,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
    }
    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def unit_converter(value: float, from_unit: str, to_unit: str) -> str:
    """Convert between common units. Supports temperature (C/F/K), distance (km/mi/m/ft), and weight (kg/lb)."""
    conversions = {
        ("km", "mi"): lambda v: v * 0.621371,
        ("mi", "km"): lambda v: v * 1.60934,
        ("m", "ft"): lambda v: v * 3.28084,
        ("ft", "m"): lambda v: v * 0.3048,
        ("kg", "lb"): lambda v: v * 2.20462,
        ("lb", "kg"): lambda v: v * 0.453592,
        ("c", "f"): lambda v: v * 9 / 5 + 32,
        ("f", "c"): lambda v: (v - 32) * 5 / 9,
        ("c", "k"): lambda v: v + 273.15,
        ("k", "c"): lambda v: v - 273.15,
        ("f", "k"): lambda v: (v - 32) * 5 / 9 + 273.15,
        ("k", "f"): lambda v: (v - 273.15) * 9 / 5 + 32,
    }
    key = (from_unit.lower(), to_unit.lower())
    if key in conversions:
        result = conversions[key](value)
        return f"{value} {from_unit} = {result:.2f} {to_unit}"
    return f"Error: Cannot convert from {from_unit} to {to_unit}"


# ---------------------------------------------------------------------------
# Agent configuration
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful assistant. Answer questions accurately and concisely.

When a question involves math, calculations, or unit conversions, use the
appropriate tool rather than computing in your head.

Always provide a direct answer to the question asked."""

MODEL = "gpt-4o-mini"
TEMPERATURE = 0

TOOLS = [calculator, unit_converter]

# ---------------------------------------------------------------------------
# Build the agent
# ---------------------------------------------------------------------------


def build_agent():
    """Build and return the agent graph."""
    llm = ChatOpenAI(model=MODEL, temperature=TEMPERATURE)
    return create_react_agent(llm, tools=TOOLS, prompt=SYSTEM_PROMPT)


# ---------------------------------------------------------------------------
# Functions called by run_eval.py
#
# run_agent_with_tools() is the contract with the eval harness. It must
# return a dict that the evaluators can score. If you replace the agent
# entirely, just make sure this function still returns the right shape.
# ---------------------------------------------------------------------------


def run_agent(question: str) -> str:
    """Run the agent on a single question and return the response text."""
    return run_agent_with_tools(question)["response"]


def run_agent_with_tools(question: str) -> dict:
    """Run the agent and return response + tool usage info for evaluation."""
    agent = build_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    messages = result["messages"]

    tools_used = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tools_used.append(tc["name"])

    return {
        "response": messages[-1].content,
        "tools_used": tools_used,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python agent.py <question>")
        sys.exit(1)
    question = " ".join(sys.argv[1:])
    print(run_agent(question))
