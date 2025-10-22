# tests/test_app.py
import json
import logging
from typing import Iterable

from fastapi.testclient import TestClient
import main

# --- logging setup (shown if you run pytest with --log-cli-level=INFO) ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("tests.fx")


client = TestClient(main.app)


def _have_keys(d: dict, keys: Iterable[str]) -> bool:
    return all(k in d for k in keys)


def _pp(payload) -> str:
    try:
        return json.dumps(payload, indent=2, sort_keys=True)
    except Exception:
        return repr(payload)


def test_health(caplog):
    caplog.set_level(logging.INFO)
    r = client.get("/health")
    assert r.status_code == 200, f"/health status != 200\nBody:\n{_pp(r.text)}"
    body = r.json()

    log.info("HEALTH: status=%s, time=%s, message=%s",
             body.get("status"), body.get("time"), body.get("message"))

    assert body.get("status") == "ok", f"Unexpected status in /health:\n{_pp(body)}"
    assert "time" in body, f"'time' missing in /health:\n{_pp(body)}"
    assert "andveron-pherbo" in body.get("message", ""), "Final checkmark message missing"


def test_summary_latest_none(caplog):
    caplog.set_level(logging.INFO)
    r = client.get("/summary")
    assert r.status_code == 200, f"/summary status != 200\nBody:\n{_pp(r.text)}"
    body = r.json()

    log.info("LATEST: mode=%s pair=%s trendline=%s",
             body.get("mode"), body.get("pair"), body.get("trendline"))

    assert body.get("pair") == "EUR/USD", f"Pair mismatch:\n{_pp(body)}"
    assert "trendline" in body, f"'trendline' missing:\n{_pp(body)}"
    assert body.get("mode") in ("none", "day"), f"Invalid mode:\n{_pp(body)}"

    if body["mode"] == "none":
        needed = ("start_rate", "end_rate", "mean_rate", "total_pct_change")
        assert _have_keys(body, needed), f"Missing summary keys:\n{_pp(body)}"
        log.info("SUMMARY: start=%.6f end=%.6f mean=%.6f total_pct=%s",
                 body["start_rate"], body["end_rate"], body["mean_rate"], body["total_pct_change"])
    else:
        assert "series" in body and isinstance(body["series"], list) and body["series"], \
            f"Daily 'series' invalid:\n{_pp(body)}"
        first = body["series"][0]
        assert _have_keys(first, ("date", "rate", "pct_change")), f"Daily row missing keys:\n{_pp(first)}"
        # Log up to first 3 rows for visibility
        preview = body["series"][:3]
        log.info("DAILY PREVIEW (first %d rows): %s", len(preview), _pp(preview))


def test_summary_range_day(caplog):
    caplog.set_level(logging.INFO)
    r = client.get("/summary?start=2025-07-01&end=2025-07-03&breakdown=day")
    assert r.status_code == 200, f"Range day status != 200:\n{_pp(r.text)}"
    body = r.json()

    log.info("RANGE-DAY: pair=%s trendline=%s count=%s",
             body.get("pair"), body.get("trendline"), len(body.get("series", [])))

    assert body.get("mode") == "day", f"Mode not 'day':\n{_pp(body)}"
    assert body.get("pair") == "EUR/USD", f"Pair mismatch:\n{_pp(body)}"
    assert "trendline" in body, f"'trendline' missing:\n{_pp(body)}"
    assert "series" in body and isinstance(body["series"], list) and body["series"], \
        f"'series' invalid:\n{_pp(body)}"
    first, last = body["series"][0], body["series"][-1]
    assert _have_keys(first, ("date", "rate", "pct_change")), f"Row keys missing:\n{_pp(first)}"
    log.info("RANGE-DAY FIRST: %s", _pp(first))
    log.info("RANGE-DAY  LAST: %s", _pp(last))


def test_summary_range_none(caplog):
    caplog.set_level(logging.INFO)
    r = client.get("/summary?start=2025-07-01&end=2025-07-03&breakdown=none")
    assert r.status_code == 200, f"Range none status != 200:\n{_pp(r.text)}"
    body = r.json()

    log.info("RANGE-NONE: pair=%s trendline=%s", body.get("pair"), body.get("trendline"))

    assert body.get("mode") == "none", f"Mode not 'none':\n{_pp(body)}"
    assert body.get("pair") == "EUR/USD", f"Pair mismatch:\n{_pp(body)}"
    for key in ("start_rate", "end_rate", "mean_rate", "total_pct_change", "trendline"):
        assert key in body, f"Missing '{key}' in response:\n{_pp(body)}"
    log.info("SUMMARY: start=%.6f end=%.6f mean=%.6f total_pct=%s",
             body["start_rate"], body["end_rate"], body["mean_rate"], body["total_pct_change"])
