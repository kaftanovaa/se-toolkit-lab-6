#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with fields: answer, tool_calls
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv


def load_env() -> None:
    """Load environment variables from .env.agent.secret."""
    env_file = Path(__file__).parent / ".env.agent.secret"
    if not env_file.exists():
        print(f"Error: {env_file} not found", file=sys.stderr)
        sys.exit(1)
    load_dotenv(env_file)


def get_env_vars() -> dict[str, str]:
    """Get required environment variables."""
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    if not api_key:
        print("Error: LLM_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not api_base:
        print("Error: LLM_API_BASE not set", file=sys.stderr)
        sys.exit(1)
    if not model:
        print("Error: LLM_MODEL not set", file=sys.stderr)
        sys.exit(1)

    return {
        "api_key": api_key,
        "api_base": api_base,
        "model": model,
    }


def call_lllm(question: str, api_key: str, api_base: str, model: str) -> str:
    """
    Call the LLM API and return the answer.

    Args:
        question: The user's question
        api_key: LLM API key
        api_base: LLM API base URL
        model: Model name to use

    Returns:
        The LLM's answer text
    """
    url = f"{api_base}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question},
        ],
        "temperature": 0.7,
    }

    print(f"Calling LLM API at {url}...", file=sys.stderr)

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()

    data = response.json()

    try:
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        print(f"Error: Unexpected API response format: {e}", file=sys.stderr)
        print(f"Response: {data}", file=sys.stderr)
        sys.exit(1)

    return answer


def main() -> None:
    """Main entry point."""
    # Parse command-line arguments
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load environment
    load_env()
    env_vars = get_env_vars()

    # Call LLM
    answer = call_lllm(
        question=question,
        api_key=env_vars["api_key"],
        api_base=env_vars["api_base"],
        model=env_vars["model"],
    )

    # Format output
    output = {
        "answer": answer,
        "tool_calls": [],
    }

    # Output JSON to stdout (only valid JSON, no extra whitespace)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
