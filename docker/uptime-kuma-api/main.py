import os
import logging
import time

from fastapi import FastAPI, HTTPException
from uptime_kuma_api import UptimeKumaApi
from tenacity import retry, stop_after_attempt, wait_fixed

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("Uptime Kuma API")


def _get_api():
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


@retry(stop=stop_after_attempt(3), wait=wait_fixed(30))
def _pause_monitor(monitor_id: int):
    try:
        api = _get_api()
        answer = api.pause_monitor(monitor_id)
        logger.info(f"Attempted tp pause monitor with ID: {monitor_id}")
        logger.info(answer)

        time.sleep(10)

        monitor_status = api.get_monitor(monitor_id)
        if monitor_status.get("active") == 0:
            logger.info(f"Successfully paused monitor with ID: {monitor_id}")
        else:
            raise Exception(
                f"Failed to pause monitor with ID: {monitor_id}. Monitor is still active."
            )
    except:
        raise


@app.post("/pause_monitor/{monitor_id}")
async def pause_monitor(monitor_id: int):
    logger.info(f"Received request to pause monitor with ID: {monitor_id}")
    try:
        _pause_monitor(monitor_id)
    except Exception as e:
        logger.error(f"Failed to pause monitor with ID {monitor_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error pausing monitor: {str(e)}")


@retry(stop=stop_after_attempt(3), wait=wait_fixed(30))
def _resume_monitor(monitor_id: int):
    try:
        api = _get_api()
        answer = api.resume_monitor(monitor_id)
        logger.info(f"Attempted to resume monitor with ID: {monitor_id}")
        logger.info(answer)

        time.sleep(10)

        monitor_status = api.get_monitor(monitor_id)
        if monitor_status.get("active") == 1:
            logger.info(f"Successfully resumed monitor with ID: {monitor_id}")
        else:
            raise Exception(
                f"Failed to resume monitor with ID: {monitor_id}. Monitor is still paused."
            )
    except:
        raise


@app.post("/resume_monitor/{monitor_id}")
async def resume_monitor(monitor_id: int):
    logger.info(f"Received request to resume monitor with ID: {monitor_id}")
    try:
        _resume_monitor(monitor_id)
    except Exception as e:
        logger.error(f"Failed to resume monitor with ID {monitor_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error resuming monitor: {str(e)}")


logger.info("Uptime Kuma API service is ready.")
