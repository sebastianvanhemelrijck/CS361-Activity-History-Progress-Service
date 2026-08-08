# Name: Sebastian Van Hemelrijck Noya
# Course: CS361 - Software Engineering 1
# Assignment: Assignment 9
# Due Date: 8/10/26
# Description: JSON storage for activity history

import json
import os
import uuid
from pathlib import Path

DATA_FILE = Path(
    os.environ.get("ACTIVITY_DATA_FILE", Path(__file__).with_name("activities.json"))
)


def load_activities():
    if not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0:
        return []
    with DATA_FILE.open("r", encoding="utf-8") as data_file:
        activities = json.load(data_file)
    if not isinstance(activities, list):
        raise ValueError("activity data must contain a JSON list")
    return activities


def save_activities(activities):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = DATA_FILE.with_suffix(DATA_FILE.suffix + ".tmp")
    with temp_file.open("w", encoding="utf-8") as output:
        json.dump(activities, output, indent=2)
    os.replace(temp_file, DATA_FILE)


def record_activity(payload):
    """Store a request once and report whether it created a new activity."""
    activities = load_activities()
    source = payload.get("source", "unknown").casefold()
    # reuse the first record when the same caller retries a request
    for activity in activities:
        if (
            activity.get("source", "unknown").casefold() == source
            and activity.get("request_id") == payload["request_id"]
        ):
            return activity, False
    activity = {**payload, "id": str(uuid.uuid4())}
    activities.append(activity)
    save_activities(activities)
    return activity, True
