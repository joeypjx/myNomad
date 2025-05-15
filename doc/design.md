
好的，我们来对软件架构进行简化，减少 CSC 的数量，使其更加简洁。

## 软件概要设计说明 (简化版)

### 1. 引言

本文档描述了一个分布式资源调度与管理系统的概要设计。该系统允许用户提交作业，系统则负责在集群中的可用节点上调度、执行和监控这些作业的任务。此版本对原有的 CSC 进行了合并和简化，以提供更清晰的宏观架构。

### 2. 软件体系结构设计

系统被重新划分为更少的、功能更内聚的计算机软件部件 (CSC)。

**系统 CSC 划分图示 (简化版):**

```
+---------------------------------------+     +------------------------------------------+
| CSC-A: Central Orchestration Service  |<--->| CSC-B: Node & Metadata Management Service|
| (API, Scheduler, Executor, AgentComm) |     | (NodeManager, DB, HealthMonitor)         |
+---------------------------------------+     +------------------------------------------+
          ^         ^                                     ^
          |         | (Task Commands)                     | (Data Access)
          |         |                                     |
          v         +------------------------------> (SQLite Database)
+---------------------------------------+
| CSC-C: Node Agent Service             |
| (Task Execution, Local State)         |
+---------------------------------------+

+---------------------------------------+
| CSL-1: Common Data Models             |
| (Shared Library - models.py)          |
+---------------------------------------+
(Used by CSC-A, CSC-B, CSC-C)
```

**CSCI (Computer Software Configuration Item):** 整个分布式资源调度与管理系统被视为一个 CSCI。

**CSC 列表 (简化版):**

1.  **CSC-A: Central Orchestration Service**:
    *   **描述**: 系统的核心控制单元。负责处理所有外部 API 请求，进行作业调度决策，执行分配计划，并与 Node Agent 进行通信。
    *   **包含原 CSCs**: API Gateway (CSC1), Scheduling Service (CSC3), Allocation Execution Service (CSC4), Inter-Service Communicator (CSC6)。
    *   **主要对应文件**: `server.py` (API 入口), `scheduler.py`, `scheduler_planner.py` (调度逻辑), `allocation_executor.py` (执行逻辑), `agent_communicator.py` (与 Agent 通信逻辑)。

2.  **CSC-B: Node & Metadata Management Service**:
    *   **描述**: 系统的状态和元数据管理中心。负责持久化存储和管理节点、作业、分配、模板等信息，并监控节点健康状态。
    *   **包含原 CSCs**: Node Management Service (CSC2), Data Persistence Layer (CSC7)。
    *   **主要对应文件**: `node_manager.py`。其数据存储为 SQLite 数据库 (`nomad.db`)。

3.  **CSC-C: Node Agent Service**:
    *   **描述**: 部署在每个计算节点上的代理服务。负责实际执行任务、监控任务状态，并向中央服务报告节点和任务状态。
    *   **等同于原 CSC**: Node Agent Service (CSC5)。
    *   **主要对应文件**: `agent.py`.

**CSL (Computer Software Library) 列表:**

1.  **CSL-1: Common Data Models**:
    *   **描述**: 定义了系统中各 CSC 共享的数据结构、类和枚举。这不是一个可执行的 CSC，而是一个基础库。
    *   **等同于原 CSC**: Common Data Models (CSC8)。
    *   **主要对应文件**: `models.py`.

### 3. CSC 间接口设计

#### 3.1. I1-R: Client - Central Orchestration Service Interface (REST API)

*   **唯一标识号**: `API_V1_R`
*   **描述**: 外部客户端与系统交互的接口，由 CSC-A 提供。
*   **数据元素/消息**: JSON 格式的请求/响应体。包括作业定义、节点注册信息、模板数据、API 密钥等。
*   **优先级**: 标准 HTTP 请求处理优先级。
*   **通信协议**: HTTP/S。
*   **端点 (部分列举, 由 `server.py` 处理)**:
    *   `POST /register`: 节点注册 (数据最终由 CSC-B 处理，但请求由 CSC-A 接收并协调)。
    *   `POST /heartbeat`: 节点心跳 (同上)。
    *   `POST /templates`, `GET /templates`, `PUT /templates/<id>`, `DELETE /templates/<id>`: 模板管理。
    *   `POST /jobs`, `GET /jobs`, `GET /jobs/<id>`, `PUT /jobs/<id>`, `DELETE /jobs/<id>`, `POST /jobs/<id>/delete`, `POST /jobs/<id>/restart`: 作业管理和调度请求。
    *   `GET /nodes`: 获取节点列表。
    *   `POST /test/clear-all`: 清理数据 (通过 CSC-A 协调 CSC-B)。

