import threading
import time
import psutil
import requests
import uuid
import json
import os
from typing import Dict, List
from flask import Flask, request, jsonify
from models import AllocationStatus, TaskStatus, TaskType

class Task:
    def __init__(self, name: str, resources: Dict, config: Dict):
        self.name = name
        self.resources = resources
        self.config = config
        self.status = TaskStatus.PENDING
        self.start_time = None
        self.end_time = None
        self.thread = None
        self.process = None  # 存储进程ID或容器ID
        self.task_type = TaskType.CONTAINER if config.get("image") else TaskType.PROCESS
        self.exit_code = None  # 添加退出码字段

    def update_status(self) -> bool:
        """更新任务的实际运行状态"""
        if not self.process:
            return False

        try:
            if self.task_type == TaskType.PROCESS:
                try:
                    process = psutil.Process(self.process)
                    if process.status() == psutil.STATUS_RUNNING:
                        self.status = TaskStatus.RUNNING
                        return True
                    elif process.status() in [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD]:
                        self.status = TaskStatus.FAILED
                        self.exit_code = process.wait(timeout=0)
                        self.end_time = time.time()
                        return True
                except psutil.NoSuchProcess:
                    if self.status == TaskStatus.RUNNING:
                        self.status = TaskStatus.FAILED
                        self.end_time = time.time()
                    return False
                    
            elif self.task_type == TaskType.CONTAINER:
                import docker
                client = docker.from_env()
                try:
                    container = client.containers.get(self.process)
                    if container.status == "running":
                        self.status = TaskStatus.RUNNING
                        return True
                    elif container.status == "exited":
                        container_info = container.attrs
                        self.exit_code = container_info["State"]["ExitCode"]
                        if self.exit_code == 0:
                            self.status = TaskStatus.COMPLETE
                        else:
                            self.status = TaskStatus.FAILED
                        self.end_time = time.time()
                        return True
                    else:
                        # 其他状态（如created, paused等）
                        print(f"[Agent] 容器 {self.process} 状态: {container.status}")
                        self.status = TaskStatus.PENDING
                        return True
                except docker.errors.NotFound:
                    if self.status == TaskStatus.RUNNING:
                        self.status = TaskStatus.FAILED
                        self.end_time = time.time()
                    return False
                    
        except Exception as e:
            print(f"[Agent] 更新任务状态时出错: {e}")
            if self.status == TaskStatus.RUNNING:
                self.status = TaskStatus.FAILED
                self.end_time = time.time()
            return False

class TaskAllocation:
    def __init__(self, allocation_id: str, job_id: str, task_group: str):
        self.id = allocation_id
        self.job_id = job_id
        self.task_group = task_group
        self.status = AllocationStatus.PENDING
        self.start_time = None
        self.end_time = None
        self.tasks: Dict[str, Task] = {}  # 存储任务名称到Task对象的映射

    def update_status(self):
        """更新分配的状态"""
        # 如果没有任务，保持PENDING状态
        if not self.tasks:
            return

        # 更新所有任务的状态
        all_complete = True
        any_failed = False
        any_running = False
        
        for task in self.tasks.values():
            task.update_status()
            
            if task.status == TaskStatus.FAILED:
                any_failed = True
            elif task.status == TaskStatus.RUNNING:
                any_running = True
                all_complete = False
            elif task.status != TaskStatus.COMPLETE:
                all_complete = False

        # 根据任务状态更新分配状态
        if any_failed:
            self.status = AllocationStatus.FAILED
            if not self.end_time:
                self.end_time = time.time()
        elif all_complete:
            self.status = AllocationStatus.COMPLETE
            if not self.end_time:
                self.end_time = time.time()
        elif any_running:
            self.status = AllocationStatus.RUNNING
            if not self.start_time:
                self.start_time = time.time()
        else:
            self.status = AllocationStatus.PENDING

