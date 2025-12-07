"""File and output folder management for VideoAgent."""

import os
from datetime import datetime
from pathlib import Path


class FileManager:
    """Manages output folders and file paths for video generation."""

    FOLDERS = ["csv", "pic", "json", "audio", "transcript", "video"]

    def __init__(self, base_path: str = "./output"):
        """Initialize FileManager with base output path.

        Args:
            base_path: Base directory for all output files
        """
        self.base_path = Path(base_path)

    def ensure_output_folders(self) -> dict[str, Path]:
        """Create output folders if they don't exist.

        Returns:
            Dictionary mapping folder names to their Path objects
        """
        paths = {}
        for folder in self.FOLDERS:
            path = self.base_path / folder
            path.mkdir(parents=True, exist_ok=True)
            paths[folder] = path
        return paths

    @staticmethod
    def get_timestamp() -> str:
        """Generate timestamp in yyyy_mm_dd_hh_mm_ss format.

        Returns:
            Timestamp string (e.g., "2025_12_07_14_30_45")
        """
        return datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    def get_file_path(
        self, folder: str, topic_id: str, extension: str, timestamp: str = None
    ) -> Path:
        """Get full file path for a topic output file.

        Args:
            folder: Output folder name (csv, pic, audio, transcript, video)
            topic_id: Topic identifier (e.g., "topic_01_major_issues")
            extension: File extension without dot (e.g., "mp3", "txt", "png")
            timestamp: Optional timestamp. If None, generates new timestamp.

        Returns:
            Full Path object for the output file
        """
        if timestamp is None:
            timestamp = self.get_timestamp()

        filename = f"{topic_id}_{timestamp}.{extension}"
        return self.base_path / folder / filename

    def get_csv_path(self, topic_id: str) -> Path:
        """Get path for CSV file (no timestamp, just topic_id).

        Args:
            topic_id: Topic identifier

        Returns:
            Path to CSV file
        """
        return self.base_path / "csv" / f"{topic_id}.csv"

    def get_json_path(self, topic_id: str) -> Path:
        """Get path for JSON file (for mock workflow input).

        Args:
            topic_id: Topic identifier

        Returns:
            Path to JSON file
        """
        return self.base_path / "json" / f"{topic_id}.json"
