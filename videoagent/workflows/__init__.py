"""Workflow definitions for video generation."""

from .video_workflow import create_video_workflow
from .mock_workflow import create_mock_workflow

__all__ = ["create_video_workflow", "create_mock_workflow"]
