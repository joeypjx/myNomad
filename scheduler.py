from typing import Dict, Optional
import threading
import time
import uuid
import queue
from models import Job, TriggerEvent
from evaluation import Evaluation, EvaluationStatus
from node_manager import NodeManager
# Forward declaration for type hint if Leader is in the same file or to avoid circularity
# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
#     from leader import Leader 

class Scheduler:
    def __init__(self, node_manager: NodeManager, leader: 'Leader'):
        self.node_manager = node_manager
        self.leader = leader
        self.evaluation_queue = queue.Queue()
        print("[Scheduler] 调度器已初始化")
        self.scheduling_thread = threading.Thread(target=self._scheduling_loop, daemon=True)
        self.scheduling_thread.start()

    def create_evaluation(self, job_data: Dict, job_id: str = None) -> Optional[Evaluation]:
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
        nodes = self.node_manager.get_healthy_nodes()
        
        if not nodes:
            print("[Scheduler] 警告：没有可用的健康节点")
            return None
        
        evaluation = Evaluation(
            id=str(uuid.uuid4()),
            trigger_event=TriggerEvent.JOB_UPDATE if existing_job else TriggerEvent.JOB_SUBMIT,
            job=job,
            nodes=nodes,
            existing_job=existing_job  # 传入现有作业信息
        )
        
        print(f"[Scheduler] 创建评估成功，评估ID: {evaluation.id}")
        return evaluation

    def enqueue_evaluation(self, evaluation: Evaluation):
        """将评估加入调度器自己的队列"""
        if evaluation:
            self.evaluation_queue.put(evaluation)
            print(f"[Scheduler] 已将评估 {evaluation.id} 加入内部队列")
        else:
            print(f"[Scheduler] 尝试加入空评估到内部队列，已忽略")

    def process_evaluation(self, evaluation: Evaluation):
        """处理单个评估"""
        print(f"\n[Scheduler] 开始处理评估 {evaluation.id}")
        success = evaluation.process(self.node_manager)
        
        if success:
            print(f"[Scheduler] 评估 {evaluation.id} 成功，开始更新分配计划")
            # 评估成功后，更新作业信息
            job_data = {
                "job_id": evaluation.job.id,
                "task_groups": [
                    {
                        "name": group.name,
                        "tasks": [
                            {
                                "name": task.name,
                                "resources": task.resources,
                                "config": task.config
                            } for task in group.tasks
                        ]
                    } for group in evaluation.job.task_groups
                ],
                "constraints": evaluation.job.constraints
            }
            self.node_manager.submit_job(job_data)
            # 提交分配计划
            self.leader.submit_plan(evaluation.plan)
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