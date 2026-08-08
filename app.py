# Name: Sebastian Van Hemelrijck Noya
# Course: CS361 - Software Engineering 1
# Assignment: Assignment 9
# Due Date: 8/10/26
# Description: REST API for recording activity history and progress summaries

import os
from collections import Counter
from datetime import datetime, timezone

from flask import Flask, jsonify, request

import storage

app = Flask(__name__)


def parse_time(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required and must be an ISO 8601 date and time.")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be a valid ISO 8601 date and time.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def send_error(status, code, message):
    return jsonify({"error": {"code": code, "message": message}}), status


@app.after_request
def allow_main_program(response):
    configured = os.environ.get(
        "MAIN_PROGRAM_ORIGINS",
        os.environ.get(
            "MAIN_PROGRAM_ORIGIN",
            "http://localhost:5173,http://127.0.0.1:5173",
        ),
    )
    allowed = {
        value.strip().rstrip("/") for value in configured.split(",") if value.strip()
    }
    origin = (request.headers.get("Origin") or "").rstrip("/")
    if origin in allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.get("/health")
def health():
    return jsonify({"service": "activity-history", "status": "ok"})


@app.post("/activities")
def record_activity():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return send_error(400, "INVALID_ACTIVITY", "The request body must be a JSON object.")

    normalized = {}
    for field in ("request_id", "name", "activity_type"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            return send_error(400, "INVALID_ACTIVITY", f"{field} is required.")
        normalized[field] = value.strip()
    try:
        normalized["completed_at"] = parse_time(
            payload.get("completed_at"), "completed_at"
        ).isoformat()
    except ValueError as error:
        return send_error(400, "INVALID_ACTIVITY", str(error))
    normalized["source"] = str(payload.get("source", "unknown")).strip() or "unknown"
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        return send_error(400, "INVALID_ACTIVITY", "metadata must be a JSON object.")
    normalized["metadata"] = metadata

    activity, created = storage.record_activity(normalized)
    return jsonify({"created": created, "activity": activity}), 201 if created else 200


@app.get("/activities")
def list_activities():
    source = request.args.get("source", "").strip().casefold()
    activities = storage.load_activities()
    if source:
        activities = [
            item for item in activities if item.get("source", "").casefold() == source
        ]
    activities.sort(key=lambda item: item["completed_at"], reverse=True)
    return jsonify({"count": len(activities), "activities": activities})


@app.get("/progress")
def progress_summary():
    try:
        start = parse_time(request.args["start"], "start") if "start" in request.args else None
        end = parse_time(request.args["end"], "end") if "end" in request.args else None
    except ValueError as error:
        return send_error(400, "INVALID_RANGE", str(error))
    if start and end and start > end:
        return send_error(400, "INVALID_RANGE", "start must be before or equal to end.")

    source = request.args.get("source", "").strip().casefold()
    activities = storage.load_activities()
    selected = []
    # keep only records from the caller and date range
    for activity in activities:
        completed = parse_time(activity["completed_at"], "completed_at")
        if source and activity.get("source", "").casefold() != source:
            continue
        if start and completed < start:
            continue
        if end and completed > end:
            continue
        selected.append(activity)

    counts = Counter(item["activity_type"] for item in selected)
    return jsonify({
        "total_activities": len(selected),
        "by_activity_type": dict(sorted(counts.items())),
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5105")), debug=False)
