"""Orchestrator for VideoAgent - coordinates Tableau data download and voice generation."""

import asyncio
import os
from typing import Callable, Optional

from dotenv import load_dotenv

from videoagent.config import (
    load_topic_config,
    sheet_topic_map,
    sheet_filters,
    get_tableau_settings,
    get_storage_settings,
)
from videoagent.services import (
    TableauService,
    get_openai_voice_client,
    get_storage_backend,
    csv_to_json,
    StorageBackend,
)


async def process_sheet(
    view: dict,
    topic_id: str,
    tableau_service: TableauService,
    storage: StorageBackend,
    filter_func: Optional[Callable[[str], str]] = None,
) -> dict:
    """Process a single sheet: download image, CSV, generate audio.

    Args:
        view: View dict with id, name, etc. from Tableau
        topic_id: Topic identifier for config lookup
        tableau_service: Initialized TableauService instance
        storage: Storage backend for writing outputs
        filter_func: Optional function to filter/transform CSV content

    Returns:
        Dictionary with processing results
    """
    view_id = view["id"]
    view_name = view["name"]

    print(f"Processing: {view_name} -> {topic_id}")

    # Load topic configuration
    topic_config = load_topic_config(topic_id)

    # Download image and save via storage backend
    image_bytes = tableau_service.download_view_image(view_id)
    image_path = storage.get_full_path("image", f"{topic_id}.png")
    storage.write_bytes(image_path, image_bytes)
    print(f"  Downloaded image: {image_path}")

    # Download CSV
    csv_content = tableau_service.download_view_csv(view_id)

    # Apply filter if provided
    if filter_func:
        csv_content = filter_func(csv_content)

    csv_path = storage.get_full_path("csv", f"{topic_id}.csv")
    storage.write_text(csv_path, csv_content)
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
    audio_path = storage.get_full_path("audio", f"{topic_id}.mp3")
    storage.write_bytes(audio_path, audio_bytes)
    print(f"  Generated audio: {audio_path}")

    # Save transcript
    transcript_path = storage.get_full_path("transcript", f"{topic_id}.txt")
    storage.write_text(transcript_path, transcript)
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

    # Get storage backend and create output structure
    storage = get_storage_backend()
    output_base = os.getenv("OUTPUT_BASE_PATH", "output")
    storage.create_output_structure(output_base)

    storage_settings = get_storage_settings()
    print(f"Storage mode: {storage_settings.mode}")
    print(f"Output base: {output_base}")

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
                storage=storage,
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
