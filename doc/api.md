
**`server.py` (Master/Control Plane APIs)**

1.  **`POST /register` - 节点注册**
    *   **请求 (Request Body)**:
        ```json
        {
            "node_id": "string (UUID)",
            "region": "string",
            "resources": {
                "cpu": "integer (e.g., Nomad CPU units)",
                "memory": "integer (MB)"
                // ... other potential resources
            },
            "healthy": "boolean",
            "endpoint": "string (URL of the agent's API, e.g., http://<agent_ip>:<agent_port>)"
        }
        ```
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "message": "Node registered successfully"
        }
        ```
    *   **响应 (Response Body - Error 400/500)**:
        ```json
        {
            "error": "string (Error message)"
        }
        ```

2.  **`POST /heartbeat` - 节点心跳**
    *   **请求 (Request Body)**:
        ```json
        {
            "node_id": "string (UUID)",
            "resources": { // Current available resources on the node
                "cpu": "integer",
                "memory": "integer",
                "cpu_used": "integer",
                "memory_used": "integer"
            },
            "healthy": "boolean",
            "timestamp": "float (Unix timestamp)",
            "allocations": { // Optional: Status of allocationsleger  on the node
                "<allocation_id_1>": {
                    "status": "string (e.g., running, complete, failed)",
                    "start_time": "float (Unix timestamp, nullable)",
                    "end_time": "float (Unix timestamp, nullable)",
                    "tasks": {
                        "<task_name_1>": {
                            "status": "string (e.g., running, complete, failed)",
                            "start_time": "float (Unix timestamp, nullable)",
                            "end_time": "float (Unix timestamp, nullable)",
                            "error": "string (nullable)",
                            "exit_code": "integer (nullable)"
                        }
                        // ... other tasks
                    }
                }
                // ... other allocations
            }
        }
        ```
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "message": "Heartbeat received"
        }
        ```
    *   **响应 (Response Body - Error 400/500)**:
        ```json
        {
            "error": "string (Error message)"
        }
        ```

3.  **`POST /jobs` - 提交新作业**
    *   **请求 (Request Body)**:
        ```json
        {
            "task_groups": [
                {
                    "name": "string (Task group name)",
                    "count": "integer (Number of instances of this task group)",
                    "tasks": [
                        {
                            "name": "string (Task name)",
                            "driver": "string (e.g., docker, exec)", // Implied by config
                            "config": {
                                // Driver-specific configuration
                                // e.g., for docker:
                                "image": "string (Docker image)",
                                "port": "integer (Optional, host port to map)",
                                // e.g., for exec:
                                "command": "string (Command to execute)"
                            },
                            "resources": {
                                "cpu": "integer",
                                "memory": "integer (MB)"
                            }
                        }
                        // ... other tasks in the group
                    ],
                    "constraints": [ // Optional
                        {
                            "attribute": "string (e.g., region, node_id, or custom attribute)",
                            "operator": "string (e.g., =, !=, >, <, regex)",
                            "value": "string"
                        }
                    // ... other constraints
                    ]
                }
                // ... other task groups
            ]
            // "job_id": "string (Optional, if updating an existing job, though a PUT to /jobs/<job_id> is more conventional)"
        }
        ```
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "job_id": "string (Generated or provided Job ID)",
            "evaluation_id": "string (ID of the evaluation created for this job submission)",
            "message": "作业评估已加入队列"
        }
        ```
    *   **响应 (Response Body - Error 400/500)**:
        ```json
        {
            "error": "string (Error message)"
        }
        ```

4.  **`PUT /jobs/<job_id>` - 更新作业**
    *   **请求 (Request Body)**: Same structure as `POST /jobs`. The `job_id` is taken from the URL path.
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "job_id": "string (Job ID from URL)",
            "evaluation_id": "string (ID of the evaluation created for this job update)",
            "message": "作业更新评估已加入队列"
        }
        ```
    *   **响应 (Response Body - Error 400/404/500)**:
        ```json
        {
            "error": "string (Error message)"
        }
        ```

5.  **`DELETE /jobs/<job_id>` - 停止作业** (Note: This is more like a "stop" operation rather than a full "delete" based on the handler `stop_job`. A separate `POST /jobs/<job_id>/delete` exists for actual deletion.)
    *   **请求 (Request Body)**: None
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "message": "作业 <job_id> 已停止"
        }
        ```
    *   **响应 (Response Body - Error 404/500)**:
        ```json
        {
            "error": "string (Error message)"
        }
        ```

6.  **`GET /jobs` - 获取所有作业信息**
    *   **请求 (Request Body)**: None
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "jobs": [
                {
                    "job_id": "string",
                    "task_groups": [ /* همانطور که در POST /jobs */ ],
                    "constraints": [ /* همانطور که در POST /jobs */ ],
                    "status": "string (e.g., pending, running, complete, failed, dead, lost)",
                    "allocations": [
                        {
                            "allocation_id": "string",
                            "node_id": "string",
                            "task_group": "string (Name of the task group)",
                            "status": "string (Allocation status)",
                            "start_time": "float (nullable)",
                            "end_time": "float (nullable)",
                            "tasks": {
                                "<task_name_1>": {
                                    "resources": { /* ... */ },
                                    "config": { /* ... */ },
                                    "status": "string (Task status)",
                                    "start_time": "float (nullable)",
                                    "end_time": "float (nullable)",
                                    "exit_code": "integer (nullable)"
                                }
                                // ... other tasks
                            }
                        }
                        // ... other allocations for this job
                    ]
                }
                // ... other jobs
            ],
            "count": "integer (Number of jobs)"
        }
        ```

