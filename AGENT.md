# Agent Architecture

## Overview

This document describes the architecture of the documentation agent (`agent.py`) that uses tools (`read_file`, `list_files`) to navigate the project wiki and answer questions with proper source references.

## LLM Provider

**Provider:** Qwen Code API (deployed on VM)

**Model:** `qwen3-coder-plus`

**Why Qwen Code API:**
- 1000 free requests per day
- Works in Russia
- OpenAI-compatible API with function calling support
- Recommended for this lab

## Architecture

The agent follows an agentic loop:

```
User question
    ↓
Send to LLM with tool schemas
    ↓
LLM responds with tool_calls? ──yes──▶ Execute tools
    │                                       │
    no                                      │
    │                                       ▼
    │                         Append results to messages
    │                                       │
    │                                       └──────┐
    ▼                                              │
Extract answer                                     │
    │                                              │
    ▼                                              │
Output JSON                                        │
                                                   │
                                                   ▼
                                          Call LLM again ──┘
```

### Agentic Loop

1. **Send question to LLM** with tool schemas defined
2. **Parse LLM response:**
   - If `tool_calls` present → execute each tool, append results as `tool` role messages, go to step 1
   - If text message (no tool calls) → extract answer and source, output JSON, exit
3. **Loop limit:** Maximum 10 tool calls per question

## Components

### 1. Environment Loading

- Reads `.env.agent.secret` from the project root
- Required variables:
  - `LLM_API_KEY` — API key for authentication
  - `LLM_API_BASE` — Base URL of the LLM API (e.g., `http://vm-ip:port/v1`)
  - `LLM_MODEL` — Model name (e.g., `qwen3-coder-plus`)

### 2. Tools

Two tools are available:

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
- Rejects paths that escape the project root

### 3. Tool Schemas (Function Calling)

Tools are defined as OpenAI-compatible function calling schemas:

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read the contents of a file...",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {"type": "string", "description": "Relative path..."}
      },
      "required": ["path"]
    }
  }
}
```

### 4. System Prompt

The system prompt instructs the LLM to:
1. Use `list_files` to explore the wiki/ directory structure
2. Use `read_file` to read relevant documentation files
3. Find specific sections that answer the question
4. Provide accurate answers with source references in format: `wiki/filename.md#section-anchor`

### 5. Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

**Fields:**
- `answer` (string, required) — The LLM's answer text
- `source` (string, required) — Wiki section reference (e.g., `wiki/git-workflow.md#section`)
- `tool_calls` (array, required) — All tool calls made with `tool`, `args`, and `result`

### 6. Output Handling

- **stdout:** Only valid JSON (single line)
- **stderr:** All debug/progress messages
- **Exit code:** 0 on success, non-zero on error

## How to Run

### Prerequisites

1. Copy environment file:
   ```bash
   cp .env.agent.example .env.agent.secret
   ```

2. Fill in your credentials:
   - `LLM_API_KEY` — Your Qwen Code API key
   - `LLM_API_BASE` — Your VM's API URL (e.g., `http://10.93.25.168:42005/v1`)
   - `LLM_MODEL` — `qwen3-coder-plus`

### Usage

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

**Expected output:**
```json
{"answer": "...", "source": "wiki/git-workflow.md#resolving-merge-conflicts", "tool_calls": [...]}
```

## Security Considerations

### Path Traversal Prevention

Both tools validate paths to prevent accessing files outside the project directory:

```python
def validate_path(path: str) -> Path:
    project_root = get_project_root()
    clean_path = path.strip("/\\")
    full_path = (project_root / clean_path).resolve()
    
    if not str(full_path).startswith(str(project_root)):
        raise ValueError("Path traversal not allowed")
    
    return full_path
```

## Error Handling

| Error | Behavior |
|-------|----------|
| File not found | Return error message in tool result |
| Path traversal attempt | Return error message, do not execute |
| LLM API error | Print to stderr, exit with non-zero code |
| Timeout (>60s) | Print to stderr, exit with non-zero code |
| Max tool calls (10) | Stop loop, use whatever answer available |

## Testing

Run the regression tests:

```bash
uv run pytest test_agent_task2.py -v
```

Tests verify:
1. Tool usage for documentation questions
2. Correct source reference extraction
3. Proper JSON output format

## Future Work (Task 3)

- Add more tools (query_api, search, etc.)
- Improve source extraction with section anchor detection
- Better handling of multi-file answers
