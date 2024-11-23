import os
import time
import sys
import subprocess
import requests
import logging
import argparse


def ntfy(ntfy_url, data, title, priority="default", tags=None):
    if ntfy_url:
        try:
            logging.info(f"Sending to ntfy http://{ntfy_url}/picsync: {data}")
            response = requests.post(
                f"http://{ntfy_url}/picsync",
                data=data,
                headers={
                    "Title": title,
                    "Priority": priority,
                    "Tags": tags if tags else "",
                },
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to send notification: {e}")


def machine_up(hostname):
    response = os.system(f"ping -c 1 {hostname}")
    response_bool = response == 0

    logging.info(f"Is '{hostname}' up: {response_bool}")
    return response_bool


def sync(hostname, username, source, target, ntfy_url):
    logging.info(f"Starting sync...\nSource: {source}\nTarget: {hostname}:{target}")

    password = os.environ.get("SSHPASS_PASSWORD")
    if not password:
        logging.error("Environment variable SSHPASS_PASSWORD not set")
        sys.exit(1)

    bash_command = [
        "sshpass",
        "-p",
        password,
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
        subprocess.run(bash_command, check=True)
    except subprocess.CalledProcessError as err:
        logging.error(f"Process failed with return code {err.returncode}\n{err}")
        ntfy(
            ntfy_url,
            f"PicSync failed for '{hostname}:{target}'\n{err}",
            "PicSync failed",
            "urgent",
            "rotating_light",
        )
        raise

    logging.info("Sync completed!")
    ntfy(
        ntfy_url,
        f"PicSync completed for '{hostname}:{target}'",
        "PicSync completed",
        "default",
        "partying_face",
    )


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-H", "--hostname", required=True, help="Hostname of the target machine"
    )
    parser.add_argument(
        "-u", "--username", required=True, help="Username for the target machine"
    )
    parser.add_argument(
        "-s", "--source", required=True, help="Source directory to sync"
    )
    parser.add_argument(
        "-t", "--target", required=True, help="Target directory on the destination"
    )

    args = parser.parse_args(args)

    ntfy_url = os.getenv("NTFY_URL")

    ntfy(
        ntfy_url,
        f"PicSync started for '{args.hostname}:{args.target}'",
        "PicSync started",
        "default",
        "partying_face",
    )

    while not machine_up(args.hostname):
        # sleep 10 minutes
        time.sleep(600)

    sync(args.hostname, args.username, args.source, args.target, ntfy_url)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    main(sys.argv[1:])
