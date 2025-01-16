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
def _modify_monitor(monitor_id: int, action: str):
    api = _get_api()
    try:
        if action == "pause":
            answer = api.pause_monitor(monitor_id)
        elif action == "resume":
            answer = api.resume_monitor(monitor_id)
        logger.info(f"Attempted to {action} monitor with ID: {monitor_id}")
        logger.info(answer)

        time.sleep(10)

        monitor_status = api.get_monitor(monitor_id)
        expected_active = 0 if action == "pause" else 1
        if monitor_status.get("active") == expected_active:
            logger.info(f"Successfully paused monitor with ID: {monitor_id}")
        else:
            raise Exception(
                f"Failed to pause monitor with ID: {monitor_id}. Monitor active status is unexpected."
            )
    except:
        raise
    finally:
        api.logout()
        del api


@app.post("/pause_monitor/{monitor_id}")
def pause_monitor(monitor_id: int):
    logger.info(f"Received request to pause monitor with ID: {monitor_id}")
    try:
        _modify_monitor(monitor_id, "pause")
    except Exception as e:
        logger.error(f"Failed to pause monitor with ID {monitor_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error pausing monitor: {str(e)}")


@app.post("/resume_monitor/{monitor_id}")
def resume_monitor(monitor_id: int):
    logger.info(f"Received request to resume monitor with ID: {monitor_id}")
    try:
        _modify_monitor(monitor_id, "resume")
    except Exception as e:
        logger.error(f"Failed to resume monitor with ID {monitor_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error resuming monitor: {str(e)}")


logger.info("Uptime Kuma API service is ready.")
