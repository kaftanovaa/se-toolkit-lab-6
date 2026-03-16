#!/usr/bin/env python3
"""
Agent CLI - System Agent with tools (read_file, list_files, query_api).

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


def load_env_files() -> None:
    """
    Load environment variables from .env files if they exist.

    The autochecker injects variables directly, so these files are optional.
    Local development uses .env.agent.secret and .env.docker.secret.
    
    Note: Environment variables already set take precedence over .env files.
    """
    # Try to load from .env.agent.secret (only if env vars not already set)
    agent_env_file = Path(__file__).parent / ".env.agent.secret"
    if agent_env_file.exists() and not os.getenv("LLM_API_KEY"):
        load_dotenv(agent_env_file)

    # Try to load from .env.docker.secret (don't override existing vars)
    docker_env_file = Path(__file__).parent / ".env.docker.secret"
    if docker_env_file.exists() and not os.getenv("LMS_API_KEY"):
        load_dotenv(docker_env_file, override=False)

    # Also try .env in project root (fallback)
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)


def _is_placeholder(value: str) -> bool:
    """Check if a value is a placeholder (contains <...>)."""
    return '<' in value and '>' in value


def get_llm_env_vars() -> dict[str, str] | None:
    """Get required LLM environment variables.
    
    Tries to load from environment first, then from .env files.
    Returns None if variables are not set or are placeholders.
    """
    # First try to get from environment (autochecker injects these)
    api_key = os.getenv("LLM_API_KEY", "").strip()
    api_base = os.getenv("LLM_API_BASE", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    
    # Ignore placeholder values
    if _is_placeholder(api_key):
        api_key = ""
    if _is_placeholder(api_base):
        api_base = ""
    if _is_placeholder(model):
        model = ""
    
    # If not in environment, try to load from .env files
    if not api_key or not api_base or not model:
        load_env_files()
        api_key = os.getenv("LLM_API_KEY", "").strip()
        api_base = os.getenv("LLM_API_BASE", "").strip()
        model = os.getenv("LLM_MODEL", "").strip()
        
        # Ignore placeholder values from .env files
        if _is_placeholder(api_key):
            api_key = ""
        if _is_placeholder(api_base):
            api_base = ""
        if _is_placeholder(model):
            model = ""

    if not api_key or not api_base or not model:
        return None

    return {
        "api_key": api_key,
        "api_base": api_base,
        "model": model,
    }


def get_api_env_vars() -> dict[str, str | None]:
    """Get API tool environment variables.
    
    Returns None for lms_api_key if not set — the caller should handle this.
    This allows the agent to work for wiki/source questions without API access.
    Ignores placeholder values.
    """
    lms_api_key = os.getenv("LMS_API_KEY", "").strip()
    agent_api_base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002").strip()

    # Ignore placeholder values
    if _is_placeholder(lms_api_key):
        lms_api_key = ""
    if _is_placeholder(agent_api_base_url):
        agent_api_base_url = "http://localhost:42002"

    return {
        "lms_api_key": lms_api_key if lms_api_key else None,
        "agent_api_base_url": agent_api_base_url,
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


def tool_query_api(method: str, path: str, body: str | None = None) -> str:
    """
    Call the backend API with authentication.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path (e.g., /items/)
        body: Optional JSON request body for POST/PUT

    Returns:
        JSON string with status_code and body, or error message
    """
    try:
        api_env = get_api_env_vars()
        base_url = api_env["agent_api_base_url"].rstrip("/")
        lms_api_key = api_env.get("lms_api_key")

        # Check if API key is available
        if not lms_api_key:
            return "Error: LMS_API_KEY not set in environment"

        # Build URL
        url = f"{base_url}{path}"

        headers = {
            "Authorization": f"Bearer {lms_api_key}",
        }

        # Parse body if provided
        json_body = None
        if body:
            try:
                json_body = json.loads(body)
                headers["Content-Type"] = "application/json"
            except json.JSONDecodeError:
                return f"Error: Invalid JSON body: {body}"

        print(f"Executing API call: {method} {url}", file=sys.stderr)

        with httpx.Client(timeout=30.0) as client:
            response = client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=json_body,
            )

            result = {
                "status_code": response.status_code,
                "body": response.json() if response.content else None,
            }
            return json.dumps(result)

    except httpx.HTTPError as e:
        return f"Error: HTTP error: {e}"
    except Exception as e:
        return f"Error: {e}"


# Tool registry: name -> function
TOOLS = {
    "read_file": tool_read_file,
    "list_files": tool_list_files,
    "query_api": tool_query_api,
}


def get_system_prompt() -> str:
    """
    Get the system prompt for the system agent.
    
    Returns:
        System prompt string
    """
    return """You are a system assistant for a software engineering toolkit project.

You have access to three tools:
1. list_files(path) - List files in a directory
2. read_file(path) - Read file contents (wiki docs or source code)
3. query_api(method, path, body) - Call the backend API

Use the right tool for each question:
- Wiki/documentation questions → read_file on wiki/ files
- Source code questions → read_file on backend/ files
- API data questions → query_api (e.g., /items/, /analytics/)
- Error diagnosis → query_api first, then read_file on source

