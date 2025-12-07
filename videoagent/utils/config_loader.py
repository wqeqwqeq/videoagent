"""YAML configuration loader for topic system prompts."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class TopicConfig(BaseModel):
    """Configuration loaded from topic YAML file."""

    name: str
    voice: str = "marin"
    instructions: str


def load_topic_config(topic_id: str, config_dir: Optional[Path] = None) -> TopicConfig:
    """Load topic configuration from YAML file.

    Args:
        topic_id: The topic identifier (e.g., "topic_01_major_issues")
        config_dir: Optional config directory path. Defaults to videoagent/config/

    Returns:
        TopicConfig with name, voice, and instructions
    """
    if config_dir is None:
        config_dir = Path(__file__).parent.parent / "config"

    config_path = config_dir / f"{topic_id}.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    return TopicConfig(
        name=config_data.get("name", topic_id),
        voice=config_data.get("voice", "marin"),
        instructions=config_data.get("instructions", ""),
    )
