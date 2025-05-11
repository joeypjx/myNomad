
好的，这是一份针对您提供的软件的详细设计说明。此设计基于先前讨论的**简化版 CSC 架构**。

## 软件详细设计说明

### 1. 引言

本文档详细描述了分布式资源调度与管理系统的设计，包括将简化的计算机软件部件 (CSC) 分解为计算机软件单元 (CSU)，即类。对每个关键类的名称、属性、操作、动态和静态特性进行了说明。

### 2. CSC 分解为 CSU

基于简化后的 CSC 架构：

*   **CSC-A: Central Orchestration Service**
    *   CSU-A1: `ServerApplication` (主要对应 `server.py` 中的 Flask 应用和路由逻辑)
    *   CSU-A2: `Scheduler` (对应 `scheduler.py`)
    *   CSU-A3: `SchedulerPlanner` (对应 `scheduler_planner.py`)
    *   CSU-A4: `AllocationExecutor` (对应 `allocation_executor.py`)
    *   CSU-A5: `AgentCommunicator` (对应 `agent_communicator.py`)
*   **CSC-B: Node & Metadata Management Service**
    *   CSU-B1: `NodeManager` (对应 `node_manager.py`)
    *   CSU-B2: `NodeHealthMonitor` (在 `node_manager.py` 中定义的类)
*   **CSC-C: Node Agent Service**
    *   CSU-C1: `AgentApplication` (主要对应 `agent.py` 中的 Flask 应用和 NodeAgent 核心逻辑)
    *   CSU-C2: `Task` (在 `agent.py` 中定义的类，表示一个具体任务)
    *   CSU-C3: `TaskAllocation` (在 `agent.py` 中定义的类，表示Agent上的一个分配)
*   **CSL-1: Common Data Models** (对应 `models.py` 中的类和枚举)
    *   `Job`, `Task` (模型定义), `TaskGroup`, `Allocation` (模型定义)
    *   Enums: `EvaluationStatus`, `JobStatus`, `TaskStatus`, `TaskType`, `AllocationStatus`, `TriggerEvent`

### 3. CSC-A: Central Orchestration Service

#### 3.1. CSU-A1: `ServerApplication`

*   **类名**: `ServerApplication` (概念性，代表 `server.py` 模块中的 Flask 应用实例和路由函数)
*   **静态特性**:
    *   Utilizes Flask framework (`Flask`, `request`, `jsonify`, `CORS`).
    *   Aggregates instances of `NodeManager` (CSU-B1), `AllocationExecutor` (CSU-A4), `Scheduler` (CSU-A2).
    *   Interacts with CSL-1 data models for request/response structures.
*   **动态特性**:
    *   A Flask `app` object is instantiated at startup.
    *   Service instances (`NodeManager`, `AllocationExecutor`, `Scheduler`) are initialized and passed to the Flask app context or used by route handlers.
    *   Listens for HTTP requests, routes them to specific handler functions based on URL patterns.
    *   Route handlers process requests, invoke backend services, and return HTTP responses.
*   **主要属性 (全局变量/app配置形式)**:
    *   `app`:
        *   类型: `Flask`
        *   描述: Flask 应用实例。
    *   `node_manager`:
        *   类型: `NodeManager` (CSU-B1)
        *   描述: 节点和元数据管理器实例。
    *   `allocation_executor`:
        *   类型: `AllocationExecutor` (CSU-A4)
        *   描述: 分配执行器实例。
    *   `scheduler`:
        *   类型: `Scheduler` (CSU-A2)
        *   描述: 调度器实例。
    *   `TEST_API_KEY`:
        *   类型: `str`
        *   描述: 用于 `/test/clear-all` 接口的 API 密钥。
        *   值域: 字符串。
        *   实际值: 从环境变量 `TEST_API_KEY` 读取，默认为 `'test_key_123'`。
*   **主要操作 (Flask 路由函数)**:

    *   `clear_all_data()`:
        *   输入参数: HTTP POST 请求，头部包含 `X-API-Key`.
        *   输出参数: JSON 响应 (成功消息或错误信息)。
        *   处理过程:
            1.  验证 `X-API-Key` 是否与 `TEST_API_KEY` 匹配。
            2.  若匹配，调用 `node_manager.clear_all_data()`。
            3.  返回操作结果。
        *   异常处理: API 密钥无效返回 401；`clear_all_data()` 失败返回 500。
    *   `register_node()`:
        *   输入参数: HTTP POST 请求，JSON body 包含 `node_id`, `region`, `resources`, `healthy`, `endpoint`.
        *   输出参数: JSON 响应 (成功消息或错误信息)。
        *   处理过程:
            1.  解析 JSON 数据。
            2.  验证必要字段是否存在。
            3.  调用 `node_manager.register_node(data)`。
            4.  若成功，调用 `allocation_executor.register_agent_endpoint(data["node_id"], data["endpoint"])`。
            5.  返回操作结果。
        *   异常处理: 数据无效返回 400；注册失败返回 500。
    *   `handle_heartbeat()`:
        *   输入参数: HTTP POST 请求，JSON body 包含 `node_id`, `resources`, `healthy`, `timestamp`, `allocations` (可选)。
        *   输出参数: JSON 响应。
        *   处理过程: 调用 `node_manager.update_heartbeat(data)`.
        *   异常处理: 数据无效返回 400；处理失败返回 500。
    *   `create_template()`, `list_templates()`, `get_template(template_id)`, `update_template(template_id)`, `delete_template(template_id)`:
        *   输入参数: 相应 HTTP 请求，包含 JSON body (创建/更新) 或路径参数 (`template_id`)。
        *   输出参数: JSON 响应。
        *   处理过程: 调用 `node_manager` 对应的模板管理方法。
        *   异常处理: 数据无效返回 400；模板不存在返回 404；操作失败返回 500。
    *   `submit_job()`:
        *   输入参数: HTTP POST 请求，JSON body 包含作业定义 (可含 `template_id`)。
        *   输出参数: JSON 响应 (含 `job_id`, `evaluation_id`)。
        *   处理过程:
            1.  解析作业数据，若含 `template_id` 则从 `node_manager` 获取模板并合并数据。
            2.  调用 `scheduler.create_evaluation(job_data)` 创建评估。
            3.  调用 `scheduler.enqueue_evaluation(evaluation)` 将评估入队。
            4.  返回评估ID和作业ID。
        *   异常处理: 数据无效返回 400；模板不存在返回 404；评估创建失败返回 500。
    *   `update_job(job_id)`:
        *   输入参数: HTTP PUT 请求，路径参数 `job_id`，JSON body 含更新数据。
        *   输出参数: JSON 响应。
        *   处理过程:
            1.  验证作业是否存在 (`node_manager.get_job`)。
            2.  调用 `scheduler.create_evaluation(data, job_id=job_id)`。
            3.  调用 `scheduler.enqueue_evaluation(evaluation)`。
        *   异常处理: 作业不存在 404；数据无效/评估创建失败 400/500。
    *   `stop_job(job_id)`:
        *   输入参数: HTTP DELETE 请求，路径参数 `job_id`。
        *   输出参数: JSON 响应。
        *   处理过程: 调用 `allocation_executor.stop_job(job_id)`。
        *   异常处理: 作业不存在 404；停止失败 500。
    *   `delete_job(job_id)` (`/jobs/<job_id>/delete`, POST):
        *   输入参数: HTTP POST 请求，路径参数 `job_id`。
        *   输出参数: JSON 响应。
        *   处理过程: 调用 `allocation_executor.delete_job(job_id)`。
        *   异常处理: 作业不存在 404；删除失败 500。
    *   `restart_job(job_id)`:
        *   输入参数: HTTP POST 请求，路径参数 `job_id`。
        *   输出参数: JSON 响应。
        *   处理过程:
            1.  获取作业信息 (`node_manager.get_job`)，验证状态是否为 "dead"。
            2.  基于原作业配置调用 `scheduler.create_evaluation` 和 `enqueue_evaluation`。
        *   异常处理: 作业不存在 404；状态不符 400；评估创建失败 400/500。
    *   `get_jobs()`, `get_job_info(job_id)`, `get_all_nodes()`:
        *   输入参数: 相应 HTTP GET 请求。
        *   输出参数: JSON 响应。
        *   处理过程: 调用 `node_manager` 对应的数据查询方法。
        *   异常处理: 查询失败 500；作业/节点不存在 404 (get_job_info)。

