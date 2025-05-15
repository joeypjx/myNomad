from typing import Dict

class AlarmManager:
    """告警管理器，负责监控资源使用情况并发出告警"""
    
    def __init__(self):
        # 资源告警阈值配置
        self.resource_thresholds = {
            "cpu_usage": 90,  # CPU使用率超过90%告警
            "memory_usage": 85,  # 内存使用率超过85%告警
            "disk_usage": 80,  # 磁盘使用率超过80%告警
        }
        print("[AlarmManager] 告警管理器已初始化")
    
    def handle_heartbeat(self, node_id: str, resources: Dict) -> None:
        """处理心跳数据中的资源使用情况
        
        Args:
            node_id: 节点ID
            resources: 资源使用情况
        """
        try:
            print(f"\n[AlarmManager] 检查节点 {node_id} 的资源使用情况")
            
            # 检查CPU使用率
            if "cpu_usage" in resources:
                cpu_usage = resources["cpu_usage"]
                if cpu_usage > self.resource_thresholds["cpu_usage"]:
                    print(f"[AlarmManager] 警告：节点 {node_id} CPU使用率过高: {cpu_usage}%")
            
            # 检查内存使用率
            if "memory_usage" in resources:
                memory_usage = resources["memory_usage"]
                if memory_usage > self.resource_thresholds["memory_usage"]:
                    print(f"[AlarmManager] 警告：节点 {node_id} 内存使用率过高: {memory_usage}%")
            
            # 检查磁盘使用率
            if "disk_usage" in resources:
                disk_usage = resources["disk_usage"]
                if disk_usage > self.resource_thresholds["disk_usage"]:
                    print(f"[AlarmManager] 警告：节点 {node_id} 磁盘使用率过高: {disk_usage}%")
                    
        except Exception as e:
            print(f"[AlarmManager] 检查资源使用情况时出错: {e}") 