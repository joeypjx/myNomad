import threading
import time
import queue
from typing import List
from models import Allocation, JobStatus
from node_manager import NodeManager
from scheduler import Scheduler
from agent_client import AgentClient

class Leader:
    def __init__(self):
        self.agent_client = AgentClient()
        self.node_manager = NodeManager()
        self.node_manager.agent_client = self.agent_client  # 注入agent_client
        self.scheduler = Scheduler(self.node_manager)
        self.evaluation_queue = queue.Queue()
        self.plan_queue = queue.Queue()
        
        # 启动评估处理线程
        self.eval_thread = threading.Thread(target=self.process_evaluations, daemon=True)
        self.eval_thread.start()
        
        # 启动计划处理线程
        self.plan_thread = threading.Thread(target=self.process_plans, daemon=True)
        self.plan_thread.start()
        
        print("[Leader] Leader服务已初始化")

    def register_agent_endpoint(self, node_id: str, endpoint: str):
        """注册agent的endpoint"""
        self.agent_client.register_agent(node_id, endpoint)

    def enqueue_evaluation(self, evaluation):
        """将评估加入队列"""
        self.evaluation_queue.put(evaluation)
        print(f"[Leader] 已将评估 {evaluation.id} 加入队列")

    def submit_plan(self, plan: List[Allocation]):
        """将计划加入队列"""
        self.plan_queue.put(plan)
        print(f"[Leader] 已将分配计划加入队列: {[alloc.id for alloc in plan]}")

    def process_evaluations(self):
        """处理评估队列中的评估"""
        while True:
            if not self.evaluation_queue.empty():
                evaluation = self.evaluation_queue.get()
                print(f"[Leader] 正在处理评估 {evaluation.id}")
                self.scheduler.process_evaluation(evaluation, self)
            time.sleep(1)

    def process_plans(self):
        """处理计划队列中的计划"""
        while True:
            if not self.plan_queue.empty():
                plan = self.plan_queue.get()
                print(f"[Leader] 正在执行分配计划: {[alloc.id for alloc in plan]}")
                for allocation in plan:
                    # 发送分配计划到agent
                    result = self.agent_client.send_allocation(allocation)
                    if result:
                        # 更新本地状态
                        allocation.status = JobStatus.RUNNING
                        self.node_manager.update_allocation(allocation)
                        print(f"[Leader] 已创建分配 {allocation.id}, 节点: {allocation.node_id}")
                    else:
                        # 分配失败
                        allocation.status = JobStatus.FAILED
                        self.node_manager.update_allocation(allocation)
                        print(f"[Leader] 分配失败 {allocation.id}")
            time.sleep(1)

    def get_node_manager(self):
        """获取节点管理器实例"""
        return self.node_manager

    def get_scheduler(self):
        """获取调度器实例"""
        return self.scheduler 