#### 3.2. CSU-A2: `Scheduler`

*   **类名**: `Scheduler`
*   **静态特性**:
    *   Aggregates `NodeManager` (CSU-B1).
    *   Holds a reference to `AllocationExecutor` (CSU-A4) (set via `set_executor`).
    *   Creates instances of `SchedulerPlanner` (CSU-A3).
    *   Uses `queue.Queue` for `evaluation_queue`.
    *   Uses CSL-1 models (`Job`, `TriggerEvent`).
*   **动态特性**:
    *   Instantiated once by `ServerApplication`.
    *   A background scheduling thread (`_scheduling_loop`) runs continuously.
    *   `create_evaluation` is called by API handlers to initiate scheduling for new/updated jobs.
    *   `enqueue_evaluation` adds `SchedulerPlanner` instances to an internal queue.
    *   The background thread dequeues evaluations and calls `process_evaluation`.
*   **属性**:
    *   `node_manager`:
        *   类型: `NodeManager` (CSU-B1)
        *   描述: 节点和元数据管理器实例。
    *   `allocation_executor`:
        *   类型: `Optional[AllocationExecutor]` (CSU-A4)
        *   描述: 分配执行器实例，通过 `set_executor` 注入。
    *   `evaluation_queue`:
        *   类型: `queue.Queue`
        *   描述: 存储待处理的 `SchedulerPlanner` 实例。
    *   `scheduling_thread`:
        *   类型: `threading.Thread`
        *   描述: 执行 `_scheduling_loop` 的后台线程。
*   **操作**:
    *   `__init__(self, node_manager: NodeManager)`:
        *   输入参数: `node_manager` (CSU-B1)。
        *   输出参数: None.
        *   处理过程: 初始化属性，启动 `scheduling_thread`。
        *   异常处理: 无特定应用级异常处理，依赖 Python 运行时。
    *   `set_executor(self, allocation_executor: AllocationExecutor)`:
        *   输入参数: `allocation_executor` (CSU-A4)。
        *   输出参数: None.
        *   处理过程: 设置 `self.allocation_executor` 引用。
    *   `create_evaluation(self, job_data: Dict, job_id: str = None) -> Optional[SchedulerPlanner]`:
        *   输入参数: `job_data` (dict, 作业定义), `job_id` (str, 可选, 用于更新)。
        *   输出参数: `SchedulerPlanner` 实例或 `None`。
        *   处理过程:
            1.  若 `job_id` 提供，则为更新操作；否则为新作业，生成新 `job_id`。
            2.  使用 `job_data` 和 `job_id` 创建 `Job` 对象 (CSL-1)。
            3.  通过 `node_manager.submit_job()` 持久化作业基础信息 (状态为 PENDING 或保留现有)。
            4.  通过 `node_manager.get_healthy_nodes()` 获取可用节点。
            5.  若无健康节点，返回 `None`。
            6.  实例化 `SchedulerPlanner` (CSU-A3) 并返回。
        *   异常处理: 若 `node_manager` 调用失败或无健康节点，可能返回 `None`。打印错误日志。
    *   `enqueue_evaluation(self, evaluation: SchedulerPlanner)`:
        *   输入参数: `evaluation` (CSU-A3)。
        *   输出参数: None.
        *   处理过程: 将 `evaluation` 对象放入 `self.evaluation_queue`。
    *   `process_evaluation(self, evaluation: SchedulerPlanner)`:
        *   输入参数: `evaluation` (CSU-A3)。
        *   输出参数: None.
        *   处理过程:
            1.  检查 `allocation_executor` 是否已设置。
            2.  调用 `evaluation.process(self.node_manager)` 获取调度决策 (`plan`, `allocations_to_delete`)。
            3.  若评估成功，调用 `self.allocation_executor.submit_plan(plan, allocations_to_delete)`。
        *   异常处理: 若 `allocation_executor` 未设置或 `evaluation.process` 抛出异常，打印错误日志。评估状态在 `_scheduling_loop` 中更新。
    *   `_scheduling_loop(self)`:
        *   输入参数: None.
        *   输出参数: None (无限循环)。
        *   处理过程:
            1.  循环等待 `evaluation_queue` 非空。
            2.  取出 `SchedulerPlanner` 实例。
            3.  调用 `self.process_evaluation()` 处理。
            4.  根据处理结果更新 `evaluation.status`。
            5.  `time.sleep(1)`。
        *   异常处理: 捕获 `process_evaluation` 中可能发生的异常，记录错误，将评估状态设为 `FAILED`。

