"""
Demo Data Generator for CloudWatch Observatory
Generates realistic mock metrics for testing without a live Prometheus instance
"""

import random
import sqlite3
from datetime import datetime, timedelta
import time

DB_PATH = 'monitoring.db'

def init_db():
    """Create the service_metrics table if it doesn't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS service_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            request_rate REAL,
            error_rate REAL,
            latency_p50 REAL,
            latency_p95 REAL,
            latency_p99 REAL,
            cpu_usage REAL,
            memory_usage REAL,
            restart_count INTEGER DEFAULT 0,
            pod_count INTEGER DEFAULT 1,
            UNIQUE(service_name, timestamp)
        )
    ''')
    conn.commit()
    conn.close()


def generate_realistic_metrics(service_name, base_time, variation='normal'):
    """Generate realistic metrics with different patterns"""
    
    # Base patterns for different service types
    patterns = {
        'api-gateway': {
            'request_rate': (80, 150),
            'error_rate': (0.001, 0.02),
            'latency_p50': (30, 60),
            'latency_p95': (90, 180),
            'latency_p99': (200, 400),
            'cpu_usage': (0.3, 0.6),
            'memory_usage': (400_000_000, 800_000_000),
            'pod_count': 3
        },
        'user-service': {
            'request_rate': (50, 100),
            'error_rate': (0.005, 0.03),
            'latency_p50': (40, 80),
            'latency_p95': (100, 200),
            'latency_p99': (250, 500),
            'cpu_usage': (0.2, 0.5),
            'memory_usage': (300_000_000, 600_000_000),
            'pod_count': 2
        },
        'payment-service': {
            'request_rate': (20, 50),
            'error_rate': (0.002, 0.015),
            'latency_p50': (100, 200),
            'latency_p95': (300, 500),
            'latency_p99': (600, 1000),
            'cpu_usage': (0.4, 0.7),
            'memory_usage': (500_000_000, 1_000_000_000),
            'pod_count': 4
        },
        'notification-service': {
            'request_rate': (10, 30),
            'error_rate': (0.01, 0.05),
            'latency_p50': (50, 100),
            'latency_p95': (150, 300),
            'latency_p99': (400, 700),
            'cpu_usage': (0.15, 0.4),
            'memory_usage': (200_000_000, 500_000_000),
            'pod_count': 2
        }
    }
    
    # Get pattern for this service or use default
    pattern = patterns.get(service_name, patterns['user-service'])
    
    # Apply variation patterns
    if variation == 'spike':
        # Simulate traffic spike
        request_rate = random.uniform(pattern['request_rate'][1] * 2, pattern['request_rate'][1] * 3)
        error_rate = random.uniform(pattern['error_rate'][1], pattern['error_rate'][1] * 2)
        cpu_usage = min(0.95, random.uniform(pattern['cpu_usage'][1], pattern['cpu_usage'][1] * 1.5))
    elif variation == 'degraded':
        # Simulate degraded performance
        request_rate = random.uniform(pattern['request_rate'][0] * 0.5, pattern['request_rate'][0])
        error_rate = random.uniform(pattern['error_rate'][1] * 2, pattern['error_rate'][1] * 5)
        cpu_usage = random.uniform(pattern['cpu_usage'][0], pattern['cpu_usage'][1])
    else:
        # Normal operation
        request_rate = random.uniform(*pattern['request_rate'])
        error_rate = random.uniform(*pattern['error_rate'])
        cpu_usage = random.uniform(*pattern['cpu_usage'])
    
    latency_p50 = random.uniform(*pattern['latency_p50'])
    latency_p95 = random.uniform(*pattern['latency_p95'])
    latency_p99 = random.uniform(*pattern['latency_p99'])
    memory_usage = random.uniform(*pattern['memory_usage'])
    
    # Occasionally increment restart count
    restart_count = random.randint(0, 1) if random.random() < 0.05 else 0
    
    return {
        'service_name': service_name,
        'timestamp': base_time.isoformat(),
        'request_rate': request_rate,
        'error_rate': error_rate,
        'latency_p50': latency_p50,
        'latency_p95': latency_p95,
        'latency_p99': latency_p99,
        'cpu_usage': cpu_usage,
        'memory_usage': memory_usage,
        'restart_count': restart_count,
        'pod_count': pattern['pod_count']
    }

def insert_metrics(metrics):
    """Insert metrics into database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO service_metrics 
        (service_name, timestamp, request_rate, error_rate, latency_p50, 
         latency_p95, latency_p99, cpu_usage, memory_usage, restart_count, pod_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        metrics['service_name'],
        metrics['timestamp'],
        metrics['request_rate'],
        metrics['error_rate'],
        metrics['latency_p50'],
        metrics['latency_p95'],
        metrics['latency_p99'],
        metrics['cpu_usage'],
        metrics['memory_usage'],
        metrics['restart_count'],
        metrics['pod_count']
    ))
    
    conn.commit()
    conn.close()

def generate_historical_data(hours=24):
    """Generate historical metrics data for the past N hours"""
    services = ['api-gateway', 'user-service', 'payment-service', 'notification-service']
    
    print(f"Generating {hours} hours of historical data...")
    
    # Generate data points every 5 minutes
    num_points = hours * 12  # 12 points per hour (every 5 min)
    
    for i in range(num_points):
        timestamp = datetime.now() - timedelta(minutes=5 * (num_points - i))
        
        for service in services:
            # Randomly introduce anomalies
            if random.random() < 0.05:  # 5% chance of anomaly
                variation = random.choice(['spike', 'degraded'])
            else:
                variation = 'normal'
            
            metrics = generate_realistic_metrics(service, timestamp, variation)
            insert_metrics(metrics)
        
        if (i + 1) % 12 == 0:  # Progress update every hour
            print(f"  Generated {i + 1}/{num_points} data points...")
    
    print(f"✓ Historical data generation complete!")

def generate_live_stream(duration_minutes=60):
    """Generate live streaming data for testing real-time updates"""
    services = ['api-gateway', 'user-service', 'payment-service', 'notification-service']
    
    print(f"Streaming live data for {duration_minutes} minutes...")
    print("Press Ctrl+C to stop")
    
    try:
        for minute in range(duration_minutes):
            timestamp = datetime.now()
            
            for service in services:
                # Higher chance of anomalies for demo
                if random.random() < 0.1:  # 10% chance
                    variation = random.choice(['spike', 'degraded'])
                    print(f"  ⚠️  {timestamp.strftime('%H:%M:%S')} - Injecting {variation} anomaly in {service}")
                else:
                    variation = 'normal'
                
                metrics = generate_realistic_metrics(service, timestamp, variation)
                insert_metrics(metrics)
            
            print(f"  ✓ {timestamp.strftime('%H:%M:%S')} - Metrics collected for all services")
            time.sleep(60)  # Wait 1 minute
            
    except KeyboardInterrupt:
        print("\n✓ Live stream stopped")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python demo_data.py historical <hours>  - Generate historical data")
        print("  python demo_data.py live <minutes>      - Stream live data")
        print("\nExamples:")
        print("  python demo_data.py historical 24")
        print("  python demo_data.py live 30")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    # Ensure the database table exists
    init_db()
    
    if mode == 'historical':
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        generate_historical_data(hours)
    elif mode == 'live':
        minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        generate_live_stream(minutes)
    else:
        print(f"Unknown mode: {mode}")
        print("Use 'historical' or 'live'")
