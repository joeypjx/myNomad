import threading
import time
import queue
from typing import List
from models import Allocation, AllocationStatus
from scheduler import Scheduler
from agent_client import AgentClient
from evaluation import Evaluation, EvaluationStatus

class Leader:
    def __init__(self, node_manager):
        self.node_manager = node_manager
        self.agent_client = AgentClient()
        self.node_manager.agent_client = self.agent_client
        self.scheduler = Scheduler(self.node_manager)
        self.evaluation_queue = queue.Queue()
        self.plan_queue = queue.Queue()
        self.is_running = False
        
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

    def enqueue_evaluation(self, evaluation: Evaluation):
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
            try:
                if not self.evaluation_queue.empty():
                    evaluation = self.evaluation_queue.get()
                    print(f"[Leader] 正在处理评估 {evaluation.id}")
                    try:
                        self.scheduler.process_evaluation(evaluation, self)
                        evaluation.status = EvaluationStatus.COMPLETE
                        print(f"[Leader] 评估 {evaluation.id} 处理完成")
                    except Exception as e:
                        evaluation.status = EvaluationStatus.FAILED
                        print(f"[Leader] 评估 {evaluation.id} 处理失败: {e}")
            except Exception as e:
                print(f"[Leader] 处理评估时出错: {e}")
            time.sleep(1)

    def process_plans(self):
        """处理计划队列中的计划"""
        while True:
            try:
                if not self.plan_queue.empty():
                    plan = self.plan_queue.get()
                    print(f"[Leader] 正在执行分配计划: {[alloc.id for alloc in plan]}")
                    for allocation in plan:
                        try:
                            # 更新分配状态为运行中
                            allocation.status = AllocationStatus.RUNNING
                            
                            # 发送分配计划到agent
                            result = self.agent_client.send_allocation(allocation)
                            if result:
                                # 更新本地状态
                                self.node_manager.update_allocation(allocation)
                                print(f"[Leader] 已创建分配 {allocation.id}, 节点: {allocation.node_id}")
                            else:
                                # 分配失败
                                allocation.status = AllocationStatus.FAILED
                                self.node_manager.update_allocation(allocation)
                                print(f"[Leader] 分配失败 {allocation.id}")
                        except Exception as e:
                            print(f"[Leader] 处理分配时出错: {e}")
                            allocation.status = AllocationStatus.FAILED
                            self.node_manager.update_allocation(allocation)
            except Exception as e:
                print(f"[Leader] 处理计划时出错: {e}")
            time.sleep(1)

    def start(self):
        """启动Leader服务"""
        if not self.is_running:
            self.is_running = True
            print("[Leader] 服务已启动")

    def stop(self):
        """停止Leader服务"""
        self.is_running = False
        if self.eval_thread:
            self.eval_thread.join()
        if self.plan_thread:
            self.plan_thread.join()
        print("[Leader] 服务已停止") 