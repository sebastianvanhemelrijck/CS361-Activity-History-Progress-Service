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


def activity(request_id, activity_type="inventory", source="PrepTrack"):
    return {
        "request_id": request_id,
        "name": "Saved a kit item",
        "activity_type": activity_type,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
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


def test_request_id_is_scoped_to_each_main_program(client):
    first = client.post(
        "/activities",
        json=activity("request-1", source="GuitarExerciseGenerator"),
    )
    second = client.post(
        "/activities",
        json=activity("request-1", source="HabitTracker"),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert client.get("/activities").json["count"] == 2


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


def test_known_20_activity_history_returns_exact_counts(client):
    completed_at = datetime.now(timezone.utc)

    for index in range(20):
        activity_type = "inventory" if index < 12 else "readiness"
        payload = activity(f"known-{index}", activity_type)
        payload["completed_at"] = completed_at.isoformat()
        response = client.post("/activities", json=payload)
        assert response.status_code == 201

    response = client.get(
        "/progress",
        query_string={
            "source": "PrepTrack",
            "start": (completed_at - timedelta(minutes=1)).isoformat(),
            "end": (completed_at + timedelta(minutes=1)).isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json["total_activities"] == 20
    assert response.json["by_activity_type"] == {
        "inventory": 12,
        "readiness": 8,
    }


def test_configured_main_program_origin_is_allowed(client, monkeypatch):
    monkeypatch.setenv(
        "MAIN_PROGRAM_ORIGINS",
        "http://localhost:3000,http://localhost:4173",
    )

    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