#### 3.3. CSU-A3: `SchedulerPlanner`

*   **类名**: `SchedulerPlanner`
*   **静态特性**:
    *   Interacts with `NodeManager` (CSU-B1) to fetch existing allocation data.
    *   Uses CSL-1 models (`EvaluationStatus`, `Job`, `Allocation`, `TriggerEvent`, `TaskGroup`).
*   **动态特性**:
    *   Instantiated by `Scheduler` (CSU-A2) for each scheduling event.
    *   `process()` method contains the core planning logic and is called once per instance.
    *   Lifecycle is short, tied to a single evaluation.
*   **属性**:
    *   `id`:
        *   类型: `str`
        *   描述: 评估的唯一标识符 (UUID)。
    *   `status`:
        *   类型: `EvaluationStatus` (Enum from CSL-1)
        *   描述: 评估的当前状态。
        *   值域: `PENDING`, `COMPLETE`, `FAILED`.
    *   `trigger_event`:
        *   类型: `TriggerEvent` (Enum from CSL-1)
        *   描述: 触发此次评估的事件类型。
    *   `job`:
        *   类型: `Job` (CSL-1)
        *   描述: 当前正在评估的作业对象。
    *   `original_nodes_snapshot`:
        *   类型: `List[Dict]`
        *   描述: 评估开始时健康节点的快照 (原始数据)。
    *   `existing_job`:
        *   类型: `Optional[Dict]`
        *   描述: 如果是作业更新，则为现有作业的数据。
    *   `plan`:
        *   类型: `List[Allocation]` (CSL-1)
        *   描述: 计划创建的新分配列表。
    *   `allocations_to_delete`:
        *   类型: `List[str]`
        *   描述: 计划删除的旧分配ID列表。
    *   `nodes_in_evaluation`:
        *   类型: `List[Dict]`
        *   描述: 节点快照的内部可变副本，资源已解析为字典并会在规划中扣减。
*   **操作**:
    *   `__init__(self, id: str, trigger_event: TriggerEvent, job: Job, nodes: List[Dict], existing_job: Optional[Dict] = None)`:
        *   输入参数: 参见属性描述。
        *   输出参数: None.
        *   处理过程: 初始化所有属性。
    *   `process(self, node_manager: NodeManager) -> Dict`:
        *   输入参数: `node_manager` (CSU-B1)。
        *   输出参数: `Dict` 包含 `{"success": bool, "plan": List[Allocation], "allocations_to_delete": List[str]}`.
        *   处理过程:
            1.  调用 `_prepare_nodes_for_evaluation()` 初始化 `self.nodes_in_evaluation`。
            2.  检查是否有健康节点，若无且作业需要资源则评估失败。
            3.  从 `node_manager` 获取当前作业的现有分配 `initial_existing_allocations_list`。
            4.  遍历作业中的每个 `task_group`:
                a.  **尝试保留现有分配 (若为JOB_UPDATE)**:
                    i.  获取现有分配的节点信息和旧任务组定义。
                    ii. 调用 `_check_tasks_changed()` 比较新旧任务定义。
                    iii.调用 `check_node_feasibility()` 检查现有节点是否仍满足新（或未变）任务组需求。
                    iv. 若可保留，则调用 `_generate_plan_and_update_resources(create_allocation=False)` 仅扣减资源，将任务组加入 `planned_or_kept_task_groups`。
                    v.  若不可保留，将旧分配 ID 加入 `self.allocations_to_delete`。
                b.  **创建新分配 (若未保留)**:
                    i.  调用 `feasibility_check()` 找到所有符合条件的节点。
                    ii. 若无符合节点，跳过此任务组。
                    iii.调用 `rank_nodes()` 对可行节点排序。
                    iv. 选择最优节点。
                    v.  调用 `_generate_plan_and_update_resources(create_allocation=True)` 创建新 `Allocation` 对象，加入 `self.plan`，并更新选中节点的内部可用资源。将任务组加入 `planned_or_kept_task_groups`。
            5.  调用 `_cleanup_removed_task_groups()` 处理作业规范中已删除的任务组，将其分配加入 `allocations_to_delete`。
            6.  调用 `_determine_evaluation_result()` 根据是否所有任务组都被覆盖来决定最终成功/失败，并更新 `self.status`。
            7.  返回决策结果。
        *   异常处理: 内部逻辑错误会打印日志，最终通过 `_determine_evaluation_result` 反映为评估失败。
    *   `_prepare_nodes_for_evaluation(self)`: (私有辅助方法)
        *   处理过程: 深拷贝 `self.original_nodes_snapshot` 到 `self.nodes_in_evaluation`，并将节点资源（通常是JSON字符串）解析为字典。处理解析错误。
    *   `_update_node_resources(self, node: Dict, resources_to_deduct: Dict)`: (私有辅助方法)
        *   处理过程: 从 `node['resources']` (字典) 中扣减 `resources_to_deduct`。
    *   `_generate_plan_and_update_resources(self, task_group: TaskGroup, selected_node: Dict, create_allocation: bool = True)`: (私有辅助方法)
        *   处理过程: 若 `create_allocation` 为 True，创建新的 `Allocation` 对象并加入 `self.plan`。然后调用 `_update_node_resources` 扣减 `selected_node` 的资源。
    *   `_check_tasks_changed(self, existing_tasks_def: List[Dict], new_tasks_def: List[Dict]) -> bool`: (私有辅助方法)
        *   处理过程: 比较任务列表的长度、名称、资源和配置是否有变化。
    *   `feasibility_check(self, task_group: TaskGroup, use_parsed_resources: bool = False) -> List[Dict]`:
        *   处理过程: 遍历 `self.nodes_in_evaluation` (若 `use_parsed_resources` 为 True) 或 `self.original_nodes_snapshot`。对每个节点，检查其健康状况、是否满足作业的区域约束、是否有足够资源 (CPU, 内存) 来运行 `task_group`。返回所有满足条件的节点列表。
    *   `rank_nodes(self, nodes: List[Dict], use_parsed_resources: bool = False) -> List[Dict]`:
        *   处理过程: 对可行节点列表进行排序。当前策略是优先选择剩余 CPU 和内存较多的节点 (bin packing-like)。
    *   `check_node_feasibility(self, node: Dict, task_group: TaskGroup, use_parsed_resources: bool = False) -> bool`:
        *   处理过程: 检查单个节点是否满足指定任务组的健康、区域和资源需求。
    *   `_cleanup_removed_task_groups(self, node_manager, existing_allocations_by_group_mutable, changes_made_to_allocations) -> bool`: (私有辅助方法)
        *   处理过程: 比较新作业定义中的任务组与 `existing_allocations_by_group_mutable`。如果现有分配对应的任务组在新作业中不存在，则将其分配ID加入 `self.allocations_to_delete`。
    *   `_determine_evaluation_result(self, planned_or_kept_task_groups: Set[str], changes_made_to_allocations: bool) -> bool`: (私有辅助方法)
        *   处理过程: 如果 `planned_or_kept_task_groups` 集合的大小小于作业中任务组的总数，则评估失败。否则成功。更新 `self.status`。

