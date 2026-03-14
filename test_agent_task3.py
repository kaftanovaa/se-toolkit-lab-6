"""
Regression tests for agent.py (Task 3) - System Agent.

Tests that agent.py:
1. Uses read_file for source code questions
2. Uses query_api for data questions
3. Returns correct answers with proper tool usage
"""

import json
import subprocess
import sys
from pathlib import Path


def run_agent(question: str) -> dict:
    """
    Run agent.py with a question and parse the output.
    
    Args:
        question: The question to ask
        
    Returns:
        Parsed JSON output
    """
    project_root = Path(__file__).parent
    agent_path = project_root / "agent.py"
    
    result = subprocess.run(
        [sys.executable, str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=120,
    )
    
    if result.returncode != 0:
        raise AssertionError(f"Agent failed: {result.stderr}")
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON output: {e}\nStdout: {result.stdout}")


def test_framework_question() -> None:
    """
    Test that asking about the backend framework uses read_file tool
    and returns FastAPI in the answer.
    """
    question = "What Python web framework does the backend use?"
    
    output = run_agent(question)
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check that tool_calls is populated
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "tool_calls should not be empty"
    
    # Check that read_file was used
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "read_file" in tools_used, f"read_file not in tool_calls: {tools_used}"
    
    # Check that answer contains FastAPI
    answer_lower = output["answer"].lower()
    assert "fastapi" in answer_lower, f"Expected 'fastapi' in answer, got: {output['answer']}"
    
    print(f"✓ Test passed: framework question", file=sys.stderr)


def test_database_count_question() -> None:
    """
    Test that asking about item count uses query_api tool.
    """
    question = "How many items are in the database?"
    
    output = run_agent(question)
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check that tool_calls is populated
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "tool_calls should not be empty"
    
    # Check that query_api was used
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "query_api" in tools_used, f"query_api not in tool_calls: {tools_used}"
    
    # Check that answer is non-empty
    assert len(output["answer"]) > 0, "Answer should not be empty"
    
    print(f"✓ Test passed: database count question", file=sys.stderr)


if __name__ == "__main__":
    # Run tests manually if executed directly
    print("Running test_framework_question...", file=sys.stderr)
    test_framework_question()
    
    print("Running test_database_count_question...", file=sys.stderr)
    test_database_count_question()
    
    print("All tests passed!", file=sys.stderr)
