"""
Regression tests for agent.py (Task 2) - Documentation Agent.

Tests that agent.py:
1. Uses tools (read_file, list_files) to answer questions
2. Returns correct source references
3. Populates tool_calls array
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


def test_git_workflow_question() -> None:
    """
    Test that asking about git workflow uses read_file tool
    and returns wiki/git-workflow.md in source.
    """
    question = "What is the Git workflow for tasks?"
    
    output = run_agent(question)
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check that tool_calls is populated
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "tool_calls should not be empty"
    
    # Check that read_file was used
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "read_file" in tools_used, f"read_file not in tool_calls: {tools_used}"
    
    # Check that source references git-workflow.md
    source = output["source"]
    assert "git-workflow.md" in source, f"Expected git-workflow.md in source, got: {source}"
    
    # Check that answer is non-empty
    assert len(output["answer"]) > 0, "Answer should not be empty"
    
    print(f"✓ Test passed", file=sys.stderr)


def test_wiki_files_question() -> None:
    """
    Test that asking about wiki files uses list_files tool.
    """
    question = "What files are in the wiki directory?"
    
    output = run_agent(question)
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    
    # Check that tool_calls is populated
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "tool_calls should not be empty"
    
    # Check that list_files was used
    tools_used = [tc["tool"] for tc in tool_calls]
    assert "list_files" in tools_used, f"list_files not in tool_calls: {tools_used}"
    
    # Check that answer is non-empty
    assert len(output["answer"]) > 0, "Answer should not be empty"
    
    print(f"✓ Test passed", file=sys.stderr)


if __name__ == "__main__":
    # Run tests manually if executed directly
    print("Running test_git_workflow_question...", file=sys.stderr)
    test_git_workflow_question()
    
    print("Running test_wiki_files_question...", file=sys.stderr)
    test_wiki_files_question()
    
    print("All tests passed!", file=sys.stderr)