#### 3.4. CSU-A4: `AllocationExecutor`

*   **类名**: `AllocationExecutor`
*   **静态特性**:
    *   Aggregates `NodeManager` (CSU-B1) and `AgentCommunicator` (CSU-A5).
    *   Uses `queue.Queue` for `plan_queue`.
    *   Uses CSL-1 models (`Allocation`, `AllocationStatus`).
*   **动态特性**:
    *   Instantiated once by `ServerApplication`.
    *   A background thread (`process_plans`) runs continuously.
    *   `submit_plan` is called by `Scheduler` (CSU-A2) to enqueue allocation decisions.
    *   API handlers in `ServerApplication` call `stop_job` or `delete_job`.
*   **属性**:
    *   `node_manager`:
        *   类型: `NodeManager` (CSU-B1)
    *   `agent_communicator`:
        *   类型: `AgentCommunicator` (CSU-A5)
    *   `plan_queue`:
        *   类型: `queue.Queue`
        *   描述: 存储待执行的分配计划 (包含创建和删除列表)。
    *   `is_running`:
        *   类型: `bool`
        *   描述: 控制 `process_plans` 线程的运行。
    *   `plan_thread`:
        *   类型: `threading.Thread`
        *   描述: 执行 `process_plans` 的后台线程。
*   **操作**:
    *   `__init__(self, node_manager: NodeManager)`:
        *   输入参数: `node_manager` (CSU-B1)。
        *   输出参数: None.
        *   处理过程: 初始化属性，创建 `AgentCommunicator` 实例，启动 `plan_thread`。
    *   `register_agent_endpoint(self, node_id: str, endpoint: str)`:
        *   输入参数: `node_id` (str), `endpoint` (str, Agent的URL)。
        *   输出参数: None.
        *   处理过程: 调用 `self.agent_communicator.register_agent(node_id, endpoint)`。
    *   `submit_plan(self, plan: List[Allocation], allocations_to_delete: List[str] = None)`:
        *   输入参数: `plan` (要创建的分配列表), `allocations_to_delete` (要删除的分配ID列表)。
        *   输出参数: None.
        *   处理过程: 将包含创建和删除指令的字典放入 `self.plan_queue`。
    *   `stop_allocation(self, allocation_id: str) -> bool`:
        *   输入参数: `allocation_id` (str)。
        *   输出参数: `bool` (操作是否成功)。
        *   处理过程:
            1.  调用 `self.node_manager.delete_allocation(allocation_id, notify_agent=True)` 获取节点ID并从数据库删除。
            2.  若成功且获取到 `node_id`，则调用 `self.agent_communicator.stop_allocation(node_id, allocation_id)` 通知Agent。
        *   异常处理: 记录错误，返回 `False` 如果任一步骤失败。
    *   `process_plans(self)`:
        *   输入参数: None.
        *   输出参数: None (无限循环)。
        *   处理过程:
            1.  循环等待 `plan_queue` 非空。
            2.  取出计划 (`{"create": [...], "delete": [...]}`)。
            3.  **处理删除**: 遍历 `allocations_to_delete`，为每个ID调用 `self.stop_allocation()`。
            4.  **处理创建**: 遍历 `allocations_to_create` (`Allocation` 对象):
                a.  设置 `allocation.status = AllocationStatus.RUNNING`。
                b.  调用 `self.agent_communicator.send_allocation(allocation)`。
                c.  若 Agent 通信成功，调用 `self.node_manager.update_allocation(allocation)` 更新数据库。
                d.  若 Agent 通信失败，设置 `allocation.status = AllocationStatus.FAILED` 并更新数据库。
            5.  `time.sleep(1)`。
        *   异常处理: 捕获通用异常，打印日志。
    *   `start(self)` & `stop(self)`: (控制服务生命周期，当前实现简单)
    *   `stop_job(self, job_id: str) -> bool`:
        *   输入参数: `job_id` (str)。
        *   输出参数: `bool` (操作是否成功)。
        *   处理过程:
            1.  调用 `self.node_manager.stop_job(job_id)` 获取需要停止的分配列表并将作业标记为 DEAD。
            2.  遍历返回的分配列表，对每个分配:
                a.  调用 `self.agent_communicator.stop_allocation(node_id, allocation_id)`。
                b.  调用 `self.node_manager.delete_allocation(allocation_id, notify_agent=False)` 从数据库删除。
        *   异常处理: 记录错误，返回 `False`。
    *   `delete_job(self, job_id: str) -> bool`:
        *   输入参数: `job_id` (str)。
        *   输出参数: `bool` (操作是否成功)。
        *   处理过程:
            1.  调用 `self.stop_job(job_id)` 确保所有任务已停止且分配记录已从Agent层面清理。
            2.  调用 `self.node_manager.clean_job_data(job_id)` 清理数据库中与该作业相关的所有剩余记录。
        *   异常处理: 记录错误，返回 `False`。

#### 3.5. CSU-A5: `AgentCommunicator`

*   **类名**: `AgentCommunicator`
*   **静态特性**:
    *   Uses `requests` library for HTTP communication.
    *   Uses CSL-1 models (`Allocation`).
*   **动态特性**:
    *   Instantiated by `AllocationExecutor` (CSU-A4).
    *   Methods are called by `AllocationExecutor` to interact with remote Node Agents.
*   **属性**:
    *   `agent_endpoints`:
        *   类型: `Dict[str, str]`
        *   描述: 存储节点ID到其Agent HTTP端点的映射。
        *   值域: Key为节点ID (str), Value为URL (str)。
