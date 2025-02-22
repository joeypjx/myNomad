import requests
import json
from typing import Dict, Optional
from models import Allocation, JobStatus

class AgentClient:
    def __init__(self):
        self.agent_endpoints = {}  # 存储节点ID到agent endpoint的映射

    def register_agent(self, node_id: str, endpoint: str):
        """注册agent的endpoint"""
        self.agent_endpoints[node_id] = endpoint
        print(f"[AgentClient] 注册agent endpoint: {node_id} -> {endpoint}")

    def send_allocation(self, allocation: Allocation) -> Optional[Dict]:
        """发送分配计划到agent"""
        node_id = allocation.node_id
        if node_id not in self.agent_endpoints:
            print(f"[AgentClient] 错误：未找到节点 {node_id} 的agent endpoint")
            return None

        try:
            endpoint = f"{self.agent_endpoints[node_id]}/allocations"
            # 将TaskGroup对象转换为可序列化的字典
            task_group_data = {
                "name": allocation.task_group.name,
                "tasks": [
                    {
                        "name": task.name,
                        "resources": task.resources,
                        "config": task.config
                    } for task in allocation.task_group.tasks
                ]
            }
            
            allocation_data = {
                "allocation_id": allocation.id,
                "job_id": allocation.job_id,
                "task_group": task_group_data,
                "status": allocation.status.value
            }
            
            print(f"[AgentClient] 发送分配计划到节点 {node_id}: {allocation.id}")
            response = requests.post(
                endpoint,
                json=allocation_data,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"[AgentClient] 节点 {node_id} 接受分配计划: {allocation.id}")
                return result
            else:
                print(f"[AgentClient] 节点 {node_id} 拒绝分配计划: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"[AgentClient] 发送分配计划到节点 {node_id} 失败: {e}")
            return None

    def get_allocation_status(self, node_id: str, allocation_id: str) -> Optional[Dict]:
        """获取分配计划的执行状态"""
        if node_id not in self.agent_endpoints:
            print(f"[AgentClient] 错误：未找到节点 {node_id} 的agent endpoint")
            return None

        try:
            endpoint = f"{self.agent_endpoints[node_id]}/allocations/{allocation_id}"
            response = requests.get(
                endpoint,
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[AgentClient] 获取分配状态失败: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"[AgentClient] 获取分配状态失败: {e}")
            return None 

    def stop_allocation(self, node_id: str, allocation_id: str) -> bool:
        """通知agent停止分配"""
        if node_id not in self.agent_endpoints:
            print(f"[AgentClient] 错误：未找到节点 {node_id} 的agent endpoint")
            return False

        try:
            endpoint = f"{self.agent_endpoints[node_id]}/allocations/{allocation_id}"
            print(f"[AgentClient] 通知节点 {node_id} 停止分配: {allocation_id}")
            response = requests.delete(
                endpoint,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"[AgentClient] 节点 {node_id} 已确认停止分配: {allocation_id}")
                return True
            else:
                print(f"[AgentClient] 节点 {node_id} 停止分配失败: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"[AgentClient] 通知节点 {node_id} 停止分配时出错: {e}")
            return False 