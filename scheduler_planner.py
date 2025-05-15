from typing import List, Dict, Optional, Set
import json
import uuid
from models import EvaluationStatus, Job, Allocation, TriggerEvent, TaskGroup

class SchedulerPlanner:
    def __init__(self, id: str, trigger_event: TriggerEvent, job: Job, nodes: List[Dict], existing_job: Optional[Dict] = None):
        self.id = id
        self.status = EvaluationStatus.PENDING
        self.trigger_event = trigger_event
        self.job = job
        # Store original nodes, but we'll use a mutable copy with parsed resources in process
        self.original_nodes_snapshot = nodes
        self.existing_job = existing_job
        self.plan: List[Allocation] = []  # 要创建的新分配
        self.allocations_to_delete: List[str] = []  # 要删除的分配ID
        self.nodes_in_evaluation: List[Dict] = [] # Will hold nodes with mutable, parsed resources
        print(f"[SchedulerPlanner] 创建评估 {id} 用于作业 {job.id}")

    
    def process(self, node_manager) -> Dict:
        """处理评估，生成分配计划。返回完整决策结果而不执行操作。"""
        print(f"\n[SchedulerPlanner] 开始处理评估 {self.id}")
        self._prepare_nodes_for_evaluation() # Initialize self.nodes_in_evaluation

        # 快速检查是否有健康节点
        healthy_nodes = [n for n in self.nodes_in_evaluation if n.get("healthy", False)]
        if not healthy_nodes and self.job.task_groups:
            print(f"[SchedulerPlanner] 评估失败：没有可用的健康节点，但作业需要 {len(self.job.task_groups)} 个任务组。")
            self.status = EvaluationStatus.FAILED
            return {"success": False, "plan": self.plan, "allocations_to_delete": self.allocations_to_delete}

        changes_made_to_allocations = False
        planned_or_kept_task_groups: Set[str] = set()

        # Get existing allocations for the job
        # This is a snapshot. We'll use a mutable copy for tracking.
        initial_existing_allocations_list = node_manager.get_job_allocations(self.job.id)
        # Make existing_allocations_by_group mutable for internal tracking during this evaluation
        existing_allocations_by_group_mutable: Dict[str, Dict] = {
            alloc["task_group"]: alloc for alloc in initial_existing_allocations_list
        }

        print(f"[SchedulerPlanner] 作业 {self.job.id} 包含 {len(self.job.task_groups)} 个任务组")
        print(f"[SchedulerPlanner] 作业的现有分配 (本次评估前)：{json.dumps(initial_existing_allocations_list, indent=2)}")

        # 处理每个任务组
        for task_group in self.job.task_groups:
            print(f"\n[SchedulerPlanner] 处理任务组：{task_group.name}")
            
            # 初始默认为需要创建新分配
            allocation_was_kept = False
            existing_allocation_details = existing_allocations_by_group_mutable.get(task_group.name)
            
            # 1. 首先尝试保留现有分配 (如果存在且是更新操作)
            if existing_allocation_details and self.trigger_event == TriggerEvent.JOB_UPDATE and self.existing_job:
                print(f"[SchedulerPlanner] 发现任务组 {task_group.name} 的现有分配：{existing_allocation_details['allocation_id']}")
                
                # 1.1 获取现有分配所在的节点信息
                current_node_id = existing_allocation_details["node_id"]
                node_info_from_eval_snapshot = next((n for n in self.nodes_in_evaluation if n["node_id"] == current_node_id), None)
                
                # 1.2 获取任务组的旧配置
                existing_task_group_def = None
                for group_def in self.existing_job.get("task_groups", []):
                    if group_def.get("name") == task_group.name:
                        existing_task_group_def = group_def
                        break
                
                # 1.3 检查任务组配置是否变化
                can_keep_allocation = False
                if existing_task_group_def:
                    # 将当前任务组转换为可比较格式
                    new_tasks_def = [{"name": t.name, "resources": t.resources, "config": t.config} for t in task_group.tasks]
                    tasks_changed = self._check_tasks_changed(existing_task_group_def["tasks"], new_tasks_def)
                    
                    # 如果任务配置未变更，且现有节点仍满足要求，可以保留分配
                    if not tasks_changed and node_info_from_eval_snapshot and self.check_node_feasibility(node_info_from_eval_snapshot, task_group, use_parsed_resources=True):
                        can_keep_allocation = True
                
                # 1.4 根据检查结果决定保留还是重新分配
                if can_keep_allocation:
                    # 保留现有分配
                    print(f"[SchedulerPlanner] 任务组 {task_group.name} 在节点 {current_node_id} 上的现有分配保持不变。")
                    planned_or_kept_task_groups.add(task_group.name)
                    allocation_was_kept = True
                    
                    # 为保留的分配预留资源
                    node_to_update_resources = next((n for n in self.nodes_in_evaluation if n["node_id"] == current_node_id), None)
                    if node_to_update_resources:
                        # 使用集中方法更新资源 - 不创建新分配
                        self._generate_plan_and_update_resources(task_group, node_to_update_resources, create_allocation=False)
                    else:
                        print(f"[SchedulerPlanner] 警告：在 self.nodes_in_evaluation 中未找到节点 {current_node_id} 以更新保留分配的资源。")
                else:
                    # 无法保留，需要删除旧分配
                    if not existing_task_group_def or tasks_changed:
                        print(f"[SchedulerPlanner] 任务组 {task_group.name} 的任务配置已更改。")
                    else:
                        print(f"[SchedulerPlanner] 现有节点 {current_node_id} 不再适用于任务组 {task_group.name}。")
                        
                    print(f"[SchedulerPlanner] 任务组 {task_group.name} 需要重新规划。将删除旧分配：{existing_allocation_details['allocation_id']}")
                    # 添加到待删除列表而非直接删除
                    self.allocations_to_delete.append(existing_allocation_details["allocation_id"])
                    changes_made_to_allocations = True
                    # 从跟踪字典中移除，防止后续重复处理
                    del existing_allocations_by_group_mutable[task_group.name]
            
            # 2. 如果无法保留现有分配，为任务组创建新的分配
            if not allocation_was_kept:
                # 2.1 寻找符合条件的节点
                feasible_nodes = self.feasibility_check(task_group, use_parsed_resources=True)
                if not feasible_nodes:
                    print(f"[SchedulerPlanner] 未找到适用于任务组 {task_group.name} 的节点。")
                    # 继续处理下一个任务组，最终评估结果由总体覆盖情况决定
                    continue
                
                # 2.2 根据策略对节点排序
                ranked_nodes = self.rank_nodes(feasible_nodes, use_parsed_resources=True)
                selected_node = ranked_nodes[0]
                
                # 2.3 创建分配并更新资源
                self._generate_plan_and_update_resources(task_group, selected_node)
                planned_or_kept_task_groups.add(task_group.name)
                changes_made_to_allocations = True

        # 处理删除的任务组
        self._cleanup_removed_task_groups(node_manager, existing_allocations_by_group_mutable, changes_made_to_allocations)

        # 返回最终评估结果
        success = self._determine_evaluation_result(planned_or_kept_task_groups, changes_made_to_allocations)
        
        return {
            "success": success,
            "plan": self.plan,
            "allocations_to_delete": self.allocations_to_delete
        }

    def _prepare_nodes_for_evaluation(self):
        """创建节点的深拷贝并解析其资源以供内部使用。"""
        self.nodes_in_evaluation = []
        for node_data in self.original_nodes_snapshot:
            # Create a copy to avoid modifying the original snapshot list/dicts
            copied_node_data = json.loads(json.dumps(node_data))
            try:
                # Parse resources string into a dictionary
                copied_node_data['resources'] = json.loads(copied_node_data['resources'])
            except (TypeError, json.JSONDecodeError):
                # If resources are already a dict (e.g., during tests or if format changes)
                # or if it's malformed, ensure it's a dict.
                if not isinstance(copied_node_data.get('resources'), dict):
                    print(f"[SchedulerPlanner] 警告：节点 {copied_node_data.get('node_id')} 的资源格式错误或非JSON字符串。将使用零资源默认值。")
                    copied_node_data['resources'] = {"cpu": 0, "memory": 0}
            self.nodes_in_evaluation.append(copied_node_data)

    def _update_node_resources(self, node: Dict, resources_to_deduct: Dict):
        """从节点中扣减资源（集中资源扣减逻辑）"""
        # 确保资源字段存在并使用默认值0防止KeyError
        node['resources']['cpu'] = node['resources'].get('cpu', 0) - resources_to_deduct.get('cpu', 0)
        node['resources']['memory'] = node['resources'].get('memory', 0) - resources_to_deduct.get('memory', 0)
        return node['resources']

    def _generate_plan_and_update_resources(self, task_group: TaskGroup, selected_node: Dict, create_allocation: bool = True):
        """
        生成分配计划并更新节点资源。
        
        Args:
            task_group: 要分配的任务组
            selected_node: 选中的节点
            create_allocation: 是否创建新的分配对象（True表示创建新分配，False表示仅扣减资源）
        
        Returns:
            Allocation对象或None（如果不创建新分配）
        """
        # 获取任务组所需资源
        tg_resources = task_group.get_total_resources()
        
        # 创建分配对象 (如果需要)
        allocation = None
        if create_allocation:
            allocation = Allocation(
                id=str(uuid.uuid4()),
                job_id=self.job.id,
                node_id=selected_node["node_id"],
                task_group=task_group
            )
            self.plan.append(allocation)
            print(f"[SchedulerPlanner] 计划分配 {allocation.id} 给节点 {selected_node['node_id']}。")
            
        # 扣减节点资源 (无论是新分配还是保留现有分配)
        remaining_resources = self._update_node_resources(selected_node, tg_resources)
        print(f"[SchedulerPlanner] {'为新分配' if create_allocation else '为保留的分配'}在节点 {selected_node['node_id']} 上预留资源。"
              f"剩余 (本次评估中)：CPU {remaining_resources['cpu']}, 内存 {remaining_resources['memory']}")
              
        return allocation

    def _check_tasks_changed(self, existing_tasks_def: List[Dict], new_tasks_def: List[Dict]) -> bool:
        if len(existing_tasks_def) != len(new_tasks_def):
            return True
        
        existing_map = {task["name"]: task for task in existing_tasks_def}
        new_map = {task["name"]: task for task in new_tasks_def}

        if set(existing_map.keys()) != set(new_map.keys()):
            return True

        for name, existing_task_conf in existing_map.items():
            new_task_conf = new_map[name]
            if existing_task_conf.get("resources") != new_task_conf.get("resources"):
                return True
            if existing_task_conf.get("config", {}) != new_task_conf.get("config", {}): # Compare config dicts
                return True
        return False

    def feasibility_check(self, task_group: TaskGroup, use_parsed_resources: bool = False) -> List[Dict]:
        """检查节点是否满足任务组要求"""
        target_nodes = self.nodes_in_evaluation if use_parsed_resources else self.original_nodes_snapshot
        
        feasible_nodes = []
        
        total_resources_needed = task_group.get_total_resources()
        
        for node in target_nodes:
            if not node.get("healthy", False): # Ensure healthy key exists
                continue
            
            # 检查任务组级别的约束条件
            constraints_satisfied = True
            for constraint in task_group.constraints:
                attribute = constraint.get("attribute")
                operator = constraint.get("operator")
                value = constraint.get("value")
                
                if not all([attribute, operator, value]):
                    continue
                    
                node_value = node.get(attribute)
                if node_value is None:
                    constraints_satisfied = False
                    break
                    
                # 根据操作符检查约束条件
                if operator == "=":
                    if str(node_value) != str(value):
                        constraints_satisfied = False
                        break
                elif operator == "!=":
                    if str(node_value) == str(value):
                        constraints_satisfied = False
                        break
                elif operator == ">":
                    if not (isinstance(node_value, (int, float)) and isinstance(value, (int, float)) and node_value > value):
                        constraints_satisfied = False
                        break
                elif operator == "<":
                    if not (isinstance(node_value, (int, float)) and isinstance(value, (int, float)) and node_value < value):
                        constraints_satisfied = False
                        break
                elif operator == "regex":
                    import re
                    if not re.search(str(value), str(node_value)):
                        constraints_satisfied = False
                        break
            
            if not constraints_satisfied:
                continue
            
            # 资源检查
            node_resources = node.get('resources', {"cpu":0, "memory":0}) # Already a dict if use_parsed_resources
            if not use_parsed_resources: # If using original snapshot, parse now
                try:
                    node_resources = json.loads(str(node_resources)) # Ensure it's a string first if it might be a dict
                except (TypeError, json.JSONDecodeError):
                    if not isinstance(node_resources, dict): # Check if already a dict
                         continue # Skip node if resources are malformed

            if node_resources.get("cpu", 0) < total_resources_needed.get("cpu", 0):
                continue
                
            if node_resources.get("memory", 0) < total_resources_needed.get("memory", 0):
                continue
            
            feasible_nodes.append(node)
            
        return feasible_nodes

    def rank_nodes(self, nodes: List[Dict], use_parsed_resources: bool = False) -> List[Dict]:
        """节点排序"""
        # Simple ranking: prefer nodes with more CPU, then more Memory (bin packing-like)
        # When use_parsed_resources is True, nodes' 'resources' are already dicts.
        def get_score(node):
            node_resources = node.get('resources', {"cpu":0, "memory":0})
            if not use_parsed_resources and isinstance(node_resources, str):
                 try:
                    node_resources = json.loads(node_resources)
                 except (TypeError, json.JSONDecodeError):
                    node_resources = {"cpu": 0, "memory": 0} # Default on error
            
            # Score higher for more available resources (reverse=True means higher score is better)
            # This is a simple bin-packing preference (fill up nodes with more resources first)
            return (node_resources.get("cpu", 0), node_resources.get("memory", 0))
        
        return sorted(nodes, key=get_score, reverse=True)

    def check_node_feasibility(self, node: Dict, task_group: TaskGroup, use_parsed_resources: bool = False) -> bool:
        """检查单个节点是否满足任务组要求"""
        if not node["healthy"]:
            return False
            
        # 如果已经使用解析过的资源，直接使用字典，不需再次解析
        if use_parsed_resources:
            resources = node["resources"]  # 已经是字典
        else:
            try:
                resources = json.loads(node["resources"])
            except (TypeError, json.JSONDecodeError):
                if isinstance(node["resources"], dict):
                    resources = node["resources"]  # 已经是字典
                else:
                    print(f"[SchedulerPlanner] 解析节点 {node.get('node_id')} 资源时出错")
                    return False
        
        total_resources = task_group.get_total_resources()
        
        if resources.get("cpu", 0) < total_resources.get("cpu", 0):
            return False
            
        if resources.get("memory", 0) < total_resources.get("memory", 0):
            return False
        
        return True 

    def _cleanup_removed_task_groups(self, node_manager, existing_allocations_by_group_mutable, changes_made_to_allocations) -> bool:
        """处理已删除任务组的分配"""
        if self.trigger_event != TriggerEvent.JOB_UPDATE:
            return changes_made_to_allocations  # 非更新操作无需清理
            
        print("\n[SchedulerPlanner] 检查是否有任务组被删除...")
        current_task_group_names_in_new_job = {tg.name for tg in self.job.task_groups}
        
        # Iterate over a copy of keys for safe deletion from the mutable dictionary
        for task_group_name_to_check in list(existing_allocations_by_group_mutable.keys()):
            if task_group_name_to_check not in current_task_group_names_in_new_job:
                alloc_details_to_delete = existing_allocations_by_group_mutable[task_group_name_to_check]
                allocation_id_to_delete = alloc_details_to_delete["allocation_id"]
                print(f"[SchedulerPlanner] 任务组 {task_group_name_to_check} 已从作业规范中删除。")
                print(f"[SchedulerPlanner] 将删除其现有分配：{allocation_id_to_delete}")
                # 添加到待删除列表而非直接删除
                self.allocations_to_delete.append(allocation_id_to_delete)
                changes_made_to_allocations = True
                del existing_allocations_by_group_mutable[task_group_name_to_check] # Clean from mutable dict
                
        return changes_made_to_allocations

    def _determine_evaluation_result(self, planned_or_kept_task_groups: Set[str], changes_made_to_allocations: bool) -> bool:
        """确定评估的最终结果并设置状态"""
        # 如果不是所有任务组都能被规划/保留，则评估失败
        if len(planned_or_kept_task_groups) < len(self.job.task_groups):
            print(f"[SchedulerPlanner] 评估失败：并非所有任务组 ({len(self.job.task_groups)}个) 都能被规划或保留 ({len(planned_or_kept_task_groups)}个已覆盖)。")
            self.status = EvaluationStatus.FAILED
            return False
            
        # 评估成功，设置相应状态并打印合适的消息
        self.status = EvaluationStatus.COMPLETE
        
        # 根据情况提供不同的成功消息
        if not self.plan and not changes_made_to_allocations and self.trigger_event == TriggerEvent.JOB_UPDATE:
            print(f"[SchedulerPlanner] 评估完成 (无变更)：计划为空，且未对分配进行任何更改。")
        elif not self.plan:
            print(f"[SchedulerPlanner] 评估完成：计划为空 (作业可能不包含任务组，或所有任务组都保留未更改)。")
        else:
            print(f"[SchedulerPlanner] 评估完成。生成了 {len(self.plan)} 个新的/更新的分配计划。")
            
        return True 