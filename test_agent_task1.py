"""
Regression test for agent.py (Task 1).

Tests that agent.py:
1. Runs successfully with a question argument
2. Outputs valid JSON to stdout
3. Contains required fields: answer, tool_calls
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_outputs_valid_json() -> None:
    """Test that agent.py outputs valid JSON with required fields."""
    # Path to agent.py in project root
    project_root = Path(__file__).parent
    agent_path = project_root / "agent.py"

    # Test question
    question = "What is 2 + 2?"

    # Run agent.py as subprocess
    # Use sys.executable to run agent.py directly (uv already activated the venv)
    result = subprocess.run(
        [sys.executable, str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=120,  # Give extra time for LLM response
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON output: {e}\nStdout: {result.stdout}")

    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Check field types
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must not be empty"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"
    assert len(output["tool_calls"]) == 0, "'tool_calls' must be empty for Task 1"

    print(f"✓ Agent output valid JSON: {output}", file=sys.stderr)
