"""Main video generation workflow with fan-out/fan-in pattern."""

import csv
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
from ..services.tableau_service import TableauService
from ..utils.config_loader import load_topic_config
from ..services.openai_voice import get_openai_voice_client
from ..utils.settings import get_output_settings, get_tableau_settings


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
class WorkflowInput(BaseModel):
    """Input for the video workflow."""

    run_id: str = ""  # Optional run identifier


class WorkflowOutput(BaseModel):
    """Output from the video workflow."""

    results: list[dict[str, str]]
    timestamp: str
    total_topics: int
    successful_topics: int


# === Helper Functions ===
def build_view_id_map(tableau: TableauService) -> dict[str, str]:
    """Build mapping from topic_id to view_id.

    This function handles the business logic of matching topic IDs
    to actual Tableau view IDs by name.

    Args:
        tableau: TableauService instance

    Returns:
        Dictionary mapping topic_id to view_id
    """
    settings = get_tableau_settings()
    views = tableau.list_views_in_workbook(settings.workbook_id)
    name_to_id = {v["name"]: v["id"] for v in views}

    view_id_map = {}
    for topic_id, view_name in TOPIC_VIEW_NAMES.items():
        if view_name in name_to_id:
            view_id_map[topic_id] = name_to_id[view_name]
        else:
            # Try partial match (case-insensitive)
            for name, vid in name_to_id.items():
                if view_name.lower() in name.lower():
                    view_id_map[topic_id] = vid
                    break

    return view_id_map


def download_all_csvs(
    tableau: TableauService, view_id_map: dict[str, str], output_dir: Path
) -> dict[str, str]:
    """Download CSV files for all topics.

    Args:
        tableau: TableauService instance
        view_id_map: Mapping from topic_id to view_id
        output_dir: Directory to save CSV files

    Returns:
        Dictionary mapping topic_id to CSV file path
    """
    csv_files = {}
    for topic_id, view_id in view_id_map.items():
        try:
            output_path = output_dir / f"{topic_id}.csv"
            tableau.download_view_csv(view_id, output_path)
            csv_files[topic_id] = str(output_path)
        except Exception as e:
            print(f"Warning: Failed to download CSV for {topic_id}: {e}")
    return csv_files


def download_all_images(
    tableau: TableauService,
    view_id_map: dict[str, str],
    output_dir: Path,
    timestamp: str,
) -> dict[str, str]:
    """Download image files for all topics.

    Args:
        tableau: TableauService instance
        view_id_map: Mapping from topic_id to view_id
        output_dir: Directory to save image files
        timestamp: Timestamp to append to filenames

    Returns:
        Dictionary mapping topic_id to image file path
    """
    image_files = {}
    for topic_id, view_id in view_id_map.items():
        try:
            output_path = output_dir / f"{topic_id}_{timestamp}.png"
            tableau.download_view_image(view_id, output_path)
            image_files[topic_id] = str(output_path)
        except Exception as e:
            print(f"Warning: Failed to download image for {topic_id}: {e}")
    return image_files


# === Step 1: Create Output Folders ===
@executor(id="create_folders")
async def create_folders(
    input: WorkflowInput, ctx: WorkflowContext[WorkflowInput]
) -> None:
    """Create output folders if they don't exist."""
    settings = get_output_settings()
    file_manager = FileManager(settings.output_base_path)

    paths = file_manager.ensure_output_folders()
    timestamp = file_manager.get_timestamp()

    # Store in shared state for other executors
    await ctx.set_shared_state("output_paths", {k: str(v) for k, v in paths.items()})
    await ctx.set_shared_state("timestamp", timestamp)
    await ctx.set_shared_state("file_manager", file_manager)

    print(f"Created output folders at {settings.output_base_path}")
    print(f"Timestamp: {timestamp}")

    await ctx.send_message(input)


# === Step 2: Download Images ===
@executor(id="download_images")
async def download_images(
    input: WorkflowInput, ctx: WorkflowContext[WorkflowInput]
) -> None:
    """Download all topic sheets as images from Tableau."""
    paths = await ctx.get_shared_state("output_paths")
    timestamp = await ctx.get_shared_state("timestamp")
    image_dir = Path(paths["pic"])

    with TableauService() as tableau:
        view_id_map = build_view_id_map(tableau)
        await ctx.set_shared_state("view_id_map", view_id_map)

        image_files = download_all_images(tableau, view_id_map, image_dir, timestamp)

    await ctx.set_shared_state("image_files", image_files)
    print(f"Downloaded {len(image_files)} image files")
    await ctx.send_message(input)


# === Step 3: Download CSVs and Transform to JSON ===
@executor(id="download_csvs")
async def download_csvs(
    _input: WorkflowInput, ctx: WorkflowContext[dict[str, TopicData]]
) -> None:
    """Download all topic sheets as CSV files and transform to JSON."""
    paths = await ctx.get_shared_state("output_paths")
    image_files = await ctx.get_shared_state("image_files")
    view_id_map = await ctx.get_shared_state("view_id_map")
    csv_dir = Path(paths["csv"])

    with TableauService() as tableau:
        csv_files = download_all_csvs(tableau, view_id_map, csv_dir)

    print(f"Downloaded {len(csv_files)} CSV files")

    # Prepare topic data map for fan-out (CSV to JSON transformation)
    topic_data_map: dict[str, TopicData] = {}

    for topic_id in TOPIC_VIEW_NAMES.keys():
        csv_path = csv_files.get(topic_id)
        image_path = image_files.get(topic_id)

        if csv_path:
            # Read CSV and convert to JSON
            json_data = []
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    json_data = list(reader)
            except Exception as e:
                print(f"Warning: Could not read CSV for {topic_id}: {e}")

            topic_data_map[topic_id] = TopicData(
                topic_id=topic_id,
                csv_path=str(csv_path) if csv_path else "",
                image_path=str(image_path) if image_path else "",
                json_data=json_data,
            )

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

        print(f"\n=== Video Generation Complete ===")
        print(f"Timestamp: {timestamp}")
        print(f"Total topics: {len(results)}")
        print(f"Successful: {successful}")

        await ctx.yield_output(output)


# === Workflow Factory ===
def create_video_workflow():
    """Create the video generation workflow with fan-out/fan-in pattern."""

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

    # Build workflow
    workflow = (
        WorkflowBuilder(
            name="Video Generation Workflow",
            description="Generates narrated audio from Tableau dashboards with parallel processing",
        )
        .set_start_executor(create_folders)
        .add_edge(create_folders, download_images)
        .add_edge(download_images, download_csvs)
        .add_edge(download_csvs, dispatcher)
        .add_fan_out_edges(dispatcher, audio_executors)
        .add_fan_in_edges(audio_executors, aggregator)
        .build()
    )

    return workflow