*   **操作**:
    *   `__init__(self)`:
        *   处理过程: 初始化 `agent_endpoints` 为空字典。
    *   `register_agent(self, node_id: str, endpoint: str)`:
        *   输入参数: `node_id` (str), `endpoint` (str, Agent URL)。
        *   输出参数: None.
        *   处理过程: 将 `node_id: endpoint` 存入 `self.agent_endpoints`。
    *   `send_allocation(self, allocation: Allocation) -> Optional[Dict]`:
        *   输入参数: `allocation` (CSL-1)。
        *   输出参数: `Optional[Dict]` (Agent的JSON响应或None)。
        *   处理过程:
            1.  根据 `allocation.node_id` 查找Agent端点。
            2.  构造发送给Agent的JSON数据 (含`allocation_id`, `job_id`, `task_group`详情, `status`)。
            3.  使用 `requests.post()` 发送HTTP请求到Agent的 `/allocations` 端点。
            4.  返回Agent的JSON响应。
        *   异常处理: 若节点端点未注册或 `requests` 调用失败 (超时、连接错误等)，打印错误日志，返回 `None`。
    *   `stop_allocation(self, node_id: str, allocation_id: str) -> bool`:
        *   输入参数: `node_id` (str), `allocation_id` (str)。
        *   输出参数: `bool` (操作是否成功)。
        *   处理过程:
            1.  根据 `node_id` 查找Agent端点。
            2.  使用 `requests.delete()` 发送HTTP请求到Agent的 `/allocations/<allocation_id>` 端点。
            3.  检查响应状态码是否为 200。
        *   异常处理: 若节点端点未注册或 `requests` 调用失败，打印错误日志，返回 `False`。

### 4. CSC-B: Node & Metadata Management Service

#### 4.1. CSU-B1: `NodeManager`

*   **类名**: `NodeManager`
*   **静态特性**:
    *   Uses `sqlite3` library for database interaction.
    *   Uses `json` for serializing/deserializing complex data types stored in DB.
    *   Aggregates an instance of `NodeHealthMonitor` (CSU-B2).
    *   Uses CSL-1 models extensively.
*   **动态特性**:
    *   Instantiated once by `ServerApplication`.
    *   Provides methods for CRUD operations on nodes, jobs, allocations, templates.
    *   `NodeHealthMonitor` runs in a separate thread, interacting with the database through this class's connection or directly.
*   **属性**:
    *   `db_path`:
        *   类型: `str`
        *   描述: SQLite数据库文件路径。
        *   值域: 文件路径字符串。
        *   实际值: Defaults to `"nomad.db"`.
    *   `heartbeat_timeout`:
        *   类型: `int`
        *   描述: 节点心跳超时时间（秒）。
        *   量化单位: 秒。
        *   实际值: `15`.
    *   `health_monitor`:
        *   类型: `NodeHealthMonitor` (CSU-B2)
        *   描述: 节点健康监控器实例。
*   **操作**:
    *   `__init__(self, db_path: str = "nomad.db")`:
        *   处理过程: 初始化 `db_path`, `heartbeat_timeout`。调用 `setup_database()`。创建并启动 `NodeHealthMonitor` 实例。
    *   `setup_database(self)`:
        *   处理过程: 连接数据库，执行 `CREATE TABLE IF NOT EXISTS` 为 `nodes`, `jobs`, `allocations`, `task_status`, `job_templates` 表。
        *   异常处理: 捕获 `sqlite3.Error`，打印日志。
    *   `_get_db_conn(self)`: (Conceptual helper for brevity, actual code uses `sqlite3.connect(self.db_path)` in each method)
        *   处理过程: 返回一个到 `self.db_path` 的 `sqlite3.Connection`。
    *   `register_node(self, node_data: Dict) -> bool`:
        *   输入: `node_data` (dict, 包含 `node_id`, `region`, `resources` (JSON str), `healthy`, `endpoint` (endpoint not stored by NodeManager directly in DB in current code, but passed for AllocationExecutor))。
        *   输出: `bool` (成功/失败)。
        *   处理: `INSERT OR REPLACE` 到 `nodes` 表。`resources` 存储为JSON字符串。`last_heartbeat` 设为当前时间。
        *   异常处理: `sqlite3.Error`，打印日志，返回 `False`。
    *   `update_heartbeat(self, heartbeat_data: Dict) -> bool`:
        *   输入: `heartbeat_data` (dict, 含 `node_id`, `resources` (JSON str), `healthy`, `timestamp`, `allocations` (dict of allocation statuses))。
        *   输出: `bool`。
        *   处理:
            1.  `UPDATE nodes` 表的 `resources`, `healthy`, `last_heartbeat`。
            2.  若 `allocations` 存在，遍历更新 `allocations` 表的 `status`, `start_time`, `end_time`, `last_update`。
            3.  遍历 `allocations` 中的 `tasks`，`INSERT OR REPLACE` 到 `task_status` 表。
        *   异常处理: `sqlite3.Error`，打印日志，返回 `False`。
    *   `get_healthy_nodes(self) -> List[Dict]`:
        *   输出: 健康节点列表 (字典，`resources` 已解析为 dict)。
        *   处理: `SELECT * FROM nodes WHERE healthy = 1`。解析 `resources` JSON 字符串。
        *   异常处理: `sqlite3.Error`，打印日志，返回空列表。
    *   `get_job(self, job_id: str) -> Optional[Dict]`:
        *   输出: 作业信息字典或 `None` (`task_groups`, `constraints` 已解析)。
        *   处理: `SELECT * FROM jobs WHERE job_id = ?`。
    *   `get_job_allocations(self, job_id: str) -> List[Dict]`:
        *   输出: 作业的分配列表 (字典)。
        *   处理: `SELECT allocation_id, node_id, task_group, status FROM allocations WHERE job_id = ?`。
    *   `submit_job(self, job_data: Dict) -> Tuple[str, bool]`:
        *   输入: `job_data` (dict, 含 `task_groups`, `constraints`, 可选 `job_id`)。
        *   输出: `(job_id, is_update)`。
        *   处理:
            1.  若 `job_id` 提供，检查是否存在以确定 `is_update` 和 `current_status`。否则生成新 `job_id`，`current_status = JobStatus.PENDING`。
            2.  `INSERT OR REPLACE` 到 `jobs` 表。`task_groups` 和 `constraints` 存储为JSON字符串。状态使用 `status_to_use`。
    *   `update_allocation(self, allocation: Allocation) -> bool`:
        *   输入: `allocation` (CSL-1 对象)。
        *   输出: `bool`.
        *   处理: `INSERT OR REPLACE` 到 `allocations` 表。调用 `update_job_status(allocation.job_id)`。
    *   `delete_allocation(self, allocation_id: str, notify_agent: bool = True) -> Tuple[bool, Optional[str]]`:
        *   输入: `allocation_id`, `notify_agent` (指示是否需要返回node_id给调用者以通知agent)。
        *   输出: `(success, node_id_to_notify_if_needed)`。
        *   处理:
            1.  若 `notify_agent`，先 `SELECT node_id FROM allocations WHERE allocation_id = ?`。
            2.  `DELETE FROM allocations WHERE allocation_id = ?`。
    *   `stop_job(self, job_id: str) -> Tuple[bool, List[Dict]]`: (Marks job as DEAD, returns allocs to be stopped by Executor)
        *   输出: `(success, list_of_allocations_on_this_job)`。
        *   处理:
            1.  调用 `get_job_allocations(job_id)` 获取分配。
            2.  `UPDATE jobs SET status = ? WHERE job_id = ?` (status = `JobStatus.DEAD.value`)。
    *   `get_all_jobs(self) -> List[Dict]`: (Returns detailed job info including allocations and tasks)
    *   `get_all_nodes(self) -> Optional[List[Dict]]`: (Returns all nodes, resources parsed)
    *   `get_node_allocations(self, node_id: str) -> List[Dict]`: (Returns allocations on a specific node)
    *   `get_allocation_tasks(self, allocation_id: str) -> List[Dict]`: (Returns tasks for a specific allocation)
    *   `get_job_info(self, job_id: str) -> Optional[Dict]`: (Returns job details and its allocations)
    *   `update_job_status(self, job_id: str) -> bool`:
        *   处理:
            1.  获取作业所有分配 (`get_job_allocations`)。
            2.  统计各状态分配数量。
            3.  根据规则 (e.g., all lost -> LOST, any running -> RUNNING/DEGRADED, all pending -> PENDING/BLOCKED) 确定新的作业状态。
            4.  若状态改变，`UPDATE jobs SET status = ? WHERE job_id = ?`。
    *   `_has_sufficient_resources(self, job_id: str) -> bool`: (Helper for `update_job_status` to determine BLOCKED)
    *   `clean_job_data(self, job_id: str) -> bool`:
        *   处理:
            1.  获取作业相关的所有 `allocation_id`。
            2.  `DELETE FROM task_status WHERE allocation_id IN (...)`。
            3.  `DELETE FROM allocations WHERE job_id = ?`。
            4.  `DELETE FROM jobs WHERE job_id = ?`。
    *   `create_job_template(...)`, `get_job_template(...)`, `list_job_templates(...)`, `update_job_template(...)`, `delete_job_template(...)`: Standard CRUD for templates.
    *   `clear_all_data(self) -> bool`:
        *   处理: `DELETE FROM` `task_status`, `allocations`, `jobs`, `nodes`, `job_templates` (in order of dependency).

