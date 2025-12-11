"""Orchestrator for VideoAgent - coordinates Tableau data download and voice generation."""

import asyncio
import csv
import io
import json
import os
from datetime import date
from typing import Callable, Optional

from dotenv import load_dotenv

from videoagent.config import (
    load_topic_config,
    sheet_topic_map,
    sheet_filters,
    get_tableau_settings,
)
from videoagent.services import TableauService, get_openai_voice_client


def create_output_folders(base_path: str = "./output") -> dict[str, str]:
    """Create output folder structure if not exists.

    Structure: output/{today's date}/{audio,image,csv,transcript}

    Args:
        base_path: Base output directory path

    Returns:
        Dictionary mapping folder names to path strings
    """
    today = date.today().isoformat()  # YYYY-MM-DD format
    folders = ["audio", "image", "csv", "transcript"]
    paths = {}

    # Create date-based subfolder
    date_path = os.path.join(base_path, today)

    for folder in folders:
        folder_path = os.path.join(date_path, folder)
        os.makedirs(folder_path, exist_ok=True)
        paths[folder] = folder_path

    return paths


def csv_to_json(csv_content: str) -> str:
    """Convert CSV content string to JSON string.

    Args:
        csv_content: CSV data as string

    Returns:
        JSON string representation of the CSV data
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    return json.dumps(rows, indent=2)


async def process_sheet(
    view: dict,
    topic_id: str,
    tableau_service: TableauService,
    output_paths: dict[str, str],
    filter_func: Optional[Callable[[str], str]] = None,
) -> dict:
    """Process a single sheet: download image, CSV, generate audio.

    Args:
        view: View dict with id, name, etc. from Tableau
        topic_id: Topic identifier for config lookup
        tableau_service: Initialized TableauService instance
        output_paths: Dictionary of output folder paths
        filter_func: Optional function to filter/transform CSV content

    Returns:
        Dictionary with processing results
    """
    view_id = view["id"]
    view_name = view["name"]

    print(f"Processing: {view_name} -> {topic_id}")

    # Load topic configuration
    topic_config = load_topic_config(topic_id)

    # Download image
    image_path = os.path.join(output_paths["image"], f"{topic_id}.png")
    tableau_service.download_view_image(view_id, image_path)
    print(f"  Downloaded image: {image_path}")

    # Download CSV
    csv_content = tableau_service.download_view_csv(view_id)

    # Apply filter if provided
    if filter_func:
        csv_content = filter_func(csv_content)

    csv_path = os.path.join(output_paths["csv"], f"{topic_id}.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(csv_content)
    print(f"  Downloaded CSV: {csv_path}")

    # Convert CSV to JSON for voice prompt
    json_content = csv_to_json(csv_content)

    # Generate audio using OpenAI voice client
    voice_client = get_openai_voice_client()
    audio_bytes, transcript = await voice_client.generate_audio(
        system_prompt=topic_config.instructions,
        user_content=json_content,
        voice=topic_config.voice,
        audio_format="mp3",
    )

    # Save audio
    audio_path = os.path.join(output_paths["audio"], f"{topic_id}.mp3")
    with open(audio_path, "wb") as f:
        f.write(audio_bytes)
    print(f"  Generated audio: {audio_path}")

    # Save transcript
    transcript_path = os.path.join(output_paths["transcript"], f"{topic_id}.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(transcript)
    print(f"  Saved transcript: {transcript_path}")

    return {
        "topic_id": topic_id,
        "view_name": view_name,
        "image_path": image_path,
        "csv_path": csv_path,
        "audio_path": audio_path,
        "transcript_path": transcript_path,
    }


async def main():
    """Main orchestrator entry point."""
    # Load environment variables
    load_dotenv()

    # Create output folder structure
    output_base = os.getenv("OUTPUT_BASE_PATH", "./output")
    output_paths = create_output_folders(output_base)
    print(f"Output folders created at: {output_base}")

    # Initialize Tableau service
    tableau_service = TableauService()
    print("Tableau service initialized")

    # Get workbook ID from settings
    tableau_settings = get_tableau_settings()
    workbook_id = tableau_settings.workbook_id

    if not workbook_id:
        raise ValueError("TABLEAU_WORKBOOK_ID not set in environment")

    # List views in workbook
    views = tableau_service.list_views_in_workbook(workbook_id)
    print(f"Found {len(views)} views in workbook")

    # Filter views to only those in sheet_topic_map
    mapped_views = []
    for view in views:
        view_name = view["name"]
        if view_name in sheet_topic_map:
            mapped_views.append(view)
            print(f"  Mapped: {view_name} -> {sheet_topic_map[view_name]}")
        else:
            print(f"  Skipped (not in mapping): {view_name}")

    print(f"\nProcessing {len(mapped_views)} mapped views...")

    # Process each mapped view
    results = []
    for view in mapped_views:
        view_name = view["name"]
        topic_id = sheet_topic_map[view_name]
        filter_func = sheet_filters.get(topic_id)

        try:
            result = await process_sheet(
                view=view,
                topic_id=topic_id,
                tableau_service=tableau_service,
                output_paths=output_paths,
                filter_func=filter_func,
            )
            results.append(result)
        except Exception as e:
            print(f"  ERROR processing {view_name}: {e}")
            results.append({
                "topic_id": topic_id,
                "view_name": view_name,
                "error": str(e),
            })

    # Sign out from Tableau
    tableau_service.sign_out()
    print("\nTableau service signed out")

    # Summary
    successful = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]

    print(f"\n{'='*50}")
    print("Processing complete!")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(failed)}")

    if failed:
        print("\nFailed items:")
        for r in failed:
            print(f"  - {r['view_name']}: {r['error']}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
