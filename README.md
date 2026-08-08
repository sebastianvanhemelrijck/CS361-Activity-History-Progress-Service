# Activity History and Progress Service

MS5 is a reusable service for recording completed activities and returning
progress summaries.

## Communication contract

The service uses a REST API with JSON at `http://127.0.0.1:5105` by default.

| Method and path | Purpose |
| --- | --- |
| `GET /health` | Check whether the service is running |
| `POST /activities` | Record one completed activity idempotently |
| `GET /activities?source=PrepTrack` | List recorded activities |
| `GET /progress?source=PrepTrack&start=...&end=...` | Count activities by type |

Recording requires `request_id`, `name`, `activity_type`, and an ISO 8601
`completed_at` value. Sending the same `request_id` twice returns the original
record without storing a duplicate.

```powershell
python -m pip install -r requirements.txt
python app.py
python -m pytest -q
```

## Sprint 3 stories

- Record a completed activity.
- View an activity and progress summary for a date range.

## Remaining shared work

Recording, persistence, idempotency, date-range summaries, validation, and the
PrepTrack contract are implemented. Deletion, export, streak calculations, and
larger accuracy/load fixtures remain available for another teammate.
