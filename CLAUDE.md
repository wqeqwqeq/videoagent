# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VideoAgent generates narrated audio from Tableau dashboards using Azure OpenAI's gpt-4o-audio-preview model. It uses Microsoft's Agent Framework to orchestrate a fan-out/fan-in workflow that processes 13 dashboard topics in parallel.

## Commands

```bash
# Install dependencies (uses uv package manager)
uv sync

# Run the main workflow (requires Tableau + Azure OpenAI credentials)
uv run python main.py

# Run mock workflow (skips Tableau, reads from ./output/json/)
uv run python main_mock.py
```

Both entry points start a DevUI server at http://localhost:8090.

## Architecture

The codebase uses the `agent_framework` package to build workflows with executors (processing steps) connected by edges.

### Workflow Pipeline

1. **create_folders** - Creates output directory structure (csv/, pic/, json/, audio/, transcript/, video/)
2. **download_csvs** - Downloads view data from Tableau as CSV
3. **download_images** - Downloads view screenshots from Tableau
4. **DispatchToAudioExecutors** - Fan-out: dispatches to 13 parallel audio executors
5. **AudioExecutor** (x13) - Generates audio + transcript using Azure OpenAI TTS
6. **AggregateResults** - Fan-in: collects results from all audio executors

The mock workflow (`main_mock.py`) skips steps 2-3 and reads JSON directly from `./output/json/`.

### Key Components

- **videoagent/workflows/** - Workflow definitions using `WorkflowBuilder`, `Executor`, `@executor`, `@handler` decorators
- **videoagent/services/tableau_service.py** - Tableau Server Client wrapper; contains `TOPIC_VIEW_NAMES` mapping (13 topics)
- **videoagent/services/file_manager.py** - Output folder management
- **videoagent/utils/openai_voice.py** - `AzureOpenAIVoiceClient` for TTS via gpt-4o-audio-preview
- **videoagent/utils/settings.py** - Pydantic settings classes loading from `.env`
- **videoagent/config/*.yaml** - Per-topic configuration with `name`, `voice`, and `instructions` (system prompts)

### Configuration

- Copy `.env.example` to `.env` and fill in Tableau and Azure OpenAI credentials
- Topic configs in `videoagent/config/topic_*.yaml` define voice and system prompt for each topic
- Available voices: alloy, ash, ballad, coral, echo, marin, sage, shimmer, verse, cedar

### Note

The workflows import `TOPIC_VIEW_NAMES` from `..constants` but the constant is actually defined in `videoagent/services/tableau_service.py`. A `constants.py` file may need to be created or imports updated.
