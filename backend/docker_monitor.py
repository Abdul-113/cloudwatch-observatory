"""
Docker Monitoring Module
Monitors Docker containers, images, networks, and volumes
"""

import docker
from docker.errors import DockerException
from datetime import datetime
from typing import List, Dict, Any
import sqlite3

DB_PATH = 'monitoring.db'

class DockerMonitor:
    """Monitor Docker containers and collect metrics"""
    
    def __init__(self, docker_host='unix://var/run/docker.sock'):
        """
        Initialize Docker client
        
        Args:
            docker_host: Docker daemon socket or TCP endpoint
                        - unix://var/run/docker.sock (local)
                        - tcp://remote-host:2375 (remote)
        """
        try:
            self.client = docker.DockerClient(base_url=docker_host)
            self.api_client = docker.APIClient(base_url=docker_host)
            # Test connection
            self.client.ping()
            print(f"✓ Connected to Docker daemon: {docker_host}")
        except DockerException as e:
            print(f"✗ Failed to connect to Docker: {e}")
            self.client = None
    
    def discover_containers(self, include_stopped=False) -> List[Dict[str, Any]]:
        """
        Discover all Docker containers
        
        Args:
            include_stopped: Include stopped containers
            
        Returns:
            List of container info dictionaries
        """
        if not self.client:
            return []
        
        try:
            containers = self.client.containers.list(all=include_stopped)
            
            discovered = []
            for container in containers:
                info = {
                    'id': container.id[:12],
                    'name': container.name,
                    'image': container.image.tags[0] if container.image.tags else container.image.id[:12],
                    'status': container.status,
                    'state': container.attrs['State'],
                    'created': container.attrs['Created'],
                    'labels': container.labels,
                    'ports': container.ports,
                    'networks': list(container.attrs['NetworkSettings']['Networks'].keys())
                }
                discovered.append(info)
            
            return discovered
            
        except DockerException as e:
            print(f"Error discovering containers: {e}")
            return []
    
    def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """
        Get real-time statistics for a container
        
        Returns metrics like CPU, memory, network I/O, disk I/O
        """
        if not self.client:
            return {}
        
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)
            
            # Calculate CPU percentage
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            cpu_percent = 0.0
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * \
                             len(stats['cpu_stats']['cpu_usage'].get('percpu_usage', [1])) * 100
            
            # Memory stats
            memory_usage = stats['memory_stats'].get('usage', 0)
            memory_limit = stats['memory_stats'].get('limit', 1)
            memory_percent = (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0
            
            # Network I/O
            networks = stats.get('networks', {})
            rx_bytes = sum(net['rx_bytes'] for net in networks.values())
            tx_bytes = sum(net['tx_bytes'] for net in networks.values())
            
            # Disk I/O
            blkio_stats = stats.get('blkio_stats', {})
            io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])
            read_bytes = sum(entry['value'] for entry in io_service_bytes 
                           if entry['op'] == 'Read')
            write_bytes = sum(entry['value'] for entry in io_service_bytes 
                            if entry['op'] == 'Write')
            
            return {
                'container_id': container_id,
                'container_name': container.name,
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': round(cpu_percent, 2),
                'memory_usage_bytes': memory_usage,
                'memory_limit_bytes': memory_limit,
                'memory_percent': round(memory_percent, 2),
                'network_rx_bytes': rx_bytes,
                'network_tx_bytes': tx_bytes,
                'disk_read_bytes': read_bytes,
                'disk_write_bytes': write_bytes,
                'pids': stats.get('pids_stats', {}).get('current', 0)
            }
            
        except Exception as e:
            print(f"Error getting stats for {container_id}: {e}")
            return {}
    
    def get_container_logs(self, container_id: str, tail=100) -> List[str]:
        """Get recent logs from a container"""
        if not self.client:
            return []
        
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=True)
            return logs.decode('utf-8').split('\n')
        except Exception as e:
            print(f"Error getting logs: {e}")
            return []
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get Docker system information"""
        if not self.client:
            return {}
        
        try:
            info = self.client.info()
            return {
                'containers_running': info['ContainersRunning'],
                'containers_paused': info['ContainersPaused'],
                'containers_stopped': info['ContainersStopped'],
                'images': info['Images'],
                'server_version': info['ServerVersion'],
                'operating_system': info['OperatingSystem'],
                'architecture': info['Architecture'],
                'ncpu': info['NCPU'],
                'mem_total': info['MemTotal'],
                'docker_root_dir': info['DockerRootDir']
            }
        except Exception as e:
            print(f"Error getting system info: {e}")
            return {}
    
    def get_image_info(self) -> List[Dict[str, Any]]:
        """Get information about Docker images"""
        if not self.client:
            return []
        
        try:
            images = self.client.images.list()
            return [
                {
                    'id': img.id[:12],
                    'tags': img.tags,
                    'size': img.attrs['Size'],
                    'created': img.attrs['Created']
                }
                for img in images
            ]
        except Exception as e:
            print(f"Error getting images: {e}")
            return []
    
    def monitor_all_containers(self) -> List[Dict[str, Any]]:
        """Collect stats from all running containers"""
        containers = self.discover_containers(include_stopped=False)
        all_stats = []
        
        for container in containers:
            if container['status'] == 'running':
                stats = self.get_container_stats(container['id'])
                if stats:
                    all_stats.append(stats)
        
        return all_stats
    
    def register_containers_as_services(self):
        """Auto-register discovered containers as monitored services"""
        containers = self.discover_containers(include_stopped=False)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        for container in containers:
            service_name = f"docker-{container['name']}"
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO services 
                    (service_name, service_type, status, last_seen)
                    VALUES (?, ?, ?, ?)
                ''', (service_name, 'docker_container', 'active', datetime.now().isoformat()))
            except Exception as e:
                print(f"Error registering {service_name}: {e}")
        
        conn.commit()
        conn.close()
        
        return len(containers)

def init_docker_tables():
    """Initialize database tables for Docker monitoring"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Container metrics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS container_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            container_id TEXT NOT NULL,
            container_name TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            cpu_percent REAL,
            memory_usage_bytes INTEGER,
            memory_percent REAL,
            network_rx_bytes INTEGER,
            network_tx_bytes INTEGER,
            disk_read_bytes INTEGER,
            disk_write_bytes INTEGER,
            pids INTEGER
        )
    ''')
    
    # Container registry
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS containers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            container_id TEXT UNIQUE NOT NULL,
            container_name TEXT NOT NULL,
            image TEXT,
            status TEXT,
            created_at TEXT,
            discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME
        )
    ''')
    
    conn.commit()
    conn.close()

# Example usage
if __name__ == '__main__':
    # Initialize tables
    init_docker_tables()
    
    # Create monitor
    monitor = DockerMonitor()
    
    # Discover containers
    print("\n=== Discovered Containers ===")
    containers = monitor.discover_containers()
    for container in containers:
        print(f"  • {container['name']} ({container['status']}) - {container['image']}")
    
    # Get system info
    print("\n=== Docker System Info ===")
    sys_info = monitor.get_system_info()
    print(f"  Running: {sys_info.get('containers_running', 0)}")
    print(f"  Stopped: {sys_info.get('containers_stopped', 0)}")
    print(f"  Images: {sys_info.get('images', 0)}")
    
    # Monitor all containers
    print("\n=== Container Stats ===")
    stats = monitor.monitor_all_containers()
    for stat in stats:
        print(f"  {stat['container_name']}:")
        print(f"    CPU: {stat['cpu_percent']:.2f}%")
        print(f"    Memory: {stat['memory_percent']:.2f}%")
        print(f"    Network: ↓{stat['network_rx_bytes']/1024/1024:.2f}MB ↑{stat['network_tx_bytes']/1024/1024:.2f}MB")
