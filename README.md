# myNomad - 分布式任务调度系统

myNomad是一个轻量级分布式任务调度系统，参考了HashiCorp Nomad的设计理念，用于在分布式环境中高效地调度和管理工作负载。它支持容器和进程两种任务类型，提供了简单而强大的任务编排功能。

## 系统架构

myNomad采用主从架构，主要包含以下组件：

- **服务器(Server)**: 作为控制平面，负责接收API请求，存储系统状态，调度任务。
- **节点管理器(NodeManager)**: 管理集群中的所有节点、作业和分配信息，维护系统状态。
- **调度器(Scheduler)**: 根据作业配置和可用资源做出调度决策，将任务组分配到合适的节点。
- **节点代理(NodeAgent)**: 部署在每个工作节点上，负责执行分配的任务，并向服务器报告心跳和任务状态。

### 核心概念

- **作业(Job)**: 用户提交的工作单元，包含一个或多个任务组。
- **任务组(Task Group)**: 一组需要在同一节点上一起调度的相关任务。
- **任务(Task)**: 最小的执行单元，可以是容器或进程。
- **分配(Allocation)**: 任务组在特定节点上的实例化，是调度的结果。

## 功能特性

- **多驱动支持**：支持Docker容器和本地进程两种执行方式
- **资源管理**：跟踪CPU、内存等资源使用情况，确保合理分配
- **健康监控**：通过心跳机制监控节点健康状态
- **状态追踪**：实时跟踪作业、分配和任务的执行状态
- **容错机制**：检测节点故障并标记相关任务为丢失状态
- **RESTful API**：提供全面的API接口用于系统管理和操作

## 快速开始

### 前提条件

- Python 3.7+
- SQLite3
- Docker (可选，用于容器任务)

### 安装依赖

```bash
pip install flask flask_cors psutil requests uuid docker
```

### 启动服务器

```bash
python server.py
```

服务器默认在端口8500上启动。

### 启动节点代理

```bash
# 在不同的主机上启动节点代理，连接到服务器
python agent.py
```

节点代理默认在端口8501上启动，并自动向服务器注册。

## 提交作业

### 容器任务示例

```bash
curl -X POST http://localhost:8500/jobs -H "Content-Type: application/json" -d '{
  "task_groups": [
    {
      "name": "web_server",
      "count": 1,
      "tasks": [
        {
          "name": "nginx",
          "resources": {
            "cpu": 100,
            "memory": 256
          },
          "config": {
            "image": "nginx:latest",
            "port": 8080
          }
        }
      ]
    }
  ]
}'
```

### 进程任务示例

```bash
curl -X POST http://localhost:8500/jobs -H "Content-Type: application/json" -d '{
  "task_groups": [
    {
      "name": "data_processor",
      "count": 1,
      "tasks": [
        {
          "name": "processor",
          "resources": {
            "cpu": 200,
            "memory": 512
          },
          "config": {
            "command": "python process_data.py"
          }
        }
      ]
    }
  ]
}'
```

## API接口

### 服务器API

| 接口 | 方法 | 描述 |
|------|------|------|
| `/register` | POST | 节点注册 |
| `/heartbeat` | POST | 处理节点心跳 |
| `/jobs` | POST | 提交新作业 |
| `/jobs` | GET | 获取所有作业信息 |
| `/jobs/{job_id}` | GET | 获取特定作业详情 |
| `/jobs/{job_id}` | PUT | 更新现有作业 |
| `/jobs/{job_id}` | DELETE | 停止作业 |
| `/jobs/{job_id}/delete` | POST | 删除作业及其资源 |
| `/jobs/{job_id}/restart` | POST | 重启已停止的作业 |
| `/nodes` | GET | 获取所有节点信息 |

### 节点代理API

| 接口 | 方法 | 描述 |
|------|------|------|
| `/allocations` | POST | 接收新的分配 |
| `/allocations/{allocation_id}` | GET | 获取分配状态 |
| `/allocations/{allocation_id}` | DELETE | 停止并移除分配 |

## 监控和管理

通过服务器API可以监控作业和节点的状态：

```bash
# 获取所有作业信息
curl http://localhost:8500/jobs

# 获取所有节点信息
curl http://localhost:8500/nodes

# 获取特定作业详情
curl http://localhost:8500/jobs/{job_id}
```

## 系统要求

- **服务器**：任何能运行Python的系统
- **节点**：支持Docker的Linux、macOS或Windows系统
- **网络**：节点需要能够访问服务器的API端点
- **资源**：根据预期工作负载调整，基本环境较轻量

## 开发与扩展

myNomad采用模块化设计，可以通过扩展以下组件添加更多功能：

1. 添加新的任务驱动（除了容器和进程）
2. 实现更复杂的调度算法
3. 添加更多资源类型的支持
4. 实现集群安全认证机制

## 注意事项

- 本系统设计用于学习和演示目的
- 生产环境使用前请确保添加适当的安全机制
- 系统状态存储在SQLite数据库中，可考虑使用更强大的数据库系统 