# Agent Architecture

## Overview

This document describes the architecture of the agent CLI (`agent.py`) that calls an LLM and returns structured JSON answers.

## LLM Provider

**Provider:** Qwen Code API (deployed on VM)

**Model:** `qwen3-coder-plus`

**Why Qwen Code API:**
- 1000 free requests per day
- Works in Russia
- OpenAI-compatible API
- Recommended for this lab

## Architecture

The agent follows a simple pipeline:

```
User question (CLI arg)
    ↓
Parse arguments
    ↓
Load environment variables (.env.agent.secret)
    ↓
Call LLM API via HTTP POST
    ↓
Parse response
    ↓
Output JSON to stdout
```

## Components

### 1. Environment Loading

- Reads `.env.agent.secret` from the project root
- Required variables:
  - `LLM_API_KEY` — API key for authentication
  - `LLM_API_BASE` — Base URL of the LLM API (e.g., `http://vm-ip:port/v1`)
  - `LLM_MODEL` — Model name (e.g., `qwen3-coder-plus`)

### 2. Command-Line Interface

- Single positional argument: the user's question
- Usage: `uv run agent.py "<question>"`
- No external CLI library needed — uses `sys.argv`

### 3. LLM API Client

- Uses `httpx` for HTTP requests
- Calls OpenAI-compatible `/v1/chat/completions` endpoint
- Sends messages in the format:
  ```json
  {
    "model": "qwen3-coder-plus",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "<question>"}
    ]
  }
  ```
- Timeout: 60 seconds

### 4. Response Processing

- Parses JSON response from LLM
- Extracts `choices[0].message.content`
- Formats output with required fields:
  - `answer`: the LLM's response text
  - `tool_calls`: empty array `[]` (reserved for Task 2+)

### 5. Output Handling

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
   - `LLM_API_BASE` — Your VM's API URL (e.g., `http://192.168.1.100:8080/v1`)
   - `LLM_MODEL` — `qwen3-coder-plus`

### Usage

```bash
uv run agent.py "What does REST stand for?"
```

**Expected output:**
```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing `.env.agent.secret` | Print error to stderr, exit 1 |
| Missing env vars | Print error to stderr, exit 1 |
| Network error | Print error to stderr, exit 1 |
| API error (4xx/5xx) | Print error to stderr, exit 1 |
| Timeout (>60s) | Print error to stderr, exit 1 |
| Unexpected response format | Print error to stderr, exit 1 |

## Testing

Run the regression test:

```bash
uv run pytest backend/tests/test_agent_task1.py -v
```

The test:
1. Runs `agent.py` as a subprocess with a test question
2. Parses stdout as JSON
3. Asserts `answer` field exists and is non-empty
4. Asserts `tool_calls` field exists and is an empty list

## Future Work (Tasks 2-3)

- Add tools (file read, API query, etc.)
- Implement agentic loop
- Populate `tool_calls` with actual tool invocations
- Expand system prompt with domain knowledge