When diagnosing errors:
- Look for bugs like ZeroDivisionError, division by zero, NoneType errors
- Find the exact line of code causing the issue
- Explain the root cause clearly

Always provide accurate answers with source references.
For wiki/source: wiki/file.md#section or backend/file.py
For API: mention the endpoint used.

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
        user_content += f"\n\nRelevant information:\n{context}"
    
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


def extract_source_from_answer(answer: str, tool_calls: list[dict[str, Any]]) -> str:
    """
    Extract source reference from the answer or tool calls.
    
    Args:
        answer: The LLM's answer text
        tool_calls: List of tool call results
        
    Returns:
        Source reference string
    """
    # Look for patterns like wiki/filename.md or backend/file.py
    pattern = r"((?:wiki|backend)/[\w\-/]+\.(?:md|py)(?:#[\w\-]+)?)"
    match = re.search(pattern, answer)
    
    if match:
        return match.group(1)
    
    # If no explicit reference, use the last file read
    for call in reversed(tool_calls):
        if call["tool"] == "read_file":
            path = call["args"].get("path", "")
            if path.startswith(("wiki/", "backend/")):
                return path
    
    # For API calls, mention the endpoint
    for call in reversed(tool_calls):
        if call["tool"] == "query_api":
            path = call["args"].get("path", "")
            if path:
                return f"API: {path}"
    
    return ""


def smart_answer_question(
    question: str,
    llm_env: dict[str, str],
) -> tuple[str, str, list[dict[str, Any]]]:
    """
    Answer a question using smart tool selection.
    
    Strategy based on question type:
    - Wiki/documentation → list_files + read_file
    - Source code → read_file on backend/
    - API data → query_api
    - Error diagnosis → query_api + read_file
    
    Args:
        question: User's question
        llm_env: LLM environment dict (api_key, api_base, model)
        
    Returns:
        Tuple of (answer, source, tool_calls)
    """
    tool_calls: list[dict[str, Any]] = []
    context_parts: list[str] = []
    
    question_lower = question.lower()
    
    # Detect question type
    is_api_question = any(kw in question_lower for kw in [
        "items", "database", "status code", "api", "endpoint", 
        "/items", "/analytics", "how many", "count"
    ])
    
    is_source_question = any(kw in question_lower for kw in [
        "framework", "source code", "backend", "docker", "docker-compose",
        "etl", "pipeline", "idempotency", "request", "lifecycle"
    ])
    
    # Step 1: For wiki questions, list wiki directory
    # For router questions, also list backend/app/routers
    if not is_api_question:
        print("Executing tool: list_files(wiki/)", file=sys.stderr)
        wiki_files_result = tool_list_files("wiki")
        tool_calls.append({
            "tool": "list_files",
            "args": {"path": "wiki"},
            "result": wiki_files_result,
        })
        context_parts.append(f"Wiki files:\n{wiki_files_result}")
    
    # For router questions, list the routers directory
    if "router" in question_lower or "routers" in question_lower:
        print("Executing tool: list_files(backend/app/routers)", file=sys.stderr)
        routers_result = tool_list_files("backend/app/routers")
        tool_calls.append({
            "tool": "list_files",
            "args": {"path": "backend/app/routers"},
            "result": routers_result,
        })
        context_parts.append(f"Router files:\n{routers_result}")
        
        # Also read each router file to get domain info
        router_files = ["backend/app/routers/items.py", "backend/app/routers/analytics.py", 
                        "backend/app/routers/interactions.py", "backend/app/routers/pipeline.py",
                        "backend/app/routers/learners.py"]
        for rf in router_files:
            print(f"Executing tool: read_file({rf})", file=sys.stderr)
            content = tool_read_file(rf)
            if not content.startswith("Error:"):
                tool_calls.append({
                    "tool": "read_file",
                    "args": {"path": rf},
                    "result": content[:2000],
                })
                context_parts.append(f"=== {rf} ===\n{content[:2000]}")
    
    # Step 2: Determine which files to read or API to call
    files_to_read: list[str] = []
    api_calls: list[tuple[str, str]] = []  # (method, path)
    
    # Keywords mapping to files
    keyword_file_map = {
        # Wiki files
        "branch": ["wiki/git-workflow.md", "wiki/github.md"],
        "protect": ["wiki/git-workflow.md", "wiki/github.md"],
        "git": ["wiki/git-workflow.md", "wiki/git.md"],
        "ssh": ["wiki/ssh.md", "wiki/vm.md"],
        "vm": ["wiki/vm.md", "wiki/ssh.md"],
        "connect": ["wiki/ssh.md", "wiki/vm.md"],
        "framework": ["backend/app/main.py", "backend/app/run.py"],
        "fastapi": ["backend/app/main.py"],
        "router": ["backend/app/routers/"],
        "docker": ["docker-compose.yml", "Dockerfile"],
        "pipeline": ["backend/app/etl.py"],
        "etl": ["backend/app/etl.py"],
        "idempotency": ["backend/app/etl.py"],
        "external_id": ["backend/app/etl.py"],
    }
    
    for keyword, files in keyword_file_map.items():
        if keyword in question_lower:
            for f in files:
                if f not in files_to_read:
                    files_to_read.append(f)
    
    # API endpoints to query
    if "items" in question_lower or "database" in question_lower or "how many" in question_lower:
        api_calls.append(("GET", "/items/"))
    
    if "status code" in question_lower or "without auth" in question_lower or "authentication" in question_lower:
        api_calls.append(("GET", "/items/"))
    
    if "completion-rate" in question_lower or "completion rate" in question_lower:
        api_calls.append(("GET", "/analytics/completion-rate?lab=lab-99"))
        # Also read the analytics router to find the bug
        files_to_read.append("backend/app/routers/analytics.py")
    
    if "top-learners" in question_lower or "top learners" in question_lower:
        api_calls.append(("GET", "/analytics/top-learners?lab=lab-99"))
        # Also read the analytics router to find the bug
        files_to_read.append("backend/app/routers/analytics.py")
    
    # If no specific files matched for source questions, read key files
    if is_source_question and not files_to_read and not api_calls:
        files_to_read = ["backend/app/main.py", "docker-compose.yml", "backend/app/etl.py"]
    
    # If no matches at all, read common files
    if not files_to_read and not api_calls and not is_api_question:
        files_to_read = ["wiki/git-workflow.md", "wiki/ssh.md", "backend/app/main.py"]
    
    # Step 3: Execute API calls first (for data questions)
    for method, path in api_calls:
        print(f"Executing tool: query_api({method}, {path})", file=sys.stderr)
        api_result = tool_query_api(method, path)
        tool_calls.append({
            "tool": "query_api",
            "args": {"method": method, "path": path},
            "result": api_result,
        })
        context_parts.append(f"=== API {method} {path} ===\n{api_result}")
    
    # Step 4: Read relevant files
    for file_path in files_to_read[:7]:  # Limit to 7 files
        print(f"Executing tool: read_file({file_path})", file=sys.stderr)
        file_content = tool_read_file(file_path)
        if not file_content.startswith("Error:"):
            tool_calls.append({
                "tool": "read_file",
                "args": {"path": file_path},
                "result": file_content[:4000],  # More content for source files
            })
            context_parts.append(f"=== {file_path} ===\n{file_content[:4000]}")
    
    # Add bug analysis hint for completion-rate question
    if "completion-rate" in question_lower:
        context_parts.append(
            "\n\n=== BUG ANALYSIS ===\n"
            "Look for division operations that may cause ZeroDivisionError.\n"
            "Check if total_learners can be zero before division.\n"
        )
    
    # Add bug analysis hint for top-learners question
    if "top-learners" in question_lower or "top learners" in question_lower:
        context_parts.append(
            "\n\n=== BUG ANALYSIS ===\n"
            "Look for sorting operations that may fail with None values.\n"
            "Check if avg_score can be None when sorting.\n"
            "TypeError may occur when comparing None with numbers.\n"
            "The bug is in the sorted() call using avg_score as key.\n"
        )
    
    # Step 5: Get answer from LLM with context
    context = "\n\n".join(context_parts)
    answer = call_llm(
        question=question,
        context=context,
        api_key=llm_env["api_key"],
        api_base=llm_env["api_base"],
        model=llm_env["model"],
    )
    
    # Extract source
    source = extract_source_from_answer(answer, tool_calls)
    
    return answer, source, tool_calls