#### 3.2. I2-R: Central Orchestration Service - Node & Metadata Management Service Interface

*   **唯一标识号**: `ORCH_META_IF`
*   **描述**: CSC-A 调用 CSC-B 以获取调度所需信息、存储/更新作业和分配状态、管理模板等。
*   **数据元素/消息**: Python 字典、CSL-1 中定义的类实例 (如 `Job`, `Node` 数据)、`job_id`, `template_id`, `allocation_id` 等。
*   **优先级**: 高 (进程内 Python 方法调用)。
*   **通信协议**: 进程内 Python 方法调用。
*   **方法调用 (由 `node_manager.py` 提供, 被 CSC-A 内部各逻辑模块调用)**:
    *   `get_healthy_nodes()`: 供调度器使用。
    *   `get_job()`, `submit_job()` (用于新建或标记更新), `update_job_status()`: 作业状态管理。
    *   `get_job_allocations()`, `update_allocation()`, `delete_allocation()`, `clean_job_data()`: 分配记录管理。
    *   `create_job_template()`, `get_job_template()`, `list_job_templates()`, `update_job_template()`, `delete_job_template()`: 模板管理。
    *   `register_node()`, `update_heartbeat()`: 节点注册和心跳数据持久化。
    *   `clear_all_data()`: 清理所有数据。

#### 3.3. I3-R: Central Orchestration Service - Node Agent Service Interface (REST API)

*   **唯一标识号**: `ORCH_AGENT_IF`
*   **描述**: CSC-A (内部的执行和通信逻辑) 调用 CSC-C 来部署或停止任务。
*   **数据元素/消息**: JSON 格式。分配定义 (包含任务组、任务配置、资源需求)。
*   **优先级**: 高。
*   **通信协议**: HTTP。
*   **端点 (由 CSC-C 即 `agent.py` 提供)**:
    *   `POST /allocations`: 接收并执行新的分配任务。
    *   `DELETE /allocations/<allocation_id>`: 停止指定的分配。

#### 3.4. I4-R: Node Agent Service - Central Orchestration Service Interface (REST API)

*   **唯一标识号**: `AGENT_ORCH_IF`
*   **描述**: CSC-C 调用 CSC-A 进行节点注册和发送心跳。
*   **数据元素/消息**: JSON 格式。节点 ID, 区域, 资源信息, 健康状况, Agent 端点, 分配状态。
*   **优先级**: 中 (心跳为周期性，注册为一次性)。
*   **通信协议**: HTTP。
*   **端点 (由 CSC-A 即 `server.py` 提供, 最终数据写入 CSC-B)**:
    *   `POST /register`: 节点注册。
    *   `POST /heartbeat`: 节点心跳。

#### 3.5. I5-R: Node & Metadata Management Service - Database Interface

*   **唯一标识号**: `META_DB_IF`
*   **描述**: CSC-B 内部与其数据存储 (SQLite 数据库) 的交互接口。
*   **数据元素/消息**: SQL 查询语句, 数据库记录行, 事务控制。
*   **优先级**: N/A (直接数据库访问)。
*   **通信协议**: `sqlite3` Python 库调用。
*   **使用者**: `node_manager.py` 及其内部的 `NodeHealthMonitor`。

#### 3.6. I6-R: Common Data Models Library Usage

*   **唯一标识号**: `CSL1_USAGE`
*   **描述**: CSC-A, CSC-B, 和 CSC-C 使用 CSL-1 中定义的共享数据模型。
*   **数据元素/消息**: `JobStatus`, `AllocationStatus`, `Task`, `Job`, `Allocation` 等枚举和类实例。
*   **优先级**: N/A。
*   **通信协议**: Python 对象实例化和方法调用。

### 4. CSCI 中各 CSC 的设计 (简化版)

#### 4.1. CSC-A: Central Orchestration Service

