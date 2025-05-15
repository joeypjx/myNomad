**`server.py` (Master/Control Plane APIs)**

1.  **`POST /register` - 节点注册**
    *   **请求 (Request Body)**:
        ```json
        {
            "node_id": "string (UUID)",
            "ip_address": "string",
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
            "allocations": { // Optional: Status of allocations on the node
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
                            "exit_code": "integer (nullable)",
                            "message": "string (nullable, detailed status/error message)"
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
                    "tasks": [
                        {
                            "name": "string (Task name)",
                            "config": {
                                "image": "string (Docker image)",
                                "port": "integer (Optional, host port to map)",
                                "command": "string (Command to execute)"
                            },
                            "resources": {
                                "cpu": "integer",
                                "memory": "integer (MB)"
                            }
                        }
                        // ... other tasks in the group
                    ],
                    "constraints": [
                        {
                            "attribute": "string (e.g., ip_address, node_id, or custom attribute)",
                            "operator": "string (e.g., =, !=, >, <, regex)",
                            "value": "string or number"
                        }
                    ]
                }
            ],
            "constraints": {}
        }
        ```
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "job_id": "string (Generated or provided Job ID)",
            "evaluation_id": "string (ID of the evaluation created for this job submission)",
            "message": "作业评估已创建并加入队列"
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

5.  **`DELETE /jobs/<job_id>` - 停止作业**
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
                    "task_groups": [
                        {
                            "name": "string",
                            "tasks": [
                                {
                                    "name": "string",
                                    "config": {
                                        "image": "string",
                                        "port": "integer",
                                        "command": "string"
                                    },
                                    "resources": {
                                        "cpu": "integer",
                                        "memory": "integer (MB)"
                                    }
                                }
                            ],
                            "constraints": [
                                {
                                    "attribute": "string",
                                    "operator": "string",
                                    "value": "string or number"
                                }
                            ]
                        }
                    ],
                    "constraints": {},
                    "status": "string (e.g., pending, running, complete, failed, dead, lost, degraded, blocked)",
                    "allocations": [
                        {
                            "allocation_id": "string",
                            "node_id": "string",
                            "task_group": "string",
                            "status": "string",
                            "start_time": "float (nullable)",
                            "end_time": "float (nullable)",
                            "tasks": {
                                "<task_name_1>": {
                                    "resources": {
                                        "cpu": "integer",
                                        "memory": "integer (MB)"
                                    },
                                    "config": {
                                        "image": "string",
                                        "port": "integer",
                                        "command": "string"
                                    },
                                    "status": "string",
                                    "start_time": "float (nullable)",
                                    "end_time": "float (nullable)",
                                    "exit_code": "integer (nullable)",
                                    "message": "string (nullable)"
                                }
                            }
                        }
                    ]
                }
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
            "task_groups": [
                {
                    "name": "string",
                    "tasks": [
                        {
                            "name": "string",
                            "config": {
                                "image": "string",
                                "port": "integer",
                                "command": "string"
                            },
                            "resources": {
                                "cpu": "integer",
                                "memory": "integer (MB)"
                            }
                        }
                    ],
                    "constraints": [
                        {
                            "attribute": "string",
                            "operator": "string",
                            "value": "string or number"
                        }
                    ]
                }
            ],
            "constraints": {},
            "status": "string",
            "allocations": [
                {
                    "allocation_id": "string",
                    "node_id": "string",
                    "task_group": "string",
                    "status": "string",
                    "start_time": "float (nullable)",
                    "end_time": "float (nullable)"
                }
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
                    "ip_address": "string",
                    "resources": {
                        "cpu": "integer (e.g., Nomad CPU units)",
                        "memory": "integer (MB)"
                    },
                    "healthy": "boolean",
                    "last_heartbeat": "float (Unix timestamp)",
                    "allocations": [
                        {
                            "allocation_id": "string",
                            "job_id": "string",
                            "task_group": "string",
                            "status": "string",
                            "start_time": "float (nullable)",
                            "end_time": "float (nullable)"
                        }
                    ]
                }
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

