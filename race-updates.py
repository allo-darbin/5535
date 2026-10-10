# Run as: python race-updates.py

import json
import time
import subprocess
import requests
import os
from pathlib import Path

# Configuration
URL = (
    "https://editor.opentracking.com/event/"
    "26ww70km/details?id=7066&e=21330" # individual
)

FILENAME = Path("team5535_live.json")

# Folder outside your git repo to save snapshots for post-race replay testing
BACKUP_DIR = Path(r"C:\Users\J\Desktop\race-updates-5335\darren")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

INTERVAL = 60

session = requests.Session()
session.headers.update({
    "Accept": "application/json",
    "User-Agent": "RaceTracker/1.0",
    "Referer": "https://editor.opentracking.com/",
})


def log(message):
    print(
        f"[{time.strftime('%H:%M:%S')}] {message}",
        flush=True,
    )


def fetch_and_commit():
    cycle_started = time.monotonic()
    temp_file = FILENAME.with_suffix(".tmp")

    try:
        # 1. Fetch the tracking data
        fetch_started = time.monotonic()

        response = session.get(URL, timeout=15)

        fetch_elapsed = time.monotonic() - fetch_started

        log(
            f"OpenTracking response: HTTP {response.status_code} "
            f"in {fetch_elapsed:.2f}s."
        )

        if not response.ok:
            log(f"Fetch failed: HTTP {response.status_code}")
            log(f"Response: {response.text[:200]}")
            return

        # 2. Parse and validate the JSON
        parse_started = time.monotonic()

        try:
            data = response.json()
        except ValueError:
            log("Response is not valid JSON; keeping previous data.")
            return

        if (
            not isinstance(data, dict)
            or data.get("type") != "details"
            or data.get("success") is not True
            or not isinstance(data.get("data"), dict)
        ):
            log("Unexpected response structure; keeping previous data.")
            return

        coordinates = data["data"].get("ll")
        log(f"Live coordinates: {coordinates}")

        # Validate that coordinates are present and usable
        if not isinstance(coordinates, str):
            log("Missing or invalid coordinates; keeping previous data.")
            return

        parts = coordinates.split(",")

        if len(parts) != 2:
            log("Invalid coordinate format; keeping previous data.")
            return

        try:
            lat, lon = map(float, parts)
        except ValueError:
            log("Invalid coordinate values; keeping previous data.")
            return

        if (
            not (-90 <= lat <= 90)
            or not (-180 <= lon <= 180)
        ):
            log("Coordinates out of range; keeping previous data.")
            return

        parse_elapsed = time.monotonic() - parse_started

        # 3. Write safely without risking the previous valid file
        write_started = time.monotonic()

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

        os.replace(temp_file, FILENAME)

        # --- LOCAL OFFLINE SNAPSHOT BACKUP (Outside Git Repo) ---
        timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
        backup_file = BACKUP_DIR / f"snap_{timestamp}.json"
        with open(backup_file, "w", encoding="utf-8") as bf:
            json.dump(data, bf, ensure_ascii=False, indent=2)
        # --------------------------------------------------------

        write_elapsed = time.monotonic() - write_started

        # 4. Stage only the tracking data file
        stage_started = time.monotonic()

        subprocess.run(
            ["git", "add", "--", str(FILENAME)],
            check=True,
            capture_output=True,
            text=True,
        )

        stage_elapsed = time.monotonic() - stage_started

        # 5. Skip commit and push when the file is unchanged
        result = subprocess.run(
            [
                "git",
                "diff",
                "--cached",
                "--quiet",
                "--",
                str(FILENAME),
            ],
            capture_output=True,
        )

        if result.returncode == 0:
            log("Data unchanged; skipping commit and push.")
            return

        if result.returncode != 1:
            raise RuntimeError("Could not check staged changes.")

        # 6. Commit only this file, not other staged files
        commit_started = time.monotonic()

        subprocess.run(
            [
                "git",
                "commit",
                "--only",
                "-m",
                f"Update race data {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "--",
                str(FILENAME),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        commit_elapsed = time.monotonic() - commit_started
        #log(f"Git commit completed in {commit_elapsed:.2f}s.")

        # 7. Push using your configured Git credentials
        push_started = time.monotonic()

        subprocess.run(
            ["git", "push"],
            check=True,
            capture_output=True,
            text=True,
            timeout=45,
        )

        push_elapsed = time.monotonic() - push_started
        #log(f"Git push completed in {push_elapsed:.2f}s.")
        log("Tracking data committed and pushed successfully.")

    except requests.RequestException as e:
        log(f"Network error: {e}")

    except subprocess.CalledProcessError as e:
        log(f"Command failed: {e.stderr or e}")

    except Exception as e:
        log(f"Error: {e}")

    finally:
        if temp_file.exists():
            temp_file.unlink()

        cycle_elapsed = time.monotonic() - cycle_started


if __name__ == "__main__":
    log(f"Tracker started; polling every {INTERVAL} seconds.")
    log(f"Offline snapshots saving to: {BACKUP_DIR}")
    log("Press Ctrl+C to stop.")

    try:
        while True:
            started = time.monotonic()

            fetch_and_commit()

            elapsed = time.monotonic() - started
            time.sleep(max(0, INTERVAL - elapsed))

    except KeyboardInterrupt:
        log("Tracker stopped.")