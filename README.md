# SK Summary (FastAPI · Frankfurter-corrected)

A lightweight FastAPI microservice that fetches EUR→USD exchange rates from the **[Frankfurter.dev v1 API](https://www.frankfurter.dev/)**,  
computes daily percentage changes and summary statistics, and falls back to a local JSON file if the network is unavailable.

---

## 🌐 Endpoints

| Path | Description |
|------|--------------|
| `/health` | Health check with status and version message |
| `/summary` | Returns either **daily** or **aggregated** exchange-rate data |

---

## ⚙️ Query Parameters

| Parameter | Type | Description | Default |
|------------|-------|-------------|----------|
| `start` | `YYYY-MM-DD` | Range start date | – |
| `end` | `YYYY-MM-DD` | Range end date | – |
| `breakdown` | `'day'` or `'none'` (also accepts `'daily'`) | Choose day-by-day vs. summarized mode | `'none'` |
| `from_ccy` | ISO 4217 currency code | Base currency | `EUR` |
| `to_ccy` | ISO 4217 currency code | Target currency | `USD` |

---

## 🧮 Output Fields

### **Daily mode**

`breakdown=day`

```json
{
  "mode": "day",
  "pair": "EUR/USD",
  "series": [
    { "date": "2025-07-01", "rate": 1.0900, "pct_change": null },
    { "date": "2025-07-02", "rate": 1.1020, "pct_change": 1.10 },
    { "date": "2025-07-03", "rate": 1.0975, "pct_change": -0.41 }
  ],
  "trendline": "2025-07-01→2025-07-03 | 💹 1.0900 ↗ 1.1020 ↘ 1.0975",
  "source": "remote_or_fallback"
}
```

---

### **Aggregated mode**

`breakdown=none`

```json
{
  "mode": "none",
  "pair": "EUR/USD",
  "start_rate": 1.09,
  "end_rate": 1.0975,
  "total_pct_change": 0.688,
  "mean_rate": 1.0965,
  "trendline": "2025-07-01→2025-07-03 | 💹 1.0900 ↗ 1.1020 ↘ 1.0975",
  "source": "remote_or_fallback"
}
```

> **Division-by-zero:** if a previous day’s rate is `0`, `pct_change` is returned as `null`.

---

## 🧭 API Reference (Frankfurter v1)

- **Latest:**  
  `https://api.frankfurter.dev/v1/latest?base=EUR&symbols=USD`

- **Date range:**  
  `https://api.frankfurter.dev/v1/2025-07-01..2025-07-03?base=EUR&symbols=USD`

Responses are shaped like:

```json
{
  "amount": 1.0,
  "base": "EUR",
  "start_date": "2025-07-01",
  "end_date": "2025-07-03",
  "rates": {
    "2025-07-01": {"USD": 1.0900},
    "2025-07-02": {"USD": 1.1020},
    "2025-07-03": {"USD": 1.0975}
  }
}
```

If this API is unreachable, the app gracefully falls back to `data/sample_sk.json`.

---

## 🧰 Local Development

### 1️⃣ Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2️⃣ Run the server

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Server runs on **http://localhost:8000**

---

## 🧪 Example Calls

### Health check

```bash
curl http://localhost:8000/health
```

### Latest (aggregated)

```bash
curl "http://localhost:8000/summary"
```

### Latest (daily mode)

```bash
curl "http://localhost:8000/summary?breakdown=day"
```

### Date range (daily)

```bash
curl "http://localhost:8000/summary?start=2025-07-01&end=2025-07-03&breakdown=day"
```

### Date range (aggregated)

```bash
curl "http://localhost:8000/summary?start=2025-07-01&end=2025-07-03&breakdown=none"
```

---

## 🧩 Project Structure

```
.
├─ main.py
├─ requirements.txt
├─ data/
│  └─ sample_sk.json
├─ tests/
│  └─ test_app.py
├─ Dockerfile
└─ .github/
   └─ workflows/
      └─ ci.yml
```

---

## 🪙 Example Local Fallback File

`data/sample_sk.json`

```json
{
  "series": [
    {"date": "2025-07-01", "from": "EUR", "to": "USD", "rate": 1.09},
    {"date": "2025-07-02", "from": "EUR", "to": "USD", "rate": 1.102},
    {"date": "2025-07-03", "from": "EUR", "to": "USD", "rate": 1.0975}
  ],
  "source": "sample"
}
```

---

## 🧾 CI & Docker

- **Tests:**
  ```bash
  pytest -q
  ```

- **Docker:**
  ```bash
  docker build -t sk-summary .
  docker run -p 8000:8000 sk-summary
  ```

---

✅ **andveron-pherbo :white_check_mark:**  
_(🍍 Leave a pineapple by the door.)_
