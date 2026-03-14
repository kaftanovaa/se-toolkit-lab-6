#!/usr/bin/env python3
"""
Agent CLI - Documentation Agent with tools (read_file, list_files).

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with fields: answer, source, tool_calls
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Maximum tool calls per question
MAX_TOOL_CALLS = 10


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


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.resolve()


def validate_path(path: str) -> Path:
    """
    Validate that a path is within the project directory.
    
    Args:
        path: Relative path from project root
        
    Returns:
        Absolute path
        
    Raises:
        ValueError: If path traversal is detected
    """
    project_root = get_project_root()
    
    # Normalize the path (remove leading/trailing slashes)
    clean_path = path.strip("/\\")
    
    # Build full path
    full_path = (project_root / clean_path).resolve()
    
    # Check for path traversal
    if not str(full_path).startswith(str(project_root)):
        raise ValueError(f"Path traversal not allowed: {path}")
    
    return full_path


def tool_read_file(path: str) -> str:
    """
    Read a file from the project repository.
    
    Args:
        path: Relative path from project root
        
    Returns:
        File contents as string, or error message
    """
    try:
        validated_path = validate_path(path)
        
        if not validated_path.exists():
            return f"Error: File not found: {path}"
        
        if not validated_path.is_file():
            return f"Error: Not a file: {path}"
        
        return validated_path.read_text(encoding="utf-8")
        
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"


def tool_list_files(path: str) -> str:
    """
    List files and directories at a given path.
    
    Args:
        path: Relative directory path from project root
        
    Returns:
        Newline-separated listing of entries, or error message
    """
    try:
        validated_path = validate_path(path)
        
        if not validated_path.exists():
            return f"Error: Directory not found: {path}"
        
        if not validated_path.is_dir():
            return f"Error: Not a directory: {path}"
        
        entries = sorted(os.listdir(validated_path))
        return "\n".join(entries)
        
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error listing directory: {e}"


# Tool registry: name -> function
TOOLS = {
    "read_file": tool_read_file,
    "list_files": tool_list_files,
}


def get_system_prompt() -> str:
    """
    Get the system prompt for the documentation agent.
    
    Returns:
        System prompt string
    """
    return """You are a documentation assistant for a software engineering toolkit project.

Answer questions based on the provided documentation context.

When answering:
1. Provide a clear, concise answer
2. Include a source reference in the format: wiki/filename.md#section-anchor
3. If you don't know the answer, say so

