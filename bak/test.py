from typing import List, Dict, Optional
from enum import Enum
import uuid
import threading
import time
import queue

class EvaluationStatus(Enum):
    PENDING = "pending"
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

class Node:
    def __init__(self, id: str, resources: Dict, healthy: bool, region: str):
        self.id = id
        self.resources = resources  # e.g., {"cpu": 1000, "memory": 4096}
        self.healthy = healthy
        self.region = region

class Allocation:
    def __init__(self, id: str, job_id: str, node_id: str, task_group: str):
        self.id = id
        self.job_id = job_id
        self.node_id = node_id
        self.task_group = task_group

class Evaluation:
    def __init__(self, id: str, trigger_event: TriggerEvent, job: Job, nodes: List[Node], allocations: List[Allocation]):
        self.id = id
        self.status = EvaluationStatus.PENDING
        self.trigger_event = trigger_event
        self.job = job
        self.nodes = nodes
        self.allocations = allocations
        self.plan = []

    def process(self):
        """处理评估，生成分配计划"""
        print(f"Processing evaluation {self.id} for job {self.job.id}")
        for task_group in self.job.task_groups:
            feasible_nodes = self.feasibility_check(task_group)
            ranked_nodes = self.rank_nodes(feasible_nodes)
            self.generate_plan(task_group, ranked_nodes)
        self.submit_plan()
        self.status = EvaluationStatus.COMPLETE
        print(f"Evaluation {self.id} completed with plan: {self.plan}")

    def feasibility_check(self, task_group: Dict) -> List[Node]:
        """检查节点的可行性"""
        feasible_nodes = []
        for node in self.nodes:
            if not node.healthy:
                continue
            if node.region != self.job.constraints.get("region"):
                continue
            if node.resources["cpu"] < task_group.get("cpu", 0):
                continue
            if node.resources["memory"] < task_group.get("memory", 0):
                continue
            feasible_nodes.append(node)
        print(f"Feasible nodes for task group {task_group['name']}: {[node.id for node in feasible_nodes]}")
        return feasible_nodes

    def rank_nodes(self, nodes: List[Node]) -> List[Node]:
        """对符合条件的节点进行排名（基于资源利用率）"""
        # 简单的排名逻辑：选择剩余资源最少的节点（装箱算法）
        ranked_nodes = sorted(nodes, key=lambda node: (node.resources["cpu"], node.resources["memory"]))
        return ranked_nodes

    def generate_plan(self, task_group: Dict, nodes: List[Node]):
        """生成分配计划"""
        if not nodes:
            print(f"No feasible nodes found for task group {task_group['name']}")
            self.status = EvaluationStatus.FAILED
            return

        selected_node = nodes[0]  # 选择排名最高的节点
        allocation = Allocation(
            id=f"alloc-{self.job.id}-{task_group['name']}-{selected_node.id}",
            job_id=self.job.id,
            node_id=selected_node.id,
            task_group=task_group["name"]
        )
        self.plan.append(allocation)
        print(f"Generated plan for task group {task_group['name']}: {allocation.id} on node {selected_node.id}")

    def submit_plan(self):
        """提交分配计划"""
        # 这里可以模拟将计划提交到 Nomad 的 Leader 服务器
        print(f"Submitting plan for evaluation {self.id}: {self.plan}")

class Scheduler:
    def __init__(self, leader):
        self.leader = leader

    def process_evaluation(self, evaluation: Evaluation):
        """处理评估并提交计划到 Leader"""
        evaluation.process()
        self.leader.submit_plan(evaluation.plan)

class Leader:
    def __init__(self):
        self.evaluation_queue = queue.Queue()  # 评估队列
        self.plan_queue = queue.Queue()       # 计划队列
        self.scheduler = Scheduler(self)      # 调度器
        self.allocations = []                 # 已创建的分配

    def enqueue_evaluation(self, evaluation: Evaluation):
        """将评估加入队列"""
        self.evaluation_queue.put(evaluation)
        print(f"Enqueued evaluation {evaluation.id}")

    def submit_plan(self, plan: List[Allocation]):
        """将计划加入队列"""
        self.plan_queue.put(plan)
        print(f"Enqueued plan: {[alloc.id for alloc in plan]}")

    def process_evaluations(self):
        """处理评估队列中的评估"""
        while True:
            if not self.evaluation_queue.empty():
                evaluation = self.evaluation_queue.get()
                print(f"Processing evaluation {evaluation.id}")
                self.scheduler.process_evaluation(evaluation)
            time.sleep(1)  # 模拟处理间隔

    def process_plans(self):
        """处理计划队列中的计划"""
        while True:
            if not self.plan_queue.empty():
                plan = self.plan_queue.get()
                print(f"Executing plan: {[alloc.id for alloc in plan]}")
                for allocation in plan:
                    self.allocations.append(allocation)
                    print(f"Created allocation {allocation.id} on node {allocation.node_id}")
            time.sleep(1)  # 模拟处理间隔

# 示例使用
if __name__ == "__main__":
    # 创建 Leader 服务器
    leader = Leader()

    # 启动评估处理线程
    eval_thread = threading.Thread(target=leader.process_evaluations, daemon=True)
    eval_thread.start()

    # 启动计划处理线程
    plan_thread = threading.Thread(target=leader.process_plans, daemon=True)
    plan_thread.start()

    # 添加节点
    nodes = [
        Node(id="node-1", resources={"cpu": 1000, "memory": 4096}, healthy=True, region="us-west"),
        Node(id="node-2", resources={"cpu": 2000, "memory": 8192}, healthy=True, region="us-west")
    ]

    # 提交作业
    job = Job(
        id="job-1",
        task_groups=[
            {"name": "web", "cpu": 500, "memory": 1024},
            {"name": "database", "cpu": 1000, "memory": 2048}
        ],
        constraints={"region": "us-west"}
    )
    evaluation = Evaluation(
        id=str(uuid.uuid4()),
        trigger_event=TriggerEvent.JOB_SUBMIT,
        job=job,
        nodes=nodes,
        allocations=[]
    )
    leader.enqueue_evaluation(evaluation)

    # 保持主线程运行
    while True:
        time.sleep(1)