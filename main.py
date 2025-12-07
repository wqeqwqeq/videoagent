"""Main entry point for VideoAgent with DevUI and Application Insights."""

import logging

from agent_framework.devui import serve

from videoagent.workflows import create_video_workflow
from videoagent.utils.observability import setup_observability


def main():
    """Run the video generation workflow with DevUI."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Setup Application Insights observability
    logger.info("Setting up observability...")
    # setup_observability()

    # Create workflow
    logger.info("Creating Video Generation Workflow...")
    workflow = create_video_workflow()

    # Start DevUI server
    logger.info("Starting DevUI server...")
    logger.info("=" * 50)
    logger.info("VideoAgent DevUI available at: http://localhost:8090")
    logger.info("=" * 50)

    serve(
        entities=[workflow],
        port=8090,
        auto_open=True,
    )


if __name__ == "__main__":
    main()
