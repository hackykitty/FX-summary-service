from __future__ import annotations

import asyncio
import json
from datetime import datetime
from statistics import mean
from typing import Dict, List, Optional, Tuple

import httpx
from dateutil.parser import isoparse
from fastapi import FastAPI, HTTPException, Query

# -------------------------------
# App configuration
# -------------------------------
PORT = 8000
BASE_URL = "https://api.frankfurter.dev/v1"
DEFAULT_FROM = "EUR"
DEFAULT_TO = "USD"
LOCAL_BACKUP = "data/sample_sk.json"  # fallback file (supports 2 shapes, see _unify_series)

_cache: Dict[Tuple[str, Optional[str], Optional[str], str, str], dict] = {}

app = FastAPI(title="SK Summary (Frankfurter-corrected)", version="1.2.0")


# -------------------------------
# Utilities
# -------------------------------
def _pct_delta_safe(current: float, previous: float) -> Optional[float]:
    """Percent change with division-by-zero protection."""
    if previous == 0:
        return None
    try:
        return ((current - previous) / previous) * 100.0
    except ZeroDivisionError:
        return None


async def _attempt_fetch(url: str, retries: int = 3, delay: float = 0.4) -> httpx.Response:
    """Small retry helper."""
    last_err = None
    for i in range(retries):
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, timeout=12.0)
                res.raise_for_status()
                return res
        except Exception as e:
            last_err = e
            if i == retries - 1:
                break
            await asyncio.sleep(delay * (i + 1))
    raise last_err


def _unify_series(obj: dict, to_ccy: str) -> List[dict]:
    """
    Convert Frankfurter responses (or our local fallback) into a list of
    {date, rate} sorted by date.

    Supported inputs:
      1) Frankfurter time series:
         { base, start_date, end_date, rates: {"YYYY-MM-DD": {"USD": 1.09, ...}, ...} }
      2) Frankfurter latest:
         { base, date, rates: {"USD": 1.09, ...} }
      3) Our local fallback array:
         { series: [ {date, from, to, rate}, ... ] }
    """
    # 1) Time series
    if "rates" in obj and isinstance(obj["rates"], dict):
        rows = []
        for d, mapping in obj["rates"].items():
            if to_ccy in mapping:
                rows.append({"date": d, "rate": float(mapping[to_ccy])})
        rows.sort(key=lambda x: x["date"])
        if rows:
            return rows

    # 2) Latest (single date)
    if "rates" in obj and "date" in obj and isinstance(obj["rates"], dict):
        if to_ccy in obj["rates"]:
            return [{"date": obj["date"], "rate": float(obj["rates"][to_ccy])}]

    # 3) Our local fallback shape
    if "series" in obj and isinstance(obj["series"], list):
        rows = [{"date": r["date"], "rate": float(r["rate"])} for r in obj["series"]]
        rows.sort(key=lambda x: x["date"])
        return rows

    return []


# -------------------------------
# Frankfurter fetchers (correct per docs)
# -------------------------------
async def _fetch_period(start: str, end: str, src: str, dst: str) -> List[dict]:
    """
    GET /{start}..{end}?base=SRC&symbols=DST
    Returns unified [{date, rate}, ...]
    """
    key = ("range", start, end, src, dst)
    if key in _cache:
        return _cache[key]["series"]

    url = f"{BASE_URL}/{start}..{end}?base={src}&symbols={dst}"
    try:
        res = await _attempt_fetch(url)
        data = res.json()
        series = _unify_series(data, dst)
        _cache[key] = {"series": series, "source": "remote"}
        return series
    except Exception:
        # fallback to local file (supports both shapes)
        try:
            with open(LOCAL_BACKUP, "r", encoding="utf-8") as f:
                blob = json.load(f)
            # If local is array-shape, filter by date & pair
            if "series" in blob:
                filtered = [
                    x for x in blob["series"]
                    if start <= x["date"] <= end and x.get("from") == src and x.get("to") == dst
                ]
                series = _unify_series({"series": filtered}, dst)
            else:
                # If local mimics Frankfurter, just unify+slice by date
                series = [r for r in _unify_series(blob, dst) if start <= r["date"] <= end]
            _cache[key] = {"series": series, "source": "fallback-file"}
            return series
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Remote + local failed: {e}")


