import threading
import time
import psutil
import requests
import uuid
import json
from typing import Dict, List
from flask import Flask, request, jsonify
from enum import Enum

class AllocationStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"

class TaskAllocation:
    def __init__(self, allocation_id: str, job_id: str, task_group: str):
        self.id = allocation_id
        self.job_id = job_id
        self.task_group = task_group
        self.status = AllocationStatus.PENDING
        self.start_time = None
        self.end_time = None

class NodeAgent:
    def __init__(self, server_url: str, region: str, agent_port: int):
        self.server_url = server_url
        self.node_id = str(uuid.uuid4())
        self.region = region
        self.healthy = True
        self.heartbeat_interval = 5  # 心跳间隔（秒）
        self.agent_port = agent_port
        self.allocations: Dict[str, TaskAllocation] = {}  # 存储分配ID到分配对象的映射
        
        # 创建Flask应用
        self.app = Flask(__name__)
        self.setup_routes()

    def setup_routes(self):
        """设置API路由"""
        @self.app.route('/allocations', methods=['POST'])
        def handle_allocation():
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400
            
            required_fields = ["allocation_id", "job_id", "task_group"]
            if not all(field in data for field in required_fields):
                return jsonify({"error": "Missing required fields"}), 400
            
            task_group_data = data["task_group"]
            allocation = TaskAllocation(
                data["allocation_id"],
                data["job_id"],
                task_group_data["name"]
            )
            
            # 存储分配信息
            self.allocations[allocation.id] = allocation
            
            # 为每个任务启动一个执行线程
            for task in task_group_data["tasks"]:
                thread = threading.Thread(
                    target=self.execute_task,
                    args=(allocation, task),
                    daemon=True
                )
                thread.start()
            
            return jsonify({
                "message": "Allocation accepted",
                "allocation_id": allocation.id
            }), 200

        @self.app.route('/allocations/<allocation_id>', methods=['GET'])
        def get_allocation_status(allocation_id):
            allocation = self.allocations.get(allocation_id)
            if not allocation:
                return jsonify({"error": "Allocation not found"}), 404
            
            return jsonify({
                "allocation_id": allocation.id,
                "job_id": allocation.job_id,
                "task_group": allocation.task_group,
                "status": allocation.status.value,
                "start_time": allocation.start_time,
                "end_time": allocation.end_time
            }), 200

    def execute_task(self, allocation: TaskAllocation, task: Dict):
        """执行单个任务"""
        try:
            print(f"[Agent] 开始执行任务: {allocation.id}/{task['name']}")
            
            # 更新任务状态
            allocation.status = AllocationStatus.RUNNING
            if not hasattr(allocation, 'start_time'):
                allocation.start_time = time.time()
            
            # 这里模拟任务执行
            # 实际应用中，这里应该根据task的config来执行具体的任务
            print(f"[Agent] 任务配置: {json.dumps(task['config'], indent=2)}")
            print(f"[Agent] 资源分配: CPU {task['resources']['cpu']}, 内存 {task['resources']['memory']}MB")
            time.sleep(10)  # 模拟任务执行时间
            
            print(f"[Agent] 任务执行完成: {allocation.id}/{task['name']}")
            
        except Exception as e:
            print(f"[Agent] 任务执行失败: {allocation.id}/{task['name']}, 错误: {e}")
            allocation.status = AllocationStatus.FAILED
            
        # 检查是否所有任务都完成了
        if allocation.status != AllocationStatus.FAILED:
            allocation.status = AllocationStatus.COMPLETE
            allocation.end_time = time.time()

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
            "healthy": self.healthy,
            "endpoint": f"http://localhost:{self.agent_port}"  # agent的endpoint
        }
        
        try:
            response = requests.post(
                f"{self.server_url}/register",
                json=registration_data
            )
            if response.status_code == 200:
                print(f"[Agent] 节点 {self.node_id} 注册成功")
                return True
            else:
                print(f"[Agent] 节点注册失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"[Agent] 注册错误: {e}")
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
                print(f"[Agent] 心跳发送失败: {response.status_code}")
        except Exception as e:
            print(f"[Agent] 心跳错误: {e}")

    def start(self):
        """启动Agent"""
        if not self.register():
            print("[Agent] 注册失败，Agent将不会启动")
            return

        def heartbeat_loop():
            while True:
                self.send_heartbeat()
                time.sleep(self.heartbeat_interval)

        # 启动心跳线程
        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        
        # 启动API服务器
        self.app.run(host='0.0.0.0', port=self.agent_port)

if __name__ == "__main__":
    # 示例使用
    agent = NodeAgent("http://localhost:8500", "us-west", 8501)
    agent.start()
    
    # 保持主程序运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Agent stopping...") 