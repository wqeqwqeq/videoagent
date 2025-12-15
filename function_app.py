"""Azure Functions entry point for VideoAgent.

Uses Python v2 programming model with timer triggers.
"""

import asyncio
import logging

import azure.functions as func

# Import the existing orchestrator
from orchestrator import main as orchestrator_main

app = func.FunctionApp()


@app.function_name(name="OrchestratorTimer")
@app.timer_trigger(
    schedule="%ORCHESTRATOR_SCHEDULE%",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def orchestrator_timer(timer: func.TimerRequest) -> None:
    """Timer trigger for the main orchestrator workflow.

    Runs the Tableau data download and voice generation pipeline.
    Schedule is configured via ORCHESTRATOR_SCHEDULE app setting (CRON format).
    Default: 0 0 6 * * * (Daily at 6 AM UTC)
    """
    if timer.past_due:
        logging.warning("Orchestrator timer is past due!")

    logging.info("Starting orchestrator workflow...")

    try:
        # Run the async main function
        results = asyncio.run(orchestrator_main())

        # Log summary
        if results:
            successful = [r for r in results if "error" not in r]
            failed = [r for r in results if "error" in r]
            logging.info(
                f"Orchestrator workflow completed. "
                f"Successful: {len(successful)}, Failed: {len(failed)}"
            )
        else:
            logging.info("Orchestrator workflow completed with no results.")

    except Exception as e:
        logging.error(f"Orchestrator workflow failed: {e}")
        raise


@app.function_name(name="VideoGeneratorTimer")
@app.timer_trigger(
    schedule="%VIDEO_SCHEDULE%",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def video_generator_timer(timer: func.TimerRequest) -> None:
    """Timer trigger for video generation.

    Combines images and audio into video files.
    Schedule is configured via VIDEO_SCHEDULE app setting (CRON format).
    Default: 0 0 7 * * * (Daily at 7 AM UTC)
    """
    if timer.past_due:
        logging.warning("Video generator timer is past due!")

    logging.info("Video generator triggered...")

    # TODO: Import and call video.py when created
    # from video import main as video_main
    # asyncio.run(video_main())

    logging.info("Video generator not yet implemented.")