async def _fetch_latest(src: str, dst: str) -> List[dict]:
    """
    GET /latest?base=SRC&symbols=DST
    Returns unified single-element [{date, rate}]
    """
    key = ("latest", None, None, src, dst)
    if key in _cache:
        return _cache[key]["series"]

    url = f"{BASE_URL}/latest?base={src}&symbols={dst}"
    try:
        res = await _attempt_fetch(url)
        data = res.json()
        series = _unify_series(data, dst)  # should be one item
        _cache[key] = {"series": series, "source": "remote"}
        return series
    except Exception:
        # fallback: take newest line from local file for src/dst
        try:
            with open(LOCAL_BACKUP, "r", encoding="utf-8") as f:
                blob = json.load(f)
            if "series" in blob:
                filt = [x for x in blob["series"] if x.get("from") == src and x.get("to") == dst]
                filt.sort(key=lambda x: x["date"])
                last = filt[-1]
                series = [{"date": last["date"], "rate": float(last["rate"])}]
            else:
                # Frankfurter-like local
                all_rows = _unify_series(blob, dst)
                series = all_rows[-1:] if all_rows else []
            _cache[key] = {"series": series, "source": "fallback-file"}
            return series
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Remote + local failed: {e}")


# -------------------------------
# Data shaping
# -------------------------------
def _daily_delta(series: List[dict]) -> List[dict]:
    out = []
    prev = None
    for s in series:
        val = float(s["rate"])
        pct = _pct_delta_safe(val, prev) if prev is not None else None
        out.append({"date": s["date"], "rate": val, "pct_change": pct})
        prev = val
    return out


def _summarize(series: List[dict]) -> dict:
    if not series:
        return {"start_rate": None, "end_rate": None, "total_pct_change": None, "mean_rate": None}
    start_r = float(series[0]["rate"])
    end_r = float(series[-1]["rate"])
    return {
        "start_rate": start_r,
        "end_rate": end_r,
        "total_pct_change": _pct_delta_safe(end_r, start_r),
        "mean_rate": mean([float(x["rate"]) for x in series]),
    }


def mini_trendpath(series: List[dict]) -> str:
    """
    Emoji trendline:
      2025-07-01→2025-07-03 | 💹 1.0900 ↗ 1.1020 ↘ 1.0975
    """
    if not series:
        return "(no data)"
    parts = [f"{series[0]['date']}→{series[-1]['date']} | 💹 {float(series[0]['rate']):.4f}"]
    for a, b in zip(series, series[1:]):
        ra, rb = float(a["rate"]), float(b["rate"])
        arrow = "↗" if rb > ra else ("↘" if rb < ra else "➡")
        parts.append(f"{arrow} {rb:.4f}")
    return " ".join(parts)


# -------------------------------
# Endpoints
# -------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat() + "Z",
        "message": "✅ andveron-pherbo :white_check_mark:"
    }


@app.get("/summary")
async def summary(
    start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD"),
    breakdown: str = Query("none", pattern="^(none|day|daily)$"),
    from_ccy: str = Query(DEFAULT_FROM),
    to_ccy: str = Query(DEFAULT_TO),
):
    # normalize
    breakdown = "day" if breakdown == "daily" else breakdown

    # Validate dates when provided
    if start and end:
        try:
            _ = isoparse(start)
            _ = isoparse(end)
        except Exception:
            raise HTTPException(status_code=400, detail="Dates must be YYYY-MM-DD")

        series = await _fetch_period(start, end, from_ccy, to_ccy)

        if breakdown == "day":
            return {
                "mode": "day",
                "pair": f"{from_ccy}/{to_ccy}",
                "series": _daily_delta(series),
                "trendline": mini_trendpath(series),
                "source": "remote_or_fallback",
            }
        else:
            return {
                "mode": "none",
                "pair": f"{from_ccy}/{to_ccy}",
                **_summarize(series),
                "trendline": mini_trendpath(series),
                "source": "remote_or_fallback",
            }

    # No range → use latest
    latest_series = await _fetch_latest(from_ccy, to_ccy)  # one item
    if breakdown == "day":
        return {
            "mode": "day",
            "pair": f"{from_ccy}/{to_ccy}",
            "series": _daily_delta(latest_series),
            "trendline": mini_trendpath(latest_series),
            "source": "remote_or_fallback",
        }
    else:
        return {
            "mode": "none",
            "pair": f"{from_ccy}/{to_ccy}",
            **_summarize(latest_series),
            "trendline": mini_trendpath(latest_series),
            "source": "remote_or_fallback",
        }


# -------------------------------
# Entrypoint
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    print("✅ andveron-pherbo :white_check_mark:")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
