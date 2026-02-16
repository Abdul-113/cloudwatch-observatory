"""
Kubernetes Monitoring Module
Monitors K8s clusters, pods, deployments, services, and nodes
"""

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from datetime import datetime
from typing import List, Dict, Any
import sqlite3

DB_PATH = 'monitoring.db'

class KubernetesMonitor:
    """Monitor Kubernetes cluster resources"""
    
    def __init__(self, kubeconfig_path=None, in_cluster=False):
        """
        Initialize Kubernetes client
        
        Args:
            kubeconfig_path: Path to kubeconfig file (default: ~/.kube/config)
            in_cluster: Use in-cluster config (when running inside K8s)
        """
        try:
            if in_cluster:
                config.load_incluster_config()
                print("✓ Using in-cluster Kubernetes configuration")
            else:
                config.load_kube_config(config_file=kubeconfig_path)
                print(f"✓ Loaded kubeconfig: {kubeconfig_path or '~/.kube/config'}")
            
            self.core_v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self.metrics_api = None  # Requires metrics-server
            
            # Test connection
            self.core_v1.get_api_resources()
            
        except Exception as e:
            print(f"✗ Failed to initialize Kubernetes client: {e}")
            self.core_v1 = None
            self.apps_v1 = None
    
    def discover_namespaces(self) -> List[str]:
        """Get all namespaces in the cluster"""
        if not self.core_v1:
            return []
        
        try:
            namespaces = self.core_v1.list_namespace()
            return [ns.metadata.name for ns in namespaces.items]
        except ApiException as e:
            print(f"Error listing namespaces: {e}")
            return []
    
    def discover_pods(self, namespace='default', label_selector=None) -> List[Dict[str, Any]]:
        """
        Discover pods in a namespace
        
        Args:
            namespace: Kubernetes namespace
            label_selector: Filter pods by labels (e.g., "app=nginx")
        """
        if not self.core_v1:
            return []
        
        try:
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector
            )
            
            discovered = []
            for pod in pods.items:
                # Get container info
                containers = []
                for container in pod.spec.containers:
                    containers.append({
                        'name': container.name,
                        'image': container.image,
                        'ports': [p.container_port for p in (container.ports or [])]
                    })
                
                # Get container statuses
                container_statuses = []
                if pod.status.container_statuses:
                    for status in pod.status.container_statuses:
                        container_statuses.append({
                            'name': status.name,
                            'ready': status.ready,
                            'restart_count': status.restart_count,
                            'state': self._get_container_state(status.state)
                        })
                
                pod_info = {
                    'name': pod.metadata.name,
                    'namespace': pod.metadata.namespace,
                    'uid': pod.metadata.uid,
                    'labels': pod.metadata.labels or {},
                    'node_name': pod.spec.node_name,
                    'phase': pod.status.phase,
                    'pod_ip': pod.status.pod_ip,
                    'host_ip': pod.status.host_ip,
                    'start_time': pod.status.start_time.isoformat() if pod.status.start_time else None,
                    'containers': containers,
                    'container_statuses': container_statuses,
                    'conditions': self._get_pod_conditions(pod.status.conditions)
                }
                discovered.append(pod_info)
            
            return discovered
            
        except ApiException as e:
            print(f"Error discovering pods: {e}")
            return []
    
    def discover_deployments(self, namespace='default') -> List[Dict[str, Any]]:
        """Discover deployments in a namespace"""
        if not self.apps_v1:
            return []
        
        try:
            deployments = self.apps_v1.list_namespaced_deployment(namespace)
            
            discovered = []
            for deploy in deployments.items:
                deploy_info = {
                    'name': deploy.metadata.name,
                    'namespace': deploy.metadata.namespace,
                    'labels': deploy.metadata.labels or {},
                    'replicas': deploy.spec.replicas,
                    'ready_replicas': deploy.status.ready_replicas or 0,
                    'available_replicas': deploy.status.available_replicas or 0,
                    'updated_replicas': deploy.status.updated_replicas or 0,
                    'strategy': deploy.spec.strategy.type,
                    'selector': deploy.spec.selector.match_labels,
                    'created': deploy.metadata.creation_timestamp.isoformat()
                }
                discovered.append(deploy_info)
            
            return discovered
            
        except ApiException as e:
            print(f"Error discovering deployments: {e}")
            return []
    
    def discover_services(self, namespace='default') -> List[Dict[str, Any]]:
        """Discover services in a namespace"""
        if not self.core_v1:
            return []
        
        try:
            services = self.core_v1.list_namespaced_service(namespace)
            
            discovered = []
            for svc in services.items:
                svc_info = {
                    'name': svc.metadata.name,
                    'namespace': svc.metadata.namespace,
                    'type': svc.spec.type,
                    'cluster_ip': svc.spec.cluster_ip,
                    'external_ips': svc.spec.external_i_ps or [],
                    'ports': [
                        {
                            'port': p.port,
                            'target_port': str(p.target_port),
                            'protocol': p.protocol
                        }
                        for p in (svc.spec.ports or [])
                    ],
                    'selector': svc.spec.selector or {},
                    'created': svc.metadata.creation_timestamp.isoformat()
                }
                
                # Get LoadBalancer ingress if available
                if svc.status.load_balancer and svc.status.load_balancer.ingress:
                    svc_info['load_balancer'] = [
                        {'ip': ing.ip, 'hostname': ing.hostname}
                        for ing in svc.status.load_balancer.ingress
                    ]
                
                discovered.append(svc_info)
            
            return discovered
            
        except ApiException as e:
            print(f"Error discovering services: {e}")
            return []
    
    def discover_nodes(self) -> List[Dict[str, Any]]:
        """Discover cluster nodes"""
        if not self.core_v1:
            return []
        
        try:
            nodes = self.core_v1.list_node()
            
            discovered = []
            for node in nodes.items:
                # Get node conditions
                conditions = {}
                if node.status.conditions:
                    for condition in node.status.conditions:
                        conditions[condition.type] = condition.status == 'True'
                
                # Get resource capacity and allocatable
                capacity = node.status.capacity or {}
                allocatable = node.status.allocatable or {}
                
                node_info = {
                    'name': node.metadata.name,
                    'labels': node.metadata.labels or {},
                    'ready': conditions.get('Ready', False),
                    'conditions': conditions,
                    'capacity': {
                        'cpu': capacity.get('cpu'),
                        'memory': capacity.get('memory'),
                        'pods': capacity.get('pods')
                    },
                    'allocatable': {
                        'cpu': allocatable.get('cpu'),
                        'memory': allocatable.get('memory'),
                        'pods': allocatable.get('pods')
                    },
                    'os_image': node.status.node_info.os_image,
                    'kernel_version': node.status.node_info.kernel_version,
                    'kubelet_version': node.status.node_info.kubelet_version,
                    'container_runtime': node.status.node_info.container_runtime_version
                }
                discovered.append(node_info)
            
            return discovered
            
        except ApiException as e:
            print(f"Error discovering nodes: {e}")
            return []
    
    def get_pod_metrics(self, namespace='default') -> List[Dict[str, Any]]:
        """
        Get pod metrics (requires metrics-server installed in cluster)
        """
        # This requires custom metrics API
        # For now, return placeholder showing how it would work
        return []
    
    def get_cluster_health(self) -> Dict[str, Any]:
        """Get overall cluster health summary"""
        if not self.core_v1:
            return {}
        
        try:
            # Get component statuses (API server, scheduler, controller-manager, etcd)
            components = self.core_v1.list_component_status()
            
            component_health = {}
            for comp in components.items:
                healthy = False
                if comp.conditions:
                    for condition in comp.conditions:
                        if condition.type == 'Healthy':
                            healthy = condition.status == 'True'
                component_health[comp.metadata.name] = healthy
            
            # Count nodes
            nodes = self.discover_nodes()
            ready_nodes = sum(1 for n in nodes if n['ready'])
            
            # Count pods across all namespaces
            all_pods = []
            for ns in self.discover_namespaces():
                all_pods.extend(self.discover_pods(namespace=ns))
            
            running_pods = sum(1 for p in all_pods if p['phase'] == 'Running')
            pending_pods = sum(1 for p in all_pods if p['phase'] == 'Pending')
            failed_pods = sum(1 for p in all_pods if p['phase'] == 'Failed')
            
            return {
                'timestamp': datetime.now().isoformat(),
                'components': component_health,
                'nodes': {
                    'total': len(nodes),
                    'ready': ready_nodes,
                    'not_ready': len(nodes) - ready_nodes
                },
                'pods': {
                    'total': len(all_pods),
                    'running': running_pods,
                    'pending': pending_pods,
                    'failed': failed_pods
                }
            }
            
        except Exception as e:
            print(f"Error getting cluster health: {e}")
            return {}
    
    def get_pod_logs(self, pod_name: str, namespace='default', tail=100) -> List[str]:
        """Get logs from a pod"""
        if not self.core_v1:
            return []
        
        try:
            logs = self.core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=tail
            )
            return logs.split('\n')
        except ApiException as e:
            print(f"Error getting logs: {e}")
            return []
    
    def register_pods_as_services(self, namespace='default'):
        """Auto-register discovered pods as monitored services"""
        pods = self.discover_pods(namespace=namespace)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        for pod in pods:
            service_name = f"k8s-{namespace}-{pod['name']}"
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO services 
                    (service_name, service_type, status, last_seen)
                    VALUES (?, ?, ?, ?)
                ''', (service_name, 'kubernetes_pod', 'active', datetime.now().isoformat()))
            except Exception as e:
                print(f"Error registering {service_name}: {e}")
        
        conn.commit()
        conn.close()
        
        return len(pods)
    
    def _get_container_state(self, state) -> str:
        """Extract container state from status"""
        if state.running:
            return 'running'
        elif state.waiting:
            return f'waiting: {state.waiting.reason}'
        elif state.terminated:
            return f'terminated: {state.terminated.reason}'
        return 'unknown'
    
    def _get_pod_conditions(self, conditions) -> Dict[str, bool]:
        """Extract pod conditions"""
        if not conditions:
            return {}
        
        return {
            condition.type: condition.status == 'True'
            for condition in conditions
        }

def init_kubernetes_tables():
    """Initialize database tables for Kubernetes monitoring"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Pod metrics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pod_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pod_name TEXT NOT NULL,
            namespace TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            phase TEXT,
            ready_containers INTEGER,
            total_containers INTEGER,
            restart_count INTEGER,
            node_name TEXT
        )
    ''')
    
    # Deployment status table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deployment_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deployment_name TEXT NOT NULL,
            namespace TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            desired_replicas INTEGER,
            ready_replicas INTEGER,
            available_replicas INTEGER,
            updated_replicas INTEGER
        )
    ''')
    
    # Cluster health table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cluster_health (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            total_nodes INTEGER,
            ready_nodes INTEGER,
            total_pods INTEGER,
            running_pods INTEGER,
            pending_pods INTEGER,
            failed_pods INTEGER,
            components_status TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# Example usage
if __name__ == '__main__':
    # Initialize tables
    init_kubernetes_tables()
    
    # Create monitor
    monitor = KubernetesMonitor()
    
    if monitor.core_v1:
        # Discover resources
        print("\n=== Namespaces ===")
        namespaces = monitor.discover_namespaces()
        print(f"Found {len(namespaces)} namespaces: {', '.join(namespaces)}")
        
        print("\n=== Nodes ===")
        nodes = monitor.discover_nodes()
        for node in nodes:
            status = '✓ Ready' if node['ready'] else '✗ Not Ready'
            print(f"  {status} {node['name']}")
            print(f"    CPU: {node['capacity']['cpu']}, Memory: {node['capacity']['memory']}")
        
        print("\n=== Pods (default namespace) ===")
        pods = monitor.discover_pods(namespace='default')
        for pod in pods:
            print(f"  • {pod['name']} ({pod['phase']})")
            for container in pod['container_statuses']:
                print(f"    - {container['name']}: {container['state']} (restarts: {container['restart_count']})")
        
        print("\n=== Deployments (default namespace) ===")
        deployments = monitor.discover_deployments(namespace='default')
        for deploy in deployments:
            print(f"  • {deploy['name']}: {deploy['ready_replicas']}/{deploy['replicas']} ready")
        
        print("\n=== Services (default namespace) ===")
        services = monitor.discover_services(namespace='default')
        for svc in services:
            print(f"  • {svc['name']} ({svc['type']}) - {svc['cluster_ip']}")
        
        print("\n=== Cluster Health ===")
        health = monitor.get_cluster_health()
        print(f"  Nodes: {health['nodes']['ready']}/{health['nodes']['total']} ready")
        print(f"  Pods: {health['pods']['running']}/{health['pods']['total']} running")
