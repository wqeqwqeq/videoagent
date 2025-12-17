"""Settings and configuration loader for VideoAgent."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============ Settings Classes ============


class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="AZURE_OPENAI_", env_file=".env", extra="ignore"
    )

    api_key: str = ""
    endpoint: str = ""
    deployment_name: str = ""
    api_version: str = "2024-10-21"

    def get_api_key(self) -> str:
        """Get API key from env or AKV fallback."""
        if "AZURE_OPENAI_API_KEY" in os.environ:
            return self.api_key
        from videoagent.services.keyvault import AKV

        akv = AKV()
        return akv.get_secret("azure-openai-api-key") or ""


class TableauSettings(BaseSettings):
    """Tableau Server configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="TABLEAU_", env_file=".env", extra="ignore"
    )

    server_url: str = ""
    site_id: str = ""
    workbook_id: str = ""
    username: str = ""
    password: str = ""

    def get_username(self) -> str:
        """Get username from env or AKV fallback."""
        if "TABLEAU_USERNAME" in os.environ:
            return self.username
        from videoagent.services.keyvault import AKV

        akv = AKV()
        return akv.get_secret("tableau-username") or ""

    def get_password(self) -> str:
        """Get password from env or AKV fallback."""
        if "TABLEAU_PASSWORD" in os.environ:
            return self.password
        from videoagent.services.keyvault import AKV

        akv = AKV()
        return akv.get_secret("tableau-password") or ""


class StorageSettings(BaseSettings):
    """Storage configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="STORAGE_", env_file=".env", extra="ignore"
    )

    mode: str = "local"  # "local" or "blob"
    account_name: str = ""
    container: str = "videoagent-output"


# Singleton instances
_azure_settings: Optional[AzureOpenAISettings] = None
_tableau_settings: Optional[TableauSettings] = None
_storage_settings: Optional[StorageSettings] = None


def get_azure_openai_settings() -> AzureOpenAISettings:
    """Get cached AzureOpenAISettings instance (singleton)."""
    global _azure_settings
    if _azure_settings is None:
        _azure_settings = AzureOpenAISettings()
    return _azure_settings


def get_tableau_settings() -> TableauSettings:
    """Get cached TableauSettings instance (singleton)."""
    global _tableau_settings
    if _tableau_settings is None:
        _tableau_settings = TableauSettings()
    return _tableau_settings


def get_storage_settings() -> StorageSettings:
    """Get cached StorageSettings instance (singleton)."""
    global _storage_settings
    if _storage_settings is None:
        _storage_settings = StorageSettings()
    return _storage_settings


# ============ Topic Config Loader ============


class TopicConfig(BaseModel):
    """Configuration loaded from topic YAML file."""

    name: str
    voice: str = "marin"
    instructions: str


def load_topic_config(topic_id: str) -> TopicConfig:
    """Load topic configuration from YAML file.

    Args:
        topic_id: Topic identifier (e.g., "topic_01_major_issues")

    Returns:
        TopicConfig with name, voice, and instructions
    """
    config_path = Path(__file__).parent / f"{topic_id}.yaml"
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return TopicConfig(**data)
