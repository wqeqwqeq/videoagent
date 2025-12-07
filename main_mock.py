"""Mock workflow entry point for testing without Tableau."""

import logging

from agent_framework.devui import serve

from videoagent.workflows import create_mock_workflow
from videoagent.utils.observability import setup_observability


def main():
    """Run the mock video generation workflow with DevUI.

    This workflow reads JSON files from ./output/json folder
    instead of downloading from Tableau.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Setup Application Insights observability
    logger.info("Setting up observability...")
    # setup_observability()

    # Create mock workflow
    logger.info("Creating Mock Video Generation Workflow...")
    logger.info("Reading JSON from ./output/json folder...")
    workflow = create_mock_workflow()

    # Start DevUI server
    logger.info("Starting DevUI server...")
    logger.info("=" * 50)
    logger.info("VideoAgent Mock DevUI available at: http://localhost:8090")
    logger.info("=" * 50)
    logger.info("")
    logger.info("To use this workflow:")
    logger.info("1. Place JSON files in ./output/json/")
    logger.info("   (e.g., topic_01_major_issues.json)")
    logger.info("2. Open DevUI and run the workflow")
    logger.info("")

    serve(
        entities=[workflow],
        port=8090,
        auto_open=True,
    )


if __name__ == "__main__":
    main()