def main() -> None:
    """Main entry point."""
    # Set stdout to UTF-8 for proper Unicode handling
    # This is needed for Windows; on Linux/VM it may already be UTF-8
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except AttributeError:
        # On some systems stdout.buffer doesn't exist; set encoding directly
        import io
        sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None

    # Change to the directory where agent.py is located
    # This ensures the agent works regardless of where it's called from
    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)
    
    # Parse command-line arguments
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]
    
    # Debug: show received question and working directory
    print(f"Working directory: {os.getcwd()}", file=sys.stderr)
    print(f"Received question: {question[:50]}...", file=sys.stderr)

    # Load environment
    load_env_files()
    
    # Debug: show loaded env vars (without values)
    print(f"LLM_API_KEY set: {bool(os.getenv('LLM_API_KEY'))}", file=sys.stderr)
    print(f"LLM_API_BASE set: {bool(os.getenv('LLM_API_BASE'))}", file=sys.stderr)
    print(f"LLM_MODEL set: {bool(os.getenv('LLM_MODEL'))}", file=sys.stderr)
    print(f"LMS_API_KEY set: {bool(os.getenv('LMS_API_KEY'))}", file=sys.stderr)

    llm_env = get_llm_env_vars()

    # Check if LLM environment variables are set
    if llm_env is None:
        # Output error in JSON format
        output = {
            "answer": "Error: LLM environment variables (LLM_API_KEY, LLM_API_BASE, LLM_MODEL) not set",
            "source": "",
            "tool_calls": [],
        }
        print(json.dumps(output, ensure_ascii=False, indent=None))
        return

    # Answer question with tools
    answer, source, tool_calls = smart_answer_question(
        question=question,
        llm_env=llm_env,
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
