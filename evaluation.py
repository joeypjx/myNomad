from typing import List, Dict
import json
import uuid
from models import EvaluationStatus, Job, Allocation, TriggerEvent

class Evaluation:
    def __init__(self, id: str, trigger_event: TriggerEvent, job: Job, nodes: List[Dict]):
        self.id = id
        self.status = EvaluationStatus.PENDING
        self.trigger_event = trigger_event
        self.job = job
        self.nodes = nodes
        self.plan = []
        print(f"[Evaluation] 创建新评估 {id} 用于作业 {job.id}")

    def process(self, node_manager):
        """处理评估，生成分配计划"""
        print(f"\n[Evaluation] 开始处理评估 {self.id}")
        print(f"[Evaluation] 作业 {self.job.id} 包含 {len(self.job.task_groups)} 个任务组")
        
        for task_group in self.job.task_groups:
            print(f"\n[Evaluation] 处理任务组: {task_group['name']}")
            print(f"[Evaluation] 资源需求: CPU {task_group.get('cpu', 0)}, 内存 {task_group.get('memory', 0)}MB")
            
            feasible_nodes = self.feasibility_check(task_group)
            if not feasible_nodes:
                print(f"[Evaluation] 没有找到适合任务组 {task_group['name']} 的节点")
                self.status = EvaluationStatus.FAILED
                return False
                
            print(f"[Evaluation] 找到 {len(feasible_nodes)} 个可用节点")
            ranked_nodes = self.rank_nodes(feasible_nodes)
            print("[Evaluation] 节点排序完成")
            
            self.generate_plan(task_group, ranked_nodes)
        
        if not self.plan:
            print("[Evaluation] 无法生成分配计划")
            self.status = EvaluationStatus.FAILED
            return False
            
        self.status = EvaluationStatus.COMPLETE
        print(f"[Evaluation] 评估完成，生成了 {len(self.plan)} 个分配计划")
        return True

    def feasibility_check(self, task_group: Dict) -> List[Dict]:
        """检查节点的可行性"""
        feasible_nodes = []
        print(f"[Evaluation] 开始节点可行性检查，共有 {len(self.nodes)} 个节点待检查")
        
        for node in self.nodes:
            if not node["healthy"]:
                print(f"[Evaluation] 节点 {node['node_id']} 不健康，跳过")
                continue
                
            if node["region"] != self.job.constraints.get("region"):
                print(f"[Evaluation] 节点 {node['node_id']} 区域不匹配，要求: {self.job.constraints.get('region')}, 实际: {node['region']}")
                continue
            
            resources = json.loads(node["resources"])
            if resources["cpu"] < task_group.get("cpu", 0):
                print(f"[Evaluation] 节点 {node['node_id']} CPU不足，要求: {task_group.get('cpu', 0)}, 可用: {resources['cpu']}")
                continue
                
            if resources["memory"] < task_group.get("memory", 0):
                print(f"[Evaluation] 节点 {node['node_id']} 内存不足，要求: {task_group.get('memory', 0)}, 可用: {resources['memory']}")
                continue
            
            print(f"[Evaluation] 节点 {node['node_id']} 满足要求")
            feasible_nodes.append(node)
            
        return feasible_nodes

    def rank_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """对符合条件的节点进行排名"""
        def get_score(node):
            resources = json.loads(node["resources"])
            return (resources["cpu"], resources["memory"])
        
        return sorted(nodes, key=get_score, reverse=True)

    def generate_plan(self, task_group: Dict, nodes: List[Dict]):
        """生成分配计划"""
        if not nodes:
            return
        
        selected_node = nodes[0]
        allocation = Allocation(
            id=str(uuid.uuid4()),
            job_id=self.job.id,
            node_id=selected_node["node_id"],
            task_group=task_group["name"]
        )
        self.plan.append(allocation) 