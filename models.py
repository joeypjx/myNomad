from typing import List, Dict
from enum import Enum

class EvaluationStatus(Enum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"

class JobStatus(Enum):
    PENDING = "pending"      # 作业已提交，但尚未被调度器处理
    RUNNING = "running"      # 作业已被调度，任务正在运行
    COMPLETE = "complete"    # 作业的所有任务都已成功完成
    FAILED = "failed"        # 作业的某些任务失败
    LOST = "lost"           # 作业的任务在运行过程中丢失（节点失联）
    DEAD = "dead"           # 作业已被显式停止
    DEGRADED = "degraded"   # 作业的部分任务失败，但仍有部分任务在运行
    BLOCKED = "blocked"     # 作业无法被调度，通常是由于资源不足或约束条件不满足

class TaskStatus(Enum):
    PENDING = "pending"    # 任务已创建但尚未开始
    RUNNING = "running"    # 任务正在运行
    COMPLETE = "complete"  # 任务已成功完成
    FAILED = "failed"      # 任务执行失败

class TaskType(Enum):
    PROCESS = "process"    # 非容器化的进程
    CONTAINER = "container"  # 容器化的任务

class AllocationStatus(Enum):
    PENDING = "pending"    # 分配已创建但尚未开始
    RUNNING = "running"    # 分配正在运行
    COMPLETE = "complete"  # 分配已成功完成
    FAILED = "failed"      # 分配执行失败
    LOST = "lost"         # 分配丢失（节点失联）
    STOPPED = "stopped"    # 分配被手动停止

class TriggerEvent(Enum):
    JOB_SUBMIT = "job_submit"
    JOB_UPDATE = "job_update"
    JOB_DEREGISTER = "job_deregister"
    NODE_FAILURE = "node_failure"
    NODE_JOIN = "node_join"

class Task:
    def __init__(self, name: str, resources: Dict, config: Dict):
        self.name = name
        self.resources = resources  # 例如：{"cpu": 100, "memory": 256}
        self.config = config       # 任务配置，例如：{"image": "nginx", "port": 80}
        self.status = TaskStatus.PENDING
        self.task_type = TaskType.CONTAINER if config.get("image") else TaskType.PROCESS

class TaskGroup:
    def __init__(self, name: str, tasks: List[Task]):
        self.name = name
        self.tasks = tasks
        self.status = JobStatus.PENDING
        
    def get_total_resources(self) -> Dict:
        """计算任务组所需的总资源"""
        total_resources = {"cpu": 0, "memory": 0}
        for task in self.tasks:
            total_resources["cpu"] += task.resources.get("cpu", 0)
            total_resources["memory"] += task.resources.get("memory", 0)
        return total_resources

class Job:
    def __init__(self, id: str, task_groups: List[Dict], constraints: Dict):
        self.id = id
        self.task_groups = [
            TaskGroup(
                name=group["name"],
                tasks=[
                    Task(
                        name=task["name"],
                        resources=task["resources"],
                        config=task.get("config", {})
                    ) for task in group["tasks"]
                ]
            ) for group in task_groups
        ]
        self.constraints = constraints
        self.status = JobStatus.PENDING

class Allocation:
    def __init__(self, id: str, job_id: str, node_id: str, task_group: TaskGroup):
        self.id = id
        self.job_id = job_id
        self.node_id = node_id
        self.task_group = task_group
        self.status = AllocationStatus.PENDING 