#### 4.2. CSU-B2: `NodeHealthMonitor`

*   **类名**: `NodeHealthMonitor`
*   **静态特性**:
    *   Uses `sqlite3` directly or via `NodeManager`'s connection for DB access.
    *   Interacts with `nodes`, `allocations`, `task_status`, `jobs` tables.
*   **动态特性**:
    *   Instantiated by `NodeManager` (CSU-B1).
    *   Runs its `_check_node_health` method in a separate daemon thread.
*   **属性**:
    *   `db_path`:
        *   类型: `str`
        *   描述: SQLite数据库文件路径 (passed from `NodeManager`).
    *   `heartbeat_timeout`:
        *   类型: `int`
        *   描述: 心跳超时阈值（秒） (passed from `NodeManager`).
    *   `is_running`:
        *   类型: `bool`
        *   描述: 控制监控线程的运行。
    *   `check_thread`:
        *   类型: `threading.Thread`
        *   描述: 执行 `_check_node_health` 的线程。
*   **操作**:
    *   `__init__(self, db_path: str, heartbeat_timeout: int = 15)`:
        *   处理过程: 初始化属性。
    *   `start(self)`:
        *   处理过程: 设置 `is_running = True`，创建并启动 `check_thread`。
    *   `stop(self)`:
        *   处理过程: 设置 `is_running = False` (线程是daemon，会随主程序退出)。
    *   `_check_node_health(self)`:
        *   输入参数: None.
        *   输出参数: None (无限循环).
        *   处理过程:
            1.  循环 (`while self.is_running`):
                a.  连接数据库 (`self.db_path`)。
                b.  计算超时时间点 (`time.time() - self.heartbeat_timeout`)。
                c.  `UPDATE nodes SET healthy = 0 WHERE last_heartbeat < ? AND healthy = 1`。
                d.  若有节点被标记为不健康:
                    i.  `SELECT` 不健康节点上状态不是 'complete', 'failed', 'lost', 'stopped' 的分配。
                    ii. 遍历这些 "丢失的" 分配:
                        - `UPDATE allocations SET status = 'lost', end_time = ? WHERE allocation_id = ?`。
                        - `UPDATE task_status SET status = 'lost', end_time = ? WHERE allocation_id = ? AND status NOT IN (...)`。
                        - 记录受影响的 `job_id`。
                    iii.遍历受影响的 `job_id`:
                        - 调用类似 `NodeManager.update_job_status` 的逻辑来重新评估并更新作业状态 (e.g., to 'lost' or 'degraded')。
                e.  提交事务，关闭连接。
                f.  `time.sleep(5)`。
        *   异常处理: 捕获 `sqlite3.Error` 或其他异常，打印日志。

### 5. CSC-C: Node Agent Service

#### 5.1. CSU-C1: `AgentApplication` (Conceptual, represents `NodeAgent` class in `agent.py`)

*   **类名**: `NodeAgent` (as defined in `agent.py`)
*   **静态特性**:
    *   Uses Flask for its API endpoint.
    *   Uses `requests` for communicating with the Central Orchestration Service (CSC-A).
    *   Uses `psutil` for system resource monitoring.
    *   Uses `docker` library if Docker tasks are supported.
    *   Manages collections of `TaskAllocation` (CSU-C3) and `Task` (CSU-C2) instances.
    *   Uses CSL-1 models for status Enums.