class NodeAgent:
    def __init__(self, server_url: str, region: str, agent_port: int):
        self.server_url = server_url
        self.node_id = self._get_or_create_node_id()
        self.region = region
        self.healthy = True
        self.heartbeat_interval = 5  # 心跳间隔（秒）
        self.agent_port = agent_port
        self.allocations: Dict[str, TaskAllocation] = {}  # 存储分配ID到分配对象的映射
        self.task_monitor_thread = threading.Thread(target=self._monitor_tasks, daemon=True)
        self.task_monitor_thread.start()
        
        # 创建Flask应用
        self.app = Flask(__name__)
        self.setup_routes()

    def _get_or_create_node_id(self) -> str:
        """获取或创建节点ID"""
        node_id_file = "node_id.txt"
        
        # 尝试从文件读取节点ID
        if os.path.exists(node_id_file):
            try:
                with open(node_id_file, 'r') as f:
                    node_id = f.read().strip()
                    if node_id:
                        print(f"[Agent] 从文件加载节点ID: {node_id}")
                        return node_id
            except Exception as e:
                print(f"[Agent] 读取节点ID文件时出错: {e}")
        
        # 如果文件不存在或读取失败，创建新的节点ID
        new_node_id = str(uuid.uuid4())
        try:
            with open(node_id_file, 'w') as f:
                f.write(new_node_id)
            print(f"[Agent] 创建新的节点ID: {new_node_id}")
        except Exception as e:
            print(f"[Agent] 保存节点ID到文件时出错: {e}")
        
        return new_node_id

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
            
            # 为每个任务创建Task对象
            for task_data in task_group_data["tasks"]:
                task = Task(
                    task_data["name"],
                    task_data["resources"],
                    task_data["config"]
                )
                allocation.tasks[task.name] = task
            
            # 存储分配信息
            self.allocations[allocation.id] = allocation
            
            # 为每个任务启动一个执行线程
            for task in allocation.tasks.values():
                task.thread = threading.Thread(
                    target=self.execute_task,
                    args=(allocation, task),
                    daemon=True
                )
                task.thread.start()
            
            return jsonify({
                "message": "Allocation accepted",
                "allocation_id": allocation.id
            }), 200

        @self.app.route('/allocations/<allocation_id>', methods=['GET'])
        def get_allocation_status(allocation_id):
            allocation = self.allocations.get(allocation_id)
            if not allocation:
                return jsonify({"error": "Allocation not found"}), 404
            
            # 收集所有任务的状态
            tasks_status = {
                task_name: {
                    "status": task.status.value,
                    "start_time": task.start_time,
                    "end_time": task.end_time
                } for task_name, task in allocation.tasks.items()
            }
            
            return jsonify({
                "allocation_id": allocation.id,
                "job_id": allocation.job_id,
                "task_group": allocation.task_group,
                "status": allocation.status.value,
                "start_time": allocation.start_time,
                "end_time": allocation.end_time,
                "tasks": tasks_status
            }), 200

        @self.app.route('/allocations/<allocation_id>', methods=['DELETE'])
        def stop_allocation(allocation_id):
            """停止分配的所有任务"""
            allocation = self.allocations.get(allocation_id)
            if not allocation:
                return jsonify({"error": "Allocation not found"}), 404
            
            print(f"[Agent] 停止分配 {allocation_id} 的所有任务")
            # 停止所有相关任务
            self.stop_tasks(allocation)
            
            # 从分配列表中移除
            del self.allocations[allocation_id]
            
            return jsonify({
                "message": f"Allocation {allocation_id} stopped and removed"
            }), 200

    def execute_task(self, allocation: TaskAllocation, task: Task):
        """执行单个任务"""
        try:
            print(f"[Agent] 开始执行任务: {allocation.id}/{task.name}")
            
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.start_time = time.time()
            allocation.start_time = allocation.start_time or task.start_time
            allocation.status = AllocationStatus.RUNNING
            
            if task.task_type == TaskType.CONTAINER:
                # 使用Docker API启动容器
                import docker
                client = docker.from_env()
                container = client.containers.run(
                    task.config["image"],
                    detach=True,
                    ports={f"{task.config['port']}/tcp": task.config['port']} if "port" in task.config else None,
                    mem_limit=f"{task.resources['memory']}m",
                    cpu_quota=int(task.resources['cpu'] * 1000),  # 转换为微秒配额
                    cpu_period=100000  # 默认的CPU周期为100ms
                )
                task.process = container.id
                print(f"[Agent] 容器已启动: {container.id}")
                
            else:
                # 启动普通进程
                import subprocess
                process = subprocess.Popen(
                    task.config["command"],
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                task.process = process.pid
                print(f"[Agent] 进程已启动: {process.pid}")
            
        except Exception as e:
            print(f"[Agent] 任务执行失败: {allocation.id}/{task.name}, 错误: {e}")
            task.status = TaskStatus.FAILED
            task.end_time = time.time()
            allocation.status = AllocationStatus.FAILED

    def _monitor_tasks(self):
        """监控所有任务的状态"""
        while True:
            try:
                for allocation_id, allocation in list(self.allocations.items()):
                    # 更新分配状态
                    allocation.update_status()
                    
                    # 打印任务状态
                    print(f"\n[Agent] 分配 {allocation_id} 的任务状态 ({allocation.status.value}):")
                    for task_name, task in allocation.tasks.items():
                        status_info = f"{task.status.value}"
                        if task.exit_code is not None:
                            status_info += f" (退出码: {task.exit_code})"
                        print(f"  - {task_name}: {status_info}")
            
            except Exception as e:
                print(f"[Agent] 监控任务时出错: {e}")
            
            time.sleep(5)  # 每5秒检查一次

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
        # 收集所有分配的状态信息
        allocations_status = {}
        for allocation_id, allocation in self.allocations.items():
            tasks_status = {}
            for task_name, task in allocation.tasks.items():
                tasks_status[task_name] = {
                    "status": task.status.value,
                    "start_time": task.start_time,
                    "end_time": task.end_time
                }
            
            allocations_status[allocation_id] = {
                "status": allocation.status.value,
                "start_time": allocation.start_time,
                "end_time": allocation.end_time,
                "tasks": tasks_status
            }

        heartbeat_data = {
            "node_id": self.node_id,
            "resources": self.get_resources(),
            "healthy": self.healthy,
            "timestamp": time.time(),
            "allocations": allocations_status
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

    def stop_tasks(self, allocation: TaskAllocation):
        """停止分配相关的所有任务"""
        print(f"[Agent] 正在停止分配 {allocation.id} 的任务")
        
        for task in allocation.tasks.values():
            try:
                if not task.process:
                    continue
                    
                if task.task_type == TaskType.CONTAINER:
                    # 停止容器
                    import docker
                    client = docker.from_env()
                    try:
                        container = client.containers.get(task.process)
                        container.stop(timeout=10)  # 给容器10秒的优雅停止时间
                        print(f"[Agent] 容器 {task.process} 已停止")
                    except docker.errors.NotFound:
                        print(f"[Agent] 容器 {task.process} 不存在")
                        
                else:
                    # 停止进程
                    try:
                        process = psutil.Process(task.process)
                        process.terminate()  # 先尝试优雅终止
                        try:
                            process.wait(timeout=5)  # 等待进程终止
                        except psutil.TimeoutExpired:
                            process.kill()  # 如果等待超时，强制终止
                        print(f"[Agent] 进程 {task.process} 已停止")
                    except psutil.NoSuchProcess:
                        print(f"[Agent] 进程 {task.process} 不存在")
                
                task.status = TaskStatus.COMPLETE
                task.end_time = time.time()
                
            except Exception as e:
                print(f"[Agent] 停止任务 {task.name} 时出错: {e}")
                task.status = TaskStatus.FAILED
                task.end_time = time.time()
        
        allocation.status = AllocationStatus.STOPPED  # 更新为 STOPPED 状态
        allocation.end_time = time.time()
        print(f"[Agent] 分配 {allocation.id} 的所有任务已停止")

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