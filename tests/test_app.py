# tests/test_app.py
from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    # updated field name
    assert "time" in body
    # optional: the special message
    assert "andveron-pherbo" in body.get("message", "")


def test_summary_latest_none():
    # No params -> latest; default breakdown='none'
    r = client.get("/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] in ("none", "day")
    assert body["pair"] == "EUR/USD"
    assert "trendline" in body

    if body["mode"] == "none":
        # aggregated keys
        assert "start_rate" in body
        assert "end_rate" in body
        assert "mean_rate" in body
        assert "total_pct_change" in body
    else:
        # daily keys
        assert "series" in body and isinstance(body["series"], list)
        row0 = body["series"][0]
        assert {"date", "rate", "pct_change"} <= set(row0.keys())


def test_summary_range_day():
    # Explicit day breakdown over a range
    r = client.get("/summary?start=2025-07-01&end=2025-07-03&breakdown=day")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "day"
    assert body["pair"] == "EUR/USD"
    assert "trendline" in body
    assert "series" in body and isinstance(body["series"], list) and len(body["series"]) >= 1
    first = body["series"][0]
    assert {"date", "rate", "pct_change"} <= set(first.keys())


def test_summary_range_none():
    # Aggregated mode over the same range
    r = client.get("/summary?start=2025-07-01&end=2025-07-03&breakdown=none")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "none"
    assert body["pair"] == "EUR/USD"
    for key in ("start_rate", "end_rate", "mean_rate", "total_pct_change", "trendline"):
        assert key in body
