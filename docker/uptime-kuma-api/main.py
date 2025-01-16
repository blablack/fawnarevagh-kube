import os
import logging
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from uptime_kuma_api import UptimeKumaApi
from tenacity import retry, stop_after_attempt, wait_fixed
import aiohttp
import asyncio

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Uptime Kuma API")

# Global session for connection pooling
session = None


async def get_session():
    global session
    if session is None:
        session = aiohttp.ClientSession()
    return session


async def close_session():
    global session
    if session:
        await session.close()
        session = None


@app.on_event("startup")
async def startup_event():
    await get_session()


@app.on_event("shutdown")
async def shutdown_event():
    await close_session()


async def get_api():
    kuma_url = os.getenv("KUMA_URL")
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")

    if not all([kuma_url, username, password]):
        raise ValueError("Missing required environment variables.")

    session = await get_session()
    api = UptimeKumaApi(kuma_url, session=session)

    try:
        await api.login(username, password)
        logger.info("Successfully logged into Uptime Kuma API.")
    except Exception as e:
        logger.error(f"Failed to log in to Uptime Kuma API: {e}")
        raise

    return api


@retry(stop=stop_after_attempt(3), wait=wait_fixed(30))
async def modify_monitor(monitor_id: int, action: str) -> Dict[str, Any]:
    api = await get_api()
    try:
        if action == "pause":
            result = await api.pause_monitor(monitor_id)
        elif action == "resume":
            result = await api.resume_monitor(monitor_id)
        else:
            raise ValueError(f"Invalid action: {action}")

        logger.info(f"Attempted to {action} monitor with ID: {monitor_id}")
        logger.info(result)

        await asyncio.sleep(10)

        monitor_status = await api.get_monitor(monitor_id)
        expected_status = 0 if action == "pause" else 1
        if monitor_status.get("active") == expected_status:
            logger.info(f"Successfully {action}d monitor with ID: {monitor_id}")
        else:
            raise Exception(
                f"Failed to {action} monitor with ID: {monitor_id}. Unexpected status."
            )

        return result
    finally:
        await api.logout()


@app.post("/pause_monitor/{monitor_id}")
async def pause_monitor(monitor_id: int):
    logger.info(f"Received request to pause monitor with ID: {monitor_id}")
    try:
        await modify_monitor(monitor_id, "pause")
    except Exception as e:
        logger.error(f"Failed to pause monitor with ID {monitor_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error pausing monitor: {str(e)}")


@app.post("/resume_monitor/{monitor_id}")
async def resume_monitor(monitor_id: int):
    logger.info(f"Received request to resume monitor with ID: {monitor_id}")
    try:
        await modify_monitor(monitor_id, "resume")
    except Exception as e:
        logger.error(f"Failed to resume monitor with ID {monitor_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error resuming monitor: {str(e)}")


logger.info("Uptime Kuma API service is ready.")
