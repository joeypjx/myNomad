import threading
import time
import psutil
import requests
import uuid
import json
from typing import Dict

class NodeAgent:
    def __init__(self, server_url: str, region: str):
        self.server_url = server_url
        self.node_id = str(uuid.uuid4())
        self.region = region
        self.healthy = True
        self.heartbeat_interval = 5  # 心跳间隔（秒）

    def get_resources(self) -> Dict:
        """获取当前节点的资源使用情况"""
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        return {
            "cpu": int((100 - cpu_percent) * 10),  # 转换为Nomad的CPU单位
            "memory": int(memory.available / (1024 * 1024)),  # 转换为MB
            "cpu_used": int(cpu_percent * 10),
            "memory_used": int((memory.total - memory.available) / (1024 * 1024))
        }

    def register(self):
        """向服务器注册节点"""
        registration_data = {
            "node_id": self.node_id,
            "region": self.region,
            "resources": self.get_resources(),
            "healthy": self.healthy
        }
        
        try:
            response = requests.post(
                f"{self.server_url}/register",
                json=registration_data
            )
            if response.status_code == 200:
                print(f"Node {self.node_id} registered successfully")
                return True
            else:
                print(f"Failed to register node {self.node_id}")
                return False
        except Exception as e:
            print(f"Registration error: {e}")
            return False

    def send_heartbeat(self):
        """发送心跳信息"""
        heartbeat_data = {
            "node_id": self.node_id,
            "resources": self.get_resources(),
            "healthy": self.healthy,
            "timestamp": time.time()
        }
        
        try:
            response = requests.post(
                f"{self.server_url}/heartbeat",
                json=heartbeat_data
            )
            if response.status_code != 200:
                print(f"Failed to send heartbeat: {response.status_code}")
        except Exception as e:
            print(f"Heartbeat error: {e}")

    def start(self):
        """启动Agent"""
        if not self.register():
            print("Registration failed, agent will not start")
            return

        def heartbeat_loop():
            while True:
                self.send_heartbeat()
                time.sleep(self.heartbeat_interval)

        # 启动心跳线程
        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        heartbeat_thread.start()

if __name__ == "__main__":
    # 示例使用
    agent = NodeAgent("http://localhost:8500", "us-west")
    agent.start()
    
    # 保持主程序运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Agent stopping...") 