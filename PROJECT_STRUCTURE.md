# CloudWatch Observatory - Project Structure

```
cloudwatch-observatory/
│
├── backend/                          # Python Flask backend
│   ├── app.py                       # Main Flask application
│   │   ├── PrometheusClient         # Prometheus query interface
│   │   ├── MetricsCollector         # Metric collection engine
│   │   ├── AnomalyDetector          # ML-based anomaly detection
│   │   └── API Endpoints:
│   │       ├── /api/services                    # List services
│   │       ├── /api/services/register           # Register new service
│   │       ├── /api/health/summary              # Health overview
│   │       ├── /api/health/anomalies            # Anomaly list
│   │       ├── /api/metrics/history             # Time-series data
│   │       └── /api/collect/<service>           # Manual collection
│   │
│   ├── demo_data.py                 # Demo data generator
│   │   ├── generate_historical_data()    # Backfill historical metrics
│   │   ├── generate_live_stream()        # Live data simulation
│   │   └── generate_realistic_metrics()  # Pattern-based generation
│   │
│   ├── test_api.py                  # API test suite
│   ├── requirements.txt             # Python dependencies
│   └── monitoring.db                # SQLite database (auto-created)
│       ├── service_metrics          # Time-series metric storage
│       ├── metrics_anomalies        # Detected anomalies
│       └── services                 # Service registry
│
├── frontend/                        # Interactive web dashboard
│   └── dashboard.html               # Single-file React-like app
│       ├── App Health View          # Service monitoring cards
│       │   ├── Health score rings
│       │   ├── Live metrics display
│       │   └── Historical charts
│       │
│       └── Anomaly Radar View       # Anomaly detection panel
│           ├── Severity badges
│           ├── Affected metrics tags
│           └── Timeline display
│
├── start.sh                         # Quick start script (Linux/Mac)
├── README.md                        # Comprehensive documentation
└── PROJECT_STRUCTURE.md             # This file

```

## Component Descriptions

### Backend Components

#### `app.py` - Main Application
- **Flask Server**: RESTful API server on port 5000
- **Database Management**: SQLite initialization and queries
- **Background Worker**: Automatic metric collection thread
- **Health Calculation**: Algorithmic health scoring (0-100)

#### `PrometheusClient`
- Queries Prometheus API for metrics
- Supports instant queries and range queries
- Error handling for network failures

#### `MetricsCollector`
- Fetches multi-metric data per service
- Constructs ServiceMetrics dataclass
- Persists to database with timestamp

#### `AnomalyDetector`
- **ECOD Model**: Empirical Cumulative Distribution
- **Isolation Forest**: Tree-based outlier detection
- **Feature Engineering**: 6-dimensional vectors
- **Severity Classification**: Critical/High/Medium/Low
- **Description Generation**: Human-readable summaries

### Frontend Components

#### Dashboard Layout
```
┌─────────────────────────────────────────────────────┐
│  CloudWatch Observatory         [Stats] [Refresh]   │
├─────────────────────────────────────────────────────┤
│  [App Health] [Anomaly Radar]                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ Service  │  │ Service  │  │ Service  │         │
│  │  Card 1  │  │  Card 2  │  │  Card 3  │         │
│  │          │  │          │  │          │         │
│  │ [Chart]  │  │ [Chart]  │  │ [Chart]  │         │
│  └──────────┘  └──────────┘  └──────────┘         │
│                                                      │
└─────────────────────────────────────────────────────┘
```

#### Service Card Structure
- **Header**: Service name + status badge
- **Health Ring**: Circular progress (Chart.js doughnut)
- **Metrics Grid**: Request rate, errors, latency, CPU
- **Trend Chart**: Historical line chart with dual axes

#### Anomaly Item Structure
- **Header**: Service name + severity badge
- **Description**: AI-generated explanation
- **Metrics Tags**: Affected metric indicators
- **Metadata**: Score, timestamp

### Database Schema

#### `service_metrics`
```sql
CREATE TABLE service_metrics (
    id INTEGER PRIMARY KEY,
    service_name TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    request_rate REAL,
    error_rate REAL,
    latency_p50 REAL,
    latency_p95 REAL,
    latency_p99 REAL,
    cpu_usage REAL,
    memory_usage REAL,
    restart_count INTEGER,
    pod_count INTEGER,
    UNIQUE(service_name, timestamp)
);
```

