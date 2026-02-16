"""
Cloud Monitoring Platform - Backend API
Handles Prometheus integration, metric collection, anomaly detection, and health APIs
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
import numpy as np
from sklearn.ensemble import IsolationForest
from pyod.models.ecod import ECOD
import requests
from typing import Dict, List, Any
import sqlite3
import json
from dataclasses import dataclass, asdict
import threading
import time

app = Flask(__name__)
CORS(app)

# Database setup
DB_PATH = 'monitoring.db'

def init_db():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Service metrics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS service_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        )
    ''')
    
    # Metrics anomaly records
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metrics_anomalies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            anomaly_type TEXT,
            severity TEXT,
            anomaly_score REAL,
            affected_metrics TEXT,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Service registry
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT UNIQUE NOT NULL,
            service_type TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Configuration
PROMETHEUS_URL = "http://localhost:9090"
METRIC_WINDOW_MINUTES = 5
ANOMALY_THRESHOLD = 0.7

@dataclass
class ServiceMetrics:
    service_name: str
    timestamp: datetime
    request_rate: float
    error_rate: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    cpu_usage: float
    memory_usage: float
    restart_count: int
    pod_count: int

class PrometheusClient:
    """Client for querying Prometheus metrics"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def query(self, query: str) -> Dict:
        """Execute Prometheus query"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/query",
                params={'query': query}
            )
            return response.json()
        except Exception as e:
            print(f"Prometheus query failed: {e}")
            return {'status': 'error', 'data': {'result': []}}
    
    def query_range(self, query: str, start: datetime, end: datetime, step: str = '1m') -> Dict:
        """Execute Prometheus range query"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/query_range",
                params={
                    'query': query,
                    'start': start.timestamp(),
                    'end': end.timestamp(),
                    'step': step
                }
            )
            return response.json()
        except Exception as e:
            print(f"Prometheus range query failed: {e}")
            return {'status': 'error', 'data': {'result': []}}