7.  **`GET /jobs/<job_id>` - 获取指定作业的详细信息**
    *   **请求 (Request Body)**: None
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "job_id": "string",
            "task_groups": [ /* As in POST /jobs */ ],
            "constraints": [ /* As in POST /jobs */ ],
            "status": "string",
            "allocations": [
                {
                    "allocation_id": "string",
                    "node_id": "string",
                    "task_group": "string",
                    "status": "string",
                    "start_time": "float (nullable)",
                    "end_time": "float (nullable)"
                    // Note: This endpoint doesn't seem to include detailed task status per allocation here,
                    // unlike GET /jobs. It might be a simplified view.
                }
                // ... other allocations for this job
            ]
        }
        ```
    *   **响应 (Response Body - Error 404)**:
        ```json
        {
            "error": "作业不存在"
        }
        ```

8.  **`GET /nodes` - 获取所有节点信息**
    *   **请求 (Request Body)**: None
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "nodes": [
                {
                    "node_id": "string",
                    "region": "string",
                    "resources": { /* As in POST /register */ },
                    "healthy": "boolean",
                    "last_heartbeat": "float (Unix timestamp)",
                    "allocations": [ // Allocations currently running on this node
                        {
                            "allocation_id": "string",
                            "job_id": "string",
                            "task_group": "string",
                            "status": "string",
                            "start_time": "float (nullable)",
                            "end_time": "float (nullable)"
                        }
                        // ... other allocations on this node
                    ]
                }
                // ... other nodes
            ],
            "count": "integer (Number of nodes)"
        }
        ```
    *   **响应 (Response Body - Error 500)**:
        ```json
        {
            "error": "获取节点信息失败"
        }
        ```

9.  **`POST /jobs/<job_id>/delete` - 删除作业及其所有相关资源**
    *   **请求 (Request Body)**: None
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "message": "作业 <job_id> 及其相关资源已删除"
        }
        ```
    *   **响应 (Response Body - Error 404/500)**:
        ```json
        {
            "error": "string (Error message)"
        }
        ```

10. **`POST /jobs/<job_id>/restart` - 重启已停止的作业**
    *   **请求 (Request Body)**: None
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "job_id": "string (Job ID)",
            "evaluation_id": "string (ID of the evaluation created for restarting)",
            "message": "作业重启评估已加入队列"
        }
        ```
    *   **响应 (Response Body - Error 400/404)**:
        ```json
        {
            "error": "string (Error message, e.g., '只能重启已停止的作业' or '作业不存在')"
        }
        ```

**`agent.py` (Node Agent APIs)**

1.  **`POST /allocations` - (由 Server 调用) 创建并运行新分配**
    *   **请求 (Request Body)**:
        ```json
        {
            "allocation_id": "string (UUID)",
            "job_id": "string (UUID)",
            "task_group": { // Details of the task group to run
                "name": "string (Task group name)",
                "tasks": [
                    {
                        "name": "string (Task name)",
                        "resources": {
                            "cpu": "integer",
                            "memory": "integer (MB)"
                        },
                        "config": {
                            // Driver-specific config, e.g.,
                            "image": "string (for docker)",
                            "port": "integer (optional, for docker, host port)",
                            "command": "string (for exec)"
                        }
                    }
                    // ... other tasks in the group
                ]
            }
        }
        ```
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "message": "Allocation accepted",
            "allocation_id": "string (Echoes the provided allocation_id)"
        }
        ```
    *   **响应 (Response Body - Error 400)**:
        ```json
        {
            "error": "string (Error message)"
        }
        ```

2.  **`GET /allocations/<allocation_id>` - (可由 Server 或监控工具调用) 获取分配状态**
    *   **请求 (Request Body)**: None
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "allocation_id": "string",
            "job_id": "string",
            "task_group": "string (Name of the task group)",
            "status": "string (e.g., pending, running, complete, failed, stopped)",
            "start_time": "float (Unix timestamp, nullable)",
            "end_time": "float (Unix timestamp, nullable)",
            "tasks": {
                "<task_name_1>": {
                    "status": "string (e.g., pending, running, complete, failed)",
                    "start_time": "float (Unix timestamp, nullable)",
                    "end_time": "float (Unix timestamp, nullable)"
                    // "exit_code" and "error" might also be relevant here but not explicitly shown in route
                }
                // ... other tasks in this allocation
            }
        }
        ```
    *   **响应 (Response Body - Error 404)**:
        ```json
        {
            "error": "Allocation not found"
        }
        ```

3.  **`DELETE /allocations/<allocation_id>` - (由 Server 调用) 停止并移除分配**
    *   **请求 (Request Body)**: None
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "message": "Allocation <allocation_id> stopped and removed"
        }
        ```
    *   **响应 (Response Body - Error 404)**:
        ```json
        {
            "error": "Allocation not found"
        }
        ```