*   **动态特性**:
    *   Instantiated once when `agent.py` is run.
    *   Registers with CSC-A on startup.
    *   Runs a Flask `app` in a thread (or main thread if `agent.start()` is blocking).
    *   Runs a heartbeat thread (`heartbeat_loop`) and a task monitoring thread (`_monitor_tasks`).
    *   Receives allocation commands from CSC-A and delegates task execution.
*   **属性**:
    *   `server_url`:
        *   类型: `str`
        *   描述: 中央服务 (CSC-A) 的 URL。
    *   `node_id`:
        *   类型: `str`
        *   描述: 当前节点的唯一ID (UUID, persisted in `node_id.txt`).
    *   `region`:
        *   类型: `str`
        *   描述: 节点所属区域。
    *   `healthy`:
        *   类型: `bool`
        *   描述: 节点健康状态。
        *   值域: `True`, `False`.
    *   `heartbeat_interval`:
        *   类型: `int`
        *   描述: 心跳发送间隔（秒）。
        *   量化单位: 秒。
        *   实际值: `5`.
    *   `agent_port`:
        *   类型: `int`
        *   描述: Agent Flask应用监听的端口。
    *   `allocations`:
        *   类型: `Dict[str, TaskAllocation]`
        *   描述: 存储当前节点上活动分配的字典 (Key: `allocation_id`, Value: `TaskAllocation` 实例)。
    *   `task_monitor_thread`:
        *   类型: `threading.Thread`
    *   `app`:
        *   类型: `Flask`
        *   描述: Agent 的 Flask 应用实例。
*   **操作**:
    *   `__init__(self, server_url: str, region: str, agent_port: int)`:
        *   处理过程: 初始化属性，调用 `_get_or_create_node_id()`, 启动 `task_monitor_thread`, 设置 Flask `app` 和路由 (`setup_routes()`)。
    *   `_get_or_create_node_id(self) -> str`:
        *   处理过程: 尝试从 `node_id.txt` 读取ID，若失败则生成新UUID并写入文件。
        *   异常处理: 文件IO错误，打印日志。
    *   `setup_routes(self)`:
        *   处理过程: 定义 Flask 路由:
            *   `POST /allocations` (`handle_allocation`): 接收新分配。
            *   `GET /allocations/<allocation_id>` (`get_allocation_status`): 返回分配状态。
            *   `DELETE /allocations/<allocation_id>` (`stop_allocation`): 停止分配。
    *   `handle_allocation(self)` (Flask route handler):
        *   输入: JSON body (分配详情)。
        *   输出: JSON response.
        *   处理:
            1.  解析数据，创建 `TaskAllocation` (CSU-C3) 和 `Task` (CSU-C2) 实例。
            2.  将 `TaskAllocation` 存入 `self.allocations`。
            3.  为每个 `Task` 启动一个 `execute_task` 线程。
        *   异常处理: 数据无效400。
    *   `get_allocation_status(self, allocation_id)` (Flask route handler):
        *   输入: `allocation_id` (str).
        *   输出: JSON (分配状态及任务状态)。
        *   处理: 从 `self.allocations` 获取分配，序列化其状态。
        *   异常处理: 分配未找到404。
    *   `stop_allocation(self, allocation_id)` (Flask route handler):
        *   输入: `allocation_id` (str).
        *   输出: JSON response.
        *   处理: 调用 `self.stop_tasks(allocation)`，从 `self.allocations` 移除。
        *   异常处理: 分配未找到404。
    *   `execute_task(self, allocation: TaskAllocation, task: Task)`:
        *   输入: `allocation` (CSU-C3), `task` (CSU-C2)。
        *   处理:
            1.  更新 `task.status` 为 `RUNNING`, `task.start_time`。
            2.  更新 `allocation.status` 为 `RUNNING`, `allocation.start_time`。
            3.  若 `task.task_type == TaskType.CONTAINER`: 使用 `docker` 库运行容器，记录 `container.id` 到 `task.process`。
            4.  若 `task.task_type == TaskType.PROCESS`: 使用 `subprocess.Popen` 运行命令，记录 `process.pid` 到 `task.process`。
        *   异常处理: 容器/进程启动失败，更新 `task.status` 为 `FAILED`, `task.end_time`，更新 `allocation.status`。打印日志。
    *   `_monitor_tasks(self)`:
        *   处理过程 (循环):
            1.  遍历 `self.allocations.values()`。
            2.  调用 `allocation.update_status()` (这会触发其内部每个 `task.update_status()`)。
            3.  打印状态日志。
            4.  `time.sleep(5)`。
        *   异常处理: 通用异常捕获，打印日志。
    *   `get_resources(self) -> Dict`:
        *   输出: `{"cpu": available_nomad_cpu, "memory": available_MB, "cpu_used": ..., "memory_used": ...}`。
        *   处理: 使用 `psutil.cpu_percent()`, `psutil.virtual_memory()` 获取系统资源。
        *   量化单位: CPU (Nomad units: 10 * % idle), Memory (MB available).
    *   `register(self) -> bool`:
        *   处理: 构造注册数据 (含 `node_id`, `region`, `resources` from `get_resources()`, `healthy`, `endpoint`)。使用 `requests.post` 发送到 `self.server_url/register`。
        *   异常处理: `requests.exceptions.RequestException`，打印日志，返回 `False`。
    *   `send_heartbeat(self)`:
        *   处理:
            1.  收集所有 `self.allocations` 及其任务的状态。
            2.  构造心跳数据 (含 `node_id`, `resources`, `healthy`, `timestamp`, `allocations` status)。
            3.  使用 `requests.post` 发送到 `self.server_url/heartbeat`。
        *   异常处理: `requests.exceptions.RequestException`，打印日志。
    *   `start(self)`:
        *   处理:
            1.  调用 `self.register()`。若失败则退出。
            2.  启动心跳线程 (`heartbeat_loop` -> `send_heartbeat` + sleep)。
            3.  调用 `self.app.run()` 启动 Flask 服务器。
    *   `stop_tasks(self, allocation: TaskAllocation)`:
        *   输入: `allocation` (CSU-C3)。
        *   处理:
            1.  遍历 `allocation.tasks.values()`。
            2.  若 `task.process` 存在:
                - 若容器: `docker_client.containers.get(task.process).stop()`。
                - 若进程: `psutil.Process(task.process).terminate()` (then `kill()` if timeout).
            3.  更新 `task.status = TaskStatus.COMPLETE`, `task.end_time`。
            4.  更新 `allocation.status = AllocationStatus.STOPPED`, `allocation.end_time`。
        *   异常处理: Docker/psutil 错误 (e.g., NoSuchProcess, NotFound)，更新任务状态为 FAILED，打印日志。

