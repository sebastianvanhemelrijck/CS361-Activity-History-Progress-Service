# Name: Sebastian Van Hemelrijck Noya
# Course: CS361 - Software Engineering 1
# Assignment: Assignment 9
# Due Date: 8/10/26
# Description: Tests for activity history and progress summaries

from datetime import datetime, timedelta, timezone

import pytest

import storage
from app import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_FILE", tmp_path / "activities.json")
    app.config.update(TESTING=True)
    return app.test_client()


def activity(request_id, activity_type="inventory"):
    return {
        "request_id": request_id,
        "name": "Saved a kit item",
        "activity_type": activity_type,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "source": "PrepTrack",
    }


def test_records_activity_and_returns_json(client):
    response = client.post("/activities", json=activity("request-1"))

    assert response.status_code == 201
    assert response.json["created"] is True
    assert response.json["activity"]["id"]


def test_request_id_makes_recording_idempotent(client):
    first = client.post("/activities", json=activity("request-1"))
    second = client.post("/activities", json=activity("request-1"))

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json["created"] is False
    assert client.get("/activities").json["count"] == 1


def test_progress_counts_a_date_range_by_type(client):
    client.post("/activities", json=activity("request-1", "inventory"))
    client.post("/activities", json=activity("request-2", "readiness"))
    client.post("/activities", json=activity("request-3", "inventory"))
    now = datetime.now(timezone.utc)
    start = (now - timedelta(minutes=1)).isoformat()
    end = (now + timedelta(minutes=1)).isoformat()

    response = client.get(
        "/progress",
        query_string={"source": "PrepTrack", "start": start, "end": end},
    )

    assert response.status_code == 200
    assert response.json["total_activities"] == 3
    assert response.json["by_activity_type"] == {"inventory": 2, "readiness": 1}
