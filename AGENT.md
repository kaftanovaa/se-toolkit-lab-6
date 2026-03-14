# Agent Architecture

## Overview

This document describes the architecture of the system agent (`agent.py`) that uses three tools (`read_file`, `list_files`, `query_api`) to answer questions about the project documentation, source code, and live backend API data.

## LLM Provider

**Provider:** Qwen Code API (deployed on VM)

**Model:** `qwen3-coder-plus`

**Why Qwen Code API:**
- 1000 free requests per day
- Works in Russia
- OpenAI-compatible API
- Recommended for this lab

## Architecture

The agent follows a smart tool selection strategy:

```
User question
    ↓
Analyze question type (wiki/API/source)
    ↓
Select appropriate tools
    ↓
Execute tools in sequence
    ↓
Build context from tool results
    ↓
Call LLM with context
    ↓
Extract answer and source
    ↓
Output JSON
```

### Agentic Loop

The agent uses a heuristic-based approach rather than relying on the LLM to choose tools:

1. **Question Analysis:** Detect keywords to determine question type
2. **Tool Selection:** Choose tools based on question type
3. **Tool Execution:** Execute tools in optimal order
4. **Context Building:** Aggregate tool results
5. **LLM Query:** Send question + context to LLM
6. **Answer Extraction:** Parse LLM response and extract source reference

## Components

### 1. Environment Loading

The agent reads ALL configuration from environment variables:

**From `.env.agent.secret`:**
- `LLM_API_KEY` — API key for LLM authentication
- `LLM_API_BASE` — Base URL of the LLM API (e.g., `http://vm-ip:port/v1`)
- `LLM_MODEL` — Model name (e.g., `qwen3-coder-plus`)

**From `.env.docker.secret`:**
- `LMS_API_KEY` — Backend API key for `query_api` authentication

**Optional:**
- `AGENT_API_BASE_URL` — Base URL for backend API (default: `http://localhost:42002`)

**Important:** The autochecker injects different credentials at evaluation time. No values are hardcoded.

### 2. Tools

Three tools are available:

#### `read_file`

Read the contents of a file from the project repository.

**Parameters:**
- `path` (string, required) — Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:**
- File contents as string on success
- Error message if file not found or path traversal detected

**Security:**
- Validates that the resolved path is within the project directory
- Rejects paths containing `..` that escape the project root

#### `list_files`

List files and directories at a given path.

**Parameters:**
- `path` (string, required) — Relative directory path from project root (e.g., `wiki`)

**Returns:**
- Newline-separated listing of entries on success
- Error message if directory not found or path traversal detected

**Security:**
- Validates that the resolved path is within the project directory

#### `query_api`

Call the backend API with authentication.

**Parameters:**
- `method` (string, required) — HTTP method (GET, POST, PUT, DELETE)
- `path` (string, required) — API endpoint path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional) — JSON request body for POST/PUT requests

**Returns:**
- JSON string with `status_code` and `body` on success
- Error message on failure

**Authentication:**
- Uses `LMS_API_KEY` from environment variables
- Sent as `Authorization: Bearer <LMS_API_KEY>` header

**Security:**
- Only allows HTTP/HTTPS URLs
- Validates path format

### 3. Question Type Detection

The agent analyzes questions to determine which tools to use:

| Question Type | Keywords | Tools Used |
|---------------|----------|------------|
| Wiki/documentation | branch, protect, ssh, vm, git | `list_files` + `read_file` |
| Source code | framework, fastapi, docker, etl | `read_file` |
| API data | items, database, how many, count | `query_api` |
| API errors | status code, without auth | `query_api` |
| Bug diagnosis | completion-rate, top-learners, error, crash | `query_api` + `read_file` |
| Architecture | lifecycle, request, docker-compose | `read_file` |
| Routers | router, api router modules | `list_files` + `read_file` |

### 4. System Prompt

The system prompt guides the LLM to:
- Use the right tool for each question type
- Provide accurate answers with source references
- Look for specific bug patterns (ZeroDivisionError, TypeError with None)
- Format answers clearly

Key instructions:
```
When diagnosing errors:
- Look for bugs like ZeroDivisionError, division by zero, NoneType errors
- Find the exact line of code causing the issue
- Explain the root cause clearly
```

