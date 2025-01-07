from typing import List, Dict, Optional
import json
import uuid
from models import EvaluationStatus, Job, Allocation, TriggerEvent, TaskGroup

class Evaluation:
    def __init__(self, id: str, trigger_event: TriggerEvent, job: Job, nodes: List[Dict], existing_job: Optional[Dict] = None):
        self.id = id
        self.status = EvaluationStatus.PENDING
        self.trigger_event = trigger_event
        self.job = job
        self.nodes = nodes
        self.existing_job = existing_job
        self.plan = []
        print(f"[Evaluation] 创建新评估 {id} 用于作业 {job.id}")

    def process(self, node_manager):
        """处理评估，生成分配计划"""
        print(f"\n[Evaluation] 开始处理评估 {self.id}")
        print(f"[Evaluation] 作业 {self.job.id} 包含 {len(self.job.task_groups)} 个任务组")
        
        # 如果是作业更新，获取现有分配
        existing_allocations = node_manager.get_job_allocations(self.job.id)
        existing_allocations_by_group = {
            alloc["task_group"]: alloc for alloc in existing_allocations
        }
        
        for task_group in self.job.task_groups:
            print(f"\n[Evaluation] 处理任务组: {task_group.name}")
            total_resources = task_group.get_total_resources()
            print(f"[Evaluation] 任务组总资源需求: CPU {total_resources['cpu']}, 内存 {total_resources['memory']}MB")
            print(f"[Evaluation] 包含 {len(task_group.tasks)} 个任务:")
            for task in task_group.tasks:
                print(f"  - {task.name}: CPU {task.resources['cpu']}, 内存 {task.resources['memory']}MB")
            
            # 检查是否存在现有分配
            existing_allocation = existing_allocations_by_group.get(task_group.name)
            if existing_allocation and self.existing_job:
                print(f"[Evaluation] 发现任务组 {task_group.name} 的现有分配: {existing_allocation['allocation_id']}")
                
                # 从现有作业信息中获取任务组配置
                existing_task_group = None
                for group in self.existing_job["task_groups"]:
                    if group["name"] == task_group.name:
                        existing_task_group = group
                        break
                
                if existing_task_group:
                    print("[Evaluation] 比较任务配置:")
                    print(f"现有任务: {json.dumps(existing_task_group['tasks'], indent=2)}")
                    new_tasks = [{"name": t.name, "resources": t.resources, "config": t.config} for t in task_group.tasks]
                    print(f"新任务: {json.dumps(new_tasks, indent=2)}")
                    
                    # 检查任务列表是否发生变化
                    tasks_changed = self._check_tasks_changed(
                        existing_task_group["tasks"],
                        new_tasks
                    )
                    
                    if tasks_changed:
                        print(f"[Evaluation] 任务组 {task_group.name} 的任务配置已变更，需要重新分配")
                        node_manager.delete_allocation(existing_allocation["allocation_id"])
                    else:
                        # 检查现有节点是否仍然满足要求
                        node_info = self.get_node_info(existing_allocation["node_id"])
                        if node_info and self.check_node_feasibility(node_info, task_group):
                            print(f"[Evaluation] 现有节点 {node_info['node_id']} 仍然满足要求，保持现有分配")
                            continue
                        else:
                            print(f"[Evaluation] 现有节点不再满足要求，需要重新分配")
                            node_manager.delete_allocation(existing_allocation["allocation_id"])
            
            # 为任务组寻找新的节点
            feasible_nodes = self.feasibility_check(task_group)
            if not feasible_nodes:
                print(f"[Evaluation] 没有找到适合任务组 {task_group.name} 的节点")
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

    def _check_tasks_changed(self, existing_tasks: List[Dict], new_tasks: List[Dict]) -> bool:
        """检查任务列表是否发生变化"""
        if len(existing_tasks) != len(new_tasks):
            return True
            
        # 将任务列表转换为字典，以任务名称为键
        existing_tasks_dict = {task["name"]: task for task in existing_tasks}
        new_tasks_dict = {task["name"]: task for task in new_tasks}
        
        # 检查任务名称是否相同
        if set(existing_tasks_dict.keys()) != set(new_tasks_dict.keys()):
            return True
            
        # 检查每个任务的配置是否相同
        for task_name, existing_task in existing_tasks_dict.items():
            new_task = new_tasks_dict[task_name]
            
            # 检查资源配置
            if existing_task["resources"] != new_task["resources"]:
                return True
                
            # 检查其他配置
            if existing_task.get("config", {}) != new_task.get("config", {}):
                return True
                
        return False

    def feasibility_check(self, task_group: TaskGroup) -> List[Dict]:
        """检查节点的可行性"""
        feasible_nodes = []
        print(f"[Evaluation] 开始节点可行性检查，共有 {len(self.nodes)} 个节点待检查")
        
        total_resources = task_group.get_total_resources()
        
        for node in self.nodes:
            if not node["healthy"]:
                print(f"[Evaluation] 节点 {node['node_id']} 不健康，跳过")
                continue
                
            if node["region"] != self.job.constraints.get("region"):
                print(f"[Evaluation] 节点 {node['node_id']} 区域不匹配，要求: {self.job.constraints.get('region')}, 实际: {node['region']}")
                continue
            
            resources = json.loads(node["resources"])
            if resources["cpu"] < total_resources["cpu"]:
                print(f"[Evaluation] 节点 {node['node_id']} CPU不足，要求: {total_resources['cpu']}, 可用: {resources['cpu']}")
                continue
                
            if resources["memory"] < total_resources["memory"]:
                print(f"[Evaluation] 节点 {node['node_id']} 内存不足，要求: {total_resources['memory']}, 可用: {resources['memory']}")
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

    def generate_plan(self, task_group: TaskGroup, nodes: List[Dict]):
        """生成分配计划"""
        if not nodes:
            return
        
        selected_node = nodes[0]
        allocation = Allocation(
            id=str(uuid.uuid4()),
            job_id=self.job.id,
            node_id=selected_node["node_id"],
            task_group=task_group
        )
        self.plan.append(allocation) 

    def get_node_info(self, node_id: str) -> Optional[Dict]:
        """从节点列表中获取节点信息"""
        for node in self.nodes:
            if node["node_id"] == node_id:
                return node
        return None

    def check_node_feasibility(self, node: Dict, task_group: TaskGroup) -> bool:
        """检查单个节点是否满足任务组要求"""
        if not node["healthy"]:
            return False
            
        if node["region"] != self.job.constraints.get("region"):
            return False
        
        resources = json.loads(node["resources"])
        total_resources = task_group.get_total_resources()
        
        if resources["cpu"] < total_resources["cpu"]:
            return False
            
        if resources["memory"] < total_resources["memory"]:
            return False
        
        return True 