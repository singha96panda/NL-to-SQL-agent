"""
agent.py

The agentic loop: connects Claude to our two tools (get_schema, run_sql)
and lets it reason step-by-step to answer natural language questions
about the database.

Before running: set your API key as an environment variable:
    export ANTHROPIC_API_KEY="your-key-here"

Then run:
    python3 agent.py
"""

import os
import json
import time
import anthropic

from schema_tool import get_schema
from sql_tool import run_sql

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
MODEL = "claude-sonnet-4-5"

# ---------------------------------------------------------------------------
# STEP A: Describe our tools to Claude in the format it expects.
# This is the "menu" of actions Claude is allowed to take.
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "get_schema",
        "description": (
            "Returns the database schema: table names, column names, and types. "
            "Always call this FIRST before writing any SQL query, so you know "
            "the exact table and column names available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "run_sql",
        "description": (
            "Executes a read-only SQL SELECT query against the database and "
            "returns the results. If the query fails (e.g. wrong column name), "
            "the error message will be returned so you can fix and retry."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A single valid SQLite SELECT statement.",
                }
            },
            "required": ["query"],
        },
    },
]

SYSTEM_PROMPT = """You are a helpful data analyst agent. You answer natural
language questions by querying a SQLite database.

Rules you must follow:
1. ALWAYS call get_schema first if you haven't already seen the schema in this conversation.
2. Write SQLite-compatible SELECT queries only.
3. If a query fails, read the error message, fix the query, and try again. Do not give up after one failure.
4. Once you have the data you need, answer the user's question in plain, friendly English.
   Do not just dump raw rows -- summarize and explain what the data means.
5. If the question cannot be answered with the available tables, say so clearly.
"""


def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Maps a tool name to the actual Python function and runs it."""
    if tool_name == "get_schema":
        return {"schema": get_schema()}
    elif tool_name == "run_sql":
        return run_sql(tool_input["query"])
    else:
        return {"error": f"Unknown tool: {tool_name}"}


def call_claude_with_retry(messages, max_retries: int = 4):
    """
    Calls the Claude API with exponential backoff retry.
    Anthropic's servers occasionally return 529 (overloaded) or
    other transient errors -- this is normal and expected in production,
    not a bug in our code. We just wait a bit and try again.
    """
    for attempt in range(max_retries):
        try:
            return client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
        except anthropic.APIStatusError as e:
            # 529 = overloaded, 429 = rate limited, 500s = server errors
            if e.status_code in (529, 429, 500, 503) and attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s, 8s...
                print(f"   ⚠️  API busy ({e.status_code}), retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise  # give up and let the error surface after max_retries


def ask_agent(user_question: str, verbose: bool = True, trace: list = None) -> str:
    """
    Runs the full agent loop for a single user question.
    Returns the final natural-language answer.

    If a `trace` list is passed in, each tool call/result is appended to it
    as a dict -- this lets a UI (like our Streamlit app) show what the agent
    did step by step, instead of only the final answer.
    """
    messages = [{"role": "user", "content": user_question}]

    while True:
        response = call_claude_with_retry(messages)

        # Add Claude's response to the conversation history
        messages.append({"role": "assistant", "content": response.content})

        # Check if Claude wants to stop (no more tool calls) or keep going
        if response.stop_reason == "tool_use":
            # Claude wants to call one or more tools.
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if verbose:
                        print(f"\n🔧 Claude is calling tool: {block.name}")
                        print(f"   with input: {block.input}")

                    result = execute_tool(block.name, block.input)

                    if verbose:
                        print(f"   → result: {json.dumps(result)[:300]}")

                    if trace is not None:
                        trace.append({
                            "tool_name": block.name,
                            "tool_input": block.input,
                            "tool_result": result,
                        })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            # Send tool results back to Claude, loop continues
            messages.append({"role": "user", "content": tool_results})

        else:
            # No more tool calls -- Claude has a final answer.
            final_text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return final_text


if __name__ == "__main__":
    print("=== NL-to-SQL Agent ===")
    print("Type a question about the shop database, or 'quit' to exit.\n")

    while True:
        question = input("You: ").strip()
        if question.lower() in ("quit", "exit"):
            break
        if not question:
            continue

        answer = ask_agent(question)
        print(f"\n💬 Agent: {answer}\n")