#### `metrics_anomalies`
```sql
CREATE TABLE metrics_anomalies (
    id INTEGER PRIMARY KEY,
    service_name TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    anomaly_type TEXT,
    severity TEXT,
    anomaly_score REAL,
    affected_metrics TEXT,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### `services`
```sql
CREATE TABLE services (
    id INTEGER PRIMARY KEY,
    service_name TEXT UNIQUE NOT NULL,
    service_type TEXT,
    status TEXT DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME
);
```

## Data Flow

### Metric Collection Flow
```
Prometheus → PrometheusClient → MetricsCollector → Database
                                        ↓
                                 AnomalyDetector
                                        ↓
                                 Anomaly Database
```

### Frontend Request Flow
```
Browser → API Endpoint → Database Query → JSON Response → UI Render
```

### Background Worker Flow
```
Timer (60s) → Fetch Active Services → For Each Service:
                                         ├─ Collect Metrics
                                         ├─ Store in DB
                                         └─ Run Anomaly Detection
```

## Technology Stack

### Backend
- **Flask 3.0.0**: Web framework
- **NumPy 1.24.3**: Numerical computing
- **scikit-learn 1.3.0**: Machine learning
- **PyOD 1.1.0**: Outlier detection
- **SQLite**: Embedded database
- **Requests**: HTTP client

### Frontend
- **Vanilla JavaScript**: No framework dependencies
- **Chart.js 4.4.0**: Data visualization
- **CSS Grid/Flexbox**: Layout system
- **Google Fonts**: Typography (Outfit, JetBrains Mono)

## Deployment Considerations

### Development
```bash
./start.sh                    # Quick start (generates demo data)
python backend/app.py         # Backend only
open frontend/dashboard.html  # Frontend only
```

### Production
1. **Database**: Migrate to PostgreSQL for scale
2. **Caching**: Add Redis for metrics aggregation
3. **Queue**: Use Celery for async collection
4. **Frontend**: Serve via Nginx/Apache
5. **Security**: Add authentication, rate limiting
6. **Monitoring**: Monitor the monitor (meta!)

### Scaling
- **Horizontal**: Multiple collector workers
- **Vertical**: Optimize SQL queries, add indexes
- **Sharding**: Partition by service or time range
- **Archive**: Move old metrics to cold storage

## Extension Points

### Adding New Metrics
1. Update `PrometheusClient.query()` with new Prometheus queries
2. Add fields to `ServiceMetrics` dataclass
3. Extend database schema
4. Update `AnomalyDetector` feature vectors

### Custom Anomaly Models
1. Implement new detector in `AnomalyDetector`
2. Add to `self.models` dictionary
3. Ensemble results with existing models

### New Visualizations
1. Add Chart.js chart type to dashboard
2. Create new API endpoint if needed
3. Style with CSS variables

### Integration Modules
- **Module A (Logs)**: Send anomaly triggers to log aggregator
- **Module B (Tracing)**: Link anomaly events to distributed traces
- **Module D (Alerts)**: Forward critical anomalies to alerting system

## Performance Characteristics

### Backend
- **API Latency**: <100ms for most endpoints
- **Collection Time**: ~2-5s per service (depends on Prometheus)
- **Anomaly Detection**: ~500ms for 24h window
- **Memory Usage**: ~100MB baseline + ~50MB per 10k metrics

### Frontend
- **Initial Load**: <2s with demo data
- **Chart Render**: ~200ms per chart
- **Auto-refresh**: Every 30s (configurable)
- **Browser Memory**: ~50MB for typical dashboard

### Database
- **Metrics/Day**: ~17,280 rows per service (1/min collection)
- **Disk Usage**: ~5MB per service per day
- **Query Speed**: <50ms with proper indexing

## Security Considerations

### Current State (Development)
- No authentication required
- CORS enabled for all origins
- SQLite file permissions only

### Production Requirements
- [ ] API key authentication
- [ ] JWT tokens for frontend
- [ ] HTTPS/TLS encryption
- [ ] Rate limiting per client
- [ ] SQL injection prevention (using parameterized queries ✓)
- [ ] Input validation
- [ ] RBAC for multi-tenant
- [ ] Audit logging

## Troubleshooting Guide

### No metrics showing
- Check Prometheus connectivity
- Verify service names match
- Ensure data exists in time range
- Check browser console for errors

### Anomalies not detecting
- Need minimum 10 data points
- Verify metrics have variance
- Check contamination parameter
- Review anomaly_score threshold

### Charts not rendering
- Verify Chart.js CDN loaded
- Check canvas element IDs
- Validate data format
- Clear browser cache

### Database locked
- Close other SQLite connections
- Check file permissions
- Consider migration to PostgreSQL

---

**Author**: Abdul - Module C Implementation
**Last Updated**: 2024-02-14
**Version**: 1.0.0
