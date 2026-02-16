"""
Extended API endpoints for Docker and Kubernetes monitoring
Add these to app.py to enable container and cluster monitoring
"""

from flask import Flask, jsonify, request
from docker_monitor import DockerMonitor, init_docker_tables
from kubernetes_monitor import KubernetesMonitor, init_kubernetes_tables
import sqlite3

# Initialize monitors (add to app.py initialization section)
docker_monitor = DockerMonitor()
k8s_monitor = KubernetesMonitor()

# Initialize tables
init_docker_tables()
init_kubernetes_tables()

# ==================== DOCKER ENDPOINTS ====================

@app.route('/api/docker/containers', methods=['GET'])
def get_docker_containers():
    """Get all Docker containers"""
    include_stopped = request.args.get('include_stopped', 'false').lower() == 'true'
    containers = docker_monitor.discover_containers(include_stopped=include_stopped)
    return jsonify(containers)

@app.route('/api/docker/containers/<container_id>/stats', methods=['GET'])
def get_container_stats(container_id):
    """Get real-time stats for a specific container"""
    stats = docker_monitor.get_container_stats(container_id)
    if not stats:
        return jsonify({'error': 'Container not found or stats unavailable'}), 404
    return jsonify(stats)

@app.route('/api/docker/containers/<container_id>/logs', methods=['GET'])
def get_container_logs(container_id):
    """Get logs from a container"""
    tail = int(request.args.get('tail', 100))
    logs = docker_monitor.get_container_logs(container_id, tail=tail)
    return jsonify({'logs': logs})

@app.route('/api/docker/system', methods=['GET'])
def get_docker_system():
    """Get Docker system information"""
    system_info = docker_monitor.get_system_info()
    return jsonify(system_info)

@app.route('/api/docker/images', methods=['GET'])
def get_docker_images():
    """Get Docker images"""
    images = docker_monitor.get_image_info()
    return jsonify(images)

@app.route('/api/docker/monitor/all', methods=['GET'])
def monitor_all_containers():
    """Get stats from all running containers"""
    stats = docker_monitor.monitor_all_containers()
    return jsonify(stats)

@app.route('/api/docker/discover', methods=['POST'])
def discover_docker_containers():
    """Auto-discover and register containers as services"""
    count = docker_monitor.register_containers_as_services()
    return jsonify({
        'success': True,
        'message': f'Registered {count} containers as services'
    })

# ==================== KUBERNETES ENDPOINTS ====================

@app.route('/api/k8s/namespaces', methods=['GET'])
def get_k8s_namespaces():
    """Get all Kubernetes namespaces"""
    namespaces = k8s_monitor.discover_namespaces()
    return jsonify(namespaces)

@app.route('/api/k8s/pods', methods=['GET'])
def get_k8s_pods():
    """Get pods in a namespace"""
    namespace = request.args.get('namespace', 'default')
    label_selector = request.args.get('labels')
    pods = k8s_monitor.discover_pods(namespace=namespace, label_selector=label_selector)
    return jsonify(pods)

@app.route('/api/k8s/deployments', methods=['GET'])
def get_k8s_deployments():
    """Get deployments in a namespace"""
    namespace = request.args.get('namespace', 'default')
    deployments = k8s_monitor.discover_deployments(namespace=namespace)
    return jsonify(deployments)

@app.route('/api/k8s/services', methods=['GET'])
def get_k8s_services():
    """Get services in a namespace"""
    namespace = request.args.get('namespace', 'default')
    services = k8s_monitor.discover_services(namespace=namespace)
    return jsonify(services)

@app.route('/api/k8s/nodes', methods=['GET'])
def get_k8s_nodes():
    """Get cluster nodes"""
    nodes = k8s_monitor.discover_nodes()
    return jsonify(nodes)

@app.route('/api/k8s/cluster/health', methods=['GET'])
def get_k8s_cluster_health():
    """Get cluster health summary"""
    health = k8s_monitor.get_cluster_health()
    return jsonify(health)

