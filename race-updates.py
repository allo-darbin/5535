
import json
import time
import subprocess
import requests
import os
from pathlib import Path

# Configuration
URL = (
    "https://editor.opentracking.com/event/"
    "26ww50km/details?id=5535&e=21331"
)
FILENAME = Path("team5535_live.json")
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
    temp_file = FILENAME.with_suffix(".tmp")

    try:
        # 1. Fetch the tracking data
        response = session.get(URL, timeout=15)

        if not response.ok:
            log(f"Fetch failed: HTTP {response.status_code}")
            log(f"Response: {response.text[:200]}")
            return

        # 2. Parse and validate the JSON
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

        # 3. Write safely without risking the previous valid file
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

        os.replace(temp_file, FILENAME)

        # 4. Stage only the tracking data file
        subprocess.run(
            ["git", "add", "--", str(FILENAME)],
            check=True,
            capture_output=True,
            text=True,
        )

        # 5. Skip commit and push when the file is unchanged
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet",
             "--", str(FILENAME)],
            capture_output=True,
        )

        if result.returncode == 0:
            log("Data unchanged; skipping commit and push.")
            return

        if result.returncode != 1:
            raise RuntimeError("Could not check staged changes.")

        # 6. Commit only this file, not other staged files
        subprocess.run(
            [
                "git", "commit", "--only",
                "-m", f"Update race data {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "--", str(FILENAME),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        # 7. Push using your configured Git credentials
        subprocess.run(
            ["git", "push"],
            check=True,
            capture_output=True,
            text=True,
            timeout=45,
        )

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


if __name__ == "__main__":
    log(f"Tracker started; polling every {INTERVAL} seconds.")
    log("Press Ctrl+C to stop.")

    try:
        while True:
            started = time.monotonic()
            fetch_and_commit()
            elapsed = time.monotonic() - started
            time.sleep(max(0, INTERVAL - elapsed))

    except KeyboardInterrupt:
        log("Tracker stopped.")