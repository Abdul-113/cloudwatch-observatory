"""
Test Suite for CloudWatch Observatory API
Run with: python test_api.py
"""

import requests
import json
from datetime import datetime

API_BASE = 'http://localhost:5000/api'

def print_test(name, passed, details=''):
    """Print test result"""
    status = '✓' if passed else '✗'
    color = '\033[92m' if passed else '\033[91m'
    reset = '\033[0m'
    print(f"{color}{status}{reset} {name}")
    if details:
        print(f"  {details}")

def test_health_summary():
    """Test health summary endpoint"""
    print("\n[Testing Health Summary Endpoint]")
    
    try:
        response = requests.get(f"{API_BASE}/health/summary")
        passed = response.status_code == 200
        
        if passed:
            data = response.json()
            print_test("GET /api/health/summary", True, f"Found {len(data)} services")
            
            if data:
                service = data[0]
                required_fields = ['service_name', 'health_score', 'status', 'request_rate', 'error_rate']
                has_fields = all(field in service for field in required_fields)
                print_test("Response structure", has_fields, "All required fields present")
        else:
            print_test("GET /api/health/summary", False, f"Status: {response.status_code}")
            
    except Exception as e:
        print_test("GET /api/health/summary", False, str(e))

def test_anomalies():
    """Test anomalies endpoint"""
    print("\n[Testing Anomalies Endpoint]")
    
    try:
        response = requests.get(f"{API_BASE}/health/anomalies?hours=24")
        passed = response.status_code == 200
        
        if passed:
            data = response.json()
            print_test("GET /api/health/anomalies", True, f"Found {len(data)} anomalies")
            
            if data:
                anomaly = data[0]
                required_fields = ['service_name', 'severity', 'anomaly_score', 'affected_metrics']
                has_fields = all(field in anomaly for field in required_fields)
                print_test("Anomaly structure", has_fields, "All required fields present")
        else:
            print_test("GET /api/health/anomalies", False, f"Status: {response.status_code}")
            
    except Exception as e:
        print_test("GET /api/health/anomalies", False, str(e))

def test_metrics_history():
    """Test metrics history endpoint"""
    print("\n[Testing Metrics History Endpoint]")
    
    try:
        response = requests.get(f"{API_BASE}/metrics/history?service=api-gateway&hours=2")
        passed = response.status_code == 200
        
        if passed:
            data = response.json()
            print_test("GET /api/metrics/history", True, f"Found {len(data)} data points")
            
            if data:
                metric = data[0]
                required_fields = ['timestamp', 'request_rate', 'error_rate', 'cpu_usage']
                has_fields = all(field in metric for field in required_fields)
                print_test("Metrics structure", has_fields, "All required fields present")
        else:
            print_test("GET /api/metrics/history", False, f"Status: {response.status_code}")
            
    except Exception as e:
        print_test("GET /api/metrics/history", False, str(e))

def test_service_registration():
    """Test service registration endpoint"""
    print("\n[Testing Service Registration]")
    
    try:
        payload = {
            'service_name': 'test-service',
            'service_type': 'microservice'
        }
        response = requests.post(f"{API_BASE}/services/register", json=payload)
        passed = response.status_code in [200, 400]  # 400 if already exists
        
        print_test("POST /api/services/register", passed, f"Status: {response.status_code}")
        
    except Exception as e:
        print_test("POST /api/services/register", False, str(e))

def test_services_list():
    """Test services list endpoint"""
    print("\n[Testing Services List]")
    
    try:
        response = requests.get(f"{API_BASE}/services")
        passed = response.status_code == 200
        
        if passed:
            data = response.json()
            print_test("GET /api/services", True, f"Found {len(data)} registered services")
        else:
            print_test("GET /api/services", False, f"Status: {response.status_code}")
            
    except Exception as e:
        print_test("GET /api/services", False, str(e))

def test_health_scores():
    """Test health score calculations"""
    print("\n[Testing Health Score Calculations]")
    
    try:
        response = requests.get(f"{API_BASE}/health/summary")
        data = response.json()
        
        if data:
            for service in data:
                score = service['health_score']
                status = service['status']
                
                # Validate score range
                score_valid = 0 <= score <= 100
                print_test(f"{service['service_name']} score range", score_valid, f"Score: {score:.1f}")
                
                # Validate status mapping
                expected_status = 'healthy' if score >= 90 else 'degraded' if score >= 70 else 'warning' if score >= 50 else 'critical'
                status_valid = status == expected_status
                print_test(f"{service['service_name']} status mapping", status_valid, f"Status: {status}")
                
    except Exception as e:
        print_test("Health score validation", False, str(e))

def run_all_tests():
    """Run all API tests"""
    print("═" * 60)
    print("CloudWatch Observatory - API Test Suite")
    print("═" * 60)
    
    test_services_list()
    test_service_registration()
    test_health_summary()
    test_metrics_history()
    test_anomalies()
    test_health_scores()
    
    print("\n" + "═" * 60)
    print("Test suite complete!")
    print("═" * 60)

if __name__ == '__main__':
    import sys
    
    print("\nChecking if backend is running...")
    try:
        response = requests.get(f"{API_BASE}/services", timeout=2)
        print("✓ Backend is accessible\n")
        run_all_tests()
    except requests.exceptions.RequestException:
        print("✗ Backend not accessible. Please start the backend server first:")
        print("  cd backend && python app.py\n")
        sys.exit(1)