11. **`POST /test/clear-all` - (测试接口) 清空所有数据和表结构**
    *   **请求 (Request Body)**: None
    *   **请求头 (Headers)**:
        *   `X-API-Key`: `string (Test API Key)`
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "message": "所有数据已清空",
            "cleared_items": {
                "jobs": "所有作业",
                "nodes": "所有节点",
                "allocations": "所有分配",
                "task_status": "所有任务状态"
            }
        }
        ```
    *   **响应 (Response Body - Error 401/500)**:
        ```json
        {
            "error": "string (Error message, e.g., 'Invalid API key')"
        }
        ```

**作业模板API (Job Templates APIs)**

1.  **`POST /templates` - 创建新的作业模板**
    *   **请求 (Request Body)**:
        ```json
        {
            "name": "string (Template name, required)",
            "description": "string (Optional)",
            "task_groups": [
                {
                    "name": "string",
                    "tasks": [
                        {
                            "name": "string",
                            "config": {
                                "image": "string",
                                "port": "integer",
                                "command": "string"
                            },
                            "resources": {
                                "cpu": "integer",
                                "memory": "integer (MB)"
                            }
                        }
                    ],
                    "constraints": [
                        {
                            "attribute": "string",
                            "operator": "string",
                            "value": "string or number"
                        }
                    ]
                }
            ],
            "constraints": {}
        }
        ```
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "template_id": "string (Generated Template ID)",
            "message": "作业模板创建成功"
        }
        ```
    *   **响应 (Response Body - Error 400/500)**:
        ```json
        {
            "error": "string (Error message)"
        }
        ```

2.  **`GET /templates` - 获取所有作业模板**
    *   **请求 (Request Body)**: None
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "templates": [
                {
                    "template_id": "string",
                    "name": "string",
                    "description": "string (nullable)",
                    "created_at": "float (Unix timestamp)",
                    "updated_at": "float (Unix timestamp)"
                }
            ],
            "count": "integer"
        }
        ```

3.  **`GET /templates/<template_id>` - 获取特定作业模板详情**
    *   **请求 (Request Body)**: None
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "template_id": "string",
            "name": "string",
            "description": "string (nullable)",
            "task_groups": [
                {
                    "name": "string",
                    "tasks": [
                        {
                            "name": "string",
                            "config": {
                                "image": "string",
                                "port": "integer",
                                "command": "string"
                            },
                            "resources": {
                                "cpu": "integer",
                                "memory": "integer (MB)"
                            }
                        }
                    ],
                    "constraints": [
                        {
                            "attribute": "string",
                            "operator": "string",
                            "value": "string or number"
                        }
                    ]
                }
            ],
            "constraints": {},
            "created_at": "float",
            "updated_at": "float"
        }
        ```
    *   **响应 (Response Body - Error 404)**:
        ```json
        {
            "error": "模板不存在"
        }
        ```

4.  **`PUT /templates/<template_id>` - 更新作业模板**
    *   **请求 (Request Body)**: Fields to update from `POST /templates` structure.
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "message": "作业模板更新成功"
        }
        ```
    *   **响应 (Response Body - Error 400/500)**:
        ```json
        {
            "error": "string (Error message)"
        }
        ```

5.  **`DELETE /templates/<template_id>` - 删除作业模板**
    *   **请求 (Request Body)**: None
    *   **响应 (Response Body - Success 200)**:
        ```json
        {
            "message": "作业模板删除成功"
        }
        ```
    *   **响应 (Response Body - Error 500)**:
        ```json
        {
            "error": "string (Error message)"
        }
        ```

**`agent.py` (Node Agent APIs)**

1.  **`POST /allocations` - (由 Server 调用) 创建并运行新分配**
    *   **请求 (Request Body)**:
        ```json
        {
            "allocation_id": "string (UUID)",
            "job_id": "string (UUID)",
            "task_group": {
                "name": "string (Task group name)",
                "tasks": [
                    {
                        "name": "string (Task name)",
                        "resources": {
                            "cpu": "integer",
                            "memory": "integer (MB)"
                        },
                        "config": {
                            "image": "string (for docker)",
                            "port": "integer (optional, for docker, host port)",
                            "command": "string (for exec)"
                        }
                    }
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
                }
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

