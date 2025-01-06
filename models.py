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

class Job:
    def __init__(self, id: str, task_groups: List[Dict], constraints: Dict):
        self.id = id
        self.task_groups = task_groups
        self.constraints = constraints
        self.status = JobStatus.PENDING

class Allocation:
    def __init__(self, id: str, job_id: str, node_id: str, task_group: str):
        self.id = id
        self.job_id = job_id
        self.node_id = node_id
        self.task_group = task_group
        self.status = JobStatus.PENDING 