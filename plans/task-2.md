# Task 2: The Documentation Agent — Implementation Plan

## Overview

Build an agentic loop that allows the LLM to use tools (`read_file`, `list_files`) to navigate the project wiki and answer questions with proper source references.

## LLM Provider

**Provider:** Qwen Code API (deployed on VM)
**Model:** `qwen3-coder-plus`

Same as Task 1 — 1000 free requests/day, works in Russia.

## Architecture

### 1. Tool Definitions

Two tools to implement:

#### `read_file`
- **Purpose:** Read content of a file from the project repository
- **Parameters:** `path` (string) — relative path from project root
- **Returns:** File contents as string, or error message
- **Security:** Block path traversal (no `../` outside project directory)

#### `list_files`
- **Purpose:** List files and directories at a given path
- **Parameters:** `path` (string) — relative directory path from project root
- **Returns:** Newline-separated listing of entries
- **Security:** Block path traversal

### 2. Tool Schemas (Function Calling)

Define tool schemas for OpenAI-compatible function calling API:

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read a file from the project repository",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {"type": "string", "description": "Relative path from project root"}
      },
      "required": ["path"]
    }
  }
}
```

Similar schema for `list_files`.

### 3. Agentic Loop

```
1. Send user question + tool schemas to LLM
2. Parse LLM response:
   - If tool_calls present:
     a. Execute each tool call
     b. Append results as tool role messages
     c. Go to step 1 (max 10 iterations)
   - If text message (no tool calls):
     a. Extract answer
     b. Extract source reference (if any)
     c. Output JSON and exit
```

**Loop limit:** Maximum 10 tool calls per question to prevent infinite loops.

### 4. System Prompt

The system prompt should instruct the LLM to:
1. Use `list_files` to discover wiki files
2. Use `read_file` to find specific information
3. Include source reference (file path + section anchor) in the answer
4. Call tools one at a time or in parallel when appropriate

Example system prompt:
```
You are a documentation assistant. You have access to two tools:
- list_files: List files in a directory
- read_file: Read contents of a file

When answering questions:
1. First explore the wiki structure with list_files
2. Then read relevant files with read_file
3. Provide accurate answers with source references (e.g., wiki/git-workflow.md#resolving-merge-conflicts)
4. Only answer when you have enough information from the files
```

### 5. Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "git-workflow.md\n..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

**Fields:**
- `answer` (string, required) — the LLM's answer
- `source` (string, required) — wiki section reference
- `tool_calls` (array, required) — all tool calls made with results

## Security Considerations

### Path Traversal Prevention

Both tools must validate paths:
1. Resolve the full path
2. Check it starts with the project root
3. Reject paths containing `..` that escape the project directory

```python
def validate_path(path: str, project_root: Path) -> Path:
    full_path = (project_root / path).resolve()
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

## Testing Strategy

Create 2 regression tests:

### Test 1: Merge Conflict Question
- **Question:** "How do you resolve a merge conflict?"
- **Expected:** `read_file` in tool_calls, `wiki/git-workflow.md` in source

### Test 2: Wiki Files Question
- **Question:** "What files are in the wiki?"
- **Expected:** `list_files` in tool_calls

## Files to Modify/Create

| File | Action | Description |
|------|--------|-------------|
| `plans/task-2.md` | Create | This plan |
| `agent.py` | Update | Add tools, agentic loop, source extraction |
| `AGENT.md` | Update | Document tools and agentic loop |
| `test_agent_task2.py` | Create | 2 regression tests |

## Acceptance Criteria Checklist

- [ ] `plans/task-2.md` exists with implementation plan
- [ ] `agent.py` defines `read_file` and `list_files` as tool schemas
- [ ] Agentic loop executes tool calls and feeds results back to LLM
- [ ] `tool_calls` in output is populated when tools are used
- [ ] `source` field correctly identifies wiki section
- [ ] Tools do not access files outside project directory
- [ ] `AGENT.md` documents tools and agentic loop
- [ ] 2 tool-calling regression tests exist and pass
- [ ] Git workflow: issue, branch, PR with `Closes #...`, partner approval, merge
