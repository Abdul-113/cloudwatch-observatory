# 🔭 CloudWatch Observatory

> Real-time cloud service monitoring dashboard with ML-powered anomaly detection.

## Overview

CloudWatch Observatory is a lightweight monitoring platform that collects metrics from Prometheus, detects anomalies using ensemble machine learning models (ECOD + Isolation Forest), and visualizes service health through a sleek web dashboard.

## Quick Start

### Prerequisites
- Python 3.8+
- pip

### Option 1: Quick Start Script (Linux / macOS)
```bash
chmod +x start.sh
./start.sh
```

### Option 2: Manual Setup
```bash
# Install dependencies
pip install -r backend/requirements.txt

# Generate demo data (24 hours)
cd backend
python demo_data.py historical 24

# Start the Flask API server
python app.py
```

Then open `frontend/dashboard.html` in your browser.

## Architecture

```
Prometheus → PrometheusClient → MetricsCollector → SQLite DB
                                        ↓
                                 AnomalyDetector
                                        ↓
                                 Anomaly Database

Browser → REST API → Database → JSON → Dashboard UI
```

## API Endpoints

| Method | Endpoint                      | Description              |
|--------|-------------------------------|--------------------------|
| GET    | `/api/services`               | List registered services |
| POST   | `/api/services/register`      | Register a new service   |
| GET    | `/api/health/summary`         | Health overview           |
| GET    | `/api/health/anomalies`       | Anomaly list              |
| GET    | `/api/metrics/history`        | Time-series metric data   |
| POST   | `/api/collect/<service>`      | Manual metric collection  |

## Demo Data

Generate realistic demo metrics for testing:

```bash
cd backend

# Backfill 24h of historical data
python demo_data.py historical 24

# Stream live metrics every 5 seconds
python demo_data.py live

# Both historical + live stream
python demo_data.py both
```

## Tech Stack

| Layer    | Technology                                     |
|----------|------------------------------------------------|
| Backend  | Flask 3.0, NumPy, scikit-learn, PyOD, SQLite   |
| Frontend | Vanilla JS, Chart.js 4.4, CSS Grid/Flexbox     |
| Fonts    | Outfit, JetBrains Mono (Google Fonts)           |

## Anomaly Detection

The system uses an **ensemble** approach combining:
- **ECOD** (Empirical Cumulative Distribution) — statistical outlier detection
- **Isolation Forest** — tree-based anomaly isolation

Anomalies are classified by severity: **Critical** (≥ 0.95), **High** (≥ 0.85), **Medium** (≥ 0.70), **Low** (≥ 0.50).

## Running Tests

```bash
cd backend
python -m unittest test_api.py -v
```

## License

MIT

---

**Author**: Abdul — Module C Implementation
