# Task 1: Call an LLM from Code — Implementation Plan

## LLM Provider

**Provider:** Qwen Code API (deployed on VM)

**Model:** `qwen3-coder-plus` (recommended, default in `.env.agent.example`)

**Why Qwen Code API:**
- 1000 free requests per day (vs 50 for OpenRouter)
- Works in Russia
- Recommended in the task description
- Autochecker runs 10 questions — OpenRouter's 50/day limit may not be enough

## Architecture

The agent (`agent.py`) will have the following components:

### 1. Environment Configuration
- Read `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` from `.env.agent.secret`
- Use `python-dotenv` to load environment variables

### 2. Command-Line Interface
- Accept a single positional argument: the user's question
- Use `sys.argv` or `argparse` for argument parsing

### 3. LLM API Client
- Use `httpx` (already in `pyproject.toml`) for async HTTP requests
- Call OpenAI-compatible `/v1/chat/completions` endpoint
- Send user question as a message with role "user"
- Set timeout to 60 seconds

### 4. Response Processing
- Parse JSON response from LLM
- Extract the `content` field from the first choice
- Format output as JSON with required fields:
  - `answer`: the LLM's response text
  - `tool_calls`: empty array `[]` (will be populated in Task 2)

### 5. Output Handling
- **stdout:** Only valid JSON (single line)
- **stderr:** All debug/progress messages
- **Exit code:** 0 on success

## Data Flow

```
User question (CLI arg)
    ↓
agent.py parses argument
    ↓
Reads env vars (.env.agent.secret)
    ↓
Calls LLM API (httpx POST /v1/chat/completions)
    ↓
Receives response
    ↓
Extracts answer, formats JSON
    ↓
Outputs JSON to stdout
```

## Error Handling

- Network errors → print error to stderr, exit with non-zero code
- API errors (4xx, 5xx) → print error to stderr, exit with non-zero code
- Timeout (>60s) → print error to stderr, exit with non-zero code
- Missing environment variables → print error to stderr, exit with non-zero code

## Testing Strategy

Create one regression test (`backend/tests/test_agent_task1.py`):
1. Run `agent.py` as subprocess with a test question
2. Parse stdout as JSON
3. Assert `answer` field exists and is non-empty string
4. Assert `tool_calls` field exists and is an empty list

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `plans/task-1.md` | Create | This plan |
| `agent.py` | Create | Main CLI agent |
| `.env.agent.secret` | Create (copy from example) | LLM credentials |
| `AGENT.md` | Update | Document architecture |
| `backend/tests/test_agent_task1.py` | Create | Regression test |

## Acceptance Criteria Checklist

- [ ] `plans/task-1.md` exists with implementation plan
- [ ] `agent.py` exists in project root
- [ ] `uv run agent.py "..."` outputs valid JSON with `answer` and `tool_calls`
- [ ] API key stored in `.env.agent.secret` (not hardcoded)
- [ ] `AGENT.md` documents the solution architecture
- [ ] 1 regression test exists and passes
- [ ] Git workflow followed: issue, branch, PR with `Closes #...`, partner approval, merge
