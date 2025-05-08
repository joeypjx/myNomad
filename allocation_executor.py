import threading
import time
import queue
from typing import List
from models import Allocation, AllocationStatus
from agent_communicator import AgentCommunicator
import sqlite3

class AllocationExecutor:
    def __init__(self, node_manager):
        self.node_manager = node_manager
        self.agent_communicator = AgentCommunicator()
        self.node_manager.agent_client = self.agent_communicator  # 暂时保留用于兼容性，后续应该修改node_manager
        self.plan_queue = queue.Queue()
        self.is_running = False
        
        # 启动计划处理线程
        self.plan_thread = threading.Thread(target=self.process_plans, daemon=True)
        self.plan_thread.start()
        
        print("[AllocationExecutor] 分配执行器已初始化")

    def register_agent_endpoint(self, node_id: str, endpoint: str):
        """注册agent的endpoint"""
        self.agent_communicator.register_agent(node_id, endpoint)

    def submit_plan(self, plan: List[Allocation], allocations_to_delete: List[str] = None):
        """将完整计划（包括要创建和要删除的分配）加入队列"""
        complete_plan = {
            "create": plan,
            "delete": allocations_to_delete or []
        }
        self.plan_queue.put(complete_plan)
        print(f"[AllocationExecutor] 已将分配计划加入队列: 创建 {len(plan)} 个, 删除 {len(allocations_to_delete or [])} 个")

    def stop_allocation(self, allocation_id: str) -> bool:
        """停止分配并从数据库中删除
        1. 调用NodeManager获取必要信息
        2. 通知相关Agent停止任务
        3. 从数据库中删除分配记录
        """
        # 先从NodeManager获取需要的信息并删除分配记录
        success, node_id = self.node_manager.delete_allocation(allocation_id, notify_agent=True)
        if not success:
            print(f"[AllocationExecutor] 删除分配记录失败: {allocation_id}")
            return False
            
        # 如果需要通知Agent
        if node_id:
            # 通过AgentCommunicator通知节点停止任务
            notify_success = self.agent_communicator.stop_allocation(node_id, allocation_id)
            if not notify_success:
                print(f"[AllocationExecutor] 警告：通知节点 {node_id} 停止分配 {allocation_id} 失败")
            
            return notify_success
        
        return True

    def process_plans(self):
        """处理计划队列中的计划"""
        while True:
            try:
                if not self.plan_queue.empty():
                    plan = self.plan_queue.get()
                    allocations_to_create = plan["create"]
                    allocations_to_delete = plan["delete"]
                    
                    # 1. 首先处理要删除的分配
                    if allocations_to_delete:
                        print(f"[AllocationExecutor] 删除 {len(allocations_to_delete)} 个旧分配: {allocations_to_delete}")
                        for allocation_id in allocations_to_delete:
                            self.stop_allocation(allocation_id)
                    
                    # 2. 然后处理要创建的分配
                    if allocations_to_create:
                        print(f"[AllocationExecutor] 正在执行分配计划: {[alloc.id for alloc in allocations_to_create]}")
                        for allocation in allocations_to_create:
                            try:
                                # 更新分配状态为运行中
                                allocation.status = AllocationStatus.RUNNING
                                
                                # 发送分配计划到agent
                                result = self.agent_communicator.send_allocation(allocation)
                                if result:
                                    # 更新本地状态
                                    self.node_manager.update_allocation(allocation)
                                    print(f"[AllocationExecutor] 已创建分配 {allocation.id}, 节点: {allocation.node_id}")
                                else:
                                    # 分配失败
                                    allocation.status = AllocationStatus.FAILED
                                    self.node_manager.update_allocation(allocation)
                                    print(f"[AllocationExecutor] 分配失败 {allocation.id}")
                            except Exception as e:
                                print(f"[AllocationExecutor] 处理分配时出错: {e}")
                                allocation.status = AllocationStatus.FAILED
                                self.node_manager.update_allocation(allocation)
            except Exception as e:
                print(f"[AllocationExecutor] 处理计划时出错: {e}")
            time.sleep(1)

    def start(self):
        """启动分配执行器服务"""
        if not self.is_running:
            self.is_running = True
            print("[AllocationExecutor] 服务已启动")

    def stop(self):
        """停止分配执行器服务"""
        self.is_running = False
        if self.plan_thread:
            self.plan_thread.join()
        print("[AllocationExecutor] 服务已停止")

    def stop_job(self, job_id: str) -> bool:
        """停止作业
        1. 通过NodeManager获取作业状态并标记为DEAD
        2. 停止所有相关的分配
        """
        # 调用NodeManager停止作业，获取需要停止的分配
        success, allocations = self.node_manager.stop_job(job_id)
        if not success:
            print(f"[AllocationExecutor] 停止作业失败: {job_id}")
            return False
            
        if not allocations:
            print(f"[AllocationExecutor] 作业 {job_id} 没有活跃的分配")
            return True
            
        # 停止所有分配
        print(f"[AllocationExecutor] 停止作业 {job_id} 的 {len(allocations)} 个分配")
        for allocation in allocations:
            allocation_id = allocation["allocation_id"]
            node_id = allocation["node_id"]
            
            # 通知Agent停止任务
            notify_success = self.agent_communicator.stop_allocation(node_id, allocation_id)
            if not notify_success:
                print(f"[AllocationExecutor] 警告：通知节点 {node_id} 停止分配 {allocation_id} 失败")
                
            # 从数据库中删除分配记录（不需要再通知Agent）
            db_success, _ = self.node_manager.delete_allocation(allocation_id, notify_agent=False)
            if not db_success:
                print(f"[AllocationExecutor] 删除分配记录失败: {allocation_id}")
                
        print(f"[AllocationExecutor] 作业 {job_id} 已完全停止")
        return True

    def delete_job(self, job_id: str) -> bool:
        """删除作业及其所有相关资源
        1. 先停止作业的所有任务（负责与Agent通信）
        2. 然后调用NodeManager清理作业相关的所有数据库记录
        """
        # 首先停止作业的所有任务
        stop_success = self.stop_job(job_id)
        if not stop_success:
            print(f"[AllocationExecutor] 警告：停止作业 {job_id} 失败，但仍将尝试删除数据")
            
        # 调用NodeManager清理所有相关数据库记录
        clean_success = self.node_manager.clean_job_data(job_id)
        if not clean_success:
            print(f"[AllocationExecutor] 清理作业 {job_id} 数据库记录失败")
            return False
            
        print(f"[AllocationExecutor] 作业 {job_id} 及其相关资源已完全删除")
        return True 