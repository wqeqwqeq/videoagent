"""Mock workflow that starts from step 4 with JSON input."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_framework import (
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    executor,
    handler,
)
from pydantic import BaseModel
from typing_extensions import Never

from ..utils.settings import TOPIC_VIEW_NAMES
from ..services.file_manager import FileManager
from ..utils.config_loader import load_topic_config
from ..services.openai_voice import get_openai_voice_client
from ..utils.settings import get_output_settings


# === Data Classes ===
@dataclass
class TopicData:
    """Data for a single topic."""

    topic_id: str
    csv_path: str
    image_path: str
    json_data: list[dict[str, Any]]


@dataclass
class TopicResult:
    """Result from processing a topic."""

    topic_id: str
    audio_path: str
    transcript_path: str
    transcript_text: str


# === Input/Output Models ===
class MockWorkflowInput(BaseModel):
    """Input for the mock workflow."""

    json_folder: str = "./output/json"  # Folder containing JSON files


class WorkflowOutput(BaseModel):
    """Output from the workflow."""

    results: list[dict[str, str]]
    timestamp: str
    total_topics: int
    successful_topics: int


# === Step 1: Load JSON Input and Create Folders ===
@executor(id="load_json_input")
async def load_json_input(
    input: MockWorkflowInput, ctx: WorkflowContext[dict[str, TopicData]]
) -> None:
    """Load JSON files from input folder and prepare topic data."""
    settings = get_output_settings()
    file_manager = FileManager(settings.output_base_path)

    # Create output folders
    paths = file_manager.ensure_output_folders()
    timestamp = file_manager.get_timestamp()

    # Store in shared state
    await ctx.set_shared_state("output_paths", {k: str(v) for k, v in paths.items()})
    await ctx.set_shared_state("timestamp", timestamp)

    print(f"Created output folders at {settings.output_base_path}")
    print(f"Timestamp: {timestamp}")

    # Load JSON files
    json_folder = Path(input.json_folder)
    topic_data_map: dict[str, TopicData] = {}

    for topic_id in TOPIC_VIEW_NAMES.keys():
        json_path = json_folder / f"{topic_id}.json"

        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    json_data = json.load(f)

                # Ensure json_data is a list
                if isinstance(json_data, dict):
                    json_data = [json_data]

                topic_data_map[topic_id] = TopicData(
                    topic_id=topic_id,
                    csv_path="",
                    image_path="",
                    json_data=json_data,
                )
                print(f"Loaded JSON for {topic_id}")
            except Exception as e:
                print(f"Warning: Could not load JSON for {topic_id}: {e}")
        else:
            print(f"Warning: JSON file not found for {topic_id}: {json_path}")

    print(f"Loaded {len(topic_data_map)} topic JSON files")
    await ctx.set_shared_state("topic_data", topic_data_map)
    await ctx.send_message(topic_data_map)


# === Dispatcher for Fan-Out ===
class DispatchToAudioExecutors(Executor):
    """Dispatches topic data to all audio executors for parallel processing."""

    def __init__(self, id: str = "dispatch_to_audio"):
        super().__init__(id=id)

    @handler
    async def dispatch(
        self, topic_data_map: dict[str, TopicData], ctx: WorkflowContext[dict[str, TopicData]]
    ) -> None:
        print(f"Dispatching {len(topic_data_map)} topics to audio executors...")
        await ctx.send_message(topic_data_map)


# === Audio Executor (TTS) ===
class AudioExecutor(Executor):
    """Executor that generates audio and transcript for a single topic."""

    def __init__(self, topic_id: str, id: str = None):
        super().__init__(id=id or f"{topic_id}_audio_executor")
        self.topic_id = topic_id

    @handler
    async def handle(
        self, topic_data_map: dict[str, TopicData], ctx: WorkflowContext[TopicResult]
    ) -> None:
        topic_data = topic_data_map.get(self.topic_id)

        if not topic_data or not topic_data.json_data:
            print(f"No data for topic: {self.topic_id}")
            await ctx.send_message(
                TopicResult(
                    topic_id=self.topic_id,
                    audio_path="",
                    transcript_path="",
                    transcript_text="",
                )
            )
            return

        # Get shared state
        paths = await ctx.get_shared_state("output_paths")
        timestamp = await ctx.get_shared_state("timestamp")

        # Load topic config
        config = load_topic_config(self.topic_id)

        # Get OpenAI voice client
        client = get_openai_voice_client()

        # Generate audio + transcript
        try:
            json_content = json.dumps(topic_data.json_data, indent=2)
            audio_bytes, transcript = await client.generate_audio(
                system_prompt=config.instructions,
                user_content=json_content,
                voice=config.voice,
            )

            # Save audio file
            audio_path = Path(paths["audio"]) / f"{self.topic_id}_{timestamp}.mp3"
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)

            # Save transcript file
            transcript_path = Path(paths["transcript"]) / f"{self.topic_id}_{timestamp}.txt"
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(transcript)

            print(f"Generated audio for {self.topic_id}")

            await ctx.send_message(
                TopicResult(
                    topic_id=self.topic_id,
                    audio_path=str(audio_path),
                    transcript_path=str(transcript_path),
                    transcript_text=transcript,
                )
            )

        except Exception as e:
            print(f"Error generating audio for {self.topic_id}: {e}")
            await ctx.send_message(
                TopicResult(
                    topic_id=self.topic_id,
                    audio_path="",
                    transcript_path="",
                    transcript_text=f"Error: {str(e)}",
                )
            )


# === Aggregator for Fan-In ===
class AggregateResults(Executor):
    """Aggregate results from all audio executors."""

    def __init__(self, id: str = "aggregate_results"):
        super().__init__(id=id)

    @handler
    async def aggregate(
        self, results: list[TopicResult], ctx: WorkflowContext[Never, WorkflowOutput]
    ) -> None:
        timestamp = await ctx.get_shared_state("timestamp")

        # Convert to serializable format
        result_dicts = []
        successful = 0

        for r in results:
            result_dicts.append(
                {
                    "topic_id": r.topic_id,
                    "audio_path": r.audio_path,
                    "transcript_path": r.transcript_path,
                }
            )
            if r.audio_path:
                successful += 1

        output = WorkflowOutput(
            results=result_dicts,
            timestamp=timestamp,
            total_topics=len(results),
            successful_topics=successful,
        )

        print(f"\n=== Mock Workflow Complete ===")
        print(f"Timestamp: {timestamp}")
        print(f"Total topics: {len(results)}")
        print(f"Successful: {successful}")

        await ctx.yield_output(output)


# === Workflow Factory ===
def create_mock_workflow():
    """Create the mock workflow that starts from JSON input.

    This workflow skips Tableau download steps and reads JSON directly
    from the ./output/json folder.
    """

    # Get all topic IDs
    topic_ids = list(TOPIC_VIEW_NAMES.keys())

    # Create dispatcher
    dispatcher = DispatchToAudioExecutors()

    # Create audio executors for each topic
    audio_executors = [
        AudioExecutor(topic_id=topic_id)
        for topic_id in topic_ids
    ]

    # Create aggregator
    aggregator = AggregateResults()

    # Build workflow (simplified - starts from load_json_input)
    workflow = (
        WorkflowBuilder(
            name="Mock Video Generation Workflow",
            description="Generates narrated audio from JSON files (skips Tableau download)",
        )
        .set_start_executor(load_json_input)
        .add_edge(load_json_input, dispatcher)
        .add_fan_out_edges(dispatcher, audio_executors)
        .add_fan_in_edges(audio_executors, aggregator)
        .build()
    )

    return workflow
