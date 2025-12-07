"""Pydantic settings for VideoAgent configuration."""

from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


# Topic ID to View Name mapping
# Maps internal topic identifiers to Tableau view names
TOPIC_VIEW_NAMES = {
    "topic_01_major_issues": "Major Issues",
    "topic_02_critical_workflows_current": "Critical Workflows Current",
    "topic_03_critical_workflows_history": "Critical Workflows History",
    "topic_04_platform_health_current": "Platform Health Current",
    "topic_05_platform_health_history": "Platform Health History",
    "topic_06_cr_deployed_24h": "CR Deployed 24h",
    "topic_07_cr_upcoming": "CR Upcoming",
    "topic_08_cr_overdue": "CR Overdue",
    "topic_09_problems_tasks": "Problems Tasks",
    "topic_10_major_incidents": "Major Incidents",
    "topic_11_manual_unplanned_activities": "Manual Unplanned Activities",
    "topic_12_upcoming_completed_events": "Upcoming Completed Events",
    "topic_13_open_items_summary": "Open Items Summary",
}

# Singleton instances
_azure_openai_settings: Optional["AzureOpenAISettings"] = None
_tableau_settings: Optional["TableauSettings"] = None


class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="AZURE_OPENAI_", env_file=".env", extra="ignore"
    )

    api_key: str = ""
    endpoint: str = ""
    deployment_name: str = ""
    api_version: str = "2024-10-21"


class TableauSettings(BaseSettings):
    """Tableau Server configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="TABLEAU_", env_file=".env", extra="ignore"
    )

    server_url: str = ""
    site_id: str = ""
    workbook_id: str = ""
    auth_method: str = "pat"  # "pat" or "username_password"
    pat_name: str = ""
    pat_value: str = ""
    username: str = ""
    password: str = ""


class OutputSettings(BaseSettings):
    """Output directory configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    output_base_path: str = "./output"


class AppInsightsSettings(BaseSettings):
    """Application Insights configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    applicationinsights_connection_string: str = ""


def get_azure_openai_settings() -> AzureOpenAISettings:
    """Get cached AzureOpenAISettings instance (singleton)."""
    global _azure_openai_settings
    if _azure_openai_settings is None:
        _azure_openai_settings = AzureOpenAISettings()
    return _azure_openai_settings


def get_tableau_settings() -> TableauSettings:
    """Get cached TableauSettings instance (singleton)."""
    global _tableau_settings
    if _tableau_settings is None:
        _tableau_settings = TableauSettings()
    return _tableau_settings


def get_output_settings() -> OutputSettings:
    """Get OutputSettings instance."""
    return OutputSettings()


def get_app_insights_settings() -> AppInsightsSettings:
    """Get AppInsightsSettings instance."""
    return AppInsightsSettings()