@app.route('/api/k8s/pods/<namespace>/<pod_name>/logs', methods=['GET'])
def get_k8s_pod_logs(namespace, pod_name):
    """Get logs from a pod"""
    tail = int(request.args.get('tail', 100))
    logs = k8s_monitor.get_pod_logs(pod_name=pod_name, namespace=namespace, tail=tail)
    return jsonify({'logs': logs})

@app.route('/api/k8s/discover', methods=['POST'])
def discover_k8s_pods():
    """Auto-discover and register pods as services"""
    namespace = request.json.get('namespace', 'default')
    count = k8s_monitor.register_pods_as_services(namespace=namespace)
    return jsonify({
        'success': True,
        'message': f'Registered {count} pods from namespace {namespace} as services'
    })

# ==================== UNIFIED MONITORING ENDPOINT ====================

@app.route('/api/infrastructure/summary', methods=['GET'])
def get_infrastructure_summary():
    """
    Get comprehensive infrastructure summary across Docker and Kubernetes
    """
    summary = {
        'timestamp': datetime.now().isoformat(),
        'docker': {},
        'kubernetes': {}
    }
    
    # Docker summary
    if docker_monitor.client:
        docker_containers = docker_monitor.discover_containers()
        docker_system = docker_monitor.get_system_info()
        summary['docker'] = {
            'available': True,
            'containers': {
                'total': len(docker_containers),
                'running': sum(1 for c in docker_containers if c['status'] == 'running'),
                'stopped': docker_system.get('containers_stopped', 0)
            },
            'images': docker_system.get('images', 0),
            'version': docker_system.get('server_version', 'unknown')
        }
    else:
        summary['docker'] = {'available': False}
    
    # Kubernetes summary
    if k8s_monitor.core_v1:
        k8s_health = k8s_monitor.get_cluster_health()
        summary['kubernetes'] = {
            'available': True,
            'nodes': k8s_health.get('nodes', {}),
            'pods': k8s_health.get('pods', {}),
            'namespaces': len(k8s_monitor.discover_namespaces())
        }
    else:
        summary['kubernetes'] = {'available': False}
    
    return jsonify(summary)

# ==================== BACKGROUND COLLECTION UPDATE ====================

def background_infrastructure_collector():
    """
    Enhanced background collector that includes Docker and Kubernetes
    Add this to the existing background_collector function
    """
    # Existing service collection code...
    
    # Docker container metrics collection
    if docker_monitor.client:
        try:
            container_stats = docker_monitor.monitor_all_containers()
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            for stat in container_stats:
                cursor.execute('''
                    INSERT INTO container_metrics 
                    (container_id, container_name, timestamp, cpu_percent, 
                     memory_usage_bytes, memory_percent, network_rx_bytes, 
                     network_tx_bytes, disk_read_bytes, disk_write_bytes, pids)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    stat['container_id'], stat['container_name'], 
                    stat['timestamp'], stat['cpu_percent'],
                    stat['memory_usage_bytes'], stat['memory_percent'],
                    stat['network_rx_bytes'], stat['network_tx_bytes'],
                    stat['disk_read_bytes'], stat['disk_write_bytes'],
                    stat['pids']
                ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error collecting Docker metrics: {e}")
    
    # Kubernetes pod metrics collection
    if k8s_monitor.core_v1:
        try:
            for namespace in k8s_monitor.discover_namespaces():
                pods = k8s_monitor.discover_pods(namespace=namespace)
                
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                
                for pod in pods:
                    ready_containers = sum(1 for c in pod['container_statuses'] if c['ready'])
                    total_containers = len(pod['container_statuses'])
                    total_restarts = sum(c['restart_count'] for c in pod['container_statuses'])
                    
                    cursor.execute('''
                        INSERT INTO pod_metrics 
                        (pod_name, namespace, timestamp, phase, ready_containers, 
                         total_containers, restart_count, node_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        pod['name'], pod['namespace'], datetime.now().isoformat(),
                        pod['phase'], ready_containers, total_containers,
                        total_restarts, pod['node_name']
                    ))
                
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"Error collecting Kubernetes metrics: {e}")