class MetricsCollector:
    """Collects and stores metrics from Prometheus"""
    
    def __init__(self, prometheus_client: PrometheusClient):
        self.prom = prometheus_client
    
    def collect_service_metrics(self, service_name: str) -> ServiceMetrics:
        """Collect all metrics for a service"""
        
        # Request rate
        req_rate_query = f'rate(http_requests_total{{service="{service_name}"}}[5m])'
        req_rate = self._extract_value(self.prom.query(req_rate_query))
        
        # Error rate
        error_rate_query = f'rate(http_requests_total{{service="{service_name}",status=~"5.."}}[5m])'
        error_rate = self._extract_value(self.prom.query(error_rate_query))
        
        # Latency percentiles
        p50_query = f'histogram_quantile(0.5, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m]))'
        p95_query = f'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m]))'
        p99_query = f'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m]))'
        
        latency_p50 = self._extract_value(self.prom.query(p50_query))
        latency_p95 = self._extract_value(self.prom.query(p95_query))
        latency_p99 = self._extract_value(self.prom.query(p99_query))
        
        # CPU and Memory
        cpu_query = f'rate(container_cpu_usage_seconds_total{{service="{service_name}"}}[5m])'
        mem_query = f'container_memory_usage_bytes{{service="{service_name}"}}'
        
        cpu_usage = self._extract_value(self.prom.query(cpu_query))
        memory_usage = self._extract_value(self.prom.query(mem_query))
        
        # Restarts and pod count
        restart_query = f'kube_pod_container_status_restarts_total{{service="{service_name}"}}'
        pod_count_query = f'count(kube_pod_info{{service="{service_name}"}})'
        
        restart_count = int(self._extract_value(self.prom.query(restart_query)))
        pod_count = int(self._extract_value(self.prom.query(pod_count_query)))
        
        return ServiceMetrics(
            service_name=service_name,
            timestamp=datetime.now(),
            request_rate=req_rate,
            error_rate=error_rate,
            latency_p50=latency_p50,
            latency_p95=latency_p95,
            latency_p99=latency_p99,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            restart_count=restart_count,
            pod_count=pod_count
        )
    
    def _extract_value(self, response: Dict) -> float:
        """Extract numeric value from Prometheus response"""
        try:
            if response['status'] == 'success' and response['data']['result']:
                return float(response['data']['result'][0]['value'][1])
        except (KeyError, IndexError, ValueError):
            pass
        return 0.0
    
    def store_metrics(self, metrics: ServiceMetrics):
        """Store metrics in database"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO service_metrics 
            (service_name, timestamp, request_rate, error_rate, latency_p50, 
             latency_p95, latency_p99, cpu_usage, memory_usage, restart_count, pod_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            metrics.service_name,
            metrics.timestamp.isoformat(),
            metrics.request_rate,
            metrics.error_rate,
            metrics.latency_p50,
            metrics.latency_p95,
            metrics.latency_p99,
            metrics.cpu_usage,
            metrics.memory_usage,
            metrics.restart_count,
            metrics.pod_count
        ))
        
        conn.commit()
        conn.close()

class AnomalyDetector:
    """Detects anomalies in service metrics using ML models"""
    
    def __init__(self):
        self.models = {
            'isolation_forest': IsolationForest(contamination=0.1, random_state=42),
            'ecod': ECOD(contamination=0.1)
        }
    
    def get_metric_features(self, service_name: str, hours: int = 24) -> np.ndarray:
        """Get feature vectors for a service over time window"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        cursor.execute('''
            SELECT request_rate, error_rate, latency_p95, cpu_usage, memory_usage, restart_count
            FROM service_metrics
            WHERE service_name = ? AND timestamp > ?
            ORDER BY timestamp DESC
        ''', (service_name, cutoff_time.isoformat()))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return np.array([])
        
        return np.array(rows)
    
    def detect_anomalies(self, service_name: str) -> List[Dict]:
        """Detect anomalies and assign severity levels"""
        features = self.get_metric_features(service_name)
        
        if len(features) < 10:
            return []
        
        anomalies = []
        
        # Use ECOD for anomaly detection
        model = ECOD(contamination=0.1)
        model.fit(features)
        
        # Get anomaly scores and predictions
        scores = model.decision_scores_
        predictions = model.labels_
        
        # Analyze recent metrics (last 5 data points)
        recent_features = features[:5]
        recent_scores = scores[:5]
        recent_predictions = predictions[:5]
        
        metric_names = ['request_rate', 'error_rate', 'latency_p95', 'cpu_usage', 'memory_usage', 'restart_count']
        
        for idx, (score, is_anomaly) in enumerate(zip(recent_scores, recent_predictions)):
            if is_anomaly == 1:
                # Determine severity
                if score > 0.9:
                    severity = 'critical'
                elif score > 0.7:
                    severity = 'high'
                elif score > 0.5:
                    severity = 'medium'
                else:
                    severity = 'low'
                
                # Find which metrics are anomalous
                feature_vector = recent_features[idx]
                affected_metrics = []
                
                for i, (metric_name, value) in enumerate(zip(metric_names, feature_vector)):
                    metric_mean = np.mean(features[:, i])
                    metric_std = np.std(features[:, i])
                    
                    if abs(value - metric_mean) > 2 * metric_std:
                        affected_metrics.append(metric_name)
                
                anomaly = {
                    'service_name': service_name,
                    'timestamp': datetime.now().isoformat(),
                    'anomaly_type': 'metric_deviation',
                    'severity': severity,
                    'anomaly_score': float(score),
                    'affected_metrics': ', '.join(affected_metrics),
                    'description': self._generate_description(severity, affected_metrics)
                }
                
                anomalies.append(anomaly)
                self._store_anomaly(anomaly)
        
        return anomalies
    
    def _generate_description(self, severity: str, affected_metrics: List[str]) -> str:
        """Generate human-readable description"""
        if not affected_metrics:
            return f"{severity.capitalize()} anomaly detected in service behavior"
        
        metrics_str = ', '.join(affected_metrics)
        return f"{severity.capitalize()} anomaly: unusual patterns in {metrics_str}"
    
    def _store_anomaly(self, anomaly: Dict):
        """Store anomaly in database"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO metrics_anomalies 
            (service_name, timestamp, anomaly_type, severity, anomaly_score, affected_metrics, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            anomaly['service_name'],
            anomaly['timestamp'],
            anomaly['anomaly_type'],
            anomaly['severity'],
            anomaly['anomaly_score'],
            anomaly['affected_metrics'],
            anomaly['description']
        ))
        
        conn.commit()
        conn.close()

# Initialize components
prom_client = PrometheusClient(PROMETHEUS_URL)
metrics_collector = MetricsCollector(prom_client)
anomaly_detector = AnomalyDetector()

# API Endpoints

@app.route('/api/services', methods=['GET'])
def get_services():
    """Get list of all registered services"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT service_name, service_type, status, last_seen FROM services')
    rows = cursor.fetchall()
    conn.close()
    
    services = [
        {
            'name': row[0],
            'type': row[1],
            'status': row[2],
            'last_seen': row[3]
        }
        for row in rows
    ]
    
    return jsonify(services)

@app.route('/api/services/register', methods=['POST'])
def register_service():
    """Register a new service"""
    data = request.json
    service_name = data.get('service_name')
    service_type = data.get('service_type', 'unknown')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO services (service_name, service_type, last_seen)
            VALUES (?, ?, ?)
        ''', (service_name, service_type, datetime.now().isoformat()))
        conn.commit()
        return jsonify({'success': True, 'message': 'Service registered'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Service already exists'}), 400
    finally:
        conn.close()

@app.route('/api/health/summary', methods=['GET'])
def get_health_summary():
    """Get health summary for all services"""
    service_name = request.args.get('service')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if service_name:
        # Get specific service health
        cursor.execute('''
            SELECT * FROM service_metrics 
            WHERE service_name = ?
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', (service_name,))
    else:
        # Get all services latest metrics
        cursor.execute('''
            SELECT sm.* FROM service_metrics sm
            INNER JOIN (
                SELECT service_name, MAX(timestamp) as max_ts
                FROM service_metrics
                GROUP BY service_name
            ) latest ON sm.service_name = latest.service_name 
            AND sm.timestamp = latest.max_ts
        ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    summary = []
    for row in rows:
        health_score = calculate_health_score(row)
        summary.append({
            'service_name': row[1],
            'timestamp': row[2],
            'request_rate': row[3],
            'error_rate': row[4],
            'latency': {
                'p50': row[5],
                'p95': row[6],
                'p99': row[7]
            },
            'resources': {
                'cpu': row[8],
                'memory': row[9]
            },
            'restart_count': row[10],
            'pod_count': row[11],
            'health_score': health_score,
            'status': get_status_from_health(health_score)
        })
    
    return jsonify(summary)

@app.route('/api/health/anomalies', methods=['GET'])
def get_anomalies():
    """Get recent anomalies"""
    service_name = request.args.get('service')
    hours = int(request.args.get('hours', 24))
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    if service_name:
        cursor.execute('''
            SELECT * FROM metrics_anomalies
            WHERE service_name = ? AND timestamp > ?
            ORDER BY timestamp DESC
        ''', (service_name, cutoff_time.isoformat()))
    else:
        cursor.execute('''
            SELECT * FROM metrics_anomalies
            WHERE timestamp > ?
            ORDER BY timestamp DESC
        ''', (cutoff_time.isoformat(),))
    
    rows = cursor.fetchall()
    conn.close()
    
    anomalies = [
        {
            'id': row[0],
            'service_name': row[1],
            'timestamp': row[2],
            'anomaly_type': row[3],
            'severity': row[4],
            'anomaly_score': row[5],
            'affected_metrics': row[6].split(', ') if row[6] else [],
            'description': row[7]
        }
        for row in rows
    ]
    
    return jsonify(anomalies)

@app.route('/api/metrics/history', methods=['GET'])
def get_metrics_history():
    """Get historical metrics for a service"""
    service_name = request.args.get('service')
    hours = int(request.args.get('hours', 24))
    
    if not service_name:
        return jsonify({'error': 'service parameter required'}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    cursor.execute('''
        SELECT * FROM service_metrics
        WHERE service_name = ? AND timestamp > ?
        ORDER BY timestamp ASC
    ''', (service_name, cutoff_time.isoformat()))
    
    rows = cursor.fetchall()
    conn.close()
    
    history = [
        {
            'timestamp': row[2],
            'request_rate': row[3],
            'error_rate': row[4],
            'latency_p50': row[5],
            'latency_p95': row[6],
            'latency_p99': row[7],
            'cpu_usage': row[8],
            'memory_usage': row[9],
            'restart_count': row[10],
            'pod_count': row[11]
        }
        for row in rows
    ]
    
    return jsonify(history)

@app.route('/api/collect/<service_name>', methods=['POST'])
def trigger_collection(service_name):
    """Manually trigger metrics collection for a service"""
    try:
        metrics = metrics_collector.collect_service_metrics(service_name)
        metrics_collector.store_metrics(metrics)
        
        # Run anomaly detection
        anomalies = anomaly_detector.detect_anomalies(service_name)
        
        return jsonify({
            'success': True,
            'metrics': asdict(metrics),
            'anomalies_detected': len(anomalies)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def calculate_health_score(metric_row) -> float:
    """Calculate 0-100 health score based on metrics"""
    error_rate = metric_row[4] or 0
    latency_p95 = metric_row[6] or 0
    cpu_usage = metric_row[8] or 0
    
    # Simple scoring algorithm
    score = 100
    
    # Penalize high error rates
    if error_rate > 0.1:
        score -= 30
    elif error_rate > 0.05:
        score -= 15
    elif error_rate > 0.01:
        score -= 5
    
    # Penalize high latency (assuming ms)
    if latency_p95 > 1000:
        score -= 25
    elif latency_p95 > 500:
        score -= 15
    elif latency_p95 > 200:
        score -= 5
    
    # Penalize high CPU
    if cpu_usage > 0.9:
        score -= 20
    elif cpu_usage > 0.7:
        score -= 10
    
    return max(0, score)

def get_status_from_health(health_score: float) -> str:
    """Convert health score to status"""
    if health_score >= 90:
        return 'healthy'
    elif health_score >= 70:
        return 'degraded'
    elif health_score >= 50:
        return 'warning'
    else:
        return 'critical'

# Background collection worker
def background_collector():
    """Background thread to collect metrics periodically"""
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT service_name FROM services WHERE status = "active"')
            services = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            for service_name in services:
                try:
                    metrics = metrics_collector.collect_service_metrics(service_name)
                    metrics_collector.store_metrics(metrics)
                    anomaly_detector.detect_anomalies(service_name)
                except Exception as e:
                    print(f"Error collecting metrics for {service_name}: {e}")
            
            time.sleep(60)  # Collect every minute
        except Exception as e:
            print(f"Background collector error: {e}")
            time.sleep(60)

# Start background collector
collector_thread = threading.Thread(target=background_collector, daemon=True)
collector_thread.start()

if __name__ == '__main__':
    # Create some demo data for testing
    demo_services = ['api-gateway', 'user-service', 'payment-service', 'notification-service']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for svc in demo_services:
        try:
            cursor.execute('INSERT INTO services (service_name, service_type, last_seen) VALUES (?, ?, ?)',
                         (svc, 'microservice', datetime.now().isoformat()))
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
