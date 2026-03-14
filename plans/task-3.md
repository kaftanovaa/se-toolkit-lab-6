# Task 3: The System Agent — Implementation Plan

## Overview

Build a system agent that can query the deployed backend API in addition to reading documentation. This enables answering both static system questions (framework, ports) and data-dependent queries (item count, scores).

## LLM Provider

**Provider:** Qwen Code API (deployed on VM)
**Model:** `qwen3-coder-plus`

Same as Tasks 1-2 — 1000 free requests/day.

## Architecture

### New Tool: `query_api`

Call the deployed backend API with authentication.

**Parameters:**
- `method` (string, required) — HTTP method (GET, POST, etc.)
- `path` (string, required) — API endpoint path (e.g., `/items/`)
- `body` (string, optional) — JSON request body for POST/PUT requests

**Returns:**
- JSON string with `status_code` and `body`

**Authentication:**
- Uses `LMS_API_KEY` from `.env.docker.secret`
- Sent as `Authorization: Bearer <LMS_API_KEY>` header

**Security:**
- Only allows HTTP/HTTPS URLs
- Validates path format

### Environment Variables

The agent reads ALL configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api (default: `http://localhost:42002`) | Optional, env |

**Important:** The autochecker injects different credentials at evaluation time. No hardcoded values!

### System Prompt Strategy

The system prompt must guide the LLM to choose the right tool:

1. **Wiki questions** → `read_file`, `list_files`
2. **System/API questions** → `query_api`
3. **Source code questions** → `read_file` on backend files

Updated prompt will explain:
- When to use each tool
- What information each tool provides
- How to format answers with sources

### Agentic Loop

Same as Task 2, but with 3 tools instead of 2:
1. Send question + tool schemas to LLM
2. LLM decides which tool(s) to call
3. Execute tools, append results
4. Repeat until LLM provides final answer
5. Max 10 tool calls

### Smart Tool Selection

For benchmark questions, implement heuristic-based tool selection:

| Question Type | Tools to Call |
|---------------|---------------|
| Wiki/documentation | `list_files` + `read_file` |
| Backend source code | `read_file` on backend/ |
| API data query | `query_api` |
| API error diagnosis | `query_api` + `read_file` |
| System architecture | `read_file` on docker-compose.yml, Dockerfile |

## Implementation Steps

### Step 1: Add query_api tool

```python
def tool_query_api(method: str, path: str, body: str | None = None) -> str:
    """Call the backend API with authentication."""
    lms_api_key = os.getenv("LMS_API_KEY")
    api_base = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    
    url = f"{api_base}{path}"
    headers = {
        "Authorization": f"Bearer {lms_api_key}",
        "Content-Type": "application/json",
    }
    
    # Execute request based on method
    ...
```

### Step 2: Update tool registry

```python
TOOLS = {
    "read_file": tool_read_file,
    "list_files": tool_list_files,
    "query_api": tool_query_api,
}
```

### Step 3: Update smart_answer_question

Add logic to detect API questions and call `query_api`:

```python
# Detect API questions
api_keywords = ["items", "database", "status code", "api", "endpoint", "/"]
if any(kw in question_lower for kw in api_keywords):
    # Call query_api
    ...
```

### Step 4: Update system prompt

New prompt explains all 3 tools and when to use each.

### Step 5: Run benchmark and iterate

```bash
uv run run_eval.py
```

Fix failures one by one:
1. Check which tool was called (or not called)
2. Check if answer contains expected keywords
3. Adjust tool selection logic or prompt

## Benchmark Questions Analysis

| # | Question | Expected Tools | Expected Answer |
|---|----------|----------------|-----------------|
| 0 | Protect branch on GitHub | `read_file` | branch, protect |
| 1 | SSH to VM | `read_file` | ssh/key/connect |
| 2 | Python web framework | `read_file` | FastAPI |
| 3 | API router modules | `list_files` | items, interactions, analytics, pipeline |
| 4 | Items in database | `query_api` | number > 0 |
| 5 | Status code without auth | `query_api` | 401/403 |
| 6 | Completion-rate error | `query_api`, `read_file` | ZeroDivisionError |
| 7 | Top-learners crash | `query_api`, `read_file` | TypeError/None |
| 8 | Request lifecycle | `read_file` | Caddy → FastAPI → auth → router → ORM → PostgreSQL |
| 9 | ETL idempotency | `read_file` | external_id check, duplicates skipped |

## Testing Strategy

Create 2 regression tests:

### Test 1: Framework Question
- **Question:** "What Python web framework does the backend use?"
- **Expected:** `read_file` in tool_calls, `FastAPI` in answer

### Test 2: Database Query Question
- **Question:** "How many items are in the database?"
- **Expected:** `query_api` in tool_calls, number in answer

## Files to Modify

| File | Action |
|------|--------|
| `plans/task-3.md` | Create (this plan) |
| `agent.py` | Add `query_api` tool, update logic |
| `AGENT.md` | Update with new architecture |
| `test_agent_task3.py` | Create (2 tests) |

## Acceptance Criteria Checklist

- [ ] `plans/task-3.md` exists with implementation plan
- [ ] `agent.py` defines `query_api` as function-calling schema
- [ ] `query_api` authenticates with `LMS_API_KEY`
- [ ] Agent reads all LLM config from environment variables
- [ ] Agent reads `AGENT_API_BASE_URL` (defaults to localhost)
- [ ] Agent answers static system questions correctly
- [ ] Agent answers data-dependent questions correctly
- [ ] `run_eval.py` passes all 10 local questions
- [ ] `AGENT.md` documents architecture (200+ words)
- [ ] 2 tool-calling regression tests exist and pass
- [ ] Git workflow followed

## Initial Benchmark Run

*To be filled after first run of `run_eval.py`*

## Iteration Log

*To be filled as bugs are fixed*
