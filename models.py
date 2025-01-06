from typing import List, Dict
from enum import Enum

class EvaluationStatus(Enum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"

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
        self.status = JobStatus.PENDING

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
        self.status = JobStatus.PENDING 