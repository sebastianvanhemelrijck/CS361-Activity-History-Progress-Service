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


# ==== Deletion ====
 
def test_delete_removes_activity_for_matching_source(client):
    created = client.post("/activities", json=activity("request-1")).json["activity"]
 
    response = client.delete(f"/activities/{created['id']}", query_string={"source": "PrepTrack"})
 
    assert response.status_code == 204
    assert client.get("/activities").json["count"] == 0
 
 
def test_delete_requires_source(client):
    created = client.post("/activities", json=activity("request-1")).json["activity"]
 
    response = client.delete(f"/activities/{created['id']}")
 
    assert response.status_code == 400
    assert response.json["error"]["code"] == "INVALID_DELETE"
 
 
def test_delete_unknown_id_returns_404(client):
    response = client.delete("/activities/does-not-exist", query_string={"source": "PrepTrack"})
 
    assert response.status_code == 404
    assert response.json["error"]["code"] == "NOT_FOUND"
 
 
def test_delete_does_not_cross_sources(client):
    created = client.post(
        "/activities", json=activity("request-1", source="PrepTrack")
    ).json["activity"]
 
    response = client.delete(
        f"/activities/{created['id']}", query_string={"source": "HabitTracker"}
    )
 
    assert response.status_code == 404
    assert client.get("/activities").json["count"] == 1
 
 
# ==== Export ====
 
def test_export_json_returns_sorted_activities_for_source(client):
    client.post("/activities", json=activity("request-1"))
    client.post("/activities", json=activity("request-2", source="HabitTracker"))
 
    response = client.get("/export", query_string={"source": "PrepTrack"})
 
    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["activities"][0]["source"] == "PrepTrack"
 
 
def test_export_csv_returns_csv_content_type(client):
    client.post("/activities", json=activity("request-1"))
 
    response = client.get("/export", query_string={"source": "PrepTrack", "format": "csv"})
 
    assert response.status_code == 200
    assert response.content_type.startswith("text/csv")
    assert "request-1" in response.get_data(as_text=True)
 
 
def test_export_rejects_unknown_format(client):
    response = client.get("/export", query_string={"format": "xml"})
 
    assert response.status_code == 400
    assert response.json["error"]["code"] == "INVALID_FORMAT"
 
 
# ==== Streaks ====
 
def test_streak_counts_consecutive_days(client):
    today = datetime.now(timezone.utc)
    for offset in range(3):  # today, yesterday, day before
        payload = activity(f"streak-{offset}")
        payload["completed_at"] = (today - timedelta(days=offset)).isoformat()
        client.post("/activities", json=payload)
 
    response = client.get("/streaks", query_string={"source": "PrepTrack"})
 
    assert response.status_code == 200
    assert response.json["current_streak"] == 3
    assert response.json["longest_streak"] == 3
    assert response.json["total_active_days"] == 3
 
 
def test_streak_resets_after_a_gap(client):
    today = datetime.now(timezone.utc)
    active_offsets = [0, 1, 5, 6, 7]  # gap between day 1 and day 5
    for offset in active_offsets:
        payload = activity(f"gap-{offset}")
        payload["completed_at"] = (today - timedelta(days=offset)).isoformat()
        client.post("/activities", json=payload)
 
    response = client.get("/streaks", query_string={"source": "PrepTrack"})
 
    assert response.status_code == 200
    assert response.json["current_streak"] == 2  # today + yesterday
    assert response.json["longest_streak"] == 3  # the 3-day run further back
    assert response.json["total_active_days"] == 5
 
 
def test_streak_is_zero_when_last_activity_is_stale(client):
    payload = activity("stale-1")
    payload["completed_at"] = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    client.post("/activities", json=payload)
 
    response = client.get("/streaks", query_string={"source": "PrepTrack"})
 
    assert response.status_code == 200
    assert response.json["current_streak"] == 0
    assert response.json["longest_streak"] == 1
 
 
def test_streak_with_no_activities_returns_zero(client):
    response = client.get("/streaks", query_string={"source": "PrepTrack"})
 
    assert response.status_code == 200
    assert response.json["current_streak"] == 0
    assert response.json["longest_streak"] == 0
    assert response.json["last_active_day"] is None
 
 
# ==== Larger optional load fixture ====
 
def test_large_history_load_stays_correct(client):
    """Sanity check behavior once a program has a large recorded history."""
    today = datetime.now(timezone.utc)
    total_records = 500
    for index in range(total_records):
        activity_type = "inventory" if index % 3 == 0 else "readiness"
        payload = activity(f"load-{index}", activity_type)
        # spread records across the last 60 days, several per day
        payload["completed_at"] = (today - timedelta(days=index % 60)).isoformat()
        response = client.post("/activities", json=payload)
        assert response.status_code == 201
 
    listed = client.get("/activities", query_string={"source": "PrepTrack"})
    assert listed.json["count"] == total_records
 
    progress = client.get(
        "/progress",
        query_string={
            "source": "PrepTrack",
            "start": (today - timedelta(days=60)).isoformat(),
            "end": (today + timedelta(minutes=1)).isoformat(),
        },
    )
    assert progress.status_code == 200
    assert progress.json["total_activities"] == total_records
    assert sum(progress.json["by_activity_type"].values()) == total_records
 
    streaks = client.get("/streaks", query_string={"source": "PrepTrack"})
    assert streaks.status_code == 200
    assert streaks.json["total_active_days"] == 60
    assert streaks.json["current_streak"] == 60
