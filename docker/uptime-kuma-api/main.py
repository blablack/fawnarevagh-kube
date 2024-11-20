import os
import logging

from fastapi import FastAPI, HTTPException
from uptime_kuma_api import UptimeKumaApi

app = FastAPI()

logging.basicConfig(
    level=logging.DEBUG,  # Set the log level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Define the log format
)
logger = logging.getLogger("Uptime Kuma API")


def get_api():
    kuma_url = os.getenv("KUMA_URL")
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")

    if not kuma_url or not username or not password:
        logger.error(
            "Environment variables KUMA_URL, USERNAME, or PASSWORD are missing."
        )
        raise ValueError("Missing required environment variables.")

    api = UptimeKumaApi(kuma_url)

    try:
        api.login(username, password)
        logger.info("Successfully logged into Uptime Kuma API.")
    except Exception as e:
        logger.error(f"Failed to log in to Uptime Kuma API: {e}")
        raise

    return api


@app.post("/pause_monitor/{monitor_id}")
async def pause_monitor(monitor_id: int):
    logger.info(f"Received request to pause monitor with ID: {monitor_id}")
    try:
        api = get_api()
        answer = api.pause_monitor(monitor_id)
        logger.info(f"Successfully paused monitor with ID: {monitor_id}")
        logger.info(answer)
    except Exception as e:
        logger.error(f"Failed to pause monitor with ID {monitor_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error pausing monitor: {str(e)}")


@app.post("/resume_monitor/{monitor_id}")
async def resume_monitor(monitor_id: int):
    logger.info(f"Received request to resume monitor with ID: {monitor_id}")
    try:
        api = get_api()
        answer = api.resume_monitor(monitor_id)
        logger.info(f"Successfully resumed monitor with ID: {monitor_id}")
        logger.info(answer)
    except Exception as e:
        logger.error(f"Failed to resume monitor with ID {monitor_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error resuming monitor: {str(e)}")


logger.info("Uptime Kuma API service is ready.")