*   **目的**: 作为系统的集中控制大脑，处理外部交互、决策、任务分发和与Agent通信。
*   **主要功能**:
    *   **API Handling (`server.py`)**:
        *   提供 I1-R 和 I4-R 中定义的 RESTful API 端点。
        *   验证请求，初步处理数据。
        *   将请求路由到内部的调度、执行或元数据管理协调逻辑。
    *   **Scheduling Logic (`scheduler.py`, `scheduler_planner.py`)**:
        *   创建评估任务，为作业制定分配计划。
        *   通过 I2-R 从 CSC-B 获取节点和现有作业/分配信息。
        *   将生成的计划传递给内部的执行逻辑。
    *   **Execution Logic (`allocation_executor.py`)**:
        *   接收调度计划。
        *   处理分配的创建和删除。对于创建，通过内部的通信逻辑（原 AgentCommunicator）调用 I3-R。
        *   对于状态更新或记录删除，通过 I2-R 与 CSC-B 交互。
    *   **Agent Communication (`agent_communicator.py` - 现为内部模块)**:
        *   负责与 CSC-C (Node Agent) 的 HTTP 通信，实现 I3-R。
        *   管理 Node Agent 的端点信息 (从节点注册时获取)。
*   **接口**: 提供 I1-R, I4-R; 使用 I2-R, I3-R, I6-R。
*   **内部设计**:
    *   `server.py` 使用 Flask，作为统一入口。
    *   调度和执行逻辑作为 `server.py` 可调用的模块。
    *   使用内部队列（如 `allocation_executor.py` 中的 `plan_queue`）解耦调度和执行步骤。

#### 4.2. CSC-B: Node & Metadata Management Service

*   **目的**: 维护系统所有持久化状态和元数据，并确保节点健康。
*   **主要功能**:
    *   **Data Persistence (`node_manager.py` + SQLite)**:
        *   通过 I5-R 对 SQLite 数据库进行所有 CRUD 操作。
        *   存储节点、作业、分配、任务状态和模板的详细信息。
    *   **State Management (`node_manager.py`)**:
        *   提供 I2-R 接口，供 CSC-A 查询和更新状态。
        *   根据心跳和分配状态更新作业和节点的整体状态。
    *   **Health Monitoring (`NodeHealthMonitor` in `node_manager.py`)**:
        *   周期性检查节点心跳超时 (通过 I5-R 读取数据库)。
        *   标记不健康节点，更新相关分配和作业状态。
*   **接口**: 提供 I2-R; 使用 I5-R, I6-R。
*   **内部设计**:
    *   核心是 `NodeManager` 类，封装了所有数据库操作和状态管理逻辑。
    *   `NodeHealthMonitor` 作为 `NodeManager` 的一个内部组件，在独立线程中运行。

#### 4.3. CSC-C: Node Agent Service

*   **目的**: 在计算节点上执行具体任务，监控任务，并向中央服务汇报。
*   **主要功能**:
    *   **Node Initialization & Registration**: 启动时通过 I4-R 向 CSC-A 注册。
    *   **API Server**: 运行本地 Flask 服务器，提供 I3-R 接口，接收来自 CSC-A 的任务指令。
    *   **Task Execution & Monitoring**:
        *   根据收到的分配指令，启动容器或进程。
        *   使用 `docker` 库或 `subprocess`/`psutil` 监控任务的本地状态。
    *   **Heartbeat Reporting**: 定期通过 I4-R向 CSC-A 发送心跳，包含节点资源、健康状况、本地任务状态。
*   **接口**: 提供 I3-R; 使用 I4-R, I6-R。
*   **内部设计**:
    *   独立的 Python 应用程序。
    *   使用 Flask 创建本地 API 端点。
    *   多线程用于任务执行、监控和心跳。
    *   内部维护当前节点上任务的状态。

#### 4.4. CSL-1: Common Data Models

*   **目的**: 为系统提供统一的数据结构和类型定义。
*   **主要功能**: 定义枚举（如 `JobStatus`）和类（如 `Task`, `Job`）。
*   **接口**: 提供 I6-R (被 CSC-A, CSC-B, CSC-C 导入和使用)。
*   **内部设计**: `models.py` 文件，包含纯 Python 定义。

这个简化版本将原来的8个 CSC/CSL 减少到了3个核心 CSC 和1个 CSL，使得整体架构在宏观层面更加简洁，同时保留了原有的核心功能划分。主要变化是将中央控制逻辑（API、调度、执行、Agent通信）合并到 CSC-A，将数据持久化和元数据管理合并到 CSC-B。Node Agent (CSC-C) 和数据模型 (CSL-1) 保持不变。