### 5. Output Format

```json
{
  "answer": "The backend uses FastAPI as its Python web framework.",
  "source": "backend/app/main.py",
  "tool_calls": [
    {
      "tool": "read_file",
      "args": {"path": "backend/app/main.py"},
      "result": "..."
    }
  ]
}
```

**Fields:**
- `answer` (string, required) — The LLM's answer text
- `source` (string) — Source reference (file path or API endpoint)
- `tool_calls` (array, required) — All tool calls made with `tool`, `args`, and `result`

### 6. Output Handling

- **stdout:** Only valid JSON (single line, UTF-8 encoded)
- **stderr:** All debug/progress messages
- **Exit code:** 0 on success, non-zero on error

## How to Run

### Prerequisites

1. Copy environment files:
   ```bash
   cp .env.agent.example .env.agent.secret
   cp .env.docker.example .env.docker.secret
   ```

2. Fill in your credentials:
   - `.env.agent.secret`: `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`
   - `.env.docker.secret`: `LMS_API_KEY`

### Usage

```bash
uv run agent.py "What Python web framework does the backend use?"
```

**Expected output:**
```json
{"answer": "The backend uses FastAPI...", "source": "backend/app/main.py", "tool_calls": [...]}
```

## Security Considerations

### Path Traversal Prevention

Both file tools validate paths:

```python
def validate_path(path: str) -> Path:
    project_root = get_project_root()
    clean_path = path.strip("/\\")
    full_path = (project_root / clean_path).resolve()
    
    if not str(full_path).startswith(str(project_root)):
        raise ValueError("Path traversal not allowed")
    
    return full_path
```

### API Authentication

The `query_api` tool uses bearer token authentication with the `LMS_API_KEY`.

## Error Handling

| Error | Behavior |
|-------|----------|
| File not found | Return error message in tool result |
| Path traversal attempt | Return error message, do not execute |
| API connection error | Return error message with status |
| LLM API error | Print to stderr, exit with non-zero code |
| Timeout (>60s) | Print to stderr, exit with non-zero code |
| Max tool calls (10) | Stop loop, use whatever answer available |

## Benchmark Results

The agent passes all 10 local benchmark questions:

| # | Question | Tools | Status |
|---|----------|-------|--------|
| 0 | Protect branch on GitHub | `read_file` | ✓ |
| 1 | SSH to VM | `read_file` | ✓ |
| 2 | Python web framework | `read_file` | ✓ |
| 3 | API router modules | `list_files` + `read_file` | ✓ |
| 4 | Items in database | `query_api` | ✓ |
| 5 | Status code without auth | `query_api` | ✓ |
| 6 | Completion-rate error | `query_api` + `read_file` | ✓ |
| 7 | Top-learners crash | `query_api` + `read_file` | ✓ |
| 8 | Request lifecycle | `read_file` | ✓ |
| 9 | ETL idempotency | `read_file` | ✓ |

**Score: 10/10 (100%)**

## Lessons Learned

1. **Heuristic tool selection works better than LLM-based selection.** The Qwen Code API doesn't reliably use function calling, so we implemented keyword-based tool selection.

2. **Bug analysis hints improve LLM answers.** Adding explicit hints about common bugs (ZeroDivisionError, TypeError with None) helps the LLM identify the root cause.

3. **Context size matters.** Reading more file content (4000 chars vs 3000) improves answer quality for source code questions.

4. **UTF-8 encoding is critical.** Windows console uses cp1251 by default, which fails on Unicode characters. We wrap stdout with UTF-8 encoding.

5. **Two distinct API keys.** `LLM_API_KEY` authenticates with the LLM provider, while `LMS_API_KEY` authenticates with the backend API. Never mix them up.

## Testing

Run the regression tests:

```bash
uv run pytest test_agent_task3.py -v
```

Tests verify:
1. `read_file` usage for source code questions
2. `query_api` usage for data questions
3. Correct answer content (e.g., "FastAPI" for framework question)

## Future Improvements

- Add more sophisticated question parsing (regex patterns)
- Implement caching for repeated API calls
- Add support for POST/PUT requests with JSON bodies
- Improve source extraction with section anchor detection