#### 5.2. CSU-C2: `Task` (in `agent.py`)

*   **类名**: `Task`
*   **静态特性**:
    *   Uses `TaskStatus`, `TaskType` enums (CSL-1).
    *   Interacts with `psutil` or `docker` library for status updates.
*   **动态特性**:
    *   Instantiated by `NodeAgent.handle_allocation` for each task in an allocation.
    *   Lifecycle managed by `NodeAgent` (execution thread, monitoring thread).
*   **属性**:
    *   `name`: `str`
    *   `resources`: `Dict` (e.g., `{"cpu": ..., "memory": ...}`)
    *   `config`: `Dict` (e.g., `{"image": "...", "command": "...", "port": ...}`)
    *   `status`: `TaskStatus` (Default: `PENDING`)
    *   `start_time`: `Optional[float]` (Unix timestamp)
    *   `end_time`: `Optional[float]` (Unix timestamp)
    *   `thread`: `Optional[threading.Thread]` (Thread running `NodeAgent.execute_task` for this task)
    *   `process`: `Optional[Union[int, str]]` (PID for process, Container ID for container)
    *   `task_type`: `TaskType` (Determined from `config`)
    *   `exit_code`: `Optional[int]`
*   **操作**:
    *   `__init__(self, name: str, resources: Dict, config: Dict)`: Initializes attributes.
    *   `update_status(self) -> bool`:
        *   输出: `bool` (True if status might have changed and was checked, False if no process to check).
        *   处理:
            1.  If `self.process` is None, return `False`.
            2.  If `task_type` is `PROCESS`:
                - Use `psutil.Process(self.process)` to check status (`psutil.STATUS_RUNNING`, `psutil.STATUS_ZOMBIE`, `psutil.STATUS_DEAD`).
                - Update `self.status`, `self.exit_code`, `self.end_time` accordingly.
            3.  If `task_type` is `CONTAINER`:
                - Use `docker.from_env().containers.get(self.process)` to check `container.status` ("running", "exited").
                - Update `self.status`, `self.exit_code` (from `container.attrs["State"]["ExitCode"]`), `self.end_time`.
        *   异常处理: `psutil.NoSuchProcess`, `docker.errors.NotFound`. If current status was `RUNNING`, set to `FAILED`. Log errors.

#### 5.3. CSU-C3: `TaskAllocation` (in `agent.py`)

*   **类名**: `TaskAllocation`
*   **静态特性**:
    *   Uses `AllocationStatus` enum (CSL-1).
    *   Aggregates `Task` (CSU-C2) instances in `self.tasks`.
*   **动态特性**:
    *   Instantiated by `NodeAgent.handle_allocation`.
    *   Its status is derived from the statuses of its constituent `Task` instances.
*   **属性**:
    *   `id`: `str` (Allocation ID)
    *   `job_id`: `str`
    *   `task_group`: `str` (Task group name)
    *   `status`: `AllocationStatus` (Default: `PENDING`)
    *   `start_time`: `Optional[float]`
    *   `end_time`: `Optional[float]`
    *   `tasks`: `Dict[str, Task]` (Key: task name, Value: `Task` instance)
*   **操作**:
    *   `__init__(self, allocation_id: str, job_id: str, task_group: str)`: Initializes attributes, `tasks` as empty dict.
    *   `update_status(self)`:
        *   处理:
            1.  Iterate `self.tasks.values()`, calling `task.update_status()` for each.
            2.  Based on all task statuses:
                - If any task is `FAILED`, `self.status = AllocationStatus.FAILED`.
                - Else if all tasks `COMPLETE`, `self.status = AllocationStatus.COMPLETE`.
                - Else if any task `RUNNING`, `self.status = AllocationStatus.RUNNING`.
                - Else `self.status = AllocationStatus.PENDING`.
            3.  Update `self.start_time` and `self.end_time` based on transitions.

### 6. CSL-1: Common Data Models (`models.py`)

These are primarily data-carrying classes and enumerations.

*   **Enums**:
    *   `EvaluationStatus(Enum)`: `PENDING`, `COMPLETE`, `FAILED`
    *   `JobStatus(Enum)`: `PENDING`, `RUNNING`, `COMPLETE`, `FAILED`, `LOST`, `DEAD`, `DEGRADED`, `BLOCKED`
    *   `TaskStatus(Enum)`: `PENDING`, `RUNNING`, `COMPLETE`, `FAILED`
    *   `TaskType(Enum)`: `PROCESS`, `CONTAINER`
    *   `AllocationStatus(Enum)`: `PENDING`, `RUNNING`, `COMPLETE`, `FAILED`, `LOST`, `STOPPED`
    *   `TriggerEvent(Enum)`: `JOB_SUBMIT`, `JOB_UPDATE`, `JOB_DEREGISTER`, `NODE_FAILURE`, `NODE_JOIN`
*   **Classes**:
    *   **`Task` (model definition)**:
        *   Attributes: `name` (str), `resources` (Dict), `config` (Dict), `status` (`TaskStatus`), `task_type` (`TaskType`).
        *   Primarily used by `Job` and `TaskGroup` for defining job structure.
    *   **`TaskGroup` (model definition)**:
        *   Attributes: `name` (str), `tasks` (List[`Task` model]), `status` (`JobStatus`).
        *   Method: `get_total_resources() -> Dict` (Calculates sum of CPU/memory for its tasks).
    *   **`Job` (model definition)**:
        *   Attributes: `id` (str), `task_groups` (List[`TaskGroup` model]), `constraints` (Dict), `status` (`JobStatus`).
    *   **`Allocation` (model definition)**:
        *   Attributes: `id` (str), `job_id` (str), `node_id` (str), `task_group` (`TaskGroup` model), `status` (`AllocationStatus`).

This detailed design provides a class-level view of the system, outlining responsibilities, data, and interactions. It should serve as a solid foundation for implementation or further refinement.
