import os
import time
import sys
import getopt
import subprocess
import requests
import logging


def ntfy(ntfy_url, data, title, priority, tags):
    if ntfy_url:
        requests.post(
            f"http://{ntfy_url}/picsync",
            data=data,
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": tags,
            },
        )


def machine_up(hostname):
    response = os.system("ping -c 1 " + hostname)
    response_bool = response == 0

    logging.info(f"Is '{hostname}' up: {response_bool}")
    return response_bool


def sync(hostname, username, source, target, ntfy_url):
    logging.info("Starting sync...")

    logging.info(f"Source: {source}")
    logging.info(f"Target: {hostname}:{target}")

    password = os.environ.get("SSHPASS_PASSWORD")
    bashCommand = [
        "sshpass",
        "-p",
        f"{password}",
        "rsync",
        "-e",
        "ssh -o StrictHostKeyChecking=no",
        "-hazL",
        "--progress",
        "--delete",
        "-v",
        source,
        f"{username}@{hostname}:{target}",
    ]

    try:
        subprocess.run(bashCommand, check=True)
    except subprocess.CalledProcessError as err:
        logging.error(
            f"Process failed because did not return a successful return code. "
            f"Returned {err.returncode}\n{err}"
        )
        ntfy(
            ntfy_url,
            f"PicSync failed for '{source}'\n{err}",
            "PicSync failed",
            "urgent",
            "rotating_light",
        )
        raise

    logging.info("Sync completed!")
    ntfy(
        ntfy_url,
        f"PicSync completed for '{source}'",
        "PicSync completed",
        "default",
        "partying_face",
    )


def main(argv):
    hostname = ""
    username = ""
    source = ""
    target = ""

    try:
        opts, args = getopt.getopt(argv, "h:u:s:t:")
    except getopt.GetoptError as err:
        logging.error(f"Error: {err}")
        sys.exit(2)

    for opt, arg in opts:
        if opt in ["-h"]:
            hostname = arg
        elif opt in ["-u"]:
            username = arg
        elif opt in ["-s"]:
            source = arg
        elif opt in ["-t"]:
            target = arg

    ntfy_url = os.getenv("NTFY_URL")

    ntfy(
        ntfy_url,
        f"PicSync started for '{source}'",
        "PicSync started",
        "default",
        "partying_face",
    )

    while not machine_up(hostname):
        # sleep 10 minutes
        time.sleep(600)

    sync(hostname, username, source, target, ntfy_url)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    main(sys.argv[1:])
