"""Storage abstraction for local and Azure Blob Storage."""

import logging
import os
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def create_output_structure(self, base_path: str = "output") -> dict[str, str]:
        """Create output folder/prefix structure.

        Args:
            base_path: Base output directory or container prefix

        Returns:
            Dictionary mapping folder names to paths/prefixes
        """
        pass

    @abstractmethod
    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> str:
        """Write text content to storage.

        Args:
            path: Full path or blob name
            content: Text content to write
            encoding: Text encoding

        Returns:
            The path/URL where content was written
        """
        pass

    @abstractmethod
    def write_bytes(self, path: str, content: bytes) -> str:
        """Write binary content to storage.

        Args:
            path: Full path or blob name
            content: Binary content to write

        Returns:
            The path/URL where content was written
        """
        pass

    @abstractmethod
    def get_full_path(self, folder_key: str, filename: str) -> str:
        """Get the full path for a file in a given folder.

        Args:
            folder_key: Folder key from output structure (audio, image, csv, transcript)
            filename: The filename to use

        Returns:
            Full path or blob name
        """
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self):
        self._output_paths: dict[str, str] = {}

    def create_output_structure(self, base_path: str = "output") -> dict[str, str]:
        """Create output folder structure on local filesystem.

        Structure: {base_path}/{YYYY-MM-DD}/{audio,image,csv,transcript}
        """
        today = date.today().isoformat()
        folders = ["audio", "image", "csv", "transcript"]
        paths = {}

        date_path = os.path.join(base_path, today)

        for folder in folders:
            folder_path = os.path.join(date_path, folder)
            os.makedirs(folder_path, exist_ok=True)
            paths[folder] = folder_path

        self._output_paths = paths
        logger.info(f"Created local output structure at {base_path}/{today}")
        return paths

    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> str:
        """Write text content to local file."""
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        logger.debug(f"Wrote text file: {path}")
        return path

    def write_bytes(self, path: str, content: bytes) -> str:
        """Write binary content to local file."""
        with open(path, "wb") as f:
            f.write(content)
        logger.debug(f"Wrote binary file: {path}")
        return path

    def get_full_path(self, folder_key: str, filename: str) -> str:
        """Get full local filesystem path."""
        return os.path.join(self._output_paths[folder_key], filename)


class BlobStorageBackend(StorageBackend):
    """Azure Blob Storage backend."""

    def __init__(self, account_name: str, container_name: str):
        """Initialize Blob Storage backend.

        Args:
            account_name: Azure Storage account name
            container_name: Container name for output
        """
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        self.account_name = account_name
        self.container_name = container_name
        self._output_paths: dict[str, str] = {}

        account_url = f"https://{account_name}.blob.core.windows.net"
        credential = DefaultAzureCredential()
        self.blob_service = BlobServiceClient(account_url, credential=credential)
        logger.info(f"Connected to blob storage via DefaultAzureCredential")

        self.container_client = self.blob_service.get_container_client(container_name)
        self._ensure_container_exists()

    def _ensure_container_exists(self):
        """Create container if it doesn't exist."""
        try:
            self.container_client.create_container()
            logger.info(f"Created container: {self.container_name}")
        except Exception as e:
            if "ContainerAlreadyExists" in str(e):
                logger.debug(f"Container already exists: {self.container_name}")
            else:
                logger.warning(f"Container check: {e}")

    def create_output_structure(self, base_path: str = "output") -> dict[str, str]:
        """Create output prefix structure for blob storage.

        In blob storage, folders are virtual (just prefixes).
        Structure: {base_path}/{YYYY-MM-DD}/{audio,image,csv,transcript}/

        Note: No actual creation needed - blobs with these prefixes
        will automatically create the "virtual folders".
        """
        today = date.today().isoformat()
        folders = ["audio", "image", "csv", "transcript"]
        paths = {}

        for folder in folders:
            prefix = f"{base_path}/{today}/{folder}"
            paths[folder] = prefix

        self._output_paths = paths
        logger.info(f"Configured blob output structure: {base_path}/{today}")
        return paths

    def write_text(self, path: str, content: str, encoding: str = "utf-8") -> str:
        """Write text content to blob storage."""
        blob_client = self.container_client.get_blob_client(path)
        blob_client.upload_blob(content.encode(encoding), overwrite=True)
        url = blob_client.url
        logger.debug(f"Wrote text blob: {path}")
        return url

    def write_bytes(self, path: str, content: bytes) -> str:
        """Write binary content to blob storage."""
        blob_client = self.container_client.get_blob_client(path)
        blob_client.upload_blob(content, overwrite=True)
        url = blob_client.url
        logger.debug(f"Wrote binary blob: {path}")
        return url

    def get_full_path(self, folder_key: str, filename: str) -> str:
        """Get full blob name (prefix + filename)."""
        return f"{self._output_paths[folder_key]}/{filename}"


# Singleton instance
_storage_backend: Optional[StorageBackend] = None


def get_storage_backend() -> StorageBackend:
    """Get configured storage backend (singleton).

    Returns:
        StorageBackend instance based on STORAGE_MODE setting
    """
    global _storage_backend
    if _storage_backend is None:
        from ..config import get_storage_settings

        settings = get_storage_settings()

        if settings.mode == "blob":
            if not settings.account_name:
                raise ValueError(
                    "Blob storage mode requires STORAGE_ACCOUNT_NAME to be set"
                )
            _storage_backend = BlobStorageBackend(
                account_name=settings.account_name,
                container_name=settings.container,
            )
        else:
            _storage_backend = LocalStorageBackend()

    return _storage_backend


def reset_storage_backend():
    """Reset the singleton (useful for testing)."""
    global _storage_backend
    _storage_backend = None
