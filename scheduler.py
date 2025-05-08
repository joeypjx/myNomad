from typing import Dict, Optional
import threading
import time
import uuid
import queue
from models import Job, TriggerEvent
from scheduler_planner import SchedulerPlanner, EvaluationStatus
from node_manager import NodeManager
# Forward declaration for type hint
# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
#     from allocation_executor import AllocationExecutor 

class Scheduler:
    def __init__(self, node_manager: NodeManager):
        self.node_manager = node_manager
        self.allocation_executor = None  # 将在之后通过set_executor设置
        self.evaluation_queue = queue.Queue()
        print("[Scheduler] 调度器已初始化")
        self.scheduling_thread = threading.Thread(target=self._scheduling_loop, daemon=True)
        self.scheduling_thread.start()

    def set_executor(self, allocation_executor):
        """设置分配执行器引用，解决循环依赖问题"""
        self.allocation_executor = allocation_executor
        print("[Scheduler] 已设置分配执行器引用")

    def create_evaluation(self, job_data: Dict, job_id: str = None) -> Optional[SchedulerPlanner]:
        """创建新的评估"""
        print("\n[Scheduler] 收到新的作业评估请求")
        
        # 如果提供了job_id，说明是更新操作
        if job_id:
            job_data["job_id"] = job_id
            # 获取现有作业信息用于比较
            existing_job = self.node_manager.get_job(job_id)
            if not existing_job:
                print("[Scheduler] 错误：找不到要更新的作业")
                return None
        else:
            job_id = str(uuid.uuid4())
            existing_job = None

        print(f"[Scheduler] 开始为作业 {job_id} 创建{'更新' if existing_job else '新'}评估")
        job = Job(job_id, job_data["task_groups"], job_data.get("constraints", {}))
        
        # 在创建评估时就持久化作业的基础状态 - 无论是新作业还是更新
        job_data_to_save = {
            "job_id": job_id,
            "task_groups": job_data["task_groups"],
            "constraints": job_data.get("constraints", {})
            # 对于新作业，默认状态为PENDING；对于更新，保留现有状态
        }
        self.node_manager.submit_job(job_data_to_save)
        print(f"[Scheduler] 已{'更新' if existing_job else '初始化'}作业 {job_id} 的基础数据")
            
        nodes = self.node_manager.get_healthy_nodes()
        
        if not nodes:
            print("[Scheduler] 警告：没有可用的健康节点")
            return None
        
        evaluation = SchedulerPlanner(
            id=str(uuid.uuid4()),
            trigger_event=TriggerEvent.JOB_UPDATE if existing_job else TriggerEvent.JOB_SUBMIT,
            job=job,
            nodes=nodes,
            existing_job=existing_job  # 传入现有作业信息
        )
        
        print(f"[Scheduler] 创建评估成功，评估ID: {evaluation.id}")
        return evaluation

    def enqueue_evaluation(self, evaluation: SchedulerPlanner):
        """将评估加入调度器自己的队列"""
        if evaluation:
            self.evaluation_queue.put(evaluation)
            print(f"[Scheduler] 已将评估 {evaluation.id} 加入内部队列")
        else:
            print(f"[Scheduler] 尝试加入空评估到内部队列，已忽略")

    def process_evaluation(self, evaluation: SchedulerPlanner):
        """处理单个评估"""
        print(f"\n[Scheduler] 开始处理评估 {evaluation.id}")
        
        # 检查是否已设置allocation_executor
        if not self.allocation_executor:
            print(f"[Scheduler] 错误：尚未设置分配执行器，无法处理评估 {evaluation.id}")
            return
            
        # 执行评估并获取决策结果
        evaluation_result = evaluation.process(self.node_manager)
        success = evaluation_result["success"]
        plan = evaluation_result["plan"]  # 新分配
        allocations_to_delete = evaluation_result["allocations_to_delete"]  # 要删除的分配
        
        if success:
            print(f"[Scheduler] 评估 {evaluation.id} 成功，开始执行分配计划")
            
            # 更新作业状态 - 如有必要
            # 注意：作业的初始状态已在create_evaluation中设置
            # 如果需要更新作业状态，可以在这里添加逻辑
            
            # 提交完整分配计划（创建和删除）给allocation_executor执行
            self.allocation_executor.submit_plan(plan, allocations_to_delete)
            print(f"[Scheduler] 提交计划: 创建 {len(plan)} 个分配, 删除 {len(allocations_to_delete)} 个分配")
        else:
            print(f"[Scheduler] 评估 {evaluation.id} 失败，无法为作业创建分配计划")

    def _scheduling_loop(self):
        """调度循环"""
        print("[Scheduler] 调度循环已启动")
        while True:
            if not self.evaluation_queue.empty():
                evaluation = self.evaluation_queue.get()
                print(f"[Scheduler] 从队列中获取评估 {evaluation.id} 进行处理")
                try:
                    self.process_evaluation(evaluation)
                    # Set evaluation status here
                    if evaluation: # Should always be true if taken from queue
                        evaluation.status = EvaluationStatus.COMPLETE
                        print(f"[Scheduler] 评估 {evaluation.id} 处理完成 (状态: {evaluation.status.value})")
                except Exception as e:
                    if evaluation: # Should always be true
                        evaluation.status = EvaluationStatus.FAILED
                    # Ensure evaluation ID is available even if evaluation object itself might be in a bad state from an error
                    eval_id_for_log = evaluation.id if evaluation else "未知"
                    print(f"[Scheduler] 评估 {eval_id_for_log} 处理失败: {e}")
            time.sleep(1) 