Respond in plain text, not JSON."""


def call_llm(
    question: str,
    context: str,
    api_key: str,
    api_base: str,
    model: str,
) -> str:
    """
    Call the LLM API and return the answer.
    
    Args:
        question: User's question
        context: Context from tool results
        api_key: LLM API key
        api_base: LLM API base URL
        model: Model name
        
    Returns:
        The LLM's answer text
    """
    url = f"{api_base}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    user_content = question
    if context:
        user_content += f"\n\nRelevant documentation:\n{context}"
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.7,
    }
    
    print(f"Calling LLM API...", file=sys.stderr)
    
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


def extract_source_from_answer(answer: str) -> str:
    """
    Extract source reference from the answer.
    
    Args:
        answer: The LLM's answer text
        
    Returns:
        Source reference string (e.g., wiki/file.md#section)
    """
    # Look for patterns like wiki/filename.md or wiki/filename.md#anchor
    pattern = r"(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)"
    match = re.search(pattern, answer)
    
    if match:
        return match.group(1)
    
    return ""


def smart_answer_question(
    question: str,
    api_key: str,
    api_base: str,
    model: str,
) -> tuple[str, str, list[dict[str, Any]]]:
    """
    Answer a question using smart tool selection.
    
    Strategy:
    1. For questions about files/structure -> call list_files on wiki/
    2. For specific questions -> read relevant wiki files
    3. Pass context to LLM for final answer
    
    Args:
        question: User's question
        api_key: LLM API key
        api_base: LLM API base URL
        model: Model name
        
    Returns:
        Tuple of (answer, source, tool_calls)
    """
    tool_calls: list[dict[str, Any]] = []
    context_parts: list[str] = []
    
    question_lower = question.lower()
    
    # Determine which tools to call based on question
    # For wiki-related questions, explore wiki directory
    
    # Step 1: List wiki directory
    print("Executing tool: list_files(wiki/)", file=sys.stderr)
    wiki_files_result = tool_list_files("wiki")
    tool_calls.append({
        "tool": "list_files",
        "args": {"path": "wiki"},
        "result": wiki_files_result,
    })
    context_parts.append(f"Wiki files:\n{wiki_files_result}")
    
    # Step 2: Determine which files to read based on question
    files_to_read: list[str] = []
    
    # Keywords mapping to files
    keyword_file_map = {
        "merge": ["wiki/git-workflow.md"],
        "conflict": ["wiki/git-workflow.md"],
        "git": ["wiki/git-workflow.md", "wiki/git.md"],
        "branch": ["wiki/git-workflow.md", "wiki/git.md"],
        "commit": ["wiki/git-workflow.md", "wiki/git.md"],
        "api": ["wiki/api.md", "wiki/rest-api.md", "wiki/web-api.md"],
        "rest": ["wiki/rest-api.md", "wiki/api.md"],
        "database": ["wiki/database.md", "wiki/postgresql.md", "wiki/sql.md"],
        "docker": ["wiki/docker.md", "wiki/docker-compose.md"],
        "python": ["wiki/python.md", "wiki/pyproject-toml.md"],
        "file": ["wiki/file-system.md", "wiki/file-formats.md"],
        "vm": ["wiki/vm.md", "wiki/vm-autochecker.md"],
        "linux": ["wiki/linux.md", "wiki/bash.md", "wiki/shell.md"],
        "test": ["wiki/quality-assurance.md"],
        "qa": ["wiki/quality-assurance.md"],
        "security": ["wiki/security.md"],
        "http": ["wiki/http.md", "wiki/rest-api.md"],
        "frontend": ["wiki/frontend.md"],
        "backend": ["wiki/backend.md", "wiki/api.md"],
    }
    
    for keyword, files in keyword_file_map.items():
        if keyword in question_lower:
            for f in files:
                if f not in files_to_read:
                    files_to_read.append(f)
    
    # If no specific files matched, read common files
    if not files_to_read:
        # Read a few key files for general questions
        files_to_read = ["wiki/git-workflow.md", "wiki/api.md", "wiki/backend.md"]
    
    # Step 3: Read relevant files
    for file_path in files_to_read[:5]:  # Limit to 5 files
        print(f"Executing tool: read_file({file_path})", file=sys.stderr)
        file_content = tool_read_file(file_path)
        if not file_content.startswith("Error:"):
            tool_calls.append({
                "tool": "read_file",
                "args": {"path": file_path},
                "result": file_content[:3000],  # Truncate long files
            })
            context_parts.append(f"=== {file_path} ===\n{file_content[:3000]}")
    
    # Step 4: Get answer from LLM with context
    context = "\n\n".join(context_parts)
    answer = call_llm(
        question=question,
        context=context,
        api_key=api_key,
        api_base=api_base,
        model=model,
    )
    
    # Extract source
    source = extract_source_from_answer(answer)
    
    # If no source extracted, use first file read
    if not source and tool_calls:
        for tc in tool_calls:
            if tc["tool"] == "read_file":
                source = tc["args"].get("path", "")
                break
    
    return answer, source, tool_calls


def main() -> None:
    """Main entry point."""
    # Set stdout to UTF-8 for proper Unicode handling
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    # Parse command-line arguments
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    # Load environment
    load_env()
    env_vars = get_env_vars()
    
    # Answer question with tools
    answer, source, tool_calls = smart_answer_question(
        question=question,
        api_key=env_vars["api_key"],
        api_base=env_vars["api_base"],
        model=env_vars["model"],
    )
    
    # Format output
    output = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls,
    }
    
    # Output JSON to stdout
    print(json.dumps(output, ensure_ascii=False, indent=None))


if __name__ == "__main__":
    